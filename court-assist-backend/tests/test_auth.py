import os
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

os.environ['DATABASE_URL'] = 'sqlite+pysqlite:///:memory:'
os.environ['JWT_SECRET_KEY'] = 'test-only-secret-key-with-at-least-32-chars'
os.environ['REDIS_URL'] = ''
os.environ['SMTP_HOST'] = 'smtp.example.invalid'
os.environ['SMTP_FROM'] = 'noreply@example.invalid'
os.environ['RESET_URL_BASE'] = 'courtassist://reset-password'

from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.services import auth_service
from app import models  # noqa: F401

engine = create_engine('sqlite+pysqlite:///:memory:', connect_args={'check_same_thread': False}, poolclass=StaticPool)
Base.metadata.create_all(engine)


def test_auth_lifecycle(monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, 'smtp_host', 'smtp.example.invalid')
    monkeypatch.setattr(settings, 'smtp_from', 'noreply@example.invalid')
    monkeypatch.setattr(settings, 'reset_url_base', 'courtassist://reset-password')
    def session_override():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[get_db] = session_override
    delivered = []
    monkeypatch.setattr(auth_service, '_send_reset_email', lambda email, token: delivered.append((email, token)))
    with TestClient(app) as client:
        assert client.get('/api/v1/health').json()['status'] == 'ok'
        assert '/api/v1/auth/register' in client.get('/openapi.json').json()['paths']
        registration = {'full_name': 'Advocate Example', 'email': ' Advocate@Example.com ', 'password': 'StrongPassword123', 'confirm_password': 'StrongPassword123', 'preferred_language': 'ml'}
        assert client.post('/api/v1/auth/register', json=registration).status_code == 201
        assert client.post('/api/v1/auth/register', json=registration).status_code == 409
        login = client.post('/api/v1/auth/login', json={'identifier': 'advocate@example.com', 'password': 'StrongPassword123'})
        assert login.status_code == 200
        tokens = login.json()
        assert tokens['user']['email'] == 'advocate@example.com'
        headers = {'Authorization': f"Bearer {tokens['access_token']}"}
        assert client.get('/api/v1/users/me', headers=headers).status_code == 200
        assert client.get('/api/v1/users/me').status_code == 401
        updated = client.patch('/api/v1/users/me', headers=headers, json={'bar_council': 'Kerala'})
        assert updated.json()['bar_council'] == 'Kerala'
        rotated = client.post('/api/v1/auth/refresh', json={'refresh_token': tokens['refresh_token']})
        assert rotated.status_code == 200
        new_tokens = rotated.json()
        assert new_tokens['refresh_token'] != tokens['refresh_token']
        assert client.post('/api/v1/auth/refresh', json={'refresh_token': tokens['refresh_token']}).status_code == 401
        assert client.post('/api/v1/auth/refresh', json={'refresh_token': new_tokens['refresh_token']}).status_code == 401
        assert client.post('/api/v1/auth/forgot-password', json={'email': 'unknown@example.com'}).status_code == 200
        assert not delivered
        assert client.post('/api/v1/auth/forgot-password', json={'email': 'advocate@example.com'}).status_code == 200
        assert len(delivered) == 1
        reset = client.post('/api/v1/auth/reset-password', json={'token': delivered[0][1], 'password': 'NewStrongPassword456', 'confirm_password': 'NewStrongPassword456'})
        assert reset.status_code == 200
        assert client.post('/api/v1/auth/reset-password', json={'token': delivered[0][1], 'password': 'NewStrongPassword456', 'confirm_password': 'NewStrongPassword456'}).status_code == 400
        assert client.post('/api/v1/auth/login', json={'identifier': 'advocate@example.com', 'password': 'StrongPassword123'}).status_code == 401
        again = client.post('/api/v1/auth/login', json={'identifier': 'advocate@example.com', 'password': 'NewStrongPassword456'})
        assert again.status_code == 200
        assert client.post('/api/v1/auth/logout', headers={'Authorization': f"Bearer {again.json()['access_token']}"}, json={'refresh_token': again.json()['refresh_token']}).status_code == 200
        assert client.post('/api/v1/auth/refresh', json={'refresh_token': again.json()['refresh_token']}).status_code == 401
        third = client.post('/api/v1/auth/login', json={'identifier': 'advocate@example.com', 'password': 'NewStrongPassword456'}).json()
        fourth = client.post('/api/v1/auth/refresh', json={'refresh_token': third['refresh_token']}).json()
        assert client.post('/api/v1/auth/logout', headers={'Authorization': f"Bearer {third['access_token']}"}, json={'refresh_token': third['refresh_token']}).status_code == 200
        assert client.post('/api/v1/auth/refresh', json={'refresh_token': fourth['refresh_token']}).status_code == 401
    app.dependency_overrides.clear()
