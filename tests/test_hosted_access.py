import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.access import validate_hosting
from app import access

@pytest.fixture
def hosted(monkeypatch,tmp_path):
    monkeypatch.setenv('JALASETU_DEPLOYED','true')
    monkeypatch.setenv('JALASETU_DB',str(tmp_path/'hosted.sqlite3'))
    monkeypatch.setenv('JALASETU_ACCESS_USER','management')
    monkeypatch.setenv('JALASETU_ACCESS_PASSWORD','test-management-password-long-enough')
    access.ATTEMPTS.clear()
    return ('management','test-management-password-long-enough')

def test_hosted_routes_require_management_access(hosted):
    with TestClient(app) as client:
        assert client.get('/api/health').status_code==200
        for route in ['/api/dashboard','/api/connections']:
            response=client.get(route)
            assert response.status_code==401 and 'www-authenticate' not in response.headers
        for route in ['/','/app.js','/docs','/openapi.json']:
            assert client.get(route,follow_redirects=False).status_code==303
        assert 'Sign in to your workspace' in client.get('/login').text
        assert client.post('/api/authority/cases',json={}).status_code==401
        assert client.get('/api/dashboard',auth=('management','incorrect')).status_code==401
        assert client.get('/api/dashboard',headers={'authorization':'Basic malformed'}).status_code==401
        response=client.get('/api/dashboard',auth=hosted)
        assert response.status_code==200 and response.headers['cache-control']=='no-store'

def test_basic_api_access_cannot_set_browser_session_keys(hosted):
    with TestClient(app) as client:
        assert client.get('/api/connections',auth=hosted).json()['editable'] is False
        response=client.post('/api/connections',json={'clear':True},auth=hosted)
        assert response.status_code==422

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


def test_ephemeral_sandbox_is_explicit_in_dashboard(hosted,monkeypatch):
    monkeypatch.setenv('JALASETU_STORAGE_MODE','ephemeral')
    with TestClient(app) as client:
        result=client.get('/api/dashboard',auth=hosted).json()
        assert result['deployment']=={'hosted':True,'storage_mode':'ephemeral'}


def test_browser_signin_cookie_and_logout(hosted):
    with TestClient(app,base_url='https://testserver') as client:
        r=client.post('/auth/login',json={'username':hosted[0],'password':hosted[1]},headers={'Origin':'https://testserver'})
        assert r.status_code==200
        cookie=r.headers['set-cookie']
        assert 'HttpOnly' in cookie and 'Secure' in cookie and 'SameSite=strict' in cookie
        assert hosted[1] not in cookie and 'Domain=' not in cookie
        assert client.get('/api/dashboard').status_code==200
        assert client.get('/').status_code==200
        assert client.post('/auth/logout',headers={'Origin':'https://testserver'}).status_code==200
        assert client.get('/api/dashboard').status_code==401


def test_browser_sessions_reject_tampering_expiry_and_cross_site_writes(hosted,monkeypatch):
    with TestClient(app,base_url='https://testserver') as client:
        payload={'username':hosted[0],'password':hosted[1]}
        assert client.post('/auth/login',json=payload,headers={'Origin':'https://evil.example'}).status_code==403
        assert client.post('/auth/login',json=payload).status_code==200
        assert client.post('/api/authority/cases',json={},headers={'Origin':'https://evil.example'}).status_code==403
        token=client.cookies.get(access.cookie_name())
        assert access.valid_session(token)
        assert not access.valid_session(token+'tampered')
        now=access.time.time();monkeypatch.setattr(access.time,'time',lambda:now+access.SESSION_SECONDS+5)
        assert not access.valid_session(token)
        assert client.get('/api/dashboard').status_code==401


def test_failed_signin_rate_limit_and_request_bounds(hosted):
    with TestClient(app,base_url='https://testserver') as client:
        assert client.post('/auth/login',content='x'*5000,headers={'Content-Type':'application/json'}).status_code==413
        assert client.post('/auth/login',data={'username':'management','password':'invalid'}).status_code==415
        for _ in range(8):
            assert client.post('/auth/login',json={'username':'management','password':'invalid'}).status_code==401
        assert client.post('/auth/login',json={'username':'management','password':'invalid'}).status_code==429
