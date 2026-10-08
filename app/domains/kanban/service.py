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


def transition_task(task_id: str, status: str, reason: str = "Moved from Team Portal",
                    current_status: str | None = None) -> CLIResult:
    """Map board drag/drop to Hermes' legal lifecycle verbs; never write SQL."""
    if current_status == status:
        return CLIResult(True, f"Task {task_id} is already {status}", "", 0)

    if status == "running":
        if current_status == "review":
            reopened = run_hermes("kanban", "reopen-review", task_id, "--reason", reason)
            if not reopened.ok:
                return CLIResult(False, "", _friendly_transition_error(reopened.stderr, "review", "running"), reopened.returncode)
            claimed = run_hermes("kanban", "claim", task_id)
            if not claimed.ok:
                return CLIResult(False, reopened.stdout,
                                 "Review was reopened, but the task could not start. It may be waiting on unfinished parent tasks; it is now back in Ready/Todo.",
                                 claimed.returncode)
            return claimed
        if current_status in {"blocked", "todo"}:
            promoted = run_hermes("kanban", "promote", task_id)
            if not promoted.ok:
                return CLIResult(False, "", _friendly_transition_error(promoted.stderr, current_status, "running"), promoted.returncode)
        return run_hermes("kanban", "claim", task_id)

    if status == "ready":
        if current_status == "running":
            result = run_hermes("kanban", "reclaim", task_id, "--reason", reason)
        elif current_status == "review":
            result = run_hermes("kanban", "reopen-review", task_id, "--reason", reason)
        elif current_status in {"todo", "blocked"}:
            result = run_hermes("kanban", "promote", task_id, reason)
        else:
            return CLIResult(False, "", f"Cannot move a {current_status or 'unknown-state'} task to Ready through the Hermes workflow.", 2)
        if not result.ok:
            return CLIResult(False, "", _friendly_transition_error(result.stderr, current_status, status), result.returncode)
        return result

    if status == "todo":
        if current_status == "review":
            result = run_hermes("kanban", "reopen-review", task_id, "--reason", reason)
        elif current_status == "blocked":
            result = run_hermes("kanban", "unblock", task_id, "--reason", reason)
        elif current_status == "running":
            result = run_hermes("kanban", "reclaim", task_id, "--reason", reason)
            if result.ok:
                return CLIResult(True, result.stdout,
                                 "The active claim was released to Ready. Hermes reserves Todo for dependency-gated tasks.", 0)
        else:
            return CLIResult(False, "", "Hermes reserves Todo for tasks waiting on unfinished dependencies. Use Ready for standalone work.", 2)
        if not result.ok:
            return CLIResult(False, "", _friendly_transition_error(result.stderr, current_status, status), result.returncode)
        return result

    if status == "blocked":
        if current_status == "running":
            result = run_hermes("kanban", "block", task_id, reason)
        elif current_status in {"ready", "todo"}:
            if current_status == "todo":
                return CLIResult(False, "", "This task is already waiting on dependencies in Todo; resolve or update its parent links instead of blocking it.", 2)
            result = run_hermes("kanban", "block", task_id, reason)
        else:
            return CLIResult(False, "", f"Cannot block a {current_status or 'unknown-state'} task from the board. Only Ready or In Progress tasks can be blocked.", 2)
        if not result.ok:
            return CLIResult(False, "", _friendly_transition_error(result.stderr, current_status, status), result.returncode)
        return result

    if status == "review":
        if current_status == "review":
            return CLIResult(True, f"Task {task_id} is already in Review", "", 0)
        if current_status in {"blocked", "todo"}:
            promoted = run_hermes("kanban", "promote", task_id)
            if not promoted.ok:
                return CLIResult(False, "", _friendly_transition_error(promoted.stderr, current_status, status), promoted.returncode)
        result = publish_artifact_for_review(task_id, "Moved to Review from Team Portal")
        if not result.ok:
            return CLIResult(False, "", _friendly_transition_error(result.stderr, current_status, status), result.returncode)
        return result

    if status == "done":
        if current_status not in {"running", "ready", "review"}:
            return CLIResult(False, "", f"A task in {current_status or 'unknown state'} cannot be completed directly. Move it to Review first.", 2)
        result = approve_artifact(task_id, "Completed from Team Portal")
        if not result.ok:
            return CLIResult(False, "", _friendly_transition_error(result.stderr, current_status, status), result.returncode)
        return result

    if status == "archived":
        result = run_hermes("kanban", "archive", task_id)
        if not result.ok:
            return CLIResult(False, "", _friendly_transition_error(result.stderr, current_status, status), result.returncode)
        return result

    return CLIResult(False, "", f"Unsupported board transition: {status}", 2)


def _friendly_transition_error(stderr: str, current_status: str | None, target_status: str) -> str:
    raw = stderr.strip()
    try:
        import json
        payload = json.loads(raw)
        if isinstance(payload, dict):
            raw = str(payload.get("detail", raw))
    except (ValueError, TypeError):
        pass
    lowered = raw.lower()
    if "cannot claim" in lowered or "not ready" in lowered:
        return "Hermes can't start this task yet. It must be Ready with no unfinished parent dependencies. Move it to Ready or resolve its parent tasks first."
    if "cannot promote" in lowered or "unsatisfied parent" in lowered:
        return "Hermes cannot move this task forward while parent dependencies are unfinished. Complete or unlink the parent task first."
    if "cannot reclaim" in lowered:
        return "Hermes could not release the active worker claim. Check whether a worker is still running, then retry."
    if "cannot reopen" in lowered or "invalid review state" in lowered:
        return "This Review card could not be reopened. It may already have an active reviewer run or be missing its review handoff."
    if "cannot request review" in lowered:
        return "Only a Ready or In Progress task can be sent for review."
    if raw:
        return f"Hermes rejected the move from {current_status or 'its current state'} to {target_status}: {raw}"
    return f"Hermes rejected moving this task from {current_status or 'its current state'} to {target_status}."


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
