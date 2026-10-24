from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Path, UploadFile

from . import service
from .schemas import (
    AssignRequest,
    BridgeResult,
    CommentRequest,
    CreateTaskRequest,
    EditTaskRequest,
    TransitionRequest,
    PublishForReviewRequest,
    RejectRequest,
    ReviewRequest,
)

router = APIRouter()

# Hermes ids are t_<hex>; anything else (e.g. '-h', '--force') never reaches the CLI.
TaskId = Annotated[str, Path(pattern=r"^t_[A-Za-z0-9_-]{1,64}$")]


def _respond(result) -> BridgeResult:
    if not result.ok:
        raise HTTPException(status_code=502, detail=result.stderr[:500] or "hermes kanban command failed")
    return BridgeResult(ok=True, detail=result.stdout[:2000])


@router.get("/assignees")
def list_assignees() -> list[str]:
    """Profiles a card can be assigned to (installed on this host). `default`
    is the operator's own agent, not a department profile, so it is left out."""
    result = service.list_assignees()
    if not result.ok:
        raise HTTPException(status_code=502, detail=result.stderr[:500] or "hermes kanban assignees failed")
    try:
        rows = json.loads(result.stdout)
    except ValueError:
        raise HTTPException(status_code=502, detail="could not parse hermes kanban assignees output")
    return sorted(r["name"] for r in rows if r.get("on_disk") and r.get("name") != "default")


@router.post("/tasks", response_model=BridgeResult)
def create_task(body: CreateTaskRequest) -> BridgeResult:
    return _respond(service.create_task(body.title, body.tenant, body.body, body.assignee, body.status, body.priority))


@router.patch("/tasks/{task_id}", response_model=BridgeResult)
def edit_task(task_id: TaskId, body: EditTaskRequest) -> BridgeResult:
    if body.title is None and body.body is None and body.priority is None:
        raise HTTPException(status_code=422, detail="At least one editable field is required")
    return _respond(service.edit_task(task_id, body.title, body.body, body.priority))


@router.post("/tasks/{task_id}/transition", response_model=BridgeResult)
def transition_task(task_id: TaskId, body: TransitionRequest) -> BridgeResult:
    return _respond(service.transition_task(task_id, body.status, body.reason, body.current_status, body.author))


@router.post("/tasks/{task_id}/claim", response_model=BridgeResult)
def claim_task(task_id: TaskId) -> BridgeResult:
    return _respond(service.claim_task(task_id))


@router.post("/tasks/{task_id}/assign", response_model=BridgeResult)
def assign_task(task_id: TaskId, body: AssignRequest) -> BridgeResult:
    return _respond(service.assign_task(task_id, body.assignee))


@router.post("/tasks/{task_id}/comments", response_model=BridgeResult)
def comment_task(task_id: TaskId, body: CommentRequest) -> BridgeResult:
    return _respond(service.comment_task(task_id, body.text, body.author))


@router.post("/tasks/{task_id}/attachments", response_model=BridgeResult)
async def attach_file(task_id: TaskId, file: UploadFile = File(...),
                      author: str | None = Form(None)) -> BridgeResult:
    max_bytes = 25 * 1024 * 1024
    data = bytearray()
    while chunk := await file.read(1024 * 1024):
        data.extend(chunk)
        if len(data) > max_bytes:
            raise HTTPException(status_code=413, detail="attachment exceeds 25 MB limit")
    if not data:
        raise HTTPException(status_code=400, detail="empty attachments are not accepted")
    return _respond(service.attach_file(task_id, file.filename or "upload", bytes(data), author))


@router.post("/tasks/{task_id}/approve", response_model=BridgeResult)
def approve_artifact(task_id: TaskId, body: ReviewRequest) -> BridgeResult:
    return _respond(service.approve_artifact(task_id, body.note, body.author))


@router.post("/tasks/{task_id}/reject", response_model=BridgeResult)
def reject_artifact(task_id: TaskId, body: RejectRequest) -> BridgeResult:
    return _respond(service.reject_artifact(task_id, body.reason, body.author))


@router.post("/tasks/{task_id}/publish-for-review", response_model=BridgeResult)
def publish_artifact_for_review(task_id: TaskId, body: PublishForReviewRequest) -> BridgeResult:
    return _respond(service.publish_artifact_for_review(task_id, body.summary))
