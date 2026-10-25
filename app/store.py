import hashlib
import json
import os
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime, timezone
from fastapi import HTTPException
from .seed import seed
from .engine import available

DEFAULT=Path(__file__).resolve().parents[1]/'data'/'jalasetu.sqlite3'

def now(): return datetime.now(timezone.utc).isoformat()
def fingerprint(data): return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()

def connect():
    p=Path(os.getenv('JALASETU_DB',str(DEFAULT))); p.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(p,timeout=15);c.row_factory=sqlite3.Row
    c.execute('CREATE TABLE IF NOT EXISTS dataset (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS plans (id TEXT PRIMARY KEY, body TEXT)')
    if not c.execute('SELECT id FROM dataset').fetchone():
        c.execute('INSERT INTO dataset VALUES(1,?)',(json.dumps(seed()),));c.commit()
    return c

def dataset():
    with connect() as c:return json.loads(c.execute('SELECT body FROM dataset WHERE id=1').fetchone()[0])

def plans():
    with connect() as c:return [json.loads(r[0]) for r in c.execute('SELECT body FROM plans ORDER BY rowid DESC')]

def bookings(c=None):
    if c is None:
        with connect() as db:return bookings(db)
    out={}
    for row in c.execute('SELECT body FROM plans'):
        p=json.loads(row[0])
        if p['status'] in ['approved_simulation','delivery_recorded']:
            for r in p['result']['reservoirs']:
                out[r['id']]=out.get(r['id'],0)+r['proposed_tmc']
    return out

def scheduled_villages(c=None):
    if c is None:
        with connect() as db:return scheduled_villages(db)
    ids=set()
    for row in c.execute('SELECT body FROM plans'):
        p=json.loads(row[0])
        if p['status'] in ['approved_simulation','delivery_recorded']:
            ids.update(v['id'] for v in p['result']['rows'] if v['allocated_m3']>0)
    return sorted(ids)

def operational_hash(c=None):
    if c is None:
        with connect() as db:return operational_hash(db)
    try:
        rows=c.execute("SELECT kind,entity,body FROM monitoring_events WHERE kind IN ('power','rain') ORDER BY observed_at DESC").fetchall()
    except sqlite3.OperationalError:return fingerprint({})
    latest={}
    for r in rows:
        key=r['kind']+':'+r['entity']
        if key not in latest:latest[key]=json.loads(r['body'])
    return fingerprint(latest)

def get(pid,c=None):
    if c is None:
        with connect() as db:return get(pid,db)
    row=c.execute('SELECT body FROM plans WHERE id=?',(pid,)).fetchone()
    if not row:raise HTTPException(404,'Proposal not found')
    return json.loads(row[0])

def save_result(result,sc,data):
    pid=uuid.uuid4().hex[:12]
    p=dict(id=pid,created_at=now(),status=result['summary']['status'],scenario=sc,
        dataset_hash=fingerprint(data),operational_hash=operational_hash(),result=result,decisions={},deliveries={},audit=[])
    with connect() as c:c.execute('INSERT INTO plans VALUES(?,?)',(pid,json.dumps(p)))
    return p

def write(c,p):c.execute('UPDATE plans SET body=? WHERE id=?',(json.dumps(p),p['id']))

def decide(pid,decision):
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        p=get(pid,c)
        if p['status']!='awaiting_approvals':raise HTTPException(409,'This proposal cannot accept further decisions. Create a revised proposal.')
        if decision.role in p['decisions']:raise HTTPException(409,'This role has already reviewed this proposal.')
        data=json.loads(c.execute('SELECT body FROM dataset WHERE id=1').fetchone()[0])
        if fingerprint(data)!=p['dataset_hash']:raise HTTPException(409,'Evidence changed. Recalculate before review.')
        if p.get('operational_hash',fingerprint({}))!=operational_hash(c):raise HTTPException(409,'Rain or feeder observations changed. Recalculate before review.')
        for v in p['result']['rows']:
            if not v['lift_head_m'] or not v['allocated_m3']:continue
            try:row=c.execute("SELECT body FROM monitoring_events WHERE kind='power' AND entity=? ORDER BY observed_at DESC LIMIT 1",(v['id'],)).fetchone()
            except sqlite3.OperationalError:row=None
            if row:
                power=json.loads(row[0]);instant=datetime.now(timezone.utc)
                expired=power.get('confirmed_until') and datetime.fromisoformat(power['confirmed_until'])<=instant
                if power['state']!='available' or (instant-datetime.fromisoformat(power['observed_at'])).total_seconds()>600 or expired:
                    raise HTTPException(409,'Feeder evidence is unavailable or expired. Refresh observations and recalculate.')
        for r in data['reservoirs']:
            age=(datetime.now(timezone.utc)-datetime.fromisoformat(r['observed_at'])).total_seconds()/3600
            if age>48 or age < -1:raise HTTPException(409,'Evidence expired. Import fresh data and recalculate.')
        p['decisions'][decision.role]=dict(**decision.model_dump(),at=now())
        p['audit'].append(dict(at=now(),action=f'{decision.role}: {decision.action}',reason=decision.reason))
        if decision.action=='reject':p['status']='rejected'
        elif len(p['decisions'])==2:
            scheduled=set(scheduled_villages(c))
            if any(v['id'] in scheduled and v['allocated_m3']>0 for v in p['result']['rows']):
                raise HTTPException(409,'An approved order already schedules this village route. Recalculate; reconcile delivery before scheduling it again.')
            booked=bookings(c)
            for r in p['result']['reservoirs']:
                if r['proposed_tmc']>available(r,booked.get(r['id'],0))['available_tmc']+1e-9:
                    raise HTTPException(409,'Another approved proposal reserved this water. Recalculate the scenario.')
            p['status']='approved_simulation'
            p['audit'].append(dict(at=now(),action='SIMULATED ORDER',reason='Both demo roles approved. No gate, pump, official or farmer was contacted.'))
        write(c,p)
        return p

def record_delivery(pid,item):
    with connect() as c:
        c.execute('BEGIN IMMEDIATE');p=get(pid,c)
        if p['status'] not in ['approved_simulation','delivery_recorded']:raise HTTPException(409,'Delivery requires both approvals.')
        v=next((v for v in p['result']['rows'] if v['id']==item.village_id),None)
        if not v:raise HTTPException(404,'Village is not in this proposal')
        # Input is the cumulative source-equivalent volume, so losses are comparable.
        if item.delivered_m3>v['allocated_m3']+1e-6:raise HTTPException(422,'Cumulative delivery exceeds approved source volume.')
        previous=p['deliveries'].get(item.village_id,{}).get('delivered_m3',0)
        if item.delivered_m3<previous:raise HTTPException(422,'Cumulative delivery cannot decrease.')
        pct=100*item.delivered_m3/v['allocated_m3'] if v['allocated_m3'] else 100
        alert='Below 90% of approved volume: verify whether delivery is still in progress or a canal/power interruption needs attention.' if pct<90 else 'At least 90% of approved source-equivalent volume recorded.'
        p['deliveries'][item.village_id]=dict(**item.model_dump(),at=now(),coverage_pct=pct,insight=alert)
        p['status']='delivery_recorded'
        p['audit'].append(dict(at=now(),action='Delivery observation',reason=f'{item.village_id}: {item.delivered_m3:.0f} m³ source-equivalent. {item.note}'))
        write(c,p);return p

def replace_dataset(data):
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        if bookings(c):raise HTTPException(409,'Approved water is reserved against this snapshot. Use a new demo database for a new dataset; reconcile commitments first in a real deployment.')
        c.execute('UPDATE dataset SET body=? WHERE id=1',(json.dumps(data),))
    return data
