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

import os
import shutil
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from .auth import require_api_key
from .config import settings
from .core.logging import configure_logging
from .core.wal_keeper import wal_keeper
from .domains.kanban.router import router as kanban_router
from .domains.messaging.router import router as messaging_router
from .domains.okr.router import router as okr_router
from .domains.people.router import router as people_router

configure_logging()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    wal_keeper.open()
    yield
    wal_keeper.close()


app = FastAPI(
    lifespan=lifespan,
    title="Hermes Bridge",
    description="Authenticated bridge exposing hermes CLI write-paths over HTTP.",
    version="0.1.0",
)


@app.get("/diagnostics", dependencies=[Depends(require_api_key)])
def diagnostics():
    binary = settings.hermes_bin
    resolved = shutil.which(binary) if not os.path.isabs(binary) else binary
    return {
        "hermes_bin": binary,
        "resolved_path": resolved,
        "executable": bool(resolved and os.path.isfile(resolved) and os.access(resolved, os.X_OK)),
        "kanban_board": settings.kanban_board,
        "kanban_db": str(wal_keeper.path),
        "kanban_db_held_open": wal_keeper.held,
    }


@app.get("/healthz")
def healthz():
    # Deliberately unauthenticated — just liveness, no data, matches the
    # same convention as team-portal's /healthz.
    return {"ok": True}


app.include_router(kanban_router, prefix="/kanban", tags=["kanban"], dependencies=[Depends(require_api_key)])
app.include_router(messaging_router, prefix="/messaging", tags=["messaging"], dependencies=[Depends(require_api_key)])
app.include_router(people_router, prefix="/people", tags=["people"], dependencies=[Depends(require_api_key)])
app.include_router(okr_router, prefix="/okr", tags=["okr"], dependencies=[Depends(require_api_key)])
