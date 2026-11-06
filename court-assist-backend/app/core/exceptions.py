from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
import logging

logger = logging.getLogger(__name__)


async def database_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.error('database_operation_failed', extra={'request_id': request.state.request_id, 'error_class': type(exc).__name__})
    return JSONResponse(status_code=503, content={'detail': 'Service temporarily unavailable'})


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [{"loc": error["loc"], "type": error["type"], "msg": "Invalid input"} for error in exc.errors()]
    return JSONResponse(status_code=422, content={'detail': errors})
