from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError
from app.api.v1.router import router
from app.core.config import get_settings
from app.core.exceptions import database_exception_handler, unexpected_exception_handler
from app.core.logging import configure_logging

configure_logging()
settings = get_settings()
app = FastAPI(title='Court Assist API', version='0.1.0')
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=False,
                   allow_methods=['GET', 'POST', 'PATCH', 'PUT', 'DELETE'], allow_headers=['Authorization', 'Content-Type'])
app.add_exception_handler(SQLAlchemyError, database_exception_handler)
app.add_exception_handler(Exception, unexpected_exception_handler)
app.include_router(router)
