"""People (Matrix account, room invites, bot allowlists, Portal access) are
managed by the deployment, not by Hermes: the bridge only runs the hook
named in HERMES_BRIDGE_PEOPLE_HOOK (harness-kit's scripts/human.sh behind a
per-client wrapper) with validated arguments, one call at a time."""
from __future__ import annotations

import json
import logging
import re
import subprocess
import threading
from dataclasses import dataclass

from ...config import settings

logger = logging.getLogger("hermes_bridge")
_lock = threading.Lock()   # the hook edits team.yaml: never two at once
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


@dataclass
class HookResult:
    ok: bool
    data: dict
    error: str = ""


def enabled() -> bool:
    return bool(settings.people_hook)


def run(action: str, localpart: str, *args: str) -> HookResult:
    cmd = [settings.people_hook, action, localpart, *args]
    logger.info("people hook: %s %s", action, localpart)   # no names, no password
    with _lock:
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, check=False,
                               timeout=settings.people_hook_timeout_seconds)
        except subprocess.TimeoutExpired:
            logger.error("people hook timed out: %s %s", action, localpart)
            return HookResult(False, {}, "timed out; check the host")
        except OSError as e:
            logger.error("people hook not runnable: %s", e)
            return HookResult(False, {}, "people hook not runnable")
    if p.returncode != 0:
        lines = [_ANSI.sub("", l).strip() for l in p.stderr.splitlines() if l.strip()]
        error = (lines[-1] if lines else f"failed (rc={p.returncode})")[:300]
        logger.warning("people hook failed (rc=%s): %s %s: %s", p.returncode, action, localpart, error)
        return HookResult(False, {}, error)
    last = next((l for l in reversed(p.stdout.splitlines()) if l.startswith("{")), "{}")
    try:
        data = json.loads(last)
    except json.JSONDecodeError:
        data = {}
    return HookResult(True, data if isinstance(data, dict) else {})
