from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.core.config import get_settings

settings = get_settings()
pool = {}
if settings.database_url.startswith('postgresql'):
    pool = {'pool_size': 5, 'max_overflow': 3, 'pool_timeout': 5, 'pool_recycle': 900,
            'connect_args': {'connect_timeout': 5, 'options': '-c statement_timeout=15000 -c idle_in_transaction_session_timeout=90000'}}
engine = create_engine(settings.database_url, pool_pre_ping=True, hide_parameters=True, **pool)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
