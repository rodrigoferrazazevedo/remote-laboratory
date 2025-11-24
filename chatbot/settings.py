import os
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit


def _normalize_api_base(raw: str | None) -> str:
    """
    Garante uso da porta 5001. Se apontar para localhost/127.x, força :5001 e caminho /api.
    """
    default = "http://localhost:5001/api"
    if not raw:
        return default
    raw = raw.strip()
    if "://" not in raw:
        raw = f"http://{raw}"
    parts = urlsplit(raw)
    host = parts.hostname or "localhost"
    scheme = parts.scheme or "http"
    path = parts.path or ""

    if host in ("localhost", "127.0.0.1"):
        netloc = f"{host}:5001"
        path = "/api"
    else:
        netloc = parts.netloc or host
        path = path if path else "/api"

    return urlunsplit((scheme, netloc, path.rstrip("/"), "", ""))


@dataclass
class Settings:
    api_base: str = _normalize_api_base(os.environ.get("CHATBOT_API_BASE"))
    openai_api_key: str | None = os.environ.get("OPENAI_API_KEY")
    openai_model: str = os.environ.get("CHATBOT_MODEL", "gpt-4o-mini")


settings = Settings()
