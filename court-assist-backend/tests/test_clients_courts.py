import os
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

os.environ['DATABASE_URL'] = 'sqlite+pysqlite:///:memory:'
os.environ['JWT_SECRET_KEY'] = 'test-only-secret-key-with-at-least-32-chars'
os.environ['REDIS_URL'] = ''
from app import models  # noqa: F401
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.court import Court


def test_client_and_court_ownership_crud():
    engine = create_engine('sqlite+pysqlite:///:memory:', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    def override():
        with Session(engine) as session: yield session
    app.dependency_overrides[get_db] = override
    with Session(engine) as db:
        shared = Court(name='Verified Shared Court', court_type='Other', state='Kerala', district='Ernakulam', address='Verified address', source='https://example.gov.in/source', is_active=True)
        db.add(shared); db.commit(); shared_id = str(shared.id)
    try:
        with TestClient(app) as client:
            def auth(email):
                client.post('/api/v1/auth/register', json={'full_name': 'Advocate User', 'email': email, 'password': 'StrongPassword123', 'confirm_password': 'StrongPassword123'})
                token = client.post('/api/v1/auth/login', json={'identifier': email, 'password': 'StrongPassword123'}).json()['access_token']
                return {'Authorization': f'Bearer {token}'}
            one, two = auth('one@example.com'), auth('two@example.com')
            payload = {'client_type': 'individual', 'full_name': 'A Client', 'phone_number': '+44 20 7946 0958', 'email': 'client@example.com', 'address': '1 Street', 'city': 'London', 'district': 'Greater London', 'state': 'England', 'postal_code': 'SW1A 1AA'}
            created = client.post('/api/v1/clients', headers=one, json=payload)
            assert created.status_code == 201; client_id = created.json()['id']
            assert client.get('/api/v1/clients?q=7946&sort=alphabetical', headers=one).json()['total'] == 1
            assert client.get(f'/api/v1/clients/{client_id}', headers=two).status_code == 404
            assert client.patch(f'/api/v1/clients/{client_id}', headers=two, json={'city': 'Nope'}).status_code == 404
            assert client.patch(f'/api/v1/clients/{client_id}', headers=one, json={'phone_number': 'invalid'}).status_code == 422
            assert client.post(f'/api/v1/clients/{client_id}/archive', headers=one).status_code == 200
            assert client.get(f'/api/v1/clients/{client_id}', headers=one).status_code == 404
            assert client.get(f'/api/v1/clients/{client_id}?include_archived=true', headers=one).status_code == 200
            assert client.get('/api/v1/clients?archived=true', headers=one).json()['total'] == 1
            assert client.post(f'/api/v1/clients/{client_id}/restore', headers=one).status_code == 200
            note = client.post(f'/api/v1/clients/{client_id}/notes', headers=one, json={'title': 'Private', 'content': 'Confidential'}).json()
            assert client.get(f'/api/v1/clients/{client_id}/notes?q=Confid', headers=one).json()[0]['id'] == note['id']
            assert client.get(f'/api/v1/clients/{client_id}/notes', headers=two).status_code == 404
            assert client.patch(f"/api/v1/clients/{client_id}/notes/{note['id']}", headers=one, json={'title': 'Updated'}).status_code == 200
            interaction = client.post(f'/api/v1/clients/{client_id}/interactions', headers=one, json={'interaction_type': 'consultation', 'interaction_date': datetime.now(timezone.utc).isoformat(), 'subject': 'Advice', 'description': 'Consulted', 'follow_up_required': True, 'follow_up_date': '2026-12-01'}).json()
            assert client.get(f'/api/v1/clients/{client_id}/interactions', headers=one).json()[0]['id'] == interaction['id']
            assert client.delete(f"/api/v1/clients/{client_id}/interactions/{interaction['id']}", headers=two).status_code == 404
            assert client.delete(f"/api/v1/clients/{client_id}/interactions/{interaction['id']}", headers=one).status_code == 204
            assert client.delete(f"/api/v1/clients/{client_id}/notes/{note['id']}", headers=one).status_code == 204
            assert client.delete(f'/api/v1/clients/{client_id}', headers=one).status_code == 204
            assert client.get(f'/api/v1/clients/{client_id}?include_archived=true', headers=one).status_code == 404

            courts = client.get('/api/v1/courts?district=Ernakulam', headers=one).json()
            assert courts['total'] == 1 and courts['items'][0]['record_scope'] == 'shared'
            assert client.patch(f'/api/v1/courts/{shared_id}', headers=one, json={'name': 'Changed'}).status_code == 403
            custom = client.post('/api/v1/courts', headers=one, json={'name': 'My Private Court', 'court_type': 'Other', 'state': 'Kerala', 'district': 'Kollam', 'address': 'Private address', 'notes': 'Private note'}).json()
            custom_id = custom['id']; assert custom['record_scope'] == 'private' and custom['can_edit'] is True
            assert client.get(f'/api/v1/courts/{custom_id}', headers=two).status_code == 404
            assert client.delete(f'/api/v1/courts/{custom_id}/favorite', headers=two).status_code == 404
            assert client.patch(f'/api/v1/courts/{custom_id}', headers=one, json={'phone_number': 'invalid'}).status_code == 422
            extensible = client.post('/api/v1/courts', headers=one, json={'name': 'Private Community Forum', 'court_type': 'Community Forum', 'state': 'Kerala', 'district': 'Kollam', 'address': 'Private reference address'})
            assert extensible.status_code == 201
            assert client.post(f'/api/v1/courts/{shared_id}/favorite', headers=one).status_code == 200
            assert client.post(f'/api/v1/courts/{shared_id}/favorite', headers=one).status_code == 200
            assert client.get('/api/v1/courts/favorites', headers=one).json()['total'] == 1
            assert client.get('/api/v1/courts/favorites', headers=two).json()['total'] == 0
            assert client.delete(f'/api/v1/courts/{shared_id}/favorite', headers=two).status_code == 204
            assert client.delete(f'/api/v1/courts/{custom_id}', headers=two).status_code == 404
            assert client.delete(f'/api/v1/courts/{custom_id}', headers=one).status_code == 204
            assert client.get(f'/api/v1/courts/{custom_id}', headers=one).status_code == 404
    finally:
        app.dependency_overrides.clear(); engine.dispose()
