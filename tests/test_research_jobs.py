import pytest
from app import research_jobs,research_panel,store

@pytest.fixture
def database(tmp_path,monkeypatch):
    monkeypatch.setenv('JALASETU_DB',str(tmp_path/'jobs.sqlite3'))

class DeferredPool:
    def __init__(self):self.calls=[]
    def submit(self,fn,*args):self.calls.append((fn,args))

def test_job_is_bounded_and_read_does_not_wait_on_graph(database,monkeypatch):
    pool=DeferredPool();monkeypatch.setattr(research_jobs,'POOL',pool)
    request=research_panel.PanelRequest(question='Review water and power evidence')
    jobs=[research_jobs.submit(request) for _ in range(3)]
    assert len(pool.calls)==3 and jobs[0]['job_active']
    assert research_jobs.read(jobs[0]['id'])['state']['status']=='queued'
    with pytest.raises(ValueError,match='queue is full'):research_jobs.submit(request)
    # Execute one queued item against a mocked graph, then confirm retrieval uses its durable result.
    monkeypatch.setattr(research_panel,'operate',lambda run_id,**kwargs:dict(id=run_id,state={'status':'awaiting_panel_review'},waiting_for_review=True,roles=5))
    fn,args=pool.calls[0];fn(*args)
    result=research_jobs.read(jobs[0]['id'])
    assert result['job_active'] is False and result['waiting_for_review']

def test_restarted_jobs_are_explicitly_interrupted(database,monkeypatch):
    pool=DeferredPool();monkeypatch.setattr(research_jobs,'POOL',pool)
    job=research_jobs.submit(research_panel.PanelRequest(question='Review dated readings'))
    research_jobs.recover()
    result=research_jobs.read(job['id'])
    assert result['state']['status']=='interrupted' and not result['job_active']
    assert 'Server restarted' in result['state']['job_message']

def test_job_failure_does_not_persist_provider_exception(database,monkeypatch):
    pool=DeferredPool();monkeypatch.setattr(research_jobs,'POOL',pool)
    job=research_jobs.submit(research_panel.PanelRequest(question='Review dated readings'))
    def fail(*a,**k):raise RuntimeError('secret-provider-credential')
    monkeypatch.setattr(research_panel,'operate',fail)
    fn,args=pool.calls[0];fn(*args)
    result=research_jobs.read(job['id'])
    assert result['state']['status']=='failed' and 'secret-provider-credential' not in str(result)
