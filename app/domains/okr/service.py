"""Writes to the team store (hermes-ontology, objectives / key results /
KPIs / check-ins) for the Team Portal's dashboard. The bridge runs the
store's CLI wrapper named in HERMES_BRIDGE_TEAM_STORE_CLI (harness-kit's
connect_ontology.sh writes ~/.hermes/scripts/ontology-cli-<client>-team.sh:
the same image, schema and DB the bots use), so every write is validated
and audited by the store with the person as actor. Reads stay with the
Portal (the store's SQLite, read-only)."""
from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field

from ...config import settings

logger = logging.getLogger("hermes_bridge")

# What the Portal may create or change. Measurement only through check-ins,
# TaskLink and Review through their own routes later.
EDITABLE_TYPES = ("Objective", "KeyResult", "KPI", "Source")
MEASURED_TYPES = {"KeyResult": "kr_measurements", "KPI": "kpi_measurements"}


@dataclass
class StoreResult:
    ok: bool
    data: dict = field(default_factory=dict)
    error: str = ""


def enabled() -> bool:
    return bool(settings.team_store_cli)


def _run(*args: str) -> StoreResult:
    """One store CLI call; stdout is one JSON document. Logged without
    values (titles and notes can be personal data)."""
    cmd = [settings.team_store_cli, *args]
    logger.info("team store: %s", args[0])
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, check=False,
                           timeout=settings.team_store_timeout_seconds)
    except subprocess.TimeoutExpired:
        return StoreResult(False, error="team store timed out; check the host")
    except OSError as e:
        logger.error("team store CLI not runnable: %s", e)
        return StoreResult(False, error="team store not runnable")
    if p.returncode != 0:
        lines = [l.strip() for l in p.stderr.splitlines() if l.strip()]
        error = (lines[-1] if lines else f"failed (rc={p.returncode})")[:300]
        logger.warning("team store %s failed (rc=%s): %s", args[0], p.returncode, error)
        return StoreResult(False, error=error)
    try:
        data = json.loads(p.stdout.strip() or "{}")
    except json.JSONDecodeError:
        return StoreResult(False, error="team store returned no JSON")
    return StoreResult(True, data if isinstance(data, dict) else {"result": data})


def get(object_id: str) -> StoreResult:
    return _run("get", "--id", object_id)


def upsert(type_name: str, data: dict, actor: str, reason: str, object_id: str | None = None,
           source: str | None = None, lawful_basis: str | None = None) -> StoreResult:
    args = ["upsert", "--type", type_name, "--data", json.dumps(data, ensure_ascii=False),
            "--actor", actor, "--reason", reason]
    if object_id:
        args += ["--id", object_id]
    if source:
        args += ["--source", source]
    if lawful_basis:
        args += ["--lawful-basis", lawful_basis]
    return _run(*args)


def link(rel: str, from_id: str, to_id: str, actor: str, reason: str) -> StoreResult:
    return _run("link", "--rel", rel, "--from", from_id, "--to", to_id, "--actor", actor, "--reason", reason)


def delete(object_id: str, actor: str, reason: str) -> StoreResult:
    return _run("delete", "--id", object_id, "--actor", actor, "--reason", reason)


def checkin(target_id: str, value: float, at: str, actor: str, reason: str, note: str = "") -> StoreResult:
    """A manual measurement on a KeyResult or KPI: Measurement + link, then
    the target's current value and check-in date."""
    target = get(target_id)
    if not target.ok:
        return target
    type_name = target.data.get("type")
    rel = MEASURED_TYPES.get(type_name or "")
    if not rel:
        return StoreResult(False, error=f"check-ins go on a KeyResult or KPI, not a {type_name}")
    m = upsert("Measurement", {"value": value, "at": at, "method": "manual", "actor": actor, "note": note}
               if note else {"value": value, "at": at, "method": "manual", "actor": actor},
               actor, reason, source=f"check-in by {actor}")
    if not m.ok:
        return m
    linked = link(rel, target_id, m.data["id"], actor, reason)
    if not linked.ok:
        return linked
    patch = {"current": value, "last_checkin": at[:10]} if type_name == "KeyResult" else {"current": value, "last_measured": at}
    return upsert(type_name, patch, actor, reason, object_id=target_id)
