import base64
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

os.environ['DATABASE_URL'] = 'sqlite+pysqlite:///:memory:'
os.environ['JWT_SECRET_KEY'] = 'test-only-secret-key-with-at-least-32-chars'
os.environ['REDIS_URL'] = ''

from app.core.config import get_settings
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app import models  # noqa: F401

ONE_PIXEL_PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/lH8AAAAASUVORK5CYII=')


def test_workspace_profile_dashboard_activity_and_private_image(tmp_path):
    engine = create_engine('sqlite+pysqlite:///:memory:', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    def session_override():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[get_db] = session_override
    settings = get_settings()
    original_storage = settings.private_storage_dir
    settings.private_storage_dir = str(tmp_path)
    try:
        with TestClient(app) as client:
            def register(email):
                assert client.post('/api/v1/auth/register', json={
                    'full_name': 'Advocate Example', 'email': email,
                    'password': 'StrongPassword123', 'confirm_password': 'StrongPassword123'}).status_code == 201
                tokens = client.post('/api/v1/auth/login', json={'identifier': email, 'password': 'StrongPassword123'}).json()
                return {'Authorization': f"Bearer {tokens['access_token']}"}
            first = register('first@example.com')
            second = register('second@example.com')
            initial = client.get('/api/v1/dashboard/overview', headers=first)
            assert initial.status_code == 200
            assert initial.json()['summary']['active_cases'] == 0
            assert initial.json()['module_availability']['cases'] is True
            assert initial.json()['recent_activities'] == []
            changed = client.patch('/api/v1/users/me', headers=first, json={
                'full_name': 'Advocate First', 'city': 'Kochi', 'pin_code': '682001',
                'enrollment_number': 'K/123/2020', 'areas_of_practice': ['Civil', 'Family']})
            assert changed.status_code == 200
            assert changed.json()['city'] == 'Kochi'
            assert changed.json()['areas_of_practice'] == ['Civil', 'Family']
            assert client.get('/api/v1/users/me', headers=second).json()['city'] is None
            assert client.patch('/api/v1/users/me', headers=first, json={'pin_code': '123'}).status_code == 422
            pref = client.patch('/api/v1/users/me/preferences', headers=first, json={
                'timezone': 'Asia/Kolkata', 'theme': 'dark', 'daily_summary': True})
            assert pref.status_code == 200
            assert pref.json()['theme'] == 'dark'
            assert client.patch('/api/v1/users/me/preferences', headers=first, json={'timezone': 'Invalid/Nowhere'}).status_code == 422
            own = client.get('/api/v1/activities?activity_type=profile_updated&limit=1', headers=first).json()
            assert own['total'] == 1 and len(own['items']) == 1
            assert 'full_name' in own['items'][0]['details']['fields']
            assert client.get('/api/v1/activities', headers=second).json()['total'] == 0
            assert client.get('/api/v1/activities?limit=1&offset=1', headers=first).json()['items'][0]['activity_type'] == 'profile_updated'
            dashboard = client.get('/api/v1/dashboard/overview', headers=first).json()
            assert dashboard['profile']['full_name'] == 'Advocate First'
            assert len(dashboard['recent_activities']) == 2
            assert dashboard['upcoming_activities'] == []
            request = client.post('/api/v1/users/me/profile-image/upload-url', headers=first,
                                  json={'content_type': 'image/png'})
            assert request.status_code == 200
            upload = request.json()
            assert client.put(upload['upload_url'], headers={**second, 'Content-Type': 'image/png'}, content=ONE_PIXEL_PNG).status_code == 404
            assert client.put(upload['upload_url'], headers={**first, 'Content-Type': 'image/png'}, content=ONE_PIXEL_PNG).status_code == 204
            assert client.post('/api/v1/users/me/profile-image/confirm', headers=first,
                               json={'upload_id': upload['upload_id']}).status_code == 200
            assert client.get('/api/v1/users/me/profile-image', headers=first).content.startswith(b'\x89PNG\r\n\x1a\n')
            assert client.get('/api/v1/users/me/profile-image', headers=second).status_code == 404
            assert client.post('/api/v1/users/me/profile-image/confirm', headers=first,
                               json={'upload_id': upload['upload_id']}).status_code == 404
            signature = client.post('/api/v1/users/me/signature-image/upload-url', headers=first,
                                    json={'content_type': 'image/png'}).json()
            assert client.put(signature['upload_url'], headers={**first, 'Content-Type': 'image/png'}, content=ONE_PIXEL_PNG).status_code == 204
            assert client.post('/api/v1/users/me/signature-image/confirm', headers=first,
                               json={'upload_id': signature['upload_id']}).status_code == 200
            assert client.get('/api/v1/users/me/signature-image', headers=first).content.startswith(b'\x89PNG\r\n\x1a\n')
            assert client.get('/api/v1/users/me/signature-image', headers=second).status_code == 404
            assert client.get('/api/v1/auth/sessions', headers=first).json()['active_sessions'] == 1
            changed_password = client.post('/api/v1/auth/change-password', headers=first, json={
                'current_password': 'StrongPassword123', 'new_password': 'EvenStrongerPassword456',
                'confirm_password': 'EvenStrongerPassword456'})
            assert changed_password.status_code == 200
            assert client.get('/api/v1/auth/sessions', headers=first).status_code == 401
            assert client.post('/api/v1/auth/login', json={'identifier': 'first@example.com', 'password': 'StrongPassword123'}).status_code == 401
            assert client.post('/api/v1/auth/login', json={'identifier': 'first@example.com', 'password': 'EvenStrongerPassword456'}).status_code == 200
    finally:
        settings.private_storage_dir = original_storage
        app.dependency_overrides.clear()
        engine.dispose()
