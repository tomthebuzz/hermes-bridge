from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Callable

from ...config import settings
from ...core.process_runner import CLIResult

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


def subscribe_tenant_room(task_id: str, tenant: str, kanban: Callable[..., CLIResult]) -> None:
    """Best effort: a card is still created when its tenant room can't be
    subscribed; the failure is only logged."""
    route = _routes().get(tenant)
    if not route:
        return
    args = ["notify-subscribe", f"--platform={route['platform']}", f"--chat-id={route['chat_id']}"]
    if route.get("chat_type"):
        args.append(f"--chat-type={route['chat_type']}")
    if route.get("notifier_profile"):
        args.append(f"--notifier-profile={route['notifier_profile']}")
    result = kanban(*args, task_id)
    if not result.ok:
        logger.warning("could not subscribe %s to %s room: %s", task_id, tenant, result.stderr[:300])
