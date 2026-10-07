from __future__ import annotations

from ...core.process_runner import CLIResult, run_hermes


def create_task(title: str, tenant: str, body: str = "", assignee: str | None = None) -> CLIResult:
    args = ["kanban", "create", title, "--tenant", tenant, "--body", body, "--json"]
    if assignee:
        args += ["--assignee", assignee]
    return run_hermes(*args)


def edit_task(task_id: str, title: str | None = None, body: str | None = None,
              priority: int | None = None) -> CLIResult:
    args = ["kanban", "edit", task_id]
    if title is not None:
        args += ["--title", title]
    if body is not None:
        args += ["--body", body]
    if priority is not None:
        args += ["--priority", str(priority)]
    return run_hermes(*args)


def transition_task(task_id: str, status: str, reason: str = "Moved from Team Portal") -> CLIResult:
    """Use supported CLI transitions; do not update SQLite status directly."""
    if status == "running":
        return run_hermes("kanban", "claim", task_id)
    if status == "ready":
        return run_hermes("kanban", "promote", task_id)
    if status == "todo":
        return run_hermes("kanban", "unblock", task_id)
    if status == "blocked":
        return run_hermes("kanban", "block", task_id, reason)
    if status == "review":
        return publish_artifact_for_review(task_id, "Moved to review from Team Portal")
    if status == "done":
        return approve_artifact(task_id, "Completed from Team Portal")
    if status == "archived":
        return run_hermes("kanban", "archive", task_id)
    return CLIResult(ok=False, stdout="", stderr=f"Unsupported or unsafe status transition: {status}")


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
