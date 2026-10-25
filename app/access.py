"""Shared management access for a hosted pilot. Not a substitute for per-user official roles."""
import base64
import binascii
import hmac
import os
from contextlib import asynccontextmanager
from pathlib import Path
from starlette.responses import JSONResponse

def hosted():return os.getenv('JALASETU_DEPLOYED','').lower() in {'1','true'}

def validate_hosting():
    password=os.getenv('JALASETU_ACCESS_PASSWORD','')
    if hosted():
        if len(password)<20:raise RuntimeError('Hosted mode requires JALASETU_ACCESS_PASSWORD with at least 20 characters.')
        if not os.getenv('JALASETU_ACCESS_USER','').strip():raise RuntimeError('Hosted mode requires JALASETU_ACCESS_USER.')
        db=os.getenv('JALASETU_DB','')
        if not db or not Path(db).is_absolute():raise RuntimeError('Hosted mode requires an absolute JALASETU_DB path on persistent storage.')
        if int(os.getenv('WEB_CONCURRENCY','1'))!=1:raise RuntimeError('SQLite pilot deployment requires one worker.')

@asynccontextmanager
async def lifespan(app):
    validate_hosting()
    from .research_jobs import recover
    recover()
    yield

async def protect(request,call_next):
    # Deliberately public and minimal for the platform health check.
    if request.url.path=='/api/health':return await call_next(request)
    expected=os.getenv('JALASETU_ACCESS_PASSWORD','')
    if hosted() and len(expected)<20:
        return JSONResponse({'detail':'Hosted access is not configured.'},status_code=503)
    if expected:
        user=os.getenv('JALASETU_ACCESS_USER','management')
        supplied_user=supplied_password=''
        try:
            scheme,encoded=request.headers.get('authorization','').split(' ',1)
            if scheme.lower()=='basic':
                supplied_user,supplied_password=base64.b64decode(encoded,validate=True).decode().split(':',1)
        except (ValueError,UnicodeDecodeError,binascii.Error):pass
        valid_user=hmac.compare_digest(supplied_user.encode(),user.encode())
        valid_password=hmac.compare_digest(supplied_password.encode(),expected.encode())
        if not (valid_user and valid_password):
            return JSONResponse({'detail':'Management sign-in required.'},status_code=401,headers={'WWW-Authenticate':'Basic realm="JalaSetu management", charset="UTF-8"','Cache-Control':'no-store'})
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='same-origin'
    if request.url.path.startswith('/api/'):response.headers['Cache-Control']='no-store'
    return response
