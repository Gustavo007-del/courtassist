from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator
from app.schemas.user import UserOut


class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: str | None = None
    phone_number: str | None = None
    password: str = Field(min_length=12, max_length=128)
    confirm_password: str = Field(max_length=128)
    preferred_language: str = Field(default='en', pattern='^(en|ml)$')

    @field_validator('full_name')
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError('Full name is required')
        return value

    @model_validator(mode='after')
    def validate_registration(self):
        if not self.email and not self.phone_number:
            raise ValueError('Email or phone number is required')
        if self.password != self.confirm_password:
            raise ValueError('Passwords do not match')
        return self


class LoginIn(BaseModel):
    identifier: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=128)
    device_id: UUID | None = None
    installation_id: UUID | None = None


class ForgotPasswordIn(BaseModel):
    email: str = Field(max_length=320)


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=12, max_length=128)
    confirm_password: str = Field(max_length=128)

    @model_validator(mode='after')
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError('Passwords do not match')
        return self


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)
    confirm_password: str = Field(max_length=128)

    @model_validator(mode='after')
    def passwords_match(self):
        if self.new_password != self.confirm_password:
            raise ValueError('Passwords do not match')
        return self


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = 'bearer'
    access_expires_in: int
    refresh_expires_in: int
    user: UserOut


class MessageOut(BaseModel):
    detail: str


class SessionInfoOut(BaseModel):
    active_sessions: int
    last_login_at: datetime | None


class ActiveSessionOut(BaseModel):
    id: UUID
    refreshed_at: datetime
    expires_at: datetime
    current: bool
