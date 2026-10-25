import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.access import validate_hosting

@pytest.fixture
def hosted(monkeypatch,tmp_path):
    monkeypatch.setenv('JALASETU_DEPLOYED','true')
    monkeypatch.setenv('JALASETU_DB',str(tmp_path/'hosted.sqlite3'))
    monkeypatch.setenv('JALASETU_ACCESS_USER','management')
    monkeypatch.setenv('JALASETU_ACCESS_PASSWORD','test-management-password-long-enough')
    return ('management','test-management-password-long-enough')

def test_hosted_routes_require_management_access(hosted):
    with TestClient(app) as client:
        assert client.get('/api/health').status_code==200
        for route in ['/','/app.js','/api/dashboard','/api/connections','/docs','/openapi.json']:
            response=client.get(route)
            assert response.status_code==401 and 'Basic' in response.headers['www-authenticate']
        assert client.post('/api/authority/cases',json={}).status_code==401
        assert client.get('/api/dashboard',auth=('management','incorrect')).status_code==401
        assert client.get('/api/dashboard',headers={'authorization':'Basic malformed'}).status_code==401
        response=client.get('/api/dashboard',auth=hosted)
        assert response.status_code==200 and response.headers['cache-control']=='no-store'

def test_hosted_provider_secrets_cannot_be_changed_in_browser(hosted):
    with TestClient(app) as client:
        assert client.get('/api/connections',auth=hosted).json()['editable'] is False
        response=client.post('/api/connections',json={'clear':True},auth=hosted)
        assert response.status_code==403

def test_hosted_startup_fails_closed(hosted,monkeypatch):
    validate_hosting()
    monkeypatch.setenv('JALASETU_ACCESS_PASSWORD','short')
    with pytest.raises(RuntimeError,match='at least 20'):validate_hosting()
    with pytest.raises(RuntimeError):
        with TestClient(app):pass

def test_hosted_database_and_worker_contract(hosted,monkeypatch):
    monkeypatch.setenv('JALASETU_DB','relative.sqlite3')
    with pytest.raises(RuntimeError,match='absolute'):validate_hosting()
    monkeypatch.setenv('JALASETU_DB','/var/data/jalasetu.sqlite3')
    monkeypatch.setenv('WEB_CONCURRENCY','2')
    with pytest.raises(RuntimeError,match='one worker'):validate_hosting()
