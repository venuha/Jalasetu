"""Provider calls are mocked here; these tests do not assert that a paid model was run."""
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import authority,connections,public_data,research_panel,model_client

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('JALASETU_DB',str(tmp_path/'authority.sqlite3'))
    for key in ['JALASETU_LLM_API_KEY','OPENAI_API_KEY','OPENAI_MODEL','JALASETU_LLM_MODEL','TYPESAFE_API_KEY','TAVILY_API_KEY']:
        monkeypatch.delenv(key,raising=False)
    connections.CONFIG.clear()
    yield TestClient(app)
    connections.CONFIG.clear()

def case(client):
    r=client.post('/api/authority/cases',json=dict(title='Review a proposed lift window',asset='Demo command',briefing='Officer reports interrupted power and asks for a coordinated irrigation review.'))
    assert r.status_code==200
    return r.json()

def answer(criteria,selected,p=1):
    n=len(criteria)
    return dict(choice=selected,probabilities={k:p if k==selected else (1-p)/(n-1) for k in criteria},confidence=(p-1/n)/(1-1/n))

def test_no_key_no_invented_decision_and_manual_assignment(client):
    item=case(client)
    result=client.post('/api/authority/cases/'+item['id']+'/assess').json()
    assert result['status']=='credentials_required'
    assert 'route' not in result['assessment']
    assert client.get('/api/authority').json()['cases'][0]['id']==item['id']
    review=dict(reviewer='Demo officer',route='joint_review',next_step='request_power_confirmation',note='Utility confirmation needed before a pumping schedule.')
    r=client.post('/api/authority/cases/'+item['id']+'/review',json=review)
    assert r.status_code==200 and r.json()['assignment']['route']=='joint_review'
    assert client.get('/api/dashboard').json()['plans']==[]
    # A model or caller cannot smuggle release approval through the assignment API.
    assert client.post('/api/authority/cases/'+item['id']+'/review',json={**review,'next_step':'open_gates'}).status_code==422
    assert client.post('/api/authority/cases/missing/assess').status_code==404

def test_jev_wire_format_validated_and_never_has_actuation_tools(client,monkeypatch):
    item=case(client)
    r=client.post('/api/connections',json={'typesafe_api_key':'secret-test-key','jev_model':'jev-test'})
    assert 'secret-test-key' not in r.text and r.json()['jev_configured']
    captured={}
    class Response:
        def raise_for_status(self):pass
        def json(self):return dict(model='jev-test-version',answers={'responsible_desk':answer(authority.ROUTES,'joint_review'),'next_step':answer(authority.STEPS,'request_power_confirmation')})
    def post(url,**kwargs):
        captured.update(url=url,**kwargs);return Response()
    monkeypatch.setattr(authority.httpx,'post',post)
    result=client.post('/api/authority/cases/'+item['id']+'/assess').json()
    assert result['status']=='routing_recommendation'
    assert result['assessment']['release_authorized'] is False
    assert captured['url']=='https://api.typesafe.ai/v1/systemone'
    assert set(captured['json']['questions'])=={'responsible_desk','next_step'}
    assert 'tools' not in captured['json']
    assert 'secret-test-key' not in json.dumps(result)
    assert client.get('/api/dashboard').json()['plans']==[]

def test_uncertainty_and_invalid_distributions_cannot_be_accepted(client,monkeypatch):
    connections.update(connections.ConnectionUpdate(typesafe_api_key='test-key-123'))
    class Response:
        def raise_for_status(self):pass
        def json(self):return dict(answers={'responsible_desk':answer(authority.ROUTES,'joint_review',.6),'next_step':answer(authority.STEPS,'officer_review',.7)})
    monkeypatch.setattr(authority.httpx,'post',lambda *a,**k:Response())
    result=authority.evaluate({'briefing':'ambiguous'})
    assert result['status']=='human_triage_required'
    invalid=answer(authority.ROUTES,'joint_review',.6);invalid['confidence']=1
    with pytest.raises(ValueError):authority.validate_choice(invalid,authority.ROUTES)
    invalid=answer(authority.ROUTES,'joint_review');invalid['probabilities']['invented_route']=0
    with pytest.raises(ValueError):authority.validate_choice(invalid,authority.ROUTES)

def test_beneficiary_previews_require_two_reviews(client):
    p=client.post('/api/plans',json={}).json()
    url='/api/plans/'+p['id']+'/decisions'
    assert not client.get('/api/authority/beneficiary-previews').json()['packets']
    for role in ['water','power']:
        assert client.post(url,json=dict(role=role,action='approve',reviewer='Demo reviewer',reason='Checked synthetic scenario')).status_code==200
        if role=='water':assert not authority.beneficiary_previews()['packets']
    preview=authority.beneficiary_previews()
    assert preview['packets'] and preview['external_delivery'] is False
    assert all(x['status']=='preview_only_not_sent' for x in preview['packets'])
    assert all('Not verified' in x['power_commitment'] for x in preview['packets'])

def test_parsers_keep_report_definitions_and_dates(monkeypatch):
    hydro='Reservoir For- 22-Oct-2026\n SRISAILAM Andhra Pradesh 269.8 885 255.21 837.3 265 869.4 770 243.8 799.9 2366 298 6571 5.33 1630.37 1.32 100\n'
    generation='DAILY GENERATION REPORT FOR 22/10/2026\nTELANGANA\n STATE TOTAL 14985.60 245.80 205.44 4.00 2.00 1.00\n'
    monkeypatch.setattr(public_data,'pdf_text',lambda b:[hydro] if b==b'hydro' else [generation])
    h=public_data.parse_hydro(b'hydro','https://npp.gov.in/report.pdf')
    assert h[1]['metric']=='effective_capacity_at_present_level' and h[1]['value']==1630.37 and h[1]['unit']=='MCM'
    assert h[0]['value']==837.3 and h[0]['observed_date']=='2026-10-22' and h[0]['page']==1
    g=public_data.parse_generation(b'gen','https://npp.gov.in/generation.pdf')
    assert g[0]['value']==205.44 and g[0]['metric']=='daily_generation_actual' and not g[0]['operationally_verified']
    monkeypatch.setattr(public_data,'pdf_text',lambda b:[hydro.replace(' 1.32 100',' 100')])
    with pytest.raises(ValueError):public_data.parse_hydro(b'x','https://npp.gov.in/report.pdf')

def test_source_failure_does_not_create_demo_observations(client,monkeypatch):
    def unavailable(*a,**k):raise RuntimeError('Unavailable')
    for fn in ['collect_npp','collect_krmb','collect_secondary','collect_weather','get']:monkeypatch.setattr(public_data,fn,unavailable)
    result=public_data.refresh()
    assert result['observations']==[] and len(result['issues'])==5
    assert public_data.latest()['observations']==[]
    assert public_data.search_public('Telangana water')['status']=='not configured'

def test_research_panel_credentials_gate_and_durable_review(client,monkeypatch):
    obs=public_data.record('Test official fixture','reservoir',1,'ft','2026-10-22','https://npp.gov.in/test','reservoir_level','Test dam')
    evidence=dict(retrieved_at='2026-10-25T00:00:00Z',observations=[obs],sources=[],issues=[],boundaries=['Test fixture only'])
    monkeypatch.setattr(public_data,'refresh',lambda *a,**k:evidence)
    request=research_panel.PanelRequest(question='Review this test evidence')
    initial=research_panel.start(request)
    assert initial['state']['status']=='credentials_required' and not initial['waiting_for_review']
    monkeypatch.setattr(research_panel,'llm_config',lambda:{'model':'mock'})
    def mock_call(messages,tools=None,force_final=False,output_schema=None):
        if tools:return dict(text='Test research summary',calls=[],usage={},protocol='responses',replay=[])
        analysis=dict(summary='Test findings',findings=[dict(statement='Fixture observation only',evidence_ids=[obs['id']])],missing_inputs=['Current operational verification'],recommendation='Request verified evidence',decision_readiness='needs_data')
        return dict(text=json.dumps(analysis),usage={})
    monkeypatch.setattr(research_panel,'call',mock_call)
    run=research_panel.start(request)
    assert run['waiting_for_review']
    assert all(run['state'][k]['status']=='model_completed' for k in ['water_analysis','farmer_analysis','power_analysis','synthesis'])
    assert research_panel.operate(run['id'])['waiting_for_review']
    done=research_panel.operate(run['id'],review=dict(reviewer='Demo reviewer',decision='request_more_data',note='Need verified input'))
    assert done['state']['status']=='completed' and not done['waiting_for_review']
    assert done['state']['synthesis']['hard_blockers'] and not client.get('/api/dashboard').json()['plans']


def test_public_allowlist_and_future_reading():
    with pytest.raises(ValueError):public_data.get('http://127.0.0.1/private')
    record=public_data.record('fixture','reservoir',1,'ft','2999-01-01')
    assert record['freshness']=='future date - investigate'
