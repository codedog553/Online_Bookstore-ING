from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env"), env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="Bookstore Agent Server", alias="AGENTSERVER_APP_NAME")
    host: str = Field(default="0.0.0.0", alias="AGENTSERVER_HOST")
    port: int = Field(default=8011, alias="AGENTSERVER_PORT")
    cors_origins: List[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"], alias="AGENTSERVER_CORS_ORIGINS")
    enforce_https: bool = Field(default=False, alias="AGENTSERVER_ENFORCE_HTTPS")
    trusted_hosts: List[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1", "testserver"], alias="AGENTSERVER_TRUSTED_HOSTS")

    read_db_url: str = Field(default="sqlite:///../backend/app/app.db", alias="AGENT_DB_READ_URL")
    write_db_url: str = Field(default="sqlite:///../backend/app/app.db", alias="AGENT_DB_WRITE_URL")

    jwt_secret: str = Field(default="dev-secret-key-change-me", alias="AGENT_JWT_SECRET")
    jwt_algorithm: str = "HS256"
    confirmation_secret: str = Field(default="agent-confirmation-secret", alias="AGENT_CONFIRMATION_SECRET")
    csrf_secret: str = Field(default="agent-csrf-secret", alias="AGENT_CSRF_SECRET")

    deepseek_api_url: str = Field(default="https://api.deepseek.com/chat/completions", alias="DEEPSEEK_API_URL")
    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
    deepseek_model: str = Field(default="deepseek-chat", alias="DEEPSEEK_MODEL")
    deepseek_timeout_seconds: int = Field(default=20, alias="DEEPSEEK_TIMEOUT_SECONDS")
    deepseek_qps: int = Field(default=1, alias="DEEPSEEK_QPS")

    chat_rate_limit: int = Field(default=20, alias="AGENT_CHAT_RATE_LIMIT")
    cart_rate_limit: int = Field(default=30, alias="AGENT_CART_RATE_LIMIT")
    rate_window_seconds: int = Field(default=60, alias="AGENT_RATE_WINDOW_SECONDS")

    log_file: str = Field(default="logs/agent_audit.log", alias="AGENT_LOG_FILE")

    @field_validator("cors_origins", "trusted_hosts", mode="before")
    @classmethod
    def split_csv(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("read_db_url", "write_db_url", mode="before")
    @classmethod
    def normalize_sqlite_url(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        if value.startswith("sqlite:///"):
            raw_path = value.replace("sqlite:///", "", 1)
            candidate = Path(raw_path)
            if not candidate.is_absolute():
                return f"sqlite:///{(BASE_DIR / candidate).resolve()}"
        return value


settings = Settings()
