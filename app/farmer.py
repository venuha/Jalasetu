"""Farm water budgeting and event-driven demonstration alerts."""
from datetime import datetime,timezone,timedelta
from typing import Literal
from pydantic import Field,model_validator
from .models import StrictModel
from . import store
import json
import uuid

FAO='https://www.fao.org/4/s2022e/s2022e08.htm'
ICAR='https://icar-iirr.org/index.php/en/component/content/article/33-iirr-technologies/113-technology-10?Itemid=258'
ACRE_HA=.40468564224

class FarmBudget(StrictModel):
    acres:float=Field(default=2,gt=0,le=10000)
    crop:Literal['Paddy','Maize','Pulses']='Paddy'
    stage:Literal['new planting','vegetative','flowering','grain filling']='vegetative'
    target_depth_mm:float=Field(default=20,ge=0,le=300)
    seepage_allowance_mm:float=Field(default=0,ge=0,le=100)
    soil_credit_mm:float=Field(default=0,ge=0,le=300)
    observed_effective_rain_mm:float=Field(default=0,ge=0,le=300)
    forecast_rain_mm:float=Field(default=0,ge=0,le=300)
    forecast_effective_fraction:float=Field(default=.6,ge=0,le=1)
    rain_probability_pct:float=Field(default=0,ge=0,le=100)
    field_efficiency:float=Field(default=.65,gt=0,le=1)
    pump_flow_lps:float=Field(default=10,gt=0,le=1000)
    critical_stress:bool=False


def farm_budget(sc:FarmBudget):
    area=sc.acres*ACRE_HA
    net=max(0,sc.target_depth_mm+sc.seepage_allowance_mm-sc.soil_credit_mm-sc.observed_effective_rain_mm)
    gross=area*net*10/sc.field_efficiency
    forecast_credit=sc.forecast_rain_mm*sc.forecast_effective_fraction
    should_review=net>0 and forecast_credit>=net and sc.rain_probability_pct>=70 and not sc.critical_stress and sc.stage!='flowering'
    policy='NO_ADDITIONAL_IRRIGATION' if net==0 else 'DEFER_FOR_RAIN_REVIEW' if should_review else 'IRRIGATION_REVIEW_REQUIRED'
    text='Verified effective rainfall and soil water meet this application target; propose zero additional irrigation.' if net==0 else 'Forecast may cover the remaining deficit. Hold the proposed new irrigation request for field review; check rain and soil conditions before restarting.' if should_review else 'A measured water deficit remains. Confirm crop-stage needs and an approved water/power window before irrigating.'
    advice=['Measure field water and delivered flow; stop at the reviewed application target rather than running for the whole power window.',
            'Check bunds and distribution leaks; compare measured delivery with the plan.',
            'Do not expand planted area solely because a power window is announced.']
    if sc.crop=='Paddy':advice.append('Discuss alternate wetting and drying with a local rice agronomist; flowering needs special water management. Do not apply generic drying advice to a stressed or flowering field.')
    return dict(policy=policy,area_ha=area,net_depth_mm=net,source_volume_m3=gross,
        field_volume_m3=area*net*10,pump_hours=gross/(sc.pump_flow_lps*3.6),
        forecast_effective_mm=forecast_credit,forecast_adjusted_m3=area*max(0,net-forecast_credit)*10/sc.field_efficiency,
        forecast_is_not_observed=True,recommendation=text,advice=advice,assumptions=sc.model_dump(),sources=[FAO,ICAR],
        note='Supplemental application calculator, not a full-season prescription. Target depth, seepage, soil credit, effective rain and efficiency need local verification. Forecast adjustment is a counterfactual, not an automatic authorized release change.')

class PowerEvent(StrictModel):
    village_id:str=Field(min_length=2,max_length=80)
    state:Literal['available','outage','unknown']
    observed_at:datetime
    confirmed_until:datetime|None=None
    source:Literal['demo utility commitment','demo feeder observation']='demo feeder observation'
    event_id:str=Field(min_length=3,max_length=100)
    @model_validator(mode='after')
    def check_times(self):
        if self.observed_at.tzinfo is None or self.confirmed_until and self.confirmed_until.tzinfo is None:raise ValueError('Use timezone-aware times')
        if self.confirmed_until and (self.source!='demo utility commitment' or self.confirmed_until<=self.observed_at):raise ValueError('A future window requires a utility commitment')
        return self

class ReleaseEvent(StrictModel):
    route_id:str=Field(min_length=2,max_length=80)
    event_id:str=Field(min_length=3,max_length=100)
    observed_at:datetime
    duration_minutes:float=Field(gt=0,le=1440)
    flow_lps:float=Field(ge=0,le=1000000)
    approved_rate_lps:float=Field(ge=0,le=1000000)
    cumulative_volume_m3:float=Field(ge=0)
    approved_volume_m3:float=Field(ge=0)
    tolerance_pct:float=Field(default=10,ge=0,le=50)
    @model_validator(mode='after')
    def check_time(self):
        if self.observed_at.tzinfo is None:raise ValueError('Use timezone-aware observation time')
        return self


def tables(c):
    c.execute('CREATE TABLE IF NOT EXISTS monitoring_events (id TEXT PRIMARY KEY, kind TEXT, entity TEXT, observed_at TEXT, body TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS alerts (id TEXT PRIMARY KEY, body TEXT)')

def latest(kind,entity,c):
    row=c.execute('SELECT observed_at,body FROM monitoring_events WHERE kind=? AND entity=? ORDER BY observed_at DESC LIMIT 1',(kind,entity)).fetchone()
    return json.loads(row['body']) if row else None

def emit(c,key,audience,severity,title,message):
    body=dict(id=key,audience=audience,severity=severity,title=title,message=message,created_at=store.now(),
              channel='in_app_demo',delivery_status='available_in_app',external_sent=False)
    c.execute('INSERT OR IGNORE INTO alerts VALUES(?,?)',(key,json.dumps(body)))
    return body

def power_event(e):
    now=datetime.now(timezone.utc)
    if abs((now-e.observed_at).total_seconds())>600:raise ValueError('Power telemetry must be within ten minutes of server time.')
    if e.confirmed_until and e.confirmed_until>now+timedelta(hours=24):raise ValueError('Demo commitment cannot exceed 24 hours.')
    entity=e.village_id
    if entity not in {v['id'] for v in store.dataset()['villages']}:raise ValueError('Unknown village')
    with store.connect() as c:
        tables(c);c.execute('BEGIN IMMEDIATE')
        existing=c.execute('SELECT body FROM monitoring_events WHERE id=?',(e.event_id,)).fetchone()
        if existing:
            if json.loads(existing[0])!=e.model_dump(mode='json'):raise ValueError('Event ID already used with different content')
            return dict(duplicate=True,alerts=[])
        prev=latest('power',entity,c)
        if prev and datetime.fromisoformat(prev['observed_at'])>=e.observed_at:raise ValueError('Out-of-order observation; latest feeder state is retained.')
        payload=e.model_dump(mode='json')
        c.execute('INSERT INTO monitoring_events VALUES(?,?,?,?,?)',(e.event_id,'power',entity,e.observed_at.isoformat(),json.dumps(payload)))
        changed=not prev or prev['state']!=e.state or prev.get('confirmed_until')!=payload.get('confirmed_until')
        alerts=[]
        if changed:
            if e.state=='outage':
                title='Unexpected power interruption' if prev and prev['state']=='available' else 'Power is unavailable'
                msg='Do not rely on the previous pumping window. Verify feeder restoration; request a revised irrigation slot. No remote pump action was performed.'
                alerts.append(emit(c,e.event_id+'-farmer','farmer','urgent',title,msg))
                alerts.append(emit(c,e.event_id+'-ops','power and irrigation desk','urgent','Replan interrupted irrigation',entity+': '+msg))
            elif e.state=='available':
                if e.confirmed_until:
                    msg=f"Demo feeder available at {e.observed_at.isoformat()}; utility schedule indicates supply until {e.confirmed_until.isoformat()}. Interruptions remain possible. Irrigate only within your reviewed water budget; check current status before travelling."
                else:msg='Power observed available now. No duration commitment is verified; do not assume a two-hour window. Confirm with the utility before planning a trip or pump run.'
                alerts.append(emit(c,e.event_id+'-farmer','farmer','info','Power availability update',entity+': '+msg))
            else:alerts.append(emit(c,e.event_id+'-unknown','farmer','warning','Feeder status unknown','Do not assume power is available. Obtain a fresh feeder reading and a confirmed schedule.'))
        return dict(duplicate=False,state=payload,alerts=alerts)


def release_event(e):
    if abs((datetime.now(timezone.utc)-e.observed_at).total_seconds())>600:raise ValueError('Release telemetry must be within ten minutes of server time.')
    with store.connect() as c:
        tables(c);c.execute('BEGIN IMMEDIATE')
        existing=c.execute('SELECT body FROM monitoring_events WHERE id=?',(e.event_id,)).fetchone()
        if existing:
            if json.loads(existing[0])!=e.model_dump(mode='json'):raise ValueError('Event ID already used with different content')
            return dict(duplicate=True,alerts=[])
        prev=latest('release',e.route_id,c)
        if prev and datetime.fromisoformat(prev['observed_at'])>=e.observed_at:raise ValueError('Out-of-order release reading')
        if prev and e.cumulative_volume_m3<prev['cumulative_volume_m3']:raise ValueError('Cumulative meter cannot decrease without a reconciled meter reset')
        factor=1+e.tolerance_pct/100
        high_rate=e.flow_lps>e.approved_rate_lps*factor
        high_volume=e.cumulative_volume_m3>e.approved_volume_m3*factor
        c.execute('INSERT INTO monitoring_events VALUES(?,?,?,?,?)',(e.event_id,'release',e.route_id,e.observed_at.isoformat(),json.dumps(e.model_dump(mode='json'))))
        alerts=[]
        # Alert on state transition, not on every repeated high sample.
        previous_high=prev and (prev['flow_lps']>prev['approved_rate_lps']*(1+prev['tolerance_pct']/100) or prev['cumulative_volume_m3']>prev['approved_volume_m3']*(1+prev['tolerance_pct']/100))
        if (high_rate or high_volume) and not previous_high:
            alerts.append(emit(c,e.event_id+'-excess','water authority and local water-body operator','urgent','Excess release detected',f"{e.route_id}: measured {e.flow_lps:.1f} L/s; cumulative {e.cumulative_volume_m3:.1f} m³ versus budget {e.approved_volume_m3:.1f} m³. Verify the meter and operator order; review a reduction or closure. No gate was operated."))
        elif previous_high and not high_rate and not high_volume:
            alerts.append(emit(c,e.event_id+'-normal','water authority','info','Release back within demo limits',e.route_id+': latest reading is within configured tolerance.'))
        return dict(duplicate=False,high_rate=high_rate,high_volume=high_volume,interval_volume_m3=e.flow_lps*e.duration_minutes*.06,alerts=alerts,
            note='Approved thresholds are user-entered demo values, not fetched from a signed operating order.')


def monitoring():
    with store.connect() as c:
        tables(c)
        alerts=[json.loads(r[0]) for r in c.execute('SELECT body FROM alerts ORDER BY rowid DESC LIMIT 100')]
        rows=c.execute('SELECT kind,entity,body FROM monitoring_events ORDER BY observed_at DESC').fetchall()
        states={}
        for r in rows:
            key=r['kind']+':'+r['entity']
            if key not in states:
                state=json.loads(r['body']);age=(datetime.now(timezone.utc)-datetime.fromisoformat(state['observed_at'])).total_seconds()
                state['stale']=age>600
                if r['kind']=='power':
                    expired=bool(state.get('confirmed_until') and datetime.fromisoformat(state['confirmed_until'])<=datetime.now(timezone.utc))
                    state['window_expired']=expired
                    state['effective_status']='unknown' if state['stale'] or expired else state['state']
                states[key]=state
        return dict(alerts=alerts,states=states,external_notifications_configured=False,
            note='In-app simulated notifications only. SMS/voice/WhatsApp require consented contacts, an authorized provider and live utility data.')

class RainEvent(StrictModel):
    village_id:str=Field(min_length=2,max_length=80)
    event_id:str=Field(min_length=3,max_length=100)
    observed_at:datetime
    effective_rain_mm:float=Field(ge=0,le=300)
    source:Literal['demo effective-rain observation']='demo effective-rain observation'
    @model_validator(mode='after')
    def check_time(self):
        if self.observed_at.tzinfo is None:raise ValueError('Use timezone-aware observation time')
        return self


def rain_event(e):
    if abs((datetime.now(timezone.utc)-e.observed_at).total_seconds())>600:raise ValueError('Rain event must be received within ten minutes of observation.')
    if e.village_id not in {v['id'] for v in store.dataset()['villages']}:raise ValueError('Unknown village')
    with store.connect() as c:
        tables(c);c.execute('BEGIN IMMEDIATE')
        prev=latest('rain',e.village_id,c)
        old=c.execute('SELECT body FROM monitoring_events WHERE id=?',(e.event_id,)).fetchone()
        if old:
            if json.loads(old[0])!=e.model_dump(mode='json'):raise ValueError('Event ID conflict')
            return dict(duplicate=True)
        if prev and datetime.fromisoformat(prev['observed_at'])>=e.observed_at:raise ValueError('Out-of-order rain observation')
        c.execute('INSERT INTO monitoring_events VALUES(?,?,?,?,?)',(e.event_id,'rain',e.village_id,e.observed_at.isoformat(),json.dumps(e.model_dump(mode='json'))))
        alert=emit(c,e.event_id+'-rain','irrigation desk and farmer','info','Rainfall requires a new water budget',f'{e.village_id}: {e.effective_rain_mm:.1f} mm effective rain entered for the current application. Pending plans require recalculation. This depth replaces, rather than adds to, an earlier observation. No gate was operated.')
        return dict(duplicate=False,alert=alert)


def operational_constraints():
    data=monitoring();outages=[];rain={}
    for key,s in data['states'].items():
        if key.startswith('power:') and s['effective_status']!='available':outages.append(s['village_id'])
        if key.startswith('rain:'):
            # Rain can remain useful after a short telemetry window, but not beyond this demo application horizon.
            age=(datetime.now(timezone.utc)-datetime.fromisoformat(s['observed_at'])).total_seconds()
            if age<86400:rain[s['village_id']]=s['effective_rain_mm']
    return dict(power_outages=outages,rain_by_village=rain)
