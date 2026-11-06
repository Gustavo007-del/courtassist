from functools import lru_cache

from fastapi import HTTPException, Request
from redis import Redis
from redis.exceptions import RedisError
from app.core.config import get_settings


@lru_cache(maxsize=4)
def redis_client(url: str) -> Redis:
    return Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1, max_connections=32)


def auth_rate_limit(request: Request) -> None:
    settings = get_settings()
    if not settings.redis_url:
        return
    key = f'auth-limit:{request.url.path}:{request.client.host if request.client else "unknown"}'
    try:
        with redis_client(settings.redis_url).pipeline() as pipe:
            pipe.incr(key)
            pipe.expire(key, 60, nx=True)
            count, _ = pipe.execute()
        if count > settings.rate_limit_per_minute:
            raise HTTPException(429, 'Too many requests', headers={'Retry-After': '60'})
    except RedisError:
        if settings.hardened:
            raise HTTPException(503, 'Authentication temporarily unavailable') from None
