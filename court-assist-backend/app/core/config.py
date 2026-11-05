from functools import lru_cache
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    app_env: str = 'development'
    database_url: str
    jwt_secret_key: str = Field(min_length=32)
    jwt_algorithm: str = 'HS256'
    access_token_expire_minutes: int = Field(default=15, ge=1, le=60)
    refresh_token_expire_days: int = Field(default=30, ge=1, le=90)
    cors_origins: str = ''
    redis_url: str = ''
    rate_limit_per_minute: int = Field(default=10, ge=1)
    smtp_host: str = ''
    smtp_port: int = 587
    smtp_username: str = ''
    smtp_password: str = ''
    smtp_from: str = ''
    reset_url_base: str = ''
    private_storage_dir: str = './private_uploads'

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
    return Settings()
