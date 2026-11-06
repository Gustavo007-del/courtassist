"""Backend-only adapters. Only deployment configuration determines network destinations."""

import hashlib
import json
import math
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from app.core.config import get_settings


class AIError(Exception):
    def __init__(self, code, retryable=False):
        super().__init__(code)
        self.code = code
        self.retryable = retryable


@dataclass
class Usage:
    input_tokens: int | None = None
    output_tokens: int | None = None


def token_count(value):
    return value if type(value) is int and 0 <= value <= 100_000_000 else None


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def check_url(value, external):
    try:
        url = urlsplit(value)
        schemes = ("https",) if external else ("http", "https")
        return bool(url.scheme in schemes and url.hostname and not (url.username or url.password or url.query or url.fragment))
    except ValueError:
        return False


class Provider:
    def __init__(self, settings):
        self.settings = settings
        self.name = settings.ai_provider
        self.model = settings.ai_model
        self.base = settings.ai_base_url.rstrip("/")
        self.embedding_base = settings.ai_embedding_url.rstrip("/") or self.base
        self.external = settings.ai_external
        self.fingerprint = hashlib.sha256(json.dumps([
            self.name, self.model, self.base, self.embedding_base, settings.ai_embedding_model,
            self.external, settings.ai_provider_policy,
        ]).encode()).hexdigest()

    def post(self, base, path, body):
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        key = self.settings.ai_api_key.get_secret_value()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        request = Request(base + path, json.dumps(body, ensure_ascii=False).encode(), headers)
        try:
            opener = build_opener(ProxyHandler({}), NoRedirect())
            with opener.open(request, timeout=self.settings.ai_timeout_seconds) as response:
                raw = response.read(4_000_001)
        except HTTPError as error:
            status = error.code
            error.close()
            raise AIError("provider_busy" if status in (429, 503) else "provider_rejected", status in (429, 503)) from None
        except (TimeoutError, URLError, OSError):
            raise AIError("provider_unreachable") from None
        if len(raw) > 4_000_000:
            raise AIError("invalid_provider_response")
        try:
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError()
            return payload
        except (ValueError, UnicodeError):
            raise AIError("invalid_provider_response") from None


class Ollama(Provider):
    def generate(self, messages, schema):
        body = self.post(self.base, "/api/chat", {
            "model": self.model, "messages": messages, "stream": False,
            "format": schema, "options": {"temperature": 0, "num_predict": 2400, "num_ctx": 16384},
        })
        if body.get("done") is not True or body.get("done_reason") == "length":
            raise AIError("incomplete_provider_response")
        message = body.get("message")
        if not isinstance(message, dict):
            raise AIError("invalid_provider_response")
        return message.get("content"), Usage(
            token_count(body.get("prompt_eval_count")), token_count(body.get("eval_count")),
        )

    def embed(self, texts):
        body = self.post(self.embedding_base, "/api/embed", {
            "model": self.settings.ai_embedding_model, "input": texts, "truncate": False,
        })
        return vectors(body.get("embeddings"), len(texts)), Usage(token_count(body.get("prompt_eval_count")))


class LlamaCpp(Provider):
    def generate(self, messages, schema):
        body = self.post(self.base, "/v1/chat/completions", {
            "model": self.model, "messages": messages, "stream": False, "temperature": 0,
            "max_tokens": 2400, "response_format": {"type": "json_object", "schema": schema},
        })
        choices = body.get("choices", [])
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise AIError("invalid_provider_response")
        if choices[0].get("finish_reason") != "stop":
            raise AIError("incomplete_provider_response")
        usage = body.get("usage") or {}
        message = choices[0].get("message")
        if not isinstance(message, dict) or not isinstance(usage, dict):
            raise AIError("invalid_provider_response")
        return message.get("content"), Usage(
            token_count(usage.get("prompt_tokens")), token_count(usage.get("completion_tokens")),
        )

    def embed(self, texts):
        body = self.post(self.embedding_base, "/v1/embeddings", {
            "model": self.settings.ai_embedding_model, "input": texts, "encoding_format": "float",
        })
        rows = body.get("data", [])
        if not isinstance(rows, list) or any(not isinstance(row, dict) or type(row.get("index")) is not int for row in rows):
            raise AIError("invalid_embeddings")
        rows.sort(key=lambda row: row["index"])
        if [row["index"] for row in rows] != list(range(len(texts))):
            raise AIError("invalid_embeddings")
        usage = body.get("usage") or {}
        if not isinstance(usage, dict):
            raise AIError("invalid_provider_response")
        return vectors([row.get("embedding") for row in rows], len(texts)), Usage(token_count(usage.get("prompt_tokens")))


def vectors(values, count):
    if not isinstance(values, list) or len(values) != count:
        raise AIError("invalid_embeddings")
    size = len(values[0]) if values and isinstance(values[0], list) else 0
    if not 1 <= size <= 4096:
        raise AIError("invalid_embeddings")
    normalized = []
    for row in values:
        if not isinstance(row, list) or len(row) != size or any(
            type(value) not in (float, int) or abs(value) > 1e10 or not math.isfinite(value) for value in row
        ):
            raise AIError("invalid_embeddings")
        norm = math.hypot(*row)
        if not norm:
            raise AIError("invalid_embeddings")
        normalized.append([value / norm for value in row])
    return normalized


def configured_provider():
    settings = get_settings()
    adapter = {"ollama": Ollama, "llama_cpp": LlamaCpp}.get(settings.ai_provider)
    if not settings.ai_enabled or not adapter or not 0 < len(settings.ai_model) <= 160:
        return None
    if not check_url(settings.ai_base_url, settings.ai_external):
        return None
    if settings.ai_embedding_url and not check_url(settings.ai_embedding_url, settings.ai_external):
        return None
    if settings.ai_external and (not settings.ai_external_no_training_verified or not settings.ai_provider_policy.strip()):
        return None
    return adapter(settings)

