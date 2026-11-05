import os
from datetime import date
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


def test_case_workflow_and_ownership():
    engine = create_engine('sqlite+pysqlite:///:memory:', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    def override():
        with Session(engine) as session: yield session
    app.dependency_overrides[get_db] = override
    try:
        with TestClient(app) as client:
            def auth(email):
                response = client.post('/api/v1/auth/register', json={'full_name': 'Advocate User', 'email': email, 'password': 'StrongPassword123', 'confirm_password': 'StrongPassword123'})
                assert response.status_code == 201
                token = client.post('/api/v1/auth/login', json={'identifier': email, 'password': 'StrongPassword123'}).json()['access_token']
                return {'Authorization': f'Bearer {token}'}
            one, two = auth('case-one@example.com'), auth('case-two@example.com')
            payload = {'client_type': 'individual', 'full_name': 'Primary Client', 'phone_number': '+44 20 7946 0958', 'address': '1 Street', 'city': 'London', 'district': 'London', 'state': 'England', 'postal_code': 'SW1A 1AA'}
            own_client = client.post('/api/v1/clients', headers=one, json=payload).json()['id']
            foreign_client = client.post('/api/v1/clients', headers=two, json={**payload, 'full_name': 'Foreign Client'}).json()['id']
            court = client.post('/api/v1/courts', headers=one, json={'name': 'Private Court', 'court_type': 'District Court', 'state': 'Kerala', 'district': 'Kollam', 'address': 'Private address'}).json()['id']
            base = {'case_title': 'Primary Client v Other', 'case_number': 'OS 1/2026', 'case_category': 'Civil', 'filing_date': '2026-01-05', 'description': 'Dispute', 'client_id': own_client, 'court_id': court}
            assert client.post('/api/v1/cases', headers=two, json={**base, 'client_id': foreign_client}).status_code == 404
            assert client.post('/api/v1/cases', headers=one, json={**base, 'client_id': foreign_client}).status_code == 404
            created = client.post('/api/v1/cases', headers=one, json={**base, 'parties': [{'client_id': own_client, 'party_name': 'Primary Client', 'party_role': 'Plaintiff'}, {'party_name': 'External Respondent', 'party_role': 'Defendant'}]})
            assert created.status_code == 201, created.text
            case_id = created.json()['id']
            assert client.post('/api/v1/cases', headers=one, json=base).status_code == 409
            assert client.get('/api/v1/cases?q=Primary&status=Pending&district=Kollam&priority=Normal&category=Civil', headers=one).json()['total'] == 1
            assert client.get('/api/v1/cases?client_id=' + own_client, headers=one).json()['total'] == 1
            assert client.get(f'/api/v1/cases/{case_id}', headers=two).status_code == 404
            assert client.get(f'/api/v1/cases/{case_id}/timeline', headers=two).status_code == 404
            parties = client.get(f'/api/v1/cases/{case_id}/parties', headers=one).json()
            assert len(parties) == 2 and any(p['client_id'] == own_client for p in parties)
            assert client.post(f'/api/v1/cases/{case_id}/parties', headers=one, json={'client_id': foreign_client, 'party_name': 'Foreign Client', 'party_role': 'Respondent'}).status_code == 404
            assert client.patch(f"/api/v1/cases/{case_id}/parties/{parties[0]['id']}", headers=two, json={'party_name': 'Wrong', 'party_role': 'Plaintiff'}).status_code == 404
            advocates = client.get(f'/api/v1/cases/{case_id}/advocates', headers=one).json()
            assert len(advocates) == 1 and advocates[0]['is_primary']
            opposing = client.post(f'/api/v1/cases/{case_id}/advocates', headers=one, json={'advocate_name': 'Opposing Counsel', 'representation_role': 'Opposing counsel'}).json()
            assert client.delete(f"/api/v1/cases/{case_id}/advocates/{advocates[0]['id']}", headers=one).status_code == 409
            assert client.delete(f"/api/v1/cases/{case_id}/advocates/{opposing['id']}", headers=one).status_code == 204
            status = client.post(f'/api/v1/cases/{case_id}/status', headers=one, json={'new_status': 'Active', 'reason': 'Registered', 'effective_date': str(date(2026, 1, 6))})
            assert status.status_code == 200, status.text
            assert status.json()['previous_status'] == 'Pending'
            assert len(client.get(f'/api/v1/cases/{case_id}/status-history', headers=one).json()) == 2
            assert client.patch(f'/api/v1/cases/{case_id}', headers=one, json={'priority': 'Urgent'}).status_code == 200
            timeline = client.get(f'/api/v1/cases/{case_id}/timeline?order=oldest', headers=one).json()
            assert timeline['total'] >= 5 and timeline['items'][0]['activity_type'] == 'case_created'
            assert client.post(f'/api/v1/cases/{case_id}/archive', headers=one).status_code == 200
            assert client.get('/api/v1/cases', headers=one).json()['total'] == 0
            assert client.get('/api/v1/cases?archived=true', headers=one).json()['total'] == 1
            assert client.get(f'/api/v1/cases/{case_id}', headers=one).status_code == 404
            assert client.get(f'/api/v1/cases/{case_id}?include_archived=true', headers=one).status_code == 200
            assert client.post(f'/api/v1/cases/{case_id}/restore', headers=one).status_code == 200
    finally:
        app.dependency_overrides.clear(); engine.dispose()
