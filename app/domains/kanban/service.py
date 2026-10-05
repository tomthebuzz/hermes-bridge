from __future__ import annotations

from ...core.process_runner import CLIResult, run_hermes


def create_task(title: str, tenant: str, body: str = "", assignee: str | None = None) -> CLIResult:
    args = ["kanban", "create", title, "--tenant", tenant, "--body", body, "--json"]
    if assignee:
        args += ["--assignee", assignee]
    return run_hermes(*args)


def claim_task(task_id: str) -> CLIResult:
    return run_hermes("kanban", "claim", task_id)


def assign_task(task_id: str, assignee: str) -> CLIResult:
    return run_hermes("kanban", "assign", task_id, assignee)


def comment_task(task_id: str, text: str, author: str | None = None) -> CLIResult:
    args = ["kanban", "comment", task_id, text]
    if author:
        args += ["--author", author]
    return run_hermes(*args)


def approve_artifact(task_id: str, note: str = "") -> CLIResult:
    """Approve == complete the review-lane card."""
    args = ["kanban", "complete", task_id]
    if note:
        args += ["--result", note]
    return run_hermes(*args)


def reject_artifact(task_id: str, reason: str) -> CLIResult:
    """Reject == request-changes, sending it back to the publisher."""
    return run_hermes("kanban", "request-changes", task_id, reason)


def publish_artifact_for_review(task_id: str, summary: str = "") -> CLIResult:
    args = ["kanban", "request-review", task_id]
    if summary:
        args += ["--summary", summary]
    return run_hermes(*args)
