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
    # Pin every kanban write to one board; unset means Hermes' *current* board,
    # which silently changes when anyone runs `hermes kanban boards switch`.
    kanban_board: str | None = None
    # Board DB the bridge holds open (see core/wal_keeper.py); derived from
    # kanban_board when unset.
    kanban_db_path: str | None = None
    # JSON file mapping tenant -> chat route; every card the bridge creates in
    # that tenant is subscribed to it (see domains/kanban/notify.py).
    notify_routes_file: str | None = None

    class Config:
        env_prefix = "HERMES_BRIDGE_"


settings = Settings()
