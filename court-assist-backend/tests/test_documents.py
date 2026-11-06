import os
import uuid
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
from app.api.v1 import documents
from app.models.document import DocumentOCR
from app.services import document_storage
from app.services.document_ocr import suggestions
from fastapi import HTTPException
import hashlib
import io


def test_upload_verification_checks_magic_size_and_checksum(monkeypatch):
    class FakeS3:
        payload = b'%PDF-1.7\nsmall private document'
        def head_object(self, **kwargs): return {'ContentLength': len(self.payload)}
        def get_object(self, **kwargs): return {'Body': io.BytesIO(self.payload)}
    fake = FakeS3()
    monkeypatch.setattr(document_storage, 'client', lambda: fake)
    checksum = hashlib.sha256(fake.payload).hexdigest()
    assert document_storage.verify_object('staging', 'application/pdf', len(fake.payload), checksum) == checksum
    try: document_storage.verify_object('staging', 'application/pdf', len(fake.payload) + 1, None)
    except HTTPException as error: assert error.status_code == 422
    else: assert False, 'Size mismatch must fail'
    fake.payload = b'not a pdf'
    try: document_storage.verify_object('staging', 'application/pdf', len(fake.payload), None)
    except HTTPException as error: assert error.status_code == 422
    else: assert False, 'Magic mismatch must fail'


def test_finalize_upload_verifies_immutable_copy(monkeypatch):
    payload = b'%PDF-1.7\nprivate'
    class FakeS3:
        objects = {'documents/staging/key': payload}
        def copy_object(self, Bucket, Key, CopySource): self.objects[Key] = self.objects[CopySource['Key']]
        def delete_object(self, Bucket, Key): self.objects.pop(Key, None)
        def head_object(self, Bucket, Key): return {'ContentLength': len(self.objects[Key])}
        def get_object(self, Bucket, Key): return {'Body': io.BytesIO(self.objects[Key])}
    fake = FakeS3()
    monkeypatch.setattr(document_storage, 'client', lambda: fake)
    document_storage.finalize_object('documents/staging/key', 'documents/stored/key', 'application/pdf', len(payload), hashlib.sha256(payload).hexdigest())
    assert 'documents/staging/key' not in fake.objects
    assert fake.objects['documents/stored/key'] == payload


def test_extraction_suggestions_keep_source_and_page():
    text = 'In the District Court of Ernakulam\nOS 55/2026\nPetitioner: A. Person\nFiling Date: 01/11/2026'
    result = suggestions([{'page_number': 3, 'extracted_text': text}])
    fields = {item['field'] for item in result}
    assert {'court_name', 'case_number', 'petitioner', 'filing_date'} <= fields
    assert all(item['page_number'] == 3 and item['source_text'] in text for item in result)


def test_private_document_upload_version_and_search(monkeypatch):
    engine = create_engine('sqlite+pysqlite:///:memory:', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    def override():
        with Session(engine) as session: yield session
    app.dependency_overrides[get_db] = override
    monkeypatch.setattr(documents, 'presigned_put', lambda key, mime: 'https://private.example.invalid/put')
    monkeypatch.setattr(documents, 'presigned_get', lambda key, name: 'https://private.example.invalid/get')
    monkeypatch.setattr(documents, 'verify_object', lambda key, mime, size, checksum: 'a' * 64)
    finalized = []
    monkeypatch.setattr(documents, 'finalize_object', lambda staging, final, mime, size, checksum: finalized.append((staging, final)))
    try:
        with TestClient(app) as api:
            def auth(email):
                assert api.post('/api/v1/auth/register', json={'full_name': 'Advocate User', 'email': email, 'password': 'StrongPassword123', 'confirm_password': 'StrongPassword123'}).status_code == 201
                token = api.post('/api/v1/auth/login', json={'identifier': email, 'password': 'StrongPassword123'}).json()['access_token']
                return {'Authorization': f'Bearer {token}'}
            one, two = auth('vault-one@example.com'), auth('vault-two@example.com')
            case = api.post('/api/v1/cases', headers=one, json={'case_title': 'Private Matter', 'case_number': 'OS 55/2026', 'case_category': 'Civil', 'filing_date': '2026-01-01'}).json()
            body = {'document_name': 'Private petition', 'original_filename': 'petition.pdf', 'mime_type': 'application/pdf', 'file_size': 100, 'document_category': 'Petition', 'case_id': case['id']}
            assert api.post('/api/v1/documents', headers=two, json=body).status_code == 404
            assert api.post('/api/v1/documents', headers=one, json={**body, 'mime_type': 'image/png'}).status_code == 422
            created = api.post('/api/v1/documents', headers=one, json=body)
            assert created.status_code == 201, created.text
            doc_id = created.json()['id']
            assert created.json()['storage_status'] == 'upload_pending'
            assert api.get(f'/api/v1/documents/{doc_id}', headers=two).status_code == 404
            assert api.get(f'/api/v1/documents/{doc_id}/download-url', headers=one).status_code == 409
            signed = api.post('/api/v1/documents/upload-url', headers=one, json={'document_id': doc_id}).json()
            assert signed['url'].startswith('https://')
            assert api.post('/api/v1/documents/confirm-upload', headers=two, json={'document_id': doc_id, 'version_id': signed['version_id']}).status_code == 404
            confirmed = api.post('/api/v1/documents/confirm-upload', headers=one, json={'document_id': doc_id, 'version_id': signed['version_id']})
            assert confirmed.status_code == 200, confirmed.text
            assert confirmed.json()['storage_status'] == 'cloud_stored'
            assert finalized[0][0] != finalized[0][1]
            assert api.get(f'/api/v1/documents/{doc_id}/download-url', headers=one).status_code == 200
            assert api.get(f'/api/v1/documents/{doc_id}/download-url', headers=two).status_code == 404
            revision = api.post(f'/api/v1/documents/{doc_id}/versions', headers=one, json={'original_filename': 'revised.pdf', 'file_size': 101, 'change_description': 'Revised filing'})
            assert revision.status_code == 201, revision.text
            version_id = revision.json()['id']
            assert api.post('/api/v1/documents/upload-url', headers=one, json={'document_id': doc_id, 'version_id': version_id}).status_code == 200
            assert api.get(f'/api/v1/documents/{doc_id}', headers=one).json()['current_version_id'] == signed['version_id']
            assert api.post('/api/v1/documents/confirm-upload', headers=one, json={'document_id': doc_id, 'version_id': version_id}).status_code == 200
            assert len(api.get(f'/api/v1/documents/{doc_id}/versions', headers=one).json()) == 2
            assert api.get(f'/api/v1/documents/{doc_id}/versions/{signed["version_id"]}/download-url', headers=one).status_code == 200
            with Session(engine) as session:
                current_id = api.get(f'/api/v1/documents/{doc_id}', headers=one).json()['current_version_id']
                session.add(DocumentOCR(document_id=uuid.UUID(doc_id), user_id=uuid.UUID(created.json()['user_id']),
                                        document_version_id=uuid.UUID(current_id), processing_status='completed',
                                        processing_provider='pypdf', extracted_text='CNR ABCD123456789012 on petition',
                                        page_results=[{'page_number': 2, 'extracted_text': 'CNR ABCD123456789012 on petition'}]))
                session.commit()
            assert api.get(f'/api/v1/documents/{doc_id}/ocr', headers=two).status_code == 404
            assert api.get(f'/api/v1/documents/{doc_id}/ocr', headers=one).json()['page_results'][0]['page_number'] == 2
            suggestion = api.get(f'/api/v1/documents/{doc_id}/extracted-metadata', headers=one).json()['suggestions'][0]
            review = {'reviewed': [{'field': suggestion['field'], 'source_value': suggestion['value'], 'status': 'accepted', 'value': suggestion['value']}]}
            assert api.post(f'/api/v1/documents/{doc_id}/extracted-metadata/confirm', headers=one, json=review).status_code == 200
            assert api.get(f'/api/v1/documents/{doc_id}', headers=one).json()['reviewed_metadata'] == review['reviewed']
            assert len(api.get('/api/v1/documents/search?q=Private', headers=one).json()['items']) == 1
            assert len(api.get('/api/v1/documents/search?q=OS%2055%2F2026', headers=one).json()['items']) == 1
            found = api.get('/api/v1/documents/search?q=ABCD123456789012', headers=one).json()['items'][0]
            assert found['page_number'] == 2
            assert api.get('/api/v1/documents/search?q=Private', headers=two).json()['items'] == []
            assert api.get(f'/api/v1/cases/{case["id"]}/documents', headers=two).status_code == 404
            assert api.delete(f'/api/v1/documents/{doc_id}', headers=one).status_code == 204
            assert api.get('/api/v1/documents?archived=true', headers=one).json()[0]['storage_status'] == 'archived'
    finally:
        app.dependency_overrides.clear(); engine.dispose()
