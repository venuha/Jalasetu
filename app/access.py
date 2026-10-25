"""Shared management sign-in for a hosted pilot, with signed expiring browser sessions."""
import base64
import binascii
import hashlib
import hmac
import json
import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
from starlette.responses import JSONResponse,HTMLResponse,RedirectResponse

SESSION_SECONDS=8*60*60
ATTEMPTS={}

def hosted():return os.getenv('JALASETU_DEPLOYED','').lower() in {'1','true'}

def deployment_status():
    return dict(hosted=hosted(),storage_mode=os.getenv('JALASETU_STORAGE_MODE','persistent') if hosted() else 'local')

def validate_hosting():
    password=os.getenv('JALASETU_ACCESS_PASSWORD','')
    if hosted():
        if len(password)<20:raise RuntimeError('Hosted mode requires JALASETU_ACCESS_PASSWORD with at least 20 characters.')
        if not os.getenv('JALASETU_ACCESS_USER','').strip():raise RuntimeError('Hosted mode requires JALASETU_ACCESS_USER.')
        db=os.getenv('JALASETU_DB','')
        if not db or not Path(db).is_absolute():raise RuntimeError('Hosted mode requires an absolute JALASETU_DB path.')
        if int(os.getenv('WEB_CONCURRENCY','1'))!=1:raise RuntimeError('SQLite pilot deployment requires one worker.')

@asynccontextmanager
async def lifespan(app):
    validate_hosting()
    from .research_jobs import recover
    recover()
    yield

def cookie_name():return '__Host-jalasetu_session' if hosted() else 'jalasetu_session'

def credentials_match(user,password):
    expected=os.getenv('JALASETU_ACCESS_PASSWORD','')
    valid_user=hmac.compare_digest(str(user).encode(),os.getenv('JALASETU_ACCESS_USER','management').encode())
    valid_password=hmac.compare_digest(str(password).encode(),expected.encode())
    return bool(expected) and valid_user and valid_password

def signed_session():
    payload=f'{int(time.time())}.{secrets.token_hex(16)}'
    signature=hmac.new(os.environ['JALASETU_ACCESS_PASSWORD'].encode(),payload.encode(),hashlib.sha256).hexdigest()
    return payload+'.'+signature

def valid_session(token):
    if not token or len(token)>160:return False
    try:
        issued,nonce,signature=token.split('.')
        age=time.time()-int(issued)
        if not -60<=age<=SESSION_SECONDS or len(nonce)!=32:return False
        payload=issued+'.'+nonce
        expected=hmac.new(os.getenv('JALASETU_ACCESS_PASSWORD','').encode(),payload.encode(),hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature,expected)
    except (ValueError,TypeError):return False

def same_origin(request):
    origin=request.headers.get('origin')
    if request.headers.get('sec-fetch-site')=='cross-site':return False
    if not origin:return True  # Non-browser API clients; browser JSON POSTs include Origin.
    parsed=urlsplit(origin)
    return parsed.scheme in (['https'] if hosted() else ['http','https']) and parsed.netloc==request.headers.get('host')

def secured(response):
    response.headers.update({'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'same-origin','Cache-Control':'no-store'})
    return response

async def login(request):
    if not same_origin(request):return JSONResponse({'detail':'Cross-site sign-in is not allowed.'},status_code=403)
    if not os.getenv('JALASETU_ACCESS_PASSWORD'):return JSONResponse({'detail':'This local workspace does not require sign-in.'},status_code=400)
    address=request.client.host if request.client else 'unknown';now=time.time()
    for key in list(ATTEMPTS):
        if now-ATTEMPTS[key][0]>60:ATTEMPTS.pop(key,None)
    if len(ATTEMPTS)>1024:ATTEMPTS.pop(next(iter(ATTEMPTS)),None)
    started,count=ATTEMPTS.get(address,(now,0))
    if count>=10:return JSONResponse({'detail':'Too many sign-in attempts. Try again in one minute.'},status_code=429)
    ATTEMPTS[address]=(started,count+1)
    if request.headers.get('content-type','').split(';')[0]!='application/json':return JSONResponse({'detail':'Expected a JSON sign-in request.'},status_code=415)
    data=bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data)>4096:return JSONResponse({'detail':'Sign-in request is too large.'},status_code=413)
    try:
        value=json.loads(data)
        if not isinstance(value,dict) or not isinstance(value.get('username'),str) or not isinstance(value.get('password'),str):raise ValueError()
    except (ValueError,UnicodeDecodeError):return JSONResponse({'detail':'Invalid sign-in request.'},status_code=400)
    if not credentials_match(value['username'],value['password']):return JSONResponse({'detail':'Incorrect username or password.'},status_code=401)
    ATTEMPTS.pop(address,None)
    response=JSONResponse({'ok':True})
    response.set_cookie(cookie_name(),signed_session(),max_age=SESSION_SECONDS,httponly=True,secure=hosted(),samesite='strict',path='/')
    return response

async def protect(request,call_next):
    if request.url.path=='/api/health':return await call_next(request)
    expected=os.getenv('JALASETU_ACCESS_PASSWORD','')
    if hosted() and len(expected)<20:return secured(JSONResponse({'detail':'Hosted access is not configured.'},status_code=503))
    if request.url.path=='/login' and request.method=='GET':
        if not expected or valid_session(request.cookies.get(cookie_name())):return RedirectResponse('/',status_code=303)
        return secured(HTMLResponse((Path(__file__).parent/'static'/'login.html').read_text()))
    if request.url.path=='/auth/login' and request.method=='POST':return secured(await login(request))
    if request.url.path=='/auth/logout' and request.method=='POST':
        if not same_origin(request):return secured(JSONResponse({'detail':'Cross-site sign-out is not allowed.'},status_code=403))
        response=JSONResponse({'ok':True});response.delete_cookie(cookie_name(),path='/',secure=hosted(),httponly=True,samesite='strict')
        return secured(response)
    if expected:
        valid=valid_session(request.cookies.get(cookie_name()))
        if valid and request.method not in ['GET','HEAD','OPTIONS'] and not same_origin(request):return secured(JSONResponse({'detail':'Cross-site writes are not allowed.'},status_code=403))
        if not valid:
            try:
                scheme,encoded=request.headers.get('authorization','').split(' ',1)
                user,password=base64.b64decode(encoded,validate=True).decode().split(':',1)
                valid=scheme.lower()=='basic' and credentials_match(user,password)
            except (ValueError,UnicodeDecodeError,binascii.Error):valid=False
        if not valid:
            return secured(JSONResponse({'detail':'Management sign-in required.'},status_code=401) if request.url.path.startswith('/api/') else RedirectResponse('/login',status_code=303))
    return secured(await call_next(request))
