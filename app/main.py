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

app=FastAPI(title='JalaSetu • Water to field',description='Local simulation. No operational control or authenticated official approvals.')

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
        model_configured=all(__import__('os').getenv(k) for k in ['JALASETU_LLM_BASE_URL','JALASETU_LLM_API_KEY','JALASETU_LLM_MODEL']))

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
