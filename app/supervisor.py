"""Durable, bounded tool orchestration with an actual LangGraph human interrupt."""
from typing import TypedDict
from pathlib import Path
import os
import uuid
import threading
from datetime import datetime,timezone
from langgraph.graph import StateGraph,START,END
from langgraph.types import interrupt,Command
from langgraph.checkpoint.sqlite import SqliteSaver
from .models import StrictModel,Scenario
from pydantic import Field
from . import store
from .engine import planner
from .network import lift_capacity,LiftScenario,network
from .integrations import weather,enrich
from .farmer import operational_constraints

LOCK=threading.RLock()

class Mission(StrictModel):
    goal: str = Field(default='Protect drinking water and improve crop rescue with feasible pumping power',min_length=5,max_length=1000)
    scenario: Scenario = Field(default_factory=Scenario)
    include_weather: bool = False
    include_kaleshwaram: bool = True

class MissionReview(StrictModel):
    accept: bool
    reviewer: str = Field(min_length=2,max_length=80)
    reason: str = Field(min_length=3,max_length=500)

class AgentState(TypedDict,total=False):
    goal:str
    scenario:dict
    include_weather:bool
    include_kaleshwaram:bool
    dataset:dict
    dataset_hash:str
    events:list
    result:dict
    alternatives:list
    capacity:dict
    weather_result:dict
    recommendation:dict
    decision:dict
    plan_id:str
    status:str

def log(s,tool,detail):
    return s.get('events',[])+[dict(tool=tool,detail=detail,at=store.now())]

def evidence(s):
    data=store.dataset()
    return dict(dataset=data,dataset_hash=store.fingerprint(data),events=log(s,'read_evidence','Read dated reservoir registry, crop demand, existing water commitments and route reservations.'),status='running')

def weather_tool(s):
    r=s['dataset']['reservoirs'][0]
    w=weather(r['latitude'],r['longitude'])
    return dict(weather_result=w,events=log(s,'weather_preview',w.get('error','Forecast preview retrieved; effective rainfall remains an explicit scenario assumption.')))

def calculate(sc,data):
    return planner.invoke(dict(dataset=data,scenario=sc,booked=store.bookings(),scheduled_villages=store.scheduled_villages(),**operational_constraints(),events=[]))

def water_tool(s):
    result=calculate(s['scenario'],s['dataset']);result.pop('dataset',None);result.pop('booked',None)
    return dict(result=result,events=log(s,'calculate_water_and_power',f"Base proposal coverage {result['summary']['coverage_pct']:.1f}%; evidence status {result['summary']['status']}."))

def alternatives_tool(s):
    options=[]
    # Bounded counterfactual search. Additional hours remain unconfirmed requests.
    for hours in [12,16,24]:
        sc=dict(s['scenario'],power_hours_override=hours)
        r=calculate(sc,s['dataset'])
        options.append(dict(hours_day=hours,scenario=sc,summary=r['summary']))
    return dict(alternatives=options,events=log(s,'compare_power_windows','Compared three bounded power-hour alternatives; reserves and canal limits retained in every candidate.'))

def capacity_tool(s):
    capacity=lift_capacity(LiftScenario())
    return dict(capacity=capacity,events=log(s,'kaleshwaram_capacity','Read sourced design context and calculate a hypothetical Package 6 lift envelope. Current operating clearance remains unknown.'))

def synthesize(s):
    base=s['result']['summary'];options=s.get('alternatives',[])
    best=max(options,key=lambda o:(o['summary']['coverage_pct'],-o['summary']['energy_mwh'])) if options else None
    gain=(best['summary']['coverage_pct']-base['coverage_pct']) if best else 0
    recommendation=dict(goal=s['goal'],base_coverage_pct=base['coverage_pct'],extra_power_coverage_gain_pct=max(0,gain),
        suggested_power_hours=best['hours_day'] if best and gain>.01 else s['scenario']['power_hours_override'],
        next_action='Refresh missing reservoir evidence before preparing an order.' if s['result']['blocked'] else 'Review whether extra grid hours can be confirmed; then revise the scenario and obtain both operating reviews.' if gain>.01 else 'Extra grid hours do not materially improve this case; review source and delivery bottlenecks.',
        evidence_gaps=['Live official reservoir observations','Authenticated engineering and operating clearance','Shared feeder and canal topology'],
        selected_scenario=s['scenario'])
    return dict(recommendation=recommendation,events=log(s,'synthesize','Keep the base scenario as the reviewable proposal; counterfactual power windows are not silently adopted.'),status='awaiting_analysis_review')

def review(s):
    decision=interrupt(dict(kind='analysis_review',recommendation=s['recommendation'],
        message='Accept this analysis to save the base proposal for separate water and power reviews. This does not approve a release.'))
    return dict(decision=decision,status='analysis_accepted' if decision['accept'] else 'analysis_rejected',events=log(s,'human_analysis_review',decision['reason']))

def finalize(s):
    if not s['decision']['accept']:return dict(status='analysis_rejected')
    current=store.dataset()
    if store.fingerprint(current)!=s['dataset_hash']:
        return dict(status='evidence_changed',events=log(s,'guard','Evidence changed while waiting; start a new mission.'))
    # Recalculate against reservations acquired while the human was reviewing.
    result=calculate(s['scenario'],current);result.pop('dataset',None);result.pop('booked',None)
    saved=store.save_result(enrich(result),s['scenario'],current)
    return dict(plan_id=saved['id'],status='proposal_saved',events=log(s,'save_reviewable_proposal','Saved a fresh base proposal. Water and power decisions are still required.'))

def build(saver):
    g=StateGraph(AgentState)
    for name,fn in [('evidence',evidence),('weather',weather_tool),('water',water_tool),('alternatives',alternatives_tool),('capacity',capacity_tool),('synthesis',synthesize),('review',review),('finalize',finalize)]:g.add_node(name,fn)
    g.add_edge(START,'evidence')
    g.add_conditional_edges('evidence',lambda s:'weather' if s['include_weather'] else 'water')
    g.add_edge('weather','water')
    g.add_conditional_edges('water',lambda s:'alternatives' if not s['result']['blocked'] and any(v['lift_head_m'] and v['coverage_pct']<99.9 and not v['already_scheduled'] for v in s['result']['rows']) else 'capacity' if s['include_kaleshwaram'] else 'synthesis')
    g.add_conditional_edges('alternatives',lambda s:'capacity' if s['include_kaleshwaram'] else 'synthesis')
    g.add_edge('capacity','synthesis');g.add_edge('synthesis','review');g.add_edge('review','finalize');g.add_edge('finalize',END)
    return g.compile(checkpointer=saver)

def path():
    p=Path(os.getenv('JALASETU_DB',str(store.DEFAULT)))
    return str(p.with_name(p.stem+'-agent.sqlite3'))

def operate(run_id,payload=None,resume=None):
    # One lock per local server process; this is a single-user demonstration.
    with LOCK,SqliteSaver.from_conn_string(path()) as saver:
        g=build(saver);config={'configurable':{'thread_id':run_id},'recursion_limit':20}
        if payload is not None:g.invoke(payload,config)
        elif resume is not None:
            snapshot=g.get_state(config)
            if not snapshot.values:raise ValueError('Agent run not found')
            if not snapshot.next:raise ValueError('Agent run has already finished')
            g.invoke(Command(resume=resume),config)
        snap=g.get_state(config)
        if not snap.values:raise ValueError('Agent run not found')
        result=dict(snap.values);result.pop('dataset',None)
        return dict(id=run_id,state=result,waiting_for_review=bool(snap.next),durable=True)

def start(mission):
    return operate(uuid.uuid4().hex[:12],payload={**mission.model_dump(), 'scenario':mission.scenario.model_dump(),'events':[]})
