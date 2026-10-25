from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from .models import Scenario,Decision,Delivery,Dataset
from . import store
from .engine import planner,available
from .integrations import weather,enrich
from .network import network,lift_capacity,LiftScenario
from .supervisor import Mission,MissionReview,start,operate
from .farmer import FarmBudget,farm_budget,PowerEvent,ReleaseEvent,power_event,release_event,monitoring,RainEvent,rain_event,operational_constraints
from . import public_data,research_panel,research_jobs,connections,authority
from pydantic import Field
from .models import StrictModel
from .access import lifespan,protect,hosted

class EvidenceRequest(StrictModel):
    latitude:float=Field(default=16.08,ge=15,le=20)
    longitude:float=Field(default=78.90,ge=77,le=82)
    include_secondary:bool=True

class SearchRequest(StrictModel):
    query:str=Field(min_length=5,max_length=500)

app=FastAPI(title='JalaSetu • Water operations',description='Planning prototype. No physical control or authenticated official approvals.',lifespan=lifespan)
app.middleware('http')(protect)

@app.get('/api/authority')
def authority_overview():return authority.overview()

@app.post('/api/authority/cases')
def authority_create(item:authority.CaseRequest):return authority.create(item)

@app.post('/api/authority/cases/{case_id}/assess')
def authority_assess(case_id:str):
    try:return authority.assess(case_id)
    except ValueError as e:raise HTTPException(404,str(e))

@app.get('/api/authority/beneficiary-previews')
def beneficiary_previews():return authority.beneficiary_previews()

@app.post('/api/authority/cases/{case_id}/review')
def authority_case_review(case_id:str,item:authority.CaseReview):
    try:return authority.review(case_id,item)
    except ValueError as e:raise HTTPException(404,str(e))

@app.get('/api/connections')
def connection_status():return connections.status()

@app.post('/api/connections')
def connection_update(item:connections.ConnectionUpdate):
    if hosted():raise HTTPException(403,'Hosted connections are managed in the hosting provider environment settings.')
    try:return connections.update(item)
    except ValueError as e:raise HTTPException(422,str(e))

@app.get('/api/public-evidence')
def public_latest():return public_data.latest()

@app.post('/api/public-evidence/refresh')
def public_refresh(item:EvidenceRequest):return public_data.refresh(item.latitude,item.longitude,item.include_secondary)

@app.post('/api/public-search')
def public_search(item:SearchRequest):return public_data.search_public(item.query)

@app.post('/api/research-panel/runs')
def research_start(item:research_panel.PanelRequest):return research_panel.start(item)

@app.post('/api/research-panel/jobs',status_code=202)
def research_job_start(item:research_panel.PanelRequest):
    try:return research_jobs.submit(item)
    except ValueError as e:raise HTTPException(429,str(e))

@app.get('/api/research-panel/jobs/{run_id}')
def research_job_read(run_id:str):
    try:return research_jobs.read(run_id)
    except ValueError as e:raise HTTPException(404,str(e))

@app.get('/api/research-panel/runs/{run_id}')
def research_read(run_id:str):
    try:return research_panel.operate(run_id)
    except ValueError as e:raise HTTPException(404,str(e))

@app.post('/api/research-panel/runs/{run_id}/review')
def research_review(run_id:str,item:research_panel.Review):
    try:return research_panel.operate(run_id,review=item.model_dump())
    except ValueError as e:raise HTTPException(409,str(e))

@app.get('/api/network')
def get_network():return network()

@app.post('/api/farm-budget')
def farm(item:FarmBudget):return farm_budget(item)

@app.get('/api/monitoring')
def monitor():return monitoring()

@app.post('/api/monitoring/rain')
def rain_observation(item:RainEvent):
    try:return rain_event(item)
    except ValueError as e:raise HTTPException(422,str(e))

@app.post('/api/monitoring/power')
def power_observation(item:PowerEvent):
    try:return power_event(item)
    except ValueError as e:raise HTTPException(422,str(e))

@app.post('/api/monitoring/release')
def release_observation(item:ReleaseEvent):
    try:return release_event(item)
    except ValueError as e:raise HTTPException(422,str(e))

@app.post('/api/lift-capacity')
def capacity(item:LiftScenario):return lift_capacity(item)

@app.post('/api/agent/runs')
def agent_start(item:Mission):return start(item)

@app.get('/api/agent/runs/{run_id}')
def agent_read(run_id:str):
    try:return operate(run_id)
    except ValueError as e:raise HTTPException(404,str(e))

@app.post('/api/agent/runs/{run_id}/review')
def agent_resume(run_id:str,item:MissionReview):
    try:return operate(run_id,resume=item.model_dump())
    except ValueError as e:raise HTTPException(409,str(e))


@app.get('/api/health')
def health():return {'ok':True,'mode':'synthetic_demo'}

@app.get('/api/dashboard')
def dashboard():
    data=store.dataset();booked=store.bookings()
    rs=[dict(**r,**available(r,booked.get(r['id'],0))) for r in data['reservoirs']]
    return dict(dataset=data,reservoirs=rs,plans=store.plans(),
        model_configured=connections.status()['llm_configured'])

@app.post('/api/plans')
def create_plan(scenario:Scenario):
    data=store.dataset()
    result=planner.invoke(dict(dataset=data,scenario=scenario.model_dump(),booked=store.bookings(),scheduled_villages=store.scheduled_villages(),**operational_constraints(),events=[]))
    # Evidence inputs are stored once, by hash, plus the full calculation snapshot in result.
    result.pop('dataset',None);result.pop('booked',None)
    result=enrich(result)
    return store.save_result(result,scenario.model_dump(),data)

@app.post('/api/compare')
def compare(scenario:Scenario):
    data=store.dataset();booked=store.bookings();options=[]
    for label,hours in [('Registered hours',None),('12 hours/day requested',12),('16 hours/day requested',16),('24 hours/day requested',24)]:
        sc=scenario.model_dump();sc['power_hours_override']=hours
        result=planner.invoke(dict(dataset=data,scenario=sc,booked=booked,scheduled_villages=store.scheduled_villages(),**operational_constraints(),events=[]))
        options.append(dict(label=label,**result['summary'],note='Evidence blocked' if result['blocked'] else 'Power outage persists' if sc['failure_mode']=='power outage' else 'Requires confirmation' if hours else 'Registered demo availability'))
    best=max(options,key=lambda o:o['coverage_pct'])
    return dict(options=options,insight=f"Best modelled coverage: {best['label']} ({best['coverage_pct']:.1f}%). Extra power cannot solve a protected-water deficit. These alternatives are not approved schedules.")

@app.get('/api/plans/{pid}')
def plan(pid:str):return store.get(pid)

@app.post('/api/plans/{pid}/decisions')
def decision(pid:str,item:Decision):return store.decide(pid,item)

@app.post('/api/plans/{pid}/deliveries')
def delivery(pid:str,item:Delivery):return store.record_delivery(pid,item)

@app.get('/api/dataset')
def export_dataset():return store.dataset()

@app.post('/api/dataset')
def import_dataset(data:Dataset):return store.replace_dataset(data.model_dump(mode='json'))

@app.get('/api/weather/{reservoir_id}')
def forecast(reservoir_id:str):
    r=next((r for r in store.dataset()['reservoirs'] if r['id']==reservoir_id),None)
    if not r:raise HTTPException(404,'Reservoir not found')
    return weather(r['latitude'],r['longitude'])

app.mount('/',StaticFiles(directory=Path(__file__).parent/'static',html=True),name='ui')
