from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass

from ..config import settings

logger = logging.getLogger("hermes_bridge")


@dataclass
class CLIResult:
    ok: bool
    stdout: str
    stderr: str
    returncode: int


def run_hermes(*args: str) -> CLIResult:
    """The ONE place every domain service shells out through. If you're
    writing a new domain and find yourself calling subprocess.run directly
    instead of this, stop — that's exactly the duplication this module
    exists to prevent (kanban_write.py and the cron scripts had three
    near-identical copies of this before the bridge existed)."""
    cmd = [settings.hermes_bin, *args]
    logger.info("running: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=settings.request_timeout_seconds, check=False,
        )
    except subprocess.TimeoutExpired:
        logger.error("timeout after %ss: %s", settings.request_timeout_seconds, " ".join(cmd))
        return CLIResult(ok=False, stdout="", stderr=f"timeout after {settings.request_timeout_seconds}s", returncode=-1)
    except FileNotFoundError:
        logger.error("hermes binary not found: %s", settings.hermes_bin)
        return CLIResult(ok=False, stdout="", stderr=f"'{settings.hermes_bin}' not found on PATH", returncode=-1)

    ok = result.returncode == 0
    if not ok:
        logger.warning("command failed (rc=%s): %s", result.returncode, result.stderr[:500])
    return CLIResult(ok=ok, stdout=result.stdout, stderr=result.stderr, returncode=result.returncode)
