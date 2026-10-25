"""Deterministic water accounting. No language model controls these calculations."""
from datetime import datetime, timezone
import copy
from typing import TypedDict
from langgraph.graph import StateGraph, START, END

TMC_M3=28_316_846.592
CFS_M3S=.028316846592


def available(r, booked=0):
    # Operating floor and hydro hold overlap: retain the larger pool, not both.
    protected = max(r['operating_floor_tmc'], r['hydro_hold_tmc'])
    protected += r['drinking_reserve_tmc'] + r['environmental_reserve_tmc'] + r['other_commitments_tmc']
    return dict(protected_tmc=protected, available_tmc=max(0,r['storage_tmc']-protected-booked),
                reserve_deficit_tmc=max(0,protected-r['storage_tmc']), booked_tmc=booked)


class State(TypedDict, total=False):
    dataset: dict
    scenario: dict
    booked: dict
    scheduled_villages: list
    power_outages:list
    rain_by_village:dict
    events: list
    blocked: list
    rows: list
    reservoirs: list
    summary: dict
    recommendations: list


def event(state, step, detail):
    return state.get('events',[]) + [dict(step=step,detail=detail,at=datetime.now(timezone.utc).isoformat())]


def validate_evidence(s):
    blocked=[]
    now=datetime.now(timezone.utc)
    for r in s['dataset']['reservoirs']:
        dt=datetime.fromisoformat(r['observed_at'])
        age=(now-dt).total_seconds()/3600
        if age>48 or age < -1:
            blocked.append(f"{r['name']}: observation is stale or future dated; upload a verified observation.")
    if s['scenario']['failure_mode']=='stale reservoir':
        blocked.append('Injected stale reservoir: refresh required before proposing a release.')
    return dict(blocked=blocked, events=event(s,'Evidence check',
        'Observation freshness checked; all operational inputs are synthetic demo data.'))


def blocked_end(s):
    return dict(rows=[],reservoirs=[],summary=dict(status='blocked',requested_tmc=0,allocated_tmc=0,
        villages_needing_water=0,energy_mwh=0,coverage_pct=0),recommendations=s['blocked'],
        events=event(s,'Human handoff','Planning paused. Missing evidence must be corrected; no approval is available.'))


def demand(s):
    rows=[]
    sc=s['scenario']
    for v in s['dataset']['villages']:
        measured_rain=s.get('rain_by_village',{}).get(v['id'],0)
        # Rain scenario and observed credit are alternative estimates, not additive duplicates.
        net_mm=max(0,v['net_irrigation_mm']*sc['demand_multiplier']-v['soil_credit_mm']-max(sc['rainfall_credit_mm'],measured_rain))
        field_m3=v['area_ha']*net_mm*10
        source_m3=field_m3/v['efficiency']
        already_scheduled=v['id'] in s.get('scheduled_villages',[])
        if already_scheduled:source_m3=0
        # Energy per cubic metre at total dynamic head. Gravity routes use zero pumping energy.
        e_per_m3=1000*9.81*v['lift_head_m']/v['pump_efficiency']/3.6e9
        days=min(sc['horizon_days'],v['deadline_days'])
        hours_day=v['power_hours_day'] if sc['power_hours_override'] is None else sc['power_hours_override']
        if sc['failure_mode']=='power outage' or v['id'] in s.get('power_outages',[]): hours_day=0
        usable_hours=max(0,days*24-v['travel_hours'])
        daily_windows=[min(hours_day,max(0,usable_hours-day*24)) for day in range(days)]
        pump_hours=sum(daily_windows)
        # Direct delivery: do not assume an unmodelled balancing tank can absorb peak pump flow.
        effective_mw=min(v['pump_capacity_mw'],e_per_m3*v['canal_capacity_cusecs']*CFS_M3S*3600) if e_per_m3 else 0
        canal_limit=v['canal_capacity_cusecs']*CFS_M3S*(pump_hours if e_per_m3 else usable_hours)*3600
        power_limit=effective_mw*pump_hours/e_per_m3 if e_per_m3 else float('inf')
        delivery_limit=min(canal_limit,power_limit)
        rows.append(dict(**v,net_mm=net_mm,measured_rain_mm=measured_rain,requested_m3=source_m3,already_scheduled=already_scheduled,
            requested_tmc=source_m3/TMC_M3,field_need_m3=field_m3,
            energy_per_m3_mwh=e_per_m3,delivery_limit_m3=delivery_limit,
            scheduled_mw=effective_mw,daily_windows=daily_windows,
            pump_hours_available=pump_hours,window_days=days,allocated_m3=0,
            priority=(0 if v['stage'] in ['flowering','grain filling'] else 1)))
    return dict(rows=rows,events=event(s,'Crop demand tool',
        'Net irrigation converted to source demand; deadlines, canal travel time and pump constraints calculated.'))


def allocate(s):
    rows=copy.deepcopy(s['rows'])
    reservoirs=[]
    for r in s['dataset']['reservoirs']:
        budget=available(r,s.get('booked',{}).get(r['id'],0))
        left=budget['available_tmc']*TMC_M3
        group=[v for v in rows if v['reservoir_id']==r['id']]
        # Within each crop-stage tier, allocate proportionately, including tail-end villages.
        for tier in [0,1]:
            tier_rows=[v for v in group if v['priority']==tier]
            capped=[min(v['requested_m3'],v['delivery_limit_m3']) for v in tier_rows]
            total=sum(capped)
            ratio=min(1,left/total) if total else 0
            for v,limit in zip(tier_rows,capped): v['allocated_m3']=limit*ratio
            left=max(0,left-total*ratio)
        allocated=sum(v['allocated_m3'] for v in group)/TMC_M3
        reservoirs.append(dict(**r,**budget,proposed_tmc=allocated,
            remaining_tmc=r['storage_tmc']-budget['booked_tmc']-allocated))
    for v in rows:
        v['allocated_tmc']=v['allocated_m3']/TMC_M3
        v['coverage_pct']=100*v['allocated_m3']/v['requested_m3'] if v['requested_m3'] else 100
        v['energy_mwh']=v['allocated_m3']*v['energy_per_m3_mwh']
        v['pump_hours_needed']=v['energy_mwh']/v['scheduled_mw'] if v['scheduled_mw'] else 0
        hours_left=v['pump_hours_needed']; schedule=[]
        for day,window in enumerate(v['daily_windows'],1):
            hours=min(hours_left,window);hours_left=max(0,hours_left-hours)
            if hours>0:schedule.append(dict(day=day,start_hour_ist=0,duration_hours=hours,mw=v['scheduled_mw'],mwh=hours*v['scheduled_mw']))
        v['power_schedule']=schedule
        flow_hours=v['pump_hours_needed'] if v['lift_head_m'] else max(1,v['window_days']*24-v['travel_hours'])
        v['recommended_flow_cusecs']=v['allocated_m3']/(max(1e-9,flow_hours)*3600)/CFS_M3S
        v['status']='Already scheduled' if v['already_scheduled'] else 'No deficit' if not v['requested_m3'] else 'Covered' if v['coverage_pct']>=99.9 else 'Partial' if v['allocated_m3'] else 'Unserved'
    return dict(rows=rows,reservoirs=reservoirs,events=event(s,'Water and power tools',
        'Protected reserves retained; demand capped by power, canal and source limits. Stage priority then proportional allocation applied.'))


def explain(s):
    rows=s['rows']; recs=[]
    for r in s['reservoirs']:
        if r['reserve_deficit_tmc']:
            recs.append(f"{r['name']}: protected-pool deficit {r['reserve_deficit_tmc']:.2f} TMC. No new crop allocation; officials should assess drinking-water contingency supply.")
    for v in rows:
        if v['measured_rain_mm'] and not v['requested_m3'] and not v['already_scheduled']:
            recs.append(f"{v['name']}: observed effective rain meets the remaining demo application need. No additional irrigation is proposed.")
        if v['id'] in s.get('power_outages',[]) and v['lift_head_m']:
            recs.append(f"{v['name']}: feeder observation is unavailable, stale or interrupted. No lift allocation; confirm restoration and replan before notifying farmers to travel.")
        if v['already_scheduled']:
            recs.append(f"{v['name']}: an approved order already schedules this route. Review its delivery before making a further request; no additional water or power is scheduled here.")
        if v['coverage_pct']<99.9:
            if v['stage']=='new planting':
                recs.append(f"{v['name']}: defer expansion of new {v['crop'].lower()} planting until supply is confirmed; discuss suitable lower-water crops with an agronomist. Coverage {v['coverage_pct']:.0f}%.")
            else:
                recs.append(f"{v['name']}: prioritize existing {v['stage']} crop for agronomist-reviewed rescue irrigation; coverage {v['coverage_pct']:.0f}%. Avoid blanket irrigation cuts.")
            if v['lift_head_m'] and v['delivery_limit_m3']<v['requested_m3']:
                recs.append(f"{v['name']}: lift power or canal window limits delivery. Compare longer confirmed power windows or a staged delivery before seeking more reservoir water.")
    if s['scenario']['rainfall_credit_mm']:
        recs.append('Rainfall credit is a user-entered scenario assumption. Verify effective rainfall before reducing an irrigation order.')
    if s['scenario']['failure_mode']=='weather unavailable':
        recs.append('Weather tool unavailable: continue with manual demand and rainfall assumptions; no fabricated forecast used.')
    recs.append('Hydropower through-flows are not counted as consumptive withdrawals. This prototype retains a configured hydro pool; a full cascade generation model is future work.')
    req=sum(v['requested_tmc'] for v in rows); alloc=sum(v['allocated_tmc'] for v in rows)
    summary=dict(status='awaiting_approvals' if alloc else 'no_feasible_release',requested_tmc=req,
        allocated_tmc=alloc,energy_mwh=sum(v['energy_mwh'] for v in rows),
        villages_needing_water=sum(v['requested_m3']>0 for v in rows),
        villages_fully_covered=sum(v['requested_m3']>0 and v['coverage_pct']>=99.9 for v in rows),
        coverage_pct=100*alloc/req if req else 100)
    return dict(summary=summary,recommendations=recs,events=event(s,'Recommendation and handoff',
        'Scenario saved for separate water and power review. Revised scenarios require fresh approvals.'))


def graph():
    g=StateGraph(State)
    for name,fn in [('evidence',validate_evidence),('blocked',blocked_end),('demand',demand),('allocate',allocate),('explain',explain)]:g.add_node(name,fn)
    g.add_edge(START,'evidence')
    g.add_conditional_edges('evidence',lambda s:'blocked' if s['blocked'] else 'demand')
    g.add_edge('blocked',END);g.add_edge('demand','allocate');g.add_edge('allocate','explain');g.add_edge('explain',END)
    return g.compile()

planner=graph()
