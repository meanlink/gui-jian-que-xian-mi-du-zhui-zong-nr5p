import hashlib, json
def checksum(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
def dataset_dict(d):
    return {'id':d.id, 'name':d.name, 'source':d.source, 'rows':len(d.records), 'checksum':d.checksum, 'created_at':d.created_at}
def job_dict(j):
    return {k:getattr(j,k) for k in ['id','name','dataset_id','params','status','result','error','approved','created_at','finished_at']}
def report_dict(r):
    return {**{k:getattr(r,k) for k in ['id','name','job_id','destination','interval_seconds','next_run','enabled','scope_version']}, 'public_scope':r.public_scope or []}
def delivery_dict(d, external=False):
    base={'id':d.id, 'report_id':d.report_id, 'created_at':d.created_at, 'destination':d.destination, 'status':d.status, 'stop_reason':d.stop_reason, 'ext_filename':d.ext_filename, 'ext_checksum':d.ext_checksum}
    if external: return base
    return {**base, 'filename':d.filename, 'checksum':d.checksum, 'scope_version':d.scope_version}
