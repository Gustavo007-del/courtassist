from fastapi import Depends, HTTPException, Request
from redis import Redis
from redis.exceptions import RedisError
from app.core.config import get_settings


def auth_rate_limit(request: Request) -> None:
    settings = get_settings()
    if not settings.redis_url:
        return
    key = f'auth-limit:{request.url.path}:{request.client.host if request.client else "unknown"}'
    try:
        redis = Redis.from_url(settings.redis_url, socket_timeout=1)
        with redis.pipeline() as pipe:
            pipe.incr(key)
            pipe.expire(key, 60, nx=True)
            count, _ = pipe.execute()
        if count > settings.rate_limit_per_minute:
            raise HTTPException(429, 'Too many requests')
    except RedisError:
        # Availability of the API does not depend on an optional rate-limit store.
        pass
