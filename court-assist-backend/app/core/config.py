from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore', hide_input_in_errors=True)
    app_env: str = 'development'
    database_url: str
    jwt_secret_key: str = Field(min_length=32)
    jwt_algorithm: str = 'HS256'
    access_token_expire_minutes: int = Field(default=15, ge=1, le=60)
    refresh_token_expire_days: int = Field(default=30, ge=1, le=90)
    cors_origins: str = ''
    trusted_hosts: str = ''
    request_max_bytes: int = Field(default=8 * 1024 * 1024, ge=1024, le=32 * 1024 * 1024)
    request_body_timeout: int = Field(default=20, ge=1, le=120)
    redis_url: str = ''
    rate_limit_per_minute: int = Field(default=10, ge=1)
    smtp_host: str = ''
    smtp_port: int = 587
    smtp_username: str = ''
    smtp_password: str = ''
    smtp_from: str = ''
    reset_url_base: str = ''
    private_storage_dir: str = './private_uploads'
    document_s3_endpoint: str = ''
    document_s3_bucket: str = ''
    document_s3_region: str = 'auto'
    document_s3_access_key: str = ''
    document_s3_secret_key: str = ''
    document_max_bytes: int = Field(default=25 * 1024 * 1024, ge=1024)
    document_url_seconds: int = Field(default=300, ge=30, le=900)
    clamav_host: str = ''
    clamav_port: int = Field(default=3310, ge=1, le=65535)
    ocr_provider: str = 'disabled'
    fcm_enabled: bool = False
    fcm_credentials_file: str = ''
    fcm_project_id: str = ''
    notification_token_keys: str = ''
    notification_max_attempts: int = Field(default=5,ge=1,le=10)
    ai_enabled: bool = False
    ai_provider: str = 'ollama'
    ai_base_url: str = ''
    ai_model: str = ''
    ai_embedding_url: str = ''
    ai_embedding_model: str = ''
    ai_api_key: SecretStr = SecretStr('')
    ai_external: bool = True
    ai_external_no_training_verified: bool = False
    ai_provider_policy: str = ''
    ai_timeout_seconds: int = Field(default=40, ge=5, le=120)
    ai_requests_per_day: int = Field(default=20, ge=1, le=200)
    ai_requests_per_minute: int = Field(default=4, ge=1, le=20)
    ai_max_source_chars: int = Field(default=60000, ge=4000, le=120000)
    ai_input_cost_per_million: float | None = Field(default=None, ge=0)
    ai_output_cost_per_million: float | None = Field(default=None, ge=0)

    @property
    def hardened(self) -> bool:
        return self.app_env in ('staging', 'production')

    @property
    def trusted_host_list(self) -> list[str]:
        return [host.strip() for host in self.trusted_hosts.split(',') if host.strip()]

    @model_validator(mode='after')
    def validate_deployment(self):
        if self.app_env not in ('development', 'testing', 'staging', 'production'):
            raise ValueError('Invalid APP_ENV')
        if self.hardened:
            if not self.database_url.startswith(('postgresql://', 'postgresql+psycopg://')):
                raise ValueError('PostgreSQL is required for staging and production')
            if not self.redis_url.startswith(('redis://', 'rediss://')):
                raise ValueError('Redis is required for staging and production')
            if len(set(self.jwt_secret_key)) < 16 or any(word in self.jwt_secret_key.lower() for word in ('replace', 'change-me', 'development', 'test-only')):
                raise ValueError('Configure a randomly generated JWT secret')
            if not self.trusted_host_list or any('*' in host or '/' in host for host in self.trusted_host_list):
                raise ValueError('Configure explicit trusted hostnames')
            for origin in self.cors_origin_list:
                url = urlsplit(origin)
                if url.scheme != 'https' or not url.hostname or url.path or url.query or url.fragment or url.username:
                    raise ValueError('Production CORS origins must be HTTPS origins')
            if not all((self.document_s3_bucket, self.document_s3_access_key, self.document_s3_secret_key)):
                raise ValueError('Configure private document storage')
            if self.document_s3_endpoint and not self.document_s3_endpoint.startswith('https://'):
                raise ValueError('Configure an HTTPS object-storage endpoint')
            if self.reset_enabled and not self.reset_url_base.startswith('https://'):
                raise ValueError('Use an HTTPS password-reset URL')
            if self.fcm_enabled and not all((self.notification_token_keys, self.fcm_credentials_file, self.fcm_project_id)):
                raise ValueError('Configure FCM credentials and device token encryption')
        return self

    @field_validator('database_url')
    @classmethod
    def use_psycopg(cls, value: str) -> str:
        return 'postgresql+psycopg://' + value.removeprefix('postgresql://') if value.startswith('postgresql://') else value

    @field_validator('jwt_algorithm')
    @classmethod
    def validate_algorithm(cls, value: str) -> str:
        if value != 'HS256':
            raise ValueError('Only HS256 is supported')
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(',') if origin.strip()]

    @property
    def reset_enabled(self) -> bool:
        return all((self.smtp_host, self.smtp_from, self.reset_url_base))


@lru_cache
def get_settings() -> Settings:
    secrets = Path('/run/secrets')
    return Settings(_secrets_dir=secrets if secrets.is_dir() else None)
