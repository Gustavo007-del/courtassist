from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.exc import SQLAlchemyError
from app.api.v1.router import router
from app.core.config import get_settings
from app.core.exceptions import database_exception_handler, validation_exception_handler
from app.core.http import SafeHTTP
from app.core.logging import configure_logging
from app.services.ai_provider import configured_provider
from app.services.notification_events import install as install_notification_events

configure_logging()
install_notification_events()
settings = get_settings()
if settings.hardened and settings.ai_enabled and configured_provider() is None:
    raise RuntimeError('Configure the enabled AI provider and its processing policy')
app = FastAPI(title='Court Assist API', version='0.1.0',
              openapi_url=None if settings.hardened else '/openapi.json')
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=False,
                   allow_methods=['GET', 'POST', 'PATCH', 'PUT', 'DELETE'],
                   allow_headers=['Authorization', 'Content-Type', 'Idempotency-Key'], expose_headers=['X-Request-ID'])
if settings.trusted_host_list:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_host_list, www_redirect=False)
app.add_middleware(SafeHTTP, limit=settings.request_max_bytes, timeout=settings.request_body_timeout, hardened=settings.hardened)
app.add_exception_handler(SQLAlchemyError, database_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.include_router(router)
