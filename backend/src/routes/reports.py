import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from src.config.database import get_db
from src.config.settings import ARTIFACT_DIR
from src.models import Report, Delivery
from src.schemas.report import ReportInput, ScopeInput
from src.middlewares.auth import current_user, admin_only, internal_only
from src.services import reports
from src.services.audit import record
from src.utils.serialization import report_dict, delivery_dict
router=APIRouter()
@router.get('/reports')
def listing(db=Depends(get_db),u=Depends(internal_only)):
    return [report_dict(r) for r in db.scalars(select(Report).order_by(Report.id.desc()))]
@router.post('/reports',status_code=201)
def create(data:ReportInput,db=Depends(get_db),u=Depends(admin_only)):
    r=reports.create(db,data); record(db,u.email,'report.schedule',{'id':r.id,'destination':r.destination}); db.commit()
    return report_dict(r)
@router.post('/reports/{id}/toggle')
def toggle(id:int,db=Depends(get_db),u=Depends(admin_only)):
    r=db.get(Report,id)
    if not r:raise HTTPException(404,'分发计划不存在')
    r.enabled=not r.enabled;record(db,u.email,'report.toggle',{'id':id,'enabled':r.enabled});db.commit()
    return report_dict(r)
@router.put('/reports/{id}/scope')
def scope(id:int,data:ScopeInput,db=Depends(get_db),u=Depends(admin_only)):
    r=db.get(Report,id)
    if not r:raise HTTPException(404,'分发计划不存在')
    r,narrowed=reports.set_scope(db,r,[x.model_dump() for x in data.public_scope])
    record(db,u.email,'report.scope',{'id':id,'scope':r.public_scope,'narrowed':narrowed,'scope_version':r.scope_version});db.commit()
    return report_dict(r)
@router.get('/deliveries')
def deliveries(db=Depends(get_db),u=Depends(current_user)):
    items=list(db.scalars(select(Delivery).order_by(Delivery.id.desc()).limit(100)))
    if u.role=='external':
        versions={r.id:r.scope_version for r in db.scalars(select(Report))}
        return [delivery_dict(d,external=True) for d in items if d.status=='ready' and versions.get(d.report_id)==d.scope_version]
    return [delivery_dict(d) for d in items]
@router.get('/deliveries/{id}/download')
def download(id:int,format:str='csv',side:str='internal',db=Depends(get_db),u=Depends(current_user)):
    d=db.get(Delivery,id)
    if not d:raise HTTPException(404,'归档不存在')
    if format not in ('csv','json'):raise HTTPException(422,'支持 CSV 或 JSON')
    if side not in ('internal','external'):raise HTTPException(422,'简报侧别须为 internal 或 external')
    if side=='internal' and u.role=='external':raise HTTPException(403,'外协账号只能下载外协简报')
    if d.status=='stopped':raise HTTPException(410,d.stop_reason or '本次分发已停发')
    if d.status!='ready':raise HTTPException(409,'两份简报文件尚未齐备，暂未开放下载')
    if side=='external':
        r=db.get(Report,d.report_id)
        if not r or r.scope_version!=d.scope_version:raise HTTPException(410,d.stop_reason or '公开范围已收窄，该外协简报停止下载')
    filename=(d.ext_filename if side=='external' else d.filename)+('.json' if format=='json' else '')
    p=os.path.join(ARTIFACT_DIR,filename)
    if not os.path.exists(p):raise HTTPException(404,'归档文件不存在，请等待下一轮分发')
    return FileResponse(p,filename=filename,media_type='application/json' if format=='json' else 'text/csv; charset=utf-8')
