"""Session isolation tests use fake credentials and mocked providers, never paid API calls."""
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import connections,access,research_jobs,research_panel,public_data,authority

PASSWORD='test-management-signin-password-only'
A='test-alpha-session-provider-key'
B='test-bravo-session-provider-key'

@pytest.fixture
def hosted(monkeypatch,tmp_path):
    monkeypatch.setenv('JALASETU_DEPLOYED','true')
    monkeypatch.setenv('JALASETU_DB',str(tmp_path/'sessions.sqlite3'))
    monkeypatch.setenv('JALASETU_ACCESS_USER','management')
    monkeypatch.setenv('JALASETU_ACCESS_PASSWORD',PASSWORD)
    monkeypatch.setenv('OPENAI_API_KEY','owner-key-must-not-be-used')
    monkeypatch.setenv('OPENAI_MODEL','owner-model')
    monkeypatch.setenv('TYPESAFE_API_KEY','owner-jev-must-not-be-used')
    access.ATTEMPTS.clear();connections.clear_all_sessions()
    yield tmp_path
    connections.clear_all_sessions()

def signin(client):
    response=client.post('/auth/login',json={'username':'management','password':PASSWORD})
    assert response.status_code==200

def connect(client,key,model='test-model'):
    r=client.post('/api/connections',json={'llm_api_key':key,'model':model,'typesafe_api_key':key,'tavily_api_key':key})
    assert r.status_code==200,r.text
    assert key not in r.text
    return r.json()

def test_two_browser_sessions_are_isolated_and_do_not_inherit_owner_keys(hosted):
    with TestClient(app,base_url='https://testserver') as a,TestClient(app,base_url='https://testserver') as b:
        signin(a);signin(b)
        assert not a.get('/api/connections').json()['llm_configured']
        assert not b.get('/api/connections').json()['jev_configured']
        assert connect(a,A,'alpha-model')['editable']
        assert not b.get('/api/connections').json()['llm_configured']
        connect(b,B,'bravo-model')
        assert a.get('/api/connections').json()['model']=='alpha-model'
        assert b.get('/api/connections').json()['model']=='bravo-model'
        cleared=a.post('/api/connections',json={'clear':True}).json()
        assert not cleared['llm_configured'] and not cleared['jev_configured']
        assert b.get('/api/connections').json()['llm_configured']
        assert b.post('/auth/logout').status_code==200
        assert len(connections.SESSIONS)==0

def test_expiration_and_validation_never_echo_keys(hosted,monkeypatch):
    with TestClient(app,base_url='https://testserver') as client:
        signin(client);connect(client,A)
        r=client.post('/api/connections',json={'llm_api_key':'private-value-too-long-'*30})
        assert r.status_code==422 and 'private-value-too-long' not in r.text
        now=connections.time.time();monkeypatch.setattr(connections.time,'time',lambda:now+connections.KEY_TTL_SECONDS+1)
        status=client.get('/api/connections').json()
        assert not status['llm_configured'] and not status['tavily_configured']
        assert not connections.SESSIONS

def test_jobs_and_parallel_specialists_use_the_submitting_session_without_checkpointing_keys(hosted,monkeypatch):
    class DeferredPool:
        def __init__(self):self.calls=[]
        def submit(self,fn,*args):self.calls.append((fn,args))
    pool=DeferredPool();monkeypatch.setattr(research_jobs,'POOL',pool)
    evidence=dict(retrieved_at='2026-10-25T00:00:00Z',observations=[],sources=[],issues=[],boundaries=['Test fixture'])
    monkeypatch.setattr(public_data,'refresh',lambda *a,**k:evidence)
    observed=[]
    def model(messages,tools=None,force_final=False,output_schema=None):
        observed.append(connections.llm_config()['key'])
        if tools:return dict(text='Fixture research only',calls=[],usage={},protocol='responses',replay=[])
        analysis=dict(summary='Test scenario review',findings=[dict(statement='Only a synthetic scenario is available',evidence_ids=['scenario:summary'])],missing_inputs=['Verified readings'],recommendation='Obtain verified data',decision_readiness='needs_data')
        return dict(text=json.dumps(analysis),usage={})
    monkeypatch.setattr(research_panel,'call',model)
    with TestClient(app,base_url='https://testserver') as a,TestClient(app,base_url='https://testserver') as b:
        signin(a);signin(b);connect(a,A);connect(b,B)
        result=a.post('/api/research-panel/jobs',json={'question':'Review evidence in a test scenario'}).json()
        assert result['job_active'] and len(pool.calls)==1
        # Run after the request scope ended: the job must retain the submitting scope, not browser B's keys.
        fn,args=pool.calls[0];fn(*args)
        report=a.get('/api/research-panel/jobs/'+result['id']).json()
        assert report['waiting_for_review'] and len(observed)==5 and set(observed)=={A}
        for path in hosted.glob('*.sqlite3'):
            raw=path.read_bytes()
            assert A.encode() not in raw and B.encode() not in raw and b'owner-key-must-not-be-used' not in raw

def test_jev_uses_the_requesting_browser_key_and_logout_revokes_it(hosted,monkeypatch):
    called=[]
    class Response:
        def raise_for_status(self):pass
        def json(self):
            def choice(options,label):return dict(choice=label,confidence=1,probabilities={k:1 if k==label else 0 for k in options})
            return dict(model='jev-test',answers={'responsible_desk':choice(authority.ROUTES,'joint_review'),'next_step':choice(authority.STEPS,'officer_review')})
    def post(url,**kwargs):called.append(kwargs['headers']['Authorization']);return Response()
    monkeypatch.setattr(authority.httpx,'post',post)
    with TestClient(app,base_url='https://testserver') as a,TestClient(app,base_url='https://testserver') as b:
        signin(a);signin(b);connect(a,A);connect(b,B)
        case=a.post('/api/authority/cases',json={'title':'Test officer review','asset':'Test source','briefing':'A fictional coordination briefing requiring review.'}).json()
        url='/api/authority/cases/'+case['id']+'/assess'
        assert a.post(url).json()['status']=='routing_recommendation'
        assert b.post(url).json()['status']=='routing_recommendation'
        assert called==['Bearer '+A,'Bearer '+B]
        a.post('/auth/logout');signin(a)
        assert a.post(url).json()['status']=='credentials_required'
        assert len(called)==2
