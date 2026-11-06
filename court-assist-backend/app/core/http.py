"""Bounded request bodies and content-free operational telemetry."""

import logging
import time
from uuid import uuid4

import anyio
from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse

logger = logging.getLogger("courtassist.http")


class SafeHTTP:
    def __init__(self, app, *, limit: int, timeout: int, hardened: bool):
        self.app, self.limit, self.timeout, self.hardened = app, limit, timeout, hardened

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request_id = uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        start = time.perf_counter()
        status = 500
        started = False

        async def send_safe(message):
            nonlocal status, started
            if message["type"] == "http.response.start":
                started, status = True, message["status"]
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "no-referrer"
                if scope["path"].startswith("/api/"):
                    headers["Cache-Control"] = "no-store"
                if self.hardened:
                    headers["Strict-Transport-Security"] = "max-age=31536000"
            await send(message)

        async def reject(code, detail):
            await JSONResponse({"detail": detail}, status_code=code)(scope, receive, send_safe)

        try:
            if scope["method"] in ("POST", "PATCH", "PUT", "DELETE"):
                lengths = Headers(scope=scope).getlist("content-length")
                if len(lengths) > 1 or (lengths and not lengths[0].isascii()) or (lengths and not lengths[0].isdecimal()):
                    return await reject(400, "Invalid Content-Length")
                if lengths and (len(lengths[0]) > 10 or int(lengths[0]) > self.limit):
                    return await reject(413, "Request body is too large")
                body = bytearray()
                try:
                    with anyio.fail_after(self.timeout):
                        while True:
                            message = await receive()
                            if message["type"] == "http.disconnect":
                                status = 499
                                return
                            chunk = message.get("body", b"")
                            if len(body) + len(chunk) > self.limit:
                                return await reject(413, "Request body is too large")
                            body.extend(chunk)
                            if not message.get("more_body"):
                                break
                except TimeoutError:
                    return await reject(408, "Request body timed out")
                if lengths and len(body) != int(lengths[0]):
                    return await reject(400, "Invalid Content-Length")

                delivered = False

                async def receive_bounded():
                    nonlocal delivered
                    if delivered:
                        return await receive()
                    delivered = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}

                await self.app(scope, receive_bounded, send_safe)
            else:
                await self.app(scope, receive, send_safe)
        except Exception as exc:
            logger.error("request_failed", extra={"request_id": request_id, "error_class": type(exc).__name__})
            if not started:
                await reject(500, "Internal server error")
            else:
                raise RuntimeError('Response stream failed') from None
        finally:
            route = getattr(scope.get("route"), "path", None)
            logger.info("request_finished", extra={
                "request_id": request_id, "method": scope["method"],
                "route": route or "unmatched", "status": status,
                "duration_ms": round((time.perf_counter() - start) * 1000, 2),
            })

