"""Bounded provider calls. Model output never mutates a water allocation or source measurement."""
import json
import httpx
from .connections import llm_config

class ModelUnavailable(RuntimeError):pass


def call(messages,tools=None,force_final=False,output_schema=None):
    config=llm_config()
    if not config:raise ModelUnavailable('Configure a model ID and matching API key in Connections.')
    headers={'Authorization':'Bearer '+config['key']}
    try:
        if config['protocol']=='responses':
            payload=dict(model=config['model'],input=messages,max_output_tokens=2600,store=False,include=["reasoning.encrypted_content"])
            if output_schema:payload['text']={'format':{'type':'json_schema','name':'sector_assessment','schema':output_schema,'strict':True}}
            if tools:
                payload.update(tools=[dict(type='function',**t) for t in tools],tool_choice='none' if force_final else 'auto')
            r=httpx.post(config['base']+'/responses',headers=headers,json=payload,timeout=45);r.raise_for_status();data=r.json()
            output=data.get('output',[])
            text=''.join(c.get('text','') for item in output if item.get('type')=='message' for c in item.get('content',[]) if c.get('type')=='output_text')
            calls=[dict(id=x['call_id'],name=x['name'],arguments=x.get('arguments','{}')) for x in output if x.get('type')=='function_call']
            return dict(text=text,calls=calls,replay=output,protocol='responses',usage=data.get('usage',{}))
        payload=dict(model=config['model'],messages=messages,max_tokens=1400)
        if output_schema:payload['response_format']={'type':'json_schema','json_schema':{'name':'sector_assessment','schema':output_schema,'strict':True}}
        if tools:payload.update(tools=[dict(type='function',function=t) for t in tools],tool_choice='none' if force_final else 'auto')
        r=httpx.post(config['base']+'/chat/completions',headers=headers,json=payload,timeout=45);r.raise_for_status();data=r.json();m=data['choices'][0]['message']
        return dict(text=m.get('content') or '',calls=[dict(id=t['id'],name=t['function']['name'],arguments=t['function'].get('arguments','{}')) for t in m.get('tool_calls',[])],replay=m,protocol='chat',usage=data.get('usage',{}))
    except httpx.HTTPStatusError as e:raise ModelUnavailable(f'Model provider returned HTTP {e.response.status_code}; check the key, model access, quota and API compatibility.') from None
    except (httpx.HTTPError,KeyError,ValueError,TypeError):raise ModelUnavailable('Model request failed or returned an unsupported response. No substitute model result was fabricated.') from None


def json_value(text):
    t=text.strip()
    if t.startswith('```'):
        lines=t.splitlines();t='\n'.join(lines[1:-1])
    value=json.loads(t)
    if not isinstance(value,dict):raise ValueError('Expected a JSON object')
    return value
