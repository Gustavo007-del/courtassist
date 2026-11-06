import os
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

def test_diary_crud_ownership_hearing_and_timeline():
    engine = create_engine('sqlite+pysqlite:///:memory:', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    def override():
        with Session(engine) as session: yield session
    app.dependency_overrides[get_db] = override
    try:
        with TestClient(app) as api:
            def auth(email):
                assert api.post('/api/v1/auth/register', json={'full_name': 'Advocate User', 'email': email, 'password': 'StrongPassword123', 'confirm_password': 'StrongPassword123'}).status_code == 201
                token = api.post('/api/v1/auth/login', json={'identifier': email, 'password': 'StrongPassword123'}).json()['access_token']
                return {'Authorization': f'Bearer {token}'}
            one, two = auth('diary-one@example.com'), auth('diary-two@example.com')
            case = api.post('/api/v1/cases', headers=one, json={'case_title': 'Diary Case', 'case_number': 'OS 11/2026', 'case_category': 'Civil', 'filing_date': '2026-01-01'}).json()
            other_case = api.post('/api/v1/cases', headers=one, json={'case_title': 'Other Case', 'case_number': 'OS 12/2026', 'case_category': 'Civil', 'filing_date': '2026-01-01'}).json()
            hearing = api.post('/api/v1/hearings', headers=one, json={'case_id': case['id'], 'hearing_date': '2026-12-10', 'hearing_type': 'Arguments', 'purpose': 'Arguments'}).json()
            body = {'case_id': case['id'], 'hearing_id': hearing['id'], 'entry_date': '2026-12-10', 'entry_type': 'Hearing', 'title': 'Private court note', 'content': 'Observed proceedings', 'request_id': 'diary-request-001'}
            assert api.post('/api/v1/diary', headers=two, json=body).status_code == 404
            assert api.post('/api/v1/diary', headers=one, json={**body, 'case_id': other_case['id']}).status_code == 422
            created = api.post('/api/v1/diary', headers=one, json=body)
            assert created.status_code == 201, created.text
            entry = created.json(); entry_id = entry['id']
            assert api.post('/api/v1/diary', headers=one, json=body).json()['id'] == entry_id
            assert api.get(f'/api/v1/diary/{entry_id}', headers=two).status_code == 404
            assert api.patch(f'/api/v1/diary/{entry_id}', headers=two, json={'title': 'Intrusion'}).status_code == 404
            assert api.get(f'/api/v1/cases/{case["id"]}/diary', headers=two).status_code == 404
            assert api.get(f'/api/v1/hearings/{hearing["id"]}/diary', headers=one).json()['total'] == 1
            assert api.get('/api/v1/diary?q=Observed&category=Hearing&important=false', headers=one).json()['total'] == 1
            assert api.get('/api/v1/diary?from_date=2026-12-11', headers=one).json()['total'] == 0
            assert api.get('/api/v1/diary?hearing_id=' + hearing['id'], headers=two).status_code == 404
            edited = api.patch(f'/api/v1/diary/{entry_id}', headers=one, json={'title': 'Updated private note', 'is_important': True}).json()
            assert edited['created_at'] == entry['created_at'] and edited['is_important']
            assert api.post(f'/api/v1/diary/{entry_id}/pin', headers=one).json()['is_pinned']
            assert api.get('/api/v1/diary?pinned=true', headers=one).json()['total'] == 1
            timeline = api.get(f'/api/v1/cases/{case["id"]}/timeline?category=diary', headers=one).json()
            assert timeline['total'] == 3
            assert {item['activity_type'] for item in timeline['items']} == {'diary_created', 'diary_updated'}
            assert api.get(f'/api/v1/cases/{case["id"]}/timeline?category=diary&from_date=2027-01-01', headers=one).json()['total'] == 0
            assert api.delete(f'/api/v1/diary/{entry_id}', headers=two).status_code == 404
            assert api.delete(f'/api/v1/diary/{entry_id}', headers=one).status_code == 204
            assert api.get(f'/api/v1/diary/{entry_id}', headers=one).status_code == 404
            timeline = api.get(f'/api/v1/cases/{case["id"]}/timeline?category=diary', headers=one).json()
            assert timeline['total'] == 4 and timeline['items'][0]['activity_type'] == 'diary_deleted'
    finally:
        app.dependency_overrides.clear(); engine.dispose()
