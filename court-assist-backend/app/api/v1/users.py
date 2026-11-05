from uuid import UUID
from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.api.v1.dependencies import current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.user import UserOut, UserUpdate
from app.schemas.preferences import PreferencesOut, PreferencesUpdate
from app.schemas.image import ImageConfirm, ImageUploadRequest, ImageUploadUrl
from app.services.user_service import update_profile, update_preferences
from app.services import image_service

router = APIRouter(prefix='/users', tags=['users'])


@router.get('/me', response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.patch('/me', response_model=UserOut)
def update_me(data: UserUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return update_profile(db, user, data)


@router.get('/me/preferences', response_model=PreferencesOut)
def my_preferences(user: User = Depends(current_user)):
    return user.preferences


@router.patch('/me/preferences', response_model=PreferencesOut)
def update_my_preferences(data: PreferencesUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return update_preferences(db, user, data)


@router.post('/me/profile-image/upload-url', response_model=ImageUploadUrl)
def profile_upload_url(data: ImageUploadRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return image_service.create_upload(db, user, 'profile', data.content_type)


@router.put('/me/profile-image/uploads/{upload_id}', status_code=204)
async def put_profile_image(upload_id: UUID, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    await image_service.receive_upload(db, user, 'profile', upload_id, request)


@router.post('/me/profile-image/confirm', response_model=UserOut)
def confirm_profile_image(data: ImageConfirm, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return image_service.confirm_upload(db, user, 'profile', data.upload_id)


@router.get('/me/profile-image')
def get_profile_image(user: User = Depends(current_user)):
    return FileResponse(image_service.image_file(user, 'profile'), headers={'Cache-Control': 'private, no-store'})


@router.post('/me/signature-image/upload-url', response_model=ImageUploadUrl)
def signature_upload_url(data: ImageUploadRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return image_service.create_upload(db, user, 'signature', data.content_type)


@router.put('/me/signature-image/uploads/{upload_id}', status_code=204)
async def put_signature_image(upload_id: UUID, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    await image_service.receive_upload(db, user, 'signature', upload_id, request)


@router.post('/me/signature-image/confirm', response_model=UserOut)
def confirm_signature_image(data: ImageConfirm, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return image_service.confirm_upload(db, user, 'signature', data.upload_id)


@router.get('/me/signature-image')
def get_signature_image(user: User = Depends(current_user)):
    return FileResponse(image_service.image_file(user, 'signature'), headers={'Cache-Control': 'private, no-store'})
