"""User-provided API credentials are process-memory only; never included in checkpoints."""
import os
import threading
from urllib.parse import urlparse
from .models import StrictModel
from pydantic import Field,model_validator

LOCK=threading.RLock()
CONFIG={}
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


def llm_config():
    with LOCK:
        key=CONFIG.get('key') or os.getenv('JALASETU_LLM_API_KEY') or os.getenv('OPENAI_API_KEY')
        base=CONFIG.get('base') or os.getenv('JALASETU_LLM_BASE_URL') or 'https://api.openai.com/v1'
        model=CONFIG.get('model') or os.getenv('JALASETU_LLM_MODEL') or os.getenv('OPENAI_MODEL')
        if not all([key,base,model]):return None
        # Credentials must never be sent to an arbitrary tool- or webpage-provided host.
        if base.rstrip('/') not in PROVIDERS.values():raise ValueError('Use a supported provider base URL')
        return dict(key=key,base=base.rstrip('/'),model=model,protocol='responses' if urlparse(base).hostname=='api.openai.com' else 'chat')

def tavily_key():
    with LOCK:return CONFIG.get('tavily') or os.getenv('TAVILY_API_KEY')

def jev_config():
    with LOCK:
        key=CONFIG.get('typesafe') or os.getenv('TYPESAFE_API_KEY')
        return dict(key=key,model=CONFIG.get('jev_model') or os.getenv('JALASETU_JEV_MODEL','jev-latest')) if key else None

def status():
    try:c=llm_config()
    except ValueError:c=None
    return dict(llm_configured=bool(c),provider=CONFIG.get('provider','environment' if c else 'not configured'),
        model=c['model'] if c else None,tavily_configured=bool(tavily_key()),jev_configured=bool(jev_config()),jev_model=(jev_config() or {}).get('model'),
        storage='Process memory only for keys entered here; restart clears them.',
        note='OpenAI/Tavily are separate services. Public-source fetches and numeric calculations do not require an LLM key. Provider API usage may be billed.')

def update(item):
    with LOCK:
        if item.clear:CONFIG.clear();return status()
        if item.llm_api_key:
            if not item.model.strip():raise ValueError('Enter the exact model ID available to your provider account')
            CONFIG.update(key=item.llm_api_key,model=item.model.strip(),provider=item.provider,base=PROVIDERS[item.provider])
        elif item.model.strip() and CONFIG.get('key'):
            if item.provider!=CONFIG.get('provider'):raise ValueError('Enter the matching key when changing provider')
            CONFIG['model']=item.model.strip()
        if item.tavily_api_key:CONFIG['tavily']=item.tavily_api_key
        if item.typesafe_api_key:CONFIG.update(typesafe=item.typesafe_api_key,jev_model=item.jev_model.strip())
        return status()
