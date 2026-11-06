import os
from datetime import date, timedelta
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


def test_tasks_recurrence_reminders_appointments_and_ownership():
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
            one, two = auth('planning-one@example.com'), auth('planning-two@example.com')
            case = api.post('/api/v1/cases', headers=one, json={'case_title': 'Planning Case', 'case_number': 'OS 77/2026', 'case_category': 'Civil', 'filing_date': '2026-01-01'}).json()
            due = (date.today() + timedelta(days=2)).isoformat()
            invalid = api.post('/api/v1/tasks', headers=two, json={'title': 'Intrusion', 'case_id': case['id']})
            assert invalid.status_code == 404
            made = api.post('/api/v1/tasks', headers=one, json={'title': 'Prepare filing', 'description': 'Draft', 'due_date': due, 'due_time': '11:00:00', 'case_id': case['id'], 'reminder_minutes': 60, 'recurrence_kind': 'weekly'})
            assert made.status_code == 201, made.text
            task_id = made.json()['id']
            assert api.get(f'/api/v1/tasks/{task_id}', headers=two).status_code == 404
            assert api.get('/api/v1/tasks?q=Prepare&priority=Medium', headers=one).json()['total'] >= 1
            before = api.get('/api/v1/tasks', headers=one).json()['total']
            assert api.get('/api/v1/tasks', headers=one).json()['total'] == before
            reminder = api.get(f'/api/v1/tasks/{task_id}/reminders', headers=one).json()
            assert len(reminder) == 1 and reminder[0]['status'] == 'pending'
            assert api.post(f'/api/v1/tasks/{task_id}/complete', headers=one).json()['status'] == 'Completed'
            assert api.get(f'/api/v1/tasks/{task_id}/reminders', headers=one).json()[0]['status'] == 'cancelled'
            assert api.post(f'/api/v1/tasks/{task_id}/reopen', headers=one).json()['status'] == 'Pending'
            assert api.patch(f'/api/v1/tasks/{task_id}', headers=one, json={'priority': 'Urgent'}).json()['priority'] == 'Urgent'
            assert api.get('/api/v1/tasks?priority=Urgent', headers=one).json()['total'] == 1
            assert api.get('/api/v1/dashboard/overview', headers=one).json()['summary']['pending_tasks'] >= 1
            past = api.post('/api/v1/tasks', headers=one, json={'title': 'Overdue task', 'due_date': '2020-01-01'})
            assert past.status_code == 201
            assert any(item['title'] == 'Overdue task' for item in api.get('/api/v1/tasks/overdue', headers=one).json()['items'])
            assert api.delete(f'/api/v1/tasks/{task_id}', headers=one).status_code == 204
            assert api.get(f'/api/v1/tasks/{task_id}', headers=one).status_code == 404
            assert api.post('/api/v1/tasks', headers=one, json={'title': 'Calendar deadline', 'due_date': due}).status_code == 201
            hearing = api.post('/api/v1/hearings', headers=one, json={'case_id': case['id'], 'hearing_date': due, 'hearing_time': '10:00:00', 'estimated_end_time': '12:00:00', 'hearing_type': 'Arguments', 'purpose': 'Arguments'}).json()
            appointment = {'title': 'Client consultation', 'appointment_date': due, 'start_time': '11:00:00', 'end_time': '11:30:00', 'case_id': case['id'], 'reminder_minutes': 30}
            conflicts = api.post('/api/v1/appointments/check-conflicts', headers=one, json=appointment)
            assert conflicts.status_code == 200 and conflicts.json()[0]['kind'] == 'hearing'
            created = api.post('/api/v1/appointments', headers=one, json=appointment)
            assert created.status_code == 201, created.text
            appointment_id = created.json()['id']
            assert api.get(f'/api/v1/appointments/{appointment_id}', headers=two).status_code == 404
            assert api.get(f'/api/v1/appointments/{appointment_id}/reminders', headers=one).json()[0]['status'] == 'pending'
            changed = api.patch(f'/api/v1/appointments/{appointment_id}', headers=one, json={'start_time': '12:00:00', 'end_time': '13:00:00'})
            assert changed.status_code == 200
            assert api.get(f'/api/v1/appointments/{appointment_id}/reminders', headers=one).json()[0]['status'] == 'pending'
            assert api.post(f'/api/v1/appointments/{appointment_id}/cancel', headers=one).json()['status'] == 'Cancelled'
            assert api.get(f'/api/v1/appointments/{appointment_id}/reminders', headers=one).json()[0]['status'] == 'cancelled'
            agenda = api.get(f'/api/v1/calendar/agenda?from_date={due}&to_date={due}', headers=one).json()
            assert {'hearing', 'task', 'appointment'} <= {row['kind'] for row in agenda}
            assert api.get(f'/api/v1/calendar/agenda?from_date={due}&to_date={due}', headers=two).json() == []
    finally:
        app.dependency_overrides.clear(); engine.dispose()
