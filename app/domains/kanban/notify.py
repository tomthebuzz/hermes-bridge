from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Callable

from ...config import settings
from ...core.process_runner import CLIResult, run_hermes
from ..okr import service as team_store

logger = logging.getLogger("hermes_bridge")


def _routes() -> dict:
    """Re-read on every call so harness-kit can add rooms without a restart.
    Format: {"<tenant>": {"platform": "matrix", "chat_id": "!room:server",
    "chat_type": "group", "notifier_profile": "<profile>"}}."""
    if not settings.notify_routes_file:
        return {}
    try:
        return json.loads(Path(settings.notify_routes_file).expanduser().read_text())
    except (OSError, ValueError) as e:
        logger.warning("notify routes unreadable (%s): %s", settings.notify_routes_file, e)
        return {}


def _route(tenant: str) -> dict | None:
    routes = _routes()
    route = routes.get(tenant) if isinstance(routes, dict) else None
    if not isinstance(route, dict) or not route.get("platform") or not route.get("chat_id"):
        if route is not None:
            logger.warning("notify route for %s is incomplete", tenant)
        return None
    return route


def subscribe_tenant_room(task_id: str, tenant: str, kanban: Callable[..., CLIResult]) -> None:
    """Best effort: a card is still created when its tenant room can't be
    subscribed; the failure is only logged."""
    route = _route(tenant)
    if route is None:
        return
    args = ["notify-subscribe", f"--platform={route['platform']}", f"--chat-id={route['chat_id']}"]
    if route.get("chat_type"):
        args.append(f"--chat-type={route['chat_type']}")
    if route.get("notifier_profile"):
        args.append(f"--notifier-profile={route['notifier_profile']}")
    result = kanban(*args, task_id)
    if not result.ok:
        logger.warning("could not subscribe %s to %s room: %s", task_id, tenant, result.stderr[:300])


# --- one Matrix thread per card -------------------------------------------
# The tenant's bot posts the card as a message in the tenant room; Hermes'
# own terminal events (done, blocked, gave up) are subscribed to that
# thread, and the bridge posts what people do in the Portal (comments,
# moves, reviews) into it too, naming the card's stakeholders so they get
# pinged. Replying in the thread reaches the bot. The thread is remembered
# in the team store (TaskThread) so the Portal can link to it.

def _send(profile: str | None, target: str, text: str) -> dict | None:
    prefix = ["-p", profile] if profile else []
    result = run_hermes(*prefix, "send", "--to", target, "--json", "--", text)
    if not result.ok:
        logger.warning("send to %s failed: %s", target.split(":")[0], result.stderr[:300])
        return None
    try:
        data = json.loads(result.stdout.strip() or "{}")
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def open_task_thread(task_id: str, title: str, tenant: str, kanban: Callable[..., CLIResult]) -> dict | None:
    """Post the card into its tenant room as the tenant's bot and subscribe
    the card's events to that thread. Falls back to the plain room
    subscription when the room has no bot or the post fails. Returns the
    thread ({room, event}) or None."""
    route = _route(tenant)
    if route is None or route.get("platform") != "matrix" or not route.get("notifier_profile"):
        subscribe_tenant_room(task_id, tenant, kanban)
        return None
    sent = _send(route["notifier_profile"], f"matrix:{route['chat_id']}", f"Task {task_id}: {title}")
    event = (sent or {}).get("message_id")
    if not event:
        subscribe_tenant_room(task_id, tenant, kanban)
        return None
    result = kanban("notify-subscribe", "--platform=matrix", f"--chat-id={route['chat_id']}", f"--thread-id={event}",
                    "--chat-type=thread", f"--parent-chat-id={route['chat_id']}",
                    f"--notifier-profile={route['notifier_profile']}", task_id)
    if not result.ok:
        logger.warning("could not subscribe %s to its thread: %s", task_id, result.stderr[:300])
    thread = {"room": route["chat_id"], "event": event, "profile": route["notifier_profile"]}
    if team_store.enabled():
        stored = team_store.upsert("TaskThread", {"task_id": task_id, "tenant": tenant, "room_id": route["chat_id"], "event_id": event},
                                   actor="bridge", reason="card created", source="hermes-bridge")
        if not stored.ok:
            logger.warning("thread of %s not recorded in the team store: %s", task_id, stored.error)
    return thread


def task_thread(task_id: str) -> dict | None:
    """The card's thread from the team store, with the bot that posts in it."""
    if not team_store.enabled():
        return None
    found = team_store.search("TaskThread", task_id)
    for item in found.data.get("items", []) if found.ok else []:
        data = item.get("data", {})
        if data.get("task_id") == task_id:
            route = _route(data.get("tenant", "")) or {}
            return {"room": data["room_id"], "event": data["event_id"], "profile": route.get("notifier_profile")}
    return None


def stakeholder_names(task_id: str) -> list[str]:
    """Display names of the card's stakeholders (TaskLink.person). A display
    name in a message pings that person in Element."""
    if not team_store.enabled():
        return []
    found = team_store.search("TaskLink", task_id)
    names = []
    for item in found.data.get("items", []) if found.ok else []:
        data = item.get("data", {})
        if data.get("task_id") == task_id and data.get("person"):
            names.append(data["person"])
    return sorted(set(names))


def post_task_event(task_id: str, text: str, by: str | None = None) -> None:
    """Best effort: tell the card's thread what just happened in the Portal."""
    thread = task_thread(task_id)
    if thread is None:
        return
    line = f"{text}" + (f" ({by})" if by else "")
    names = [n for n in stakeholder_names(task_id) if n != by]   # the actor needs no ping
    if names:
        line += " · " + ", ".join(names)
    _send(thread.get("profile"), f"matrix:{thread['room']}:{thread['event']}", line)
