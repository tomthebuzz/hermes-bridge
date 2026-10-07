from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

from ...core.process_runner import CLIResult, run_hermes


def _task_id_from_create(stdout: str) -> str | None:
    try:
        obj = json.loads(stdout)
        if isinstance(obj, dict):
            if obj.get("id") or obj.get("task_id"):
                return str(obj.get("id") or obj.get("task_id"))
            if isinstance(obj.get("task"), dict) and obj["task"].get("id"):
                return str(obj["task"]["id"])
    except (json.JSONDecodeError, TypeError):
        pass
    match = re.search(r"\bt_[A-Za-z0-9_-]+\b", stdout)
    return match.group(0) if match else None


def create_task(title: str, tenant: str, body: str = "", assignee: str | None = None,
                status: str = "running", priority: int = 0) -> CLIResult:
    allowed = {"triage", "todo", "ready", "running", "review", "blocked", "done", "archived"}
    if status not in allowed:
        return CLIResult(False, "", f"unsupported initial status: {status}", 2)
    initial = "blocked" if status in {"todo", "ready"} else "running"
    args = ["kanban", "create", title, "--tenant", tenant, "--body", body]
    args += ["--triage"] if status == "triage" else ["--initial-status", initial]
    args += ["--priority", str(priority), "--json"]
    if assignee:
        args += ["--assignee", assignee]
    created = run_hermes(*args)
    if not created.ok or status in {"triage", "running", "blocked"}:
        return created
    task_id = _task_id_from_create(created.stdout)
    if not task_id:
        return CLIResult(False, created.stdout,
                         "task was created but its ID could not be parsed; verify it with hermes kanban list", 1)
    if status == "todo":
        # Standalone tasks cannot be created directly in Todo; the Hermes
        # state machine reserves it for dependency-gated work. Land the card in
        # Ready instead of inserting a raw status into SQLite.
        steps = [run_hermes("kanban", "promote", task_id)]
    elif status == "ready":
        steps = [run_hermes("kanban", "promote", task_id)]
    elif status == "review":
        steps = [publish_artifact_for_review(task_id, "Created in Review from Team Portal")]
    elif status == "done":
        steps = [approve_artifact(task_id, "Created as Done from Team Portal")]
    else:  # archived
        steps = [approve_artifact(task_id, "Created for archive from Team Portal"),
                 run_hermes("kanban", "archive", task_id)]
    failed = next((result for result in steps if not result.ok), None)
    if failed:
        return CLIResult(False, created.stdout,
                         f"created {task_id} but could not move it to {status}: {failed.stderr}", failed.returncode)
    return CLIResult(True, created.stdout, "", 0)


def attach_file(task_id: str, filename: str, data: bytes) -> CLIResult:
    """Use Hermes' supported attachment CLI path, not direct DB/file metadata writes."""
    safe_name = Path(filename).name.strip()
    if not safe_name or safe_name in {".", ".."}:
        return CLIResult(False, "", "invalid filename", 2)
    with tempfile.TemporaryDirectory(prefix="hermes-bridge-attachment-") as tmp:
        path = Path(tmp) / safe_name
        path.write_bytes(data)
        return run_hermes("kanban", "attach", task_id, str(path))


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
    return CLIResult(False, "", f"Unsupported or unsafe status transition: {status}", 2)


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
    args = ["kanban", "complete", task_id]
    if note:
        args += ["--result", note]
    return run_hermes(*args)


def reject_artifact(task_id: str, reason: str) -> CLIResult:
    return run_hermes("kanban", "request-changes", task_id, reason)


def publish_artifact_for_review(task_id: str, summary: str = "") -> CLIResult:
    args = ["kanban", "request-review", task_id]
    if summary:
        args += ["--summary", summary]
    return run_hermes(*args)
