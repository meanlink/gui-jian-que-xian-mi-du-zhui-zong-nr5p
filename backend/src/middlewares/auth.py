from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.config.database import get_db
from src.models import User
from src.utils.security import decode_token
bearer = HTTPBearer(auto_error=False)
def current_user(token: HTTPAuthorizationCredentials | None = Depends(bearer), db=Depends(get_db)):
    try:
        user = db.get(User, decode_token(token.credentials))
        if user is None: raise ValueError('missing user')
        return user
    except Exception:
        raise HTTPException(401, '登录已过期，请重新登录')
def internal_only(user=Depends(current_user)):
    if user.role == 'external': raise HTTPException(403, '外协账号只能下载外协简报')
    return user
def can_write(user=Depends(internal_only)):
    if user.role not in ('admin','analyst'): raise HTTPException(403, '当前账号没有写入权限')
    return user
def admin_only(user=Depends(internal_only)):
    if user.role != 'admin': raise HTTPException(403, '需要业务负责人批准')
    return user
