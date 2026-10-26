from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path

from . import service
from .schemas import CheckinRequest, DeleteRequest, LinkRequest, StoreResponse, UpsertRequest

router = APIRouter()

ObjectIdPath = Annotated[str, Path(pattern=r"^[a-z]+_[0-9a-f]{6,40}$")]


def _guard() -> None:
    if not service.enabled():
        raise HTTPException(status_code=503, detail="team store not configured on this bridge (HERMES_BRIDGE_TEAM_STORE_CLI)")


def _respond(result: service.StoreResult, body) -> StoreResponse:
    if not result.ok:
        raise HTTPException(status_code=502, detail=result.error or "team store call failed")
    return StoreResponse(ok=True, object=result.data, sanitized=body.sanitized)


@router.post("/objects", response_model=StoreResponse)
def upsert_object(body: UpsertRequest) -> StoreResponse:
    _guard()
    if body.id is None and body.type == "KeyResult" and not body.objective_id:
        raise HTTPException(status_code=422, detail="a new KeyResult needs objective_id")
    result = service.upsert(body.type, body.data, body.actor, body.reason, object_id=body.id,
                            source=None if body.id else f"Portal, {body.actor}")
    if result.ok and body.id is None and body.type == "KeyResult" and body.objective_id:
        linked = service.link("key_results", body.objective_id, result.data["id"], body.actor, body.reason)
        if not linked.ok:
            raise HTTPException(status_code=502, detail=f"key result created ({result.data['id']}) but not linked: {linked.error}")
    return _respond(result, body)


@router.post("/links", response_model=StoreResponse)
def link_objects(body: LinkRequest) -> StoreResponse:
    _guard()
    return _respond(service.link(body.rel, body.from_id, body.to_id, body.actor, body.reason), body)


@router.post("/objects/{object_id}/delete", response_model=StoreResponse)
def delete_object(object_id: ObjectIdPath, body: DeleteRequest) -> StoreResponse:
    _guard()
    return _respond(service.delete(object_id, body.actor, body.reason), body)


@router.post("/checkin", response_model=StoreResponse)
def checkin(body: CheckinRequest) -> StoreResponse:
    _guard()
    at = body.at or dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return _respond(service.checkin(body.target_id, body.value, at, body.actor, body.reason, body.note), body)
