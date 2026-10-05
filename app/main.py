"""
Hermes Bridge — thin authenticated HTTP bridge exposing the `hermes` CLI's
write-paths (Kanban writes, Telegram sends) for callers that can't exec the
CLI directly: Docker containers on the same host today, K8s pods later.

This file does wiring only. Business logic lives in app/domains/<name>/
(router + service + schemas each). To add a new capability:
  1. New subpackage under app/domains/
  2. schemas.py (pydantic request/response), service.py (calls
     core.process_runner.run_hermes), router.py (FastAPI routes)
  3. One include_router() line below.
Nothing above this file needs to change.

Run natively on the same host as the real Hermes install (NOT
containerized) — it execs the real `hermes` CLI directly, so there should
be exactly one Hermes install in the whole picture. See launchd/ for the
native service definition (same pattern as Hermes' own gateway service).
"""
from __future__ import annotations

from fastapi import Depends, FastAPI

from .auth import require_api_key
from .config import settings
from .core.logging import configure_logging
from .domains.kanban.router import router as kanban_router
from .domains.messaging.router import router as messaging_router

configure_logging()

app = FastAPI(
    title="Hermes Bridge",
    description="Authenticated bridge exposing hermes CLI write-paths over HTTP.",
    version="0.1.0",
)


@app.get("/healthz")
def healthz():
    # Deliberately unauthenticated — just liveness, no data, matches the
    # same convention as team-portal's /healthz.
    return {"ok": True}


app.include_router(kanban_router, prefix="/kanban", tags=["kanban"], dependencies=[Depends(require_api_key)])
app.include_router(messaging_router, prefix="/messaging", tags=["messaging"], dependencies=[Depends(require_api_key)])
