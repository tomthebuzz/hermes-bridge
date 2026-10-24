from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

from ...config import settings
from ...core.process_runner import CLIResult, run_hermes
from .notify import subscribe_tenant_room


def _kanban(*args: str) -> CLIResult:
    board = ["--board", settings.kanban_board] if settings.kanban_board else []
    return run_hermes("kanban", *board, *args)


def _kanban_with_body(args: list[str], body: str, positional: list[str]) -> CLIResult:
    """Pass the body via --body-file: argparse reads a value like "-x" as a flag,
    and Hermes documents --body-file for bodies with flag-like lines."""
    with tempfile.TemporaryDirectory(prefix="hermes-bridge-body-") as tmp:
        path = Path(tmp) / "body.md"
        path.write_text(body, encoding="utf-8")
        return _kanban(*args, "--body-file", str(path), "--", *positional)


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
    # Hermes lands a standalone task in Ready unless told otherwise; Todo is
    # reserved for dependency-gated work and a fresh card has no claim, so
    # todo/ready/running all start in Ready rather than faking a raw status.
    args = ["create", f"--tenant={tenant}"]
    if status == "triage":
        args += ["--triage"]
    elif status == "blocked":
        args += ["--initial-status", "blocked"]
    args += ["--priority", str(priority), "--json"]
    if assignee:
        args += [f"--assignee={assignee}"]
    created = _kanban_with_body(args, body, [title])
    if not created.ok:
        return created
    task_id = _task_id_from_create(created.stdout)
    if task_id:
        subscribe_tenant_room(task_id, tenant, _kanban)
    if status in {"triage", "todo", "ready", "running", "blocked"}:
        return created
    if not task_id:
        return CLIResult(False, created.stdout,
                         "task was created but its ID could not be parsed; verify it with hermes kanban list", 1)
    if status == "review":
        steps = [publish_artifact_for_review(task_id, "Created in Review from Team Portal")]
    elif status == "done":
        steps = [approve_artifact(task_id, "Created as Done from Team Portal")]
    else:  # archived
        steps = [approve_artifact(task_id, "Created for archive from Team Portal"),
                 _kanban("archive", task_id)]
    failed = next((result for result in steps if not result.ok), None)
    if failed:
        return CLIResult(False, created.stdout,
                         f"created {task_id} but could not move it to {status}: {failed.stderr}", failed.returncode)
    return CLIResult(True, created.stdout, "", 0)


def attach_file(task_id: str, filename: str, data: bytes, author: str | None = None) -> CLIResult:
    """Use Hermes' supported attachment CLI path, not direct DB/file metadata writes."""
    safe_name = Path(filename).name.strip()
    if not safe_name or safe_name in {".", ".."}:
        return CLIResult(False, "", "invalid filename", 2)
    with tempfile.TemporaryDirectory(prefix="hermes-bridge-attachment-") as tmp:
        path = Path(tmp) / safe_name
        path.write_bytes(data)
        author_args = [f"--author={author}"] if author else []
        return _kanban("attach", *author_args, task_id, str(path))


def edit_task(task_id: str, title: str | None = None, body: str | None = None,
              priority: int | None = None) -> CLIResult:
    # `edit` has no --body-file; the "=" form keeps dash-leading values from
    # being read as flags.
    args = ["edit"]
    if title is not None:
        args += [f"--title={title}"]
    if body is not None:
        args += [f"--body={body}"]
    if priority is not None:
        args += ["--priority", str(priority)]
    return _kanban(*args, "--", task_id)


def transition_task(task_id: str, status: str, reason: str = "Moved from Team Portal",
                    current_status: str | None = None, author: str | None = None) -> CLIResult:
    """Map board drag/drop to Hermes' legal lifecycle verbs; never write SQL."""
    if current_status == status:
        return CLIResult(True, f"Task {task_id} is already {status}", "", 0)

    if current_status == "triage":
        return _leave_triage(task_id, status)

    if status == "running":
        if current_status == "review":
            reopened = _kanban("reopen-review", task_id, f"--reason={reason}")
            if not reopened.ok:
                return CLIResult(False, "", _friendly_transition_error(reopened.stderr, "review", "running"), reopened.returncode)
            claimed = _kanban("claim", task_id)
            if not claimed.ok:
                return CLIResult(False, reopened.stdout,
                                 "Review was reopened, but the task could not start. It may be waiting on unfinished parent tasks; it is now back in Ready/Todo.",
                                 claimed.returncode)
            return claimed
        if current_status in {"blocked", "todo"}:
            verb = "unblock" if current_status == "blocked" else "promote"
            promoted = _kanban(verb, task_id)
            if not promoted.ok:
                return CLIResult(False, "", _friendly_transition_error(promoted.stderr, current_status, "running"), promoted.returncode)
        return _kanban("claim", task_id)

    if status == "ready":
        if current_status == "running":
            result = _kanban("reclaim", task_id, f"--reason={reason}")
        elif current_status == "review":
            result = _kanban("reopen-review", task_id, f"--reason={reason}")
        elif current_status == "blocked":
            result = _kanban("unblock", task_id, f"--reason={reason}")
        elif current_status == "todo":
            result = _kanban("promote", "--", task_id, reason)
        else:
            return CLIResult(False, "", f"Cannot move a {current_status or 'unknown-state'} task to Ready through the Hermes workflow.", 2)
        if not result.ok:
            return CLIResult(False, "", _friendly_transition_error(result.stderr, current_status, status), result.returncode)
        return result

    if status == "todo":
        if current_status == "review":
            result = _kanban("reopen-review", task_id, f"--reason={reason}")
        elif current_status == "blocked":
            result = _kanban("unblock", task_id, f"--reason={reason}")
        elif current_status == "running":
            result = _kanban("reclaim", task_id, f"--reason={reason}")
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
            result = _kanban("block", "--", task_id, reason)
        elif current_status in {"ready", "todo"}:
            if current_status == "todo":
                return CLIResult(False, "", "This task is already waiting on dependencies in Todo; resolve or update its parent links instead of blocking it.", 2)
            result = _kanban("block", "--", task_id, reason)
        else:
            return CLIResult(False, "", f"Cannot block a {current_status or 'unknown-state'} task from the board. Only Ready or In Progress tasks can be blocked.", 2)
        if not result.ok:
            return CLIResult(False, "", _friendly_transition_error(result.stderr, current_status, status), result.returncode)
        return result

    if status == "review":
        if current_status == "review":
            return CLIResult(True, f"Task {task_id} is already in Review", "", 0)
        if current_status in {"blocked", "todo"}:
            verb = "unblock" if current_status == "blocked" else "promote"
            promoted = _kanban(verb, task_id)
            if not promoted.ok:
                return CLIResult(False, "", _friendly_transition_error(promoted.stderr, current_status, status), promoted.returncode)
        result = publish_artifact_for_review(task_id, "Moved to Review from Team Portal")
        if not result.ok:
            return CLIResult(False, "", _friendly_transition_error(result.stderr, current_status, status), result.returncode)
        return result

    if status == "done":
        if current_status not in {"running", "ready", "review"}:
            return CLIResult(False, "", f"A task in {current_status or 'unknown state'} cannot be completed directly. Move it to Review first.", 2)
        result = approve_artifact(task_id, "Completed from Team Portal", author)
        if not result.ok:
            return CLIResult(False, "", _friendly_transition_error(result.stderr, current_status, status), result.returncode)
        return result

    if status == "archived":
        result = _kanban("archive", task_id)
        if not result.ok:
            return CLIResult(False, "", _friendly_transition_error(result.stderr, current_status, status), result.returncode)
        return result

    return CLIResult(False, "", f"Unsupported board transition: {status}", 2)


def _leave_triage(task_id: str, status: str) -> CLIResult:
    """Triage has one exit, `specify`: Hermes' triage specifier (an LLM) fleshes
    out the card and lands it in Todo. The gateway also does this on its own
    each dispatcher tick, so this only makes it happen now."""
    if status not in {"todo", "ready", "running"}:
        return CLIResult(False, "", "A Triage card first has to be specified: move it to Todo or Ready.", 2)
    specified = _kanban("specify", "--author=Team Portal", task_id)
    if not specified.ok:
        return CLIResult(False, "", _friendly_transition_error(specified.stderr, "triage", status), specified.returncode)
    if status == "todo":
        return specified
    promoted = _kanban("promote", task_id)
    # specify lands standalone cards straight in Ready; promote then refuses.
    if not promoted.ok and "is 'ready'" in promoted.stderr:
        promoted = CLIResult(True, specified.stdout, "", 0)
    if not promoted.ok:
        return CLIResult(False, specified.stdout,
                         "The card was specified and is in Todo; it waits there until its parent tasks finish.", promoted.returncode)
    return _kanban("claim", task_id) if status == "running" else promoted


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
    if "live worker is running" in lowered or "live-claim" in lowered:
        return "A Hermes worker is still running this task. Wait for it to finish, or move the card back to Ready to release the worker, then retry."
    if "no result or summary evidence" in lowered:
        return "Hermes needs a short note describing what was done before it can mark this task Done."
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
    return _kanban("claim", task_id)


def assign_task(task_id: str, assignee: str) -> CLIResult:
    return _kanban("assign", task_id, assignee)


def comment_task(task_id: str, text: str, author: str | None = None) -> CLIResult:
    args = ["comment"]
    if author:
        args += [f"--author={author}"]
    return _kanban(*args, "--", task_id, text)


def approve_artifact(task_id: str, note: str = "", author: str | None = None) -> CLIResult:
    # `complete` records no approver; with an author the approval is posted as
    # their comment and named in the result, so it stays attributable.
    if author:
        commented = comment_task(task_id, f"APPROVED: {note}" if note else "APPROVED", author)
        if not commented.ok:
            return commented
        note = f"Approved by {author}" + (f": {note}" if note else "")
    args = ["complete", task_id]
    if note:
        args += [f"--result={note}"]
    return _kanban(*args)


def reject_artifact(task_id: str, reason: str, author: str | None = None) -> CLIResult:
    # request-changes only applies while a reviewer run claimed from Review is
    # active; a card a human rejects from the Review column has no such run, so
    # fall back to reopen-review. Its --reason comment is credited to the
    # bridge's own profile, so the reason is posted as the reviewer instead.
    result = _kanban("request-changes", "--", task_id, reason)
    if result.ok or "active review run" not in result.stderr:
        return result
    if not author:
        return _kanban("reopen-review", f"--reason={reason}", task_id)
    commented = comment_task(task_id, f"CHANGES REQUESTED: {reason}", author)
    if not commented.ok:
        return commented
    return _kanban("reopen-review", task_id)


def list_assignees() -> CLIResult:
    return _kanban("assignees", "--json")


def publish_artifact_for_review(task_id: str, summary: str = "") -> CLIResult:
    args = ["request-review", task_id]
    if summary:
        args += [f"--summary={summary}"]
    return _kanban(*args)
