from __future__ import annotations

from fastapi import APIRouter, HTTPException

from . import service
from .schemas import (
    AssignRequest,
    BridgeResult,
    CommentRequest,
    CreateTaskRequest,
    PublishForReviewRequest,
    RejectRequest,
    ReviewRequest,
)

router = APIRouter()


def _respond(result) -> BridgeResult:
    if not result.ok:
        raise HTTPException(status_code=502, detail=result.stderr[:500] or "hermes kanban command failed")
    return BridgeResult(ok=True, detail=result.stdout[:2000])


@router.post("/tasks", response_model=BridgeResult)
def create_task(body: CreateTaskRequest) -> BridgeResult:
    return _respond(service.create_task(body.title, body.tenant, body.body, body.assignee))


@router.post("/tasks/{task_id}/claim", response_model=BridgeResult)
def claim_task(task_id: str) -> BridgeResult:
    return _respond(service.claim_task(task_id))


@router.post("/tasks/{task_id}/assign", response_model=BridgeResult)
def assign_task(task_id: str, body: AssignRequest) -> BridgeResult:
    return _respond(service.assign_task(task_id, body.assignee))


@router.post("/tasks/{task_id}/comments", response_model=BridgeResult)
def comment_task(task_id: str, body: CommentRequest) -> BridgeResult:
    return _respond(service.comment_task(task_id, body.text, body.author))


@router.post("/tasks/{task_id}/approve", response_model=BridgeResult)
def approve_artifact(task_id: str, body: ReviewRequest) -> BridgeResult:
    return _respond(service.approve_artifact(task_id, body.note))


@router.post("/tasks/{task_id}/reject", response_model=BridgeResult)
def reject_artifact(task_id: str, body: RejectRequest) -> BridgeResult:
    return _respond(service.reject_artifact(task_id, body.reason))


@router.post("/tasks/{task_id}/publish-for-review", response_model=BridgeResult)
def publish_artifact_for_review(task_id: str, body: PublishForReviewRequest) -> BridgeResult:
    return _respond(service.publish_artifact_for_review(task_id, body.summary))
