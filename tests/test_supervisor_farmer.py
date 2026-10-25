from datetime import datetime,timezone,timedelta
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.network import LiftScenario,lift_capacity
from app.farmer import FarmBudget,farm_budget

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('JALASETU_DB',str(tmp_path/'test.sqlite3'))
    monkeypatch.delenv('JALASETU_LLM_API_KEY',raising=False)
    return TestClient(app)

def test_lift_bounded_by_power_and_units():
    r=lift_capacity(LiftScenario(available_power_mw=0));assert r['lifted_tmc_day']==0
    r=lift_capacity(LiftScenario(online_units=0));assert r['lifted_tmc_day']==0
    r=lift_capacity(LiftScenario());assert r['feasible_flow_cumecs']<=7*89
    assert r['energy_mwh']<=r['usable_power_mw']*12+1e-6
    assert r['current_safe_operating_capacity'] is None

def test_two_acres_units():
    r=farm_budget(FarmBudget())
    assert r['area_ha']==pytest.approx(.80937128448)
    assert r['field_volume_m3']==pytest.approx(161.874256896)
    assert r['pump_hours']==pytest.approx(r['source_volume_m3']/36)

def test_observed_rain_removes_demand():
    r=farm_budget(FarmBudget(observed_effective_rain_mm=20))
    assert r['source_volume_m3']==0;assert r['policy']=='NO_ADDITIONAL_IRRIGATION'

def test_forecast_is_review_not_measured_credit():
    r=farm_budget(FarmBudget(forecast_rain_mm=40,rain_probability_pct=90))
    assert r['policy']=='DEFER_FOR_RAIN_REVIEW';assert r['source_volume_m3']>0
    assert r['forecast_adjusted_m3']==0
    r=farm_budget(FarmBudget(forecast_rain_mm=40,rain_probability_pct=90,critical_stress=True))
    assert r['policy']=='IRRIGATION_REVIEW_REQUIRED'
    r=farm_budget(FarmBudget(forecast_rain_mm=40,rain_probability_pct=90,stage='flowering'))
    assert r['policy']=='IRRIGATION_REVIEW_REQUIRED'

def test_durable_agent_interrupt_resume(client):
    r=client.post('/api/agent/runs',json={'goal':'Protect drinking water and rescue crops'});assert r.status_code==200,r.text
    run=r.json();assert run['waiting_for_review'];assert run['durable'];assert not run['state'].get('plan_id')
    assert any(e['tool']=='compare_power_windows' for e in run['state']['events'])
    saved=client.get('/api/agent/runs/'+run['id']).json();assert saved['waiting_for_review']
    r=client.post('/api/agent/runs/'+run['id']+'/review',json={'accept':True,'reviewer':'Engineer demo','reason':'Evidence and assumptions reviewed'})
    assert r.status_code==200,r.text
    final=r.json();assert not final['waiting_for_review'];assert final['state']['status']=='proposal_saved'
    plan=client.get('/api/plans/'+final['state']['plan_id']).json();assert plan['status']=='awaiting_approvals'
    assert client.post('/api/agent/runs/'+run['id']+'/review',json={'accept':True,'reviewer':'Again','reason':'Duplicate'}).status_code==409

def test_agent_rejection_and_changed_evidence(client):
    run=client.post('/api/agent/runs',json={}).json()
    r=client.post('/api/agent/runs/'+run['id']+'/review',json={'accept':False,'reviewer':'Reviewer','reason':'Need engineering details'}).json()
    assert r['state']['status']=='analysis_rejected';assert client.get('/api/dashboard').json()['plans']==[]
    run=client.post('/api/agent/runs',json={}).json();data=client.get('/api/dataset').json();data['label']='Changed'
    client.post('/api/dataset',json=data)
    r=client.post('/api/agent/runs/'+run['id']+'/review',json={'accept':True,'reviewer':'Reviewer','reason':'Test evidence change'}).json()
    assert r['state']['status']=='evidence_changed'

def power_event(event_id,state='available',seconds=0,**kw):
    return dict(event_id=event_id,village_id='V011',state=state,observed_at=(datetime.now(timezone.utc)+timedelta(seconds=seconds)).isoformat(),**kw)

def test_power_alerts_outage_and_idempotency(client):
    e=power_event('event-1');r=client.post('/api/monitoring/power',json=e);assert r.status_code==200,r.text
    assert 'No duration' in r.json()['alerts'][0]['message']
    assert client.post('/api/monitoring/power',json=e).json()['duplicate']
    outage=power_event('event-2','outage',seconds=1)
    r=client.post('/api/monitoring/power',json=outage);assert len(r.json()['alerts'])==2
    assert r.json()['alerts'][0]['title']=='Unexpected power interruption'
    assert client.post('/api/monitoring/power',json=power_event('event-3','outage',seconds=2)).json()['alerts']==[]
    assert all(not a['external_sent'] for a in client.get('/api/monitoring').json()['alerts'])

def test_power_window_requires_commitment_and_freshness(client):
    e=power_event('invalid');e['confirmed_until']=(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat()
    assert client.post('/api/monitoring/power',json=e).status_code==422
    e['source']='demo utility commitment';assert client.post('/api/monitoring/power',json=e).status_code==200
    assert client.get('/api/monitoring').json()['states']['power:V011']['effective_status']=='available'
    assert client.post('/api/monitoring/power',json=power_event('old',seconds=-1000)).status_code==422

def test_release_alert_threshold_dedup_and_volume(client):
    e=dict(event_id='release-1',route_id='demo-outlet',observed_at=datetime.now(timezone.utc).isoformat(),duration_minutes=10,flow_lps=25,approved_rate_lps=10,cumulative_volume_m3=300,approved_volume_m3=250)
    r=client.post('/api/monitoring/release',json=e);assert r.status_code==200,r.text
    assert r.json()['high_rate'] and r.json()['high_volume'];assert r.json()['interval_volume_m3']==15
    assert len(r.json()['alerts'])==1
    assert client.post('/api/monitoring/release',json=e).json()['duplicate']
    e.update(event_id='release-2',observed_at=(datetime.now(timezone.utc)+timedelta(seconds=1)).isoformat(),cumulative_volume_m3=310)
    assert client.post('/api/monitoring/release',json=e).json()['alerts']==[]
    e.update(event_id='release-3',observed_at=(datetime.now(timezone.utc)+timedelta(seconds=2)).isoformat(),cumulative_volume_m3=100)
    assert client.post('/api/monitoring/release',json=e).status_code==422

def test_village_rain_and_power_drive_planning_and_invalidate_review(client):
    baseline=client.post('/api/plans',json={}).json()
    e=dict(event_id='rain-event-1',village_id='V051',observed_at=datetime.now(timezone.utc).isoformat(),effective_rain_mm=100)
    assert client.post('/api/monitoring/rain',json=e).status_code==200
    r=client.post('/api/plans/'+baseline['id']+'/decisions',json=dict(role='water',action='approve',reviewer='Demo',reason='Changed evidence'))
    assert r.status_code==409
    p=client.post('/api/plans',json={}).json()
    row=next(v for v in p['result']['rows'] if v['id']=='V051');assert row['requested_m3']==0
    outage=power_event('lift-outage','outage');outage['village_id']='V071'
    assert client.post('/api/monitoring/power',json=outage).status_code==200
    p=client.post('/api/plans',json={}).json()
    row=next(v for v in p['result']['rows'] if v['id']=='V071');assert row['allocated_m3']==0
    assert any('feeder' in x for x in p['result']['recommendations'])
