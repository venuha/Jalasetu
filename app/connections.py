"""Visitor credentials live only in expiring, isolated process-memory sessions."""
import hashlib
import os
import threading
import time
from contextvars import ContextVar
from datetime import datetime,timezone
from urllib.parse import urlparse
from .models import StrictModel
from pydantic import Field

LOCK=threading.RLock()
CONFIG={}  # Legacy single-user local workspace only; never used as hosted fallback.
SESSIONS={}
CURRENT_SCOPE=ContextVar('jalasetu_key_scope',default=None)
KEY_TTL_SECONDS=30*60
PROVIDERS={
 'openai':'https://api.openai.com/v1',
 'nebius':'https://api.tokenfactory.nebius.com/v1',
 'fireworks':'https://api.fireworks.ai/inference/v1',
}

class ConnectionUpdate(StrictModel):
    provider:str=Field(default='openai',pattern='^(openai|nebius|fireworks)$')
    model:str=Field(default='',max_length=150)
    llm_api_key:str|None=Field(default=None,min_length=8,max_length=512)
    tavily_api_key:str|None=Field(default=None,min_length=8,max_length=512)
    typesafe_api_key:str|None=Field(default=None,min_length=8,max_length=512)
    jev_model:str=Field(default='jev-latest',min_length=1,max_length=100)
    clear:bool=False


def is_hosted():
    from .access import hosted
    return hosted()

def session_scope(token):
    # Called only after the login cookie has been validated by access middleware.
    return hashlib.sha256(token.encode()).hexdigest(),int(token.split('.')[0])+8*60*60

def bind_session(token):return CURRENT_SCOPE.set(session_scope(token))

def sweep_expired():
    with LOCK:
        now=time.time()
        for key in list(SESSIONS):
            if SESSIONS[key]['expires_at']<=now:SESSIONS.pop(key,None)

def clear_session(token):
    if not token:return
    with LOCK:SESSIONS.pop(session_scope(token)[0],None)

def clear_all_sessions():
    with LOCK:SESSIONS.clear()

def current():
    sweep_expired();scope=CURRENT_SCOPE.get()
    with LOCK:
        if scope:return dict(SESSIONS.get(scope[0],{}).get('values',{}))
        return {} if is_hosted() else dict(CONFIG)

def local_environment():return CURRENT_SCOPE.get() is None and not is_hosted()

def llm_config():
    values=current();fallback=local_environment()
    key=values.get('key') or ((os.getenv('JALASETU_LLM_API_KEY') or os.getenv('OPENAI_API_KEY')) if fallback else None)
    base=values.get('base') or (os.getenv('JALASETU_LLM_BASE_URL') if fallback else None) or PROVIDERS['openai']
    model=values.get('model') or ((os.getenv('JALASETU_LLM_MODEL') or os.getenv('OPENAI_MODEL')) if fallback else None)
    if not all([key,base,model]):return None
    if base.rstrip('/') not in PROVIDERS.values():raise ValueError('Use a supported provider base URL')
    return dict(key=key,base=base.rstrip('/'),model=model,protocol='responses' if urlparse(base).hostname=='api.openai.com' else 'chat')

def tavily_key():return current().get('tavily') or (os.getenv('TAVILY_API_KEY') if local_environment() else None)

def jev_config():
    values=current();fallback=local_environment()
    key=values.get('typesafe') or (os.getenv('TYPESAFE_API_KEY') if fallback else None)
    return dict(key=key,model=values.get('jev_model') or (os.getenv('JALASETU_JEV_MODEL') if fallback else None) or 'jev-latest') if key else None

def status():
    values=current();scope=CURRENT_SCOPE.get()
    try:c=llm_config()
    except ValueError:c=None
    with LOCK:expiry=SESSIONS.get(scope[0],{}).get('expires_at') if scope else None
    return dict(llm_configured=bool(c),provider=values.get('provider','environment' if c else 'not configured'),
        model=c['model'] if c else None,tavily_configured=bool(tavily_key()),jev_configured=bool(jev_config()),jev_model=(jev_config() or {}).get('model'),
        editable=bool(scope) or not is_hosted(),session_only=bool(scope) or is_hosted(),
        expires_at=datetime.fromtimestamp(expiry,timezone.utc).isoformat() if expiry else None,
        storage='Keys stay in this signed-in browser session’s server memory only. They expire 30 minutes after connection update, and clear on sign-out, explicit removal or server restart.' if scope or is_hosted() else 'Local single-user process memory; restart clears entered keys. Local environment credentials remain separately configured.',
        note='Each hosted session supplies its own keys. They are never written to browser storage, files, checkpoints or the database. Provider API usage may be billed to the supplied keys.')

def update(item):
    scope=CURRENT_SCOPE.get()
    if is_hosted() and not scope:raise ValueError('Sign in through the browser form before connecting session keys.')
    with LOCK:
        if item.clear:
            if scope:SESSIONS.pop(scope[0],None)
            else:CONFIG.clear()
            return status()
        values=current()
        if item.llm_api_key:
            if not item.model.strip():raise ValueError('Enter the exact model ID available to your provider account')
            values.update(key=item.llm_api_key,model=item.model.strip(),provider=item.provider,base=PROVIDERS[item.provider])
        elif item.model.strip() and values.get('key'):
            if item.provider!=values.get('provider'):raise ValueError('Enter the matching key when changing provider')
            values['model']=item.model.strip()
        if item.tavily_api_key:values['tavily']=item.tavily_api_key
        if item.typesafe_api_key:values.update(typesafe=item.typesafe_api_key,jev_model=item.jev_model.strip())
        if scope:
            sweep_expired()
            if scope[0] not in SESSIONS and len(SESSIONS)>=256:raise ValueError('Session key capacity reached. Try again after unused sessions expire.')
            SESSIONS[scope[0]]=dict(values=values,expires_at=min(time.time()+KEY_TTL_SECONDS,scope[1]))
        else:CONFIG.clear();CONFIG.update(values)
        return status()
