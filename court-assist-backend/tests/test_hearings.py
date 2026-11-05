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

def test_hearing_history_conflicts_reminders_and_ownership():
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
            one, two = auth('hearing-one@example.com'), auth('hearing-two@example.com')
            case = api.post('/api/v1/cases', headers=one, json={'case_title': 'A v B', 'case_number': 'OS 10/2026', 'case_category': 'Civil', 'filing_date': '2026-01-01'}).json()
            case_id = case['id']
            body = {'case_id': case_id, 'hearing_date': '2026-12-10', 'hearing_type': 'Arguments', 'purpose': 'Arguments'}
            assert api.post('/api/v1/hearings', headers=two, json=body).status_code == 404
            date_only = api.post('/api/v1/hearings', headers=one, json=body)
            assert date_only.status_code == 201, date_only.text
            first = date_only.json(); assert first['hearing_time'] is None
            assert api.get(f"/api/v1/hearings/{first['id']}", headers=two).status_code == 404
            second = api.post('/api/v1/hearings', headers=one, json={**body, 'hearing_time': '10:00:00', 'estimated_end_time': '11:00:00'}).json()
            assert api.post('/api/v1/hearings/check-conflicts', headers=one, json={**body, 'hearing_time': '10:30:00', 'estimated_end_time': '11:30:00'}).json()[0]['kind'] in ('confirmed', 'unknown_time')
            warnings = api.post('/api/v1/hearings/check-conflicts', headers=one, json=body).json()
            assert all(item['kind'] == 'unknown_time' for item in warnings)
            daily_warnings = api.get('/api/v1/calendar/day/conflicts?day=2026-12-10', headers=one).json()
            assert daily_warnings and all(item['kind'] == 'unknown_time' for item in daily_warnings)
            reminder = api.post(f"/api/v1/hearings/{second['id']}/reminders", headers=one, json={'reminder_type': 'one_day'}).json()
            again = api.post(f"/api/v1/hearings/{second['id']}/reminders", headers=one, json={'reminder_type': 'one_day'}).json()
            assert reminder['id'] == again['id'] and reminder['status'] == 'pending'
            assert api.get(f"/api/v1/hearings/{second['id']}/reminders", headers=two).status_code == 404
            completed = api.post(f"/api/v1/hearings/{second['id']}/complete", headers=one, json={'proceedings_notes': 'Heard arguments', 'outcome': 'Adjourned by court', 'next_hearing_date': '2027-01-12'})
            assert completed.status_code == 200, completed.text
            assert completed.json()['follow_up_hearing_id']
            assert api.post(f"/api/v1/hearings/{second['id']}/complete", headers=one, json={'next_hearing_date': '2027-01-12'}).status_code == 409
            history = api.get(f'/api/v1/cases/{case_id}/hearings/history', headers=one).json()
            assert history['total'] == 3
            assert api.get('/api/v1/calendar/month?year=2027&month=1', headers=one).json()['total'] == 1
            assert api.patch(f"/api/v1/hearings/{second['id']}", headers=one, json={'hearing_date': '2026-12-11'}).status_code == 409
            assert api.get(f"/api/v1/hearings/{second['id']}/reminders", headers=one).json()[0]['status'] == 'cancelled'
    finally:
        app.dependency_overrides.clear(); engine.dispose()
