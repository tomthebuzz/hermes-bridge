from __future__ import annotations

import logging
import re
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


# Logged as-is: the command words and flag names, task ids, profile names.
# Everything else (titles, bodies, comments, reasons, messages, login links)
# can be personal data or a secret and is replaced by its length.
_SAFE_VALUE = re.compile(r"^(t_[A-Za-z0-9_-]+|[a-z][a-z0-9_-]{0,31}|\d{1,6})$")


def redact(args: tuple[str, ...]) -> str:
    out, after_dashdash = [], False
    for a in args:
        if a == "--":
            after_dashdash = True
            out.append(a)
        elif not after_dashdash and a.startswith("-"):
            out.append(a.split("=", 1)[0] + ("=<%d chars>" % len(a.split("=", 1)[1]) if "=" in a else ""))
        elif not after_dashdash and _SAFE_VALUE.match(a):
            out.append(a)
        elif after_dashdash and re.match(r"^t_[A-Za-z0-9_-]+$", a):
            out.append(a)
        else:
            out.append(f"<{len(a)} chars>")
    return "hermes " + " ".join(out)


def run_hermes(*args: str) -> CLIResult:
    """The ONE place every domain service shells out through. If you're
    writing a new domain and find yourself calling subprocess.run directly
    instead of this, stop — that's exactly the duplication this module
    exists to prevent (kanban_write.py and the cron scripts had three
    near-identical copies of this before the bridge existed)."""
    cmd = [settings.hermes_bin, *args]
    logger.info("running: %s", redact(args))
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
