import copy
from datetime import datetime,timedelta,timezone
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.engine import planner,available,TMC_M3
from app.seed import seed
from app.models import Scenario,Dataset

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('JALASETU_DB',str(tmp_path/'test.sqlite3'))
    monkeypatch.delenv('JALASETU_LLM_API_KEY',raising=False)
    return TestClient(app)

def calc(data=None,**sc):
    return planner.invoke(dict(dataset=data or seed(),scenario=Scenario(**sc).model_dump(),booked={},events=[]))

def make_plan(c):
    r=c.post('/api/plans',json={});assert r.status_code==200,r.text;return r.json()

def decision(c,p,role,action='approve'):
    return c.post(f'/api/plans/{p["id"]}/decisions',json=dict(role=role,action=action,reviewer='Demo reviewer',reason='Reviewed sample assumptions'))

def test_reserves_and_conservation():
    result=calc()
    for r in result['reservoirs']:
        assert r['proposed_tmc']<=r['available_tmc']+1e-10
        if r['storage_tmc']>=r['protected_tmc']:assert r['remaining_tmc']>=r['protected_tmc']-1e-10
        else:assert r['proposed_tmc']==0
    assert sum(v['allocated_tmc'] for v in result['rows'])==pytest.approx(result['summary']['allocated_tmc'])
    for v in result['rows']:
        assert v['allocated_m3']<=min(v['requested_m3'],v['delivery_limit_m3'])+1e-6
        assert v['recommended_flow_cusecs']<=v['canal_capacity_cusecs']+1e-6
        assert sum(w['mwh'] for w in v['power_schedule'])==pytest.approx(v['energy_mwh'])
        assert v['pump_hours_needed']<=v['pump_hours_available']+1e-6
        if not v['lift_head_m']:assert v['energy_mwh']==0

def test_water_unit_calculation():
    data=seed();data['villages']=data['villages'][2:3];v=data['villages'][0]
    v.update(area_ha=10000,net_irrigation_mm=40,soil_credit_mm=0,efficiency=.6)
    r=calc(data)['rows'][0]
    assert r['requested_m3']==pytest.approx(4_000_000/.6)
    assert r['requested_tmc']==pytest.approx(.2354311115)

def test_stale_data_blocks():
    data=seed();data['reservoirs'][0]['observed_at']=(datetime.now(timezone.utc)-timedelta(days=3)).isoformat()
    result=calc(data);assert result['summary']['status']=='blocked';assert not result['rows']

def test_outage_keeps_gravity_but_stops_lifts():
    result=calc(failure_mode='power outage')
    assert all(v['allocated_m3']==0 for v in result['rows'] if v['lift_head_m'])
    assert any(v['allocated_m3']>0 for v in result['rows'] if not v['lift_head_m'])

def test_extra_power_does_not_override_drinking_hold():
    result=calc(power_hours_override=24)
    assert next(r for r in result['reservoirs'] if r['id']=='srisailam')['proposed_tmc']==0

def test_rainfall_never_negative_demand():
    result=calc(rainfall_credit_mm=100)
    assert result['summary']['requested_tmc']==0
    assert result['summary']['status']=='no_feasible_release'

def test_weather_failure_recovery():
    result=calc(failure_mode='weather unavailable')
    assert result['summary']['allocated_tmc']>0
    assert any('unavailable' in t for t in result['recommendations'])

def test_two_reviews_and_delivery(client):
    p=make_plan(client)
    assert client.post(f'/api/plans/{p["id"]}/deliveries',json={'village_id':'V021','delivered_m3':0,'note':'Test'}).status_code==409
    assert decision(client,p,'water').json()['status']=='awaiting_approvals'
    assert decision(client,p,'water').status_code==409
    approved=decision(client,p,'power').json();assert approved['status']=='approved_simulation'
    v=next(v for v in approved['result']['rows'] if v['allocated_m3']>0)
    url=f'/api/plans/{p["id"]}/deliveries'
    assert client.post(url,json=dict(village_id=v['id'],delivered_m3=v['allocated_m3']+1,note='Too much')).status_code==422
    assert client.post(url,json=dict(village_id=v['id'],delivered_m3=100,note='Partial delivery')).status_code==200
    assert client.post(url,json=dict(village_id=v['id'],delivered_m3=50,note='Decreased')).status_code==422
    assert client.get(f'/api/plans/{p["id"]}').json()['deliveries'][v['id']]['delivered_m3']==100

def test_rejection_cannot_be_overridden(client):
    p=make_plan(client);assert decision(client,p,'water','reject').json()['status']=='rejected'
    assert decision(client,p,'power').status_code==409

def test_changed_evidence_invalidates_pending(client):
    p=make_plan(client);d=client.get('/api/dataset').json();d['label']='Updated fixture'
    assert client.post('/api/dataset',json=d).status_code==200
    assert decision(client,p,'water').status_code==409

def test_water_not_double_booked(client):
    data=client.get('/api/dataset').json()
    # Make available water scarce so each independent proposal exhausts the same pool.
    for r in data['reservoirs']:
        r['storage_tmc']=min(r['capacity_tmc'],available(r)['protected_tmc']+.001)
    assert client.post('/api/dataset',json=data).status_code==200
    a=make_plan(client);b=make_plan(client)
    assert decision(client,a,'water').status_code==200
    assert decision(client,a,'power').status_code==200
    assert decision(client,b,'water').status_code==200
    assert decision(client,b,'power').status_code==409
    # Failed final review is rolled back, not saved as a misleading approval.
    assert 'power' not in client.get('/api/plans/'+b['id']).json()['decisions']
    assert client.post('/api/dataset',json=data).status_code==409

def test_input_validation(client):
    assert client.post('/api/plans',json={'demand_multiplier':-1}).status_code==422
    d=seed();d['villages'][0]['reservoir_id']='unknown'
    assert client.post('/api/dataset',json=d).status_code==422
    d=seed();d['reservoirs'][0]['storage_tmc']=10000
    assert client.post('/api/dataset',json=d).status_code==422
    d=seed();d['mode']='live'
    assert client.post('/api/dataset',json=d).status_code==422

def test_compare_does_not_create_orders(client):
    r=client.post('/api/compare',json={});assert r.status_code==200;assert len(r.json()['options'])==4
    assert client.get('/api/dashboard').json()['plans']==[]

def test_weather_adapter_failure(monkeypatch):
    import httpx
    from app.integrations import weather
    def broken(*a,**kw):raise httpx.ConnectError('offline')
    monkeypatch.setattr(httpx,'get',broken)
    assert 'after 2 attempts' in weather(17,78)['error']

def test_approved_routes_are_not_scheduled_again(client):
    p=make_plan(client)
    decision(client,p,'water');assert decision(client,p,'power').status_code==200
    new=make_plan(client)
    committed={v['id'] for v in p['result']['rows'] if v['allocated_m3']>0}
    assert all(v['allocated_m3']==0 and v['already_scheduled'] for v in new['result']['rows'] if v['id'] in committed)

def test_power_schedule_meets_deadline_and_capacity():
    result=calc(power_hours_override=24)
    for v in result['rows']:
        for w in v['power_schedule']:
            assert w['duration_hours']<=24
            assert (w['day']-1)*24+w['duration_hours']+v['travel_hours']<=v['window_days']*24+1e-6
            assert w['mw']<=v['pump_capacity_mw']
