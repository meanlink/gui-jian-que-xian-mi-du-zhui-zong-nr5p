import time, os, csv, io, math, hashlib, json
from fastapi import HTTPException
from sqlalchemy import select
from src.models import Job, Dataset, Report, Delivery
from src.config.settings import ARTIFACT_DIR
from src.services.business import analyze_external
from src.services.audit import record
def create(db, data):
    j=db.get(Job,data.job_id)
    if not j or j.status!='completed' or not j.approved:
        raise HTTPException(409,'请先选择已完成且获批准的分析结果')
    r=Report(name=data.name, job_id=j.id, destination=data.destination, interval_seconds=data.interval_seconds, next_run=time.time()+data.delay_seconds, enabled=True, public_scope=[], scope_version=1)
    db.add(r); db.flush()
    return r
def normalize_scope(ranges):
    """校验公开范围并排序合并：非负有限里程、起点小于终点、重叠或相接的区间并成一段。"""
    items=[]
    for item in ranges or []:
        try:
            a,b=float(item['from_km']),float(item['to_km'])
        except (KeyError,TypeError,ValueError):
            raise HTTPException(422,'公开范围须为起止里程区间')
        if not (math.isfinite(a) and math.isfinite(b)) or a<0 or b<0 or a>=b:
            raise HTTPException(422,'公开范围里程须非负且起点小于终点')
        items.append((a,b))
    items.sort()
    merged=[]
    for a,b in items:
        if merged and a<=merged[-1][1]: merged[-1]=(merged[-1][0],max(merged[-1][1],b))
        else: merged.append((a,b))
    return merged
def _difference(old,new):
    """旧范围中不再被新范围覆盖的里程；非空即为收窄。"""
    rest=[]
    for s,e in old:
        cur=s
        for s2,e2 in new:
            if e2<cur: continue
            if s2>e: break
            if s2>cur: rest.append((cur,min(s2,e)))
            cur=max(cur,e2)
            if cur>=e: break
        if cur<e: rest.append((cur,e))
    return rest
def set_scope(db, report, ranges):
    """设置公开范围。只扩大不升版本；一旦收窄即升版本，旧版本外协简报停止下载、生成中的停发。"""
    new=normalize_scope(ranges)
    old=normalize_scope(report.public_scope or [])
    if new==old: return report, False
    report.public_scope=[{'from_km':a,'to_km':b} for a,b in new]
    if not _difference(old,new): return report, False
    report.scope_version=(report.scope_version or 1)+1
    for d in db.scalars(select(Delivery).where(Delivery.report_id==report.id, Delivery.scope_version<report.scope_version)):
        if d.status=='partial':
            d.status='stopped'; d.stop_reason='公开范围收窄，按旧范围计算的本次分发停发'
        elif d.status=='ready' and not d.stop_reason:
            d.stop_reason='公开范围收窄，旧外协简报停止下载'
    return report, True
def _write_briefing(base, job, result, extra):
    """写出一份简报的 CSV 与 JSON（先写临时文件再原子替换，中断不会留下半个文件）。"""
    out=io.StringIO()
    out.write('\ufeff')
    table=result.get('table',{})
    cols=table.get('columns',[])
    writer=csv.writer(out)
    def safe(v):
        if isinstance(v,(int,float)) and not isinstance(v,bool): return v
        text=str(v)
        return "'"+text if text.startswith(('=','+','-','@','\t','\r')) else text
    writer.writerow([safe(c['label']) for c in cols])
    for row in table.get('rows',[]): writer.writerow([safe(row.get(c['key'],'')) for c in cols])
    data=out.getvalue().encode('utf-8')
    digest=hashlib.sha256(data).hexdigest()
    os.makedirs(ARTIFACT_DIR,exist_ok=True)
    path=os.path.join(ARTIFACT_DIR,base)
    with open(path+'.tmp','wb') as f:f.write(data)
    os.replace(path+'.tmp',path)
    payload={'job':job.name,'params':job.params,'result':result,'checksum':digest}
    payload.update(extra)
    with open(path+'.json.tmp','w') as f: json.dump(payload,f,ensure_ascii=False,allow_nan=False)
    os.replace(path+'.json.tmp',path+'.json')
    return digest
def deliver(db, report):
    """生成内部与外协两份简报。中断后重试沿用同一归档；两份文件齐备才开放；收窄并发时本次停发。"""
    j=db.get(Job,report.job_id)
    if not j or not j.approved: return None
    d=db.scalar(select(Delivery).where(Delivery.report_id==report.id, Delivery.status=='partial').order_by(Delivery.id.desc()))
    if d and d.scope_version!=report.scope_version:
        d.status='stopped'; d.stop_reason='公开范围收窄，按旧范围计算的本次分发停发'
        record(db,'worker','report.delivery_stopped',{'id':report.id,'delivery':d.id,'reason':d.stop_reason})
        d=None
    if not d:
        d=Delivery(report_id=report.id, created_at=time.time(), checksum='', ext_checksum='', filename='', ext_filename='', destination=report.destination, status='partial', scope_version=report.scope_version, stop_reason='')
        db.add(d); db.flush()
        d.filename=f'report-{report.id}-delivery-{d.id}.csv'
        d.ext_filename=f'report-{report.id}-delivery-{d.id}-external.csv'
        db.commit() # 归档占位先落库：中断后重试沿用同一归档，不新增记录
    # 内部简报：批准结果的固定快照，照发
    d.checksum=_write_briefing(d.filename, j, j.result, {'kind':'internal'})
    # 外协简报：只发获准里程，沿用已批准试验的参数按公开范围分段重算
    dataset=db.get(Dataset,j.dataset_id)
    scope=report.public_scope or []
    ext_result=analyze_external(dataset.records if dataset else [], j.params, scope)
    d.ext_checksum=_write_briefing(d.ext_filename, j, ext_result, {'kind':'external','scope':scope})
    db.flush()
    db.refresh(report) # 开放前复核范围版本：与收窄并发时，按旧范围算的不能发
    if report.scope_version!=d.scope_version:
        d.status='stopped'; d.stop_reason='公开范围收窄，按旧范围计算的本次分发停发'
        record(db,'worker','report.delivery_stopped',{'id':report.id,'delivery':d.id,'reason':d.stop_reason})
        db.commit()
        return None
    d.status='ready'
    report.next_run=time.time()+report.interval_seconds
    return d
