from __future__ import annotations

from fastapi import Header, HTTPException

from .config import settings


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """One dependency, applied to every domain router at include_router()
    time in main.py. This service has real write access to the Kanban
    board and can send real Telegram messages — never skip this, never
    bind beyond loopback/tailnet without it.

    Deliberately returns 401 for BOTH missing and wrong keys (not 422 for
    missing) — a caller shouldn't be able to distinguish "I forgot the
    header" from "I guessed wrong" through the status code."""
    if x_api_key is None or x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")
