"""Bounded single-process research jobs so hosted HTTP requests need not wait on models."""
from concurrent.futures import ThreadPoolExecutor
import json
import uuid
from . import store,research_panel

POOL=ThreadPoolExecutor(max_workers=1,thread_name_prefix='research-panel')

def table(c):c.execute('CREATE TABLE IF NOT EXISTS research_jobs (id TEXT PRIMARY KEY, status TEXT NOT NULL, message TEXT NOT NULL)')

def recover():
    with store.connect() as c:
        table(c)
        c.execute("UPDATE research_jobs SET status='interrupted',message='Server restarted before the panel finished. Start a new panel; completed graph checkpoints remain available.' WHERE status IN ('queued','running')")

def set_status(run_id,status,message=''):
    with store.connect() as c:
        table(c);c.execute('UPDATE research_jobs SET status=?,message=? WHERE id=?',(status,message,run_id))

def work(run_id,payload):
    set_status(run_id,'running')
    try:
        research_panel.operate(run_id,payload=payload)
        set_status(run_id,'finished')
    except Exception:
        # Do not persist raw provider exceptions, which could contain credentials or request details.
        set_status(run_id,'failed','Panel execution failed. No model findings were fabricated. Start a new run or inspect the server logs.')

def submit(request):
    run_id=uuid.uuid4().hex[:12]
    with store.connect() as c:
        table(c);c.execute('BEGIN IMMEDIATE')
        count=c.execute("SELECT COUNT(*) FROM research_jobs WHERE status IN ('queued','running')").fetchone()[0]
        if count>=3:raise ValueError('Research queue is full. Wait for an existing panel to finish.')
        c.execute('INSERT INTO research_jobs VALUES(?,?,?)',(run_id,'queued',''))
    POOL.submit(work,run_id,request.model_dump())
    return dict(id=run_id,state=dict(status='queued'),waiting_for_review=False,roles=5,job_active=True)

def read(run_id):
    with store.connect() as c:
        table(c);row=c.execute('SELECT status,message FROM research_jobs WHERE id=?',(run_id,)).fetchone()
    if row and row['status']!='finished':
        return dict(id=run_id,state=dict(status=row['status'],job_message=row['message']),waiting_for_review=False,roles=5,job_active=row['status'] in ['queued','running'])
    return dict(**research_panel.operate(run_id),job_active=False)
