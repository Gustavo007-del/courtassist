from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
import logging

logger = logging.getLogger(__name__)


async def database_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.exception('Database operation failed')
    return JSONResponse(status_code=503, content={'detail': 'Service temporarily unavailable'})


async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception('Unhandled request error')
    return JSONResponse(status_code=500, content={'detail': 'Internal server error'})
