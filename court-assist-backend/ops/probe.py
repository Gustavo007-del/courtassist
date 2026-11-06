"""Run inside a private API container. Output contains status only."""

import json
import sys

from sqlalchemy import text

from app.api.v1.rate_limit import redis_client
from app.core.config import get_settings
from app.database.session import SessionLocal
from app.services.document_storage import client


def database():
    with SessionLocal() as session:
        session.execute(text("SELECT 1"))


def broker():
    redis = redis_client(get_settings().redis_url)
    redis.ping()
    return {queue: redis.llen(queue) for queue in
            ("court-assist-ocr", "court-assist-notifications", "court-assist-ai")}


def storage():
    client().head_bucket(Bucket=get_settings().document_s3_bucket)


def main():
    result = {}
    for name, check in (("database", database), ("redis", broker), ("storage", storage)):
        try:
            detail = check()
            result[name] = {"status": "ok", **({"queue_depth": detail} if detail is not None else {})}
        except Exception:
            result[name] = {"status": "unavailable"}
    print(json.dumps(result))
    return int(any(row["status"] != "ok" for row in result.values()))


if __name__ == "__main__":
    sys.exit(main())

