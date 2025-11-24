import os
from dataclasses import dataclass


@dataclass
class Settings:
    api_base: str = os.environ.get("CHATBOT_API_BASE", "http://localhost:5001/api").rstrip("/")
    openai_api_key: str | None = os.environ.get("OPENAI_API_KEY")
    openai_model: str = os.environ.get("CHATBOT_MODEL", "gpt-4o-mini")


settings = Settings()
