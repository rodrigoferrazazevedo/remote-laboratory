import os
from dataclasses import dataclass


def _env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(f"Variável de ambiente {name} não definida e não há padrão.")
    return value


@dataclass
class Settings:
    api_base: str = os.environ.get("CHATBOT_API_BASE", "http://localhost:5000/api").rstrip("/")
    openai_api_key: str = _env("OPENAI_API_KEY")
    openai_model: str = os.environ.get("CHATBOT_MODEL", "gpt-4o-mini")


settings = Settings()
