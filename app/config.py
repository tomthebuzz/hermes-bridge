from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Fail-closed by design: api_key has no default, so the service
    refuses to start without one explicitly set — mirrors the same
    discipline as team-portal's RBAC (see that repo's app/rbac.py)."""

    hermes_bin: str = "hermes"
    bind_host: str = "127.0.0.1"   # loopback by default — see README "Never expose this publicly"
    bind_port: int = 8765
    api_key: str
    request_timeout_seconds: float = 30.0

    class Config:
        env_prefix = "HERMES_BRIDGE_"


settings = Settings()
