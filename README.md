# hermes-bridge

**Deploying all three repos together? Start at [RUNBOOK.md](RUNBOOK.md)
— step-by-step order, verification commands, and rollback.**

Thin authenticated HTTP bridge exposing the `hermes` CLI's write-paths
(Kanban writes, Telegram sends) over HTTP, for callers that can't exec the
CLI directly — Docker containers on the Mac mini today, K8s pods later.
Runs NATIVE on the same host as the real Hermes install (not
containerized) — it execs the real `hermes` binary, so there's exactly one
Hermes install in the whole picture, no version-skew between a "real"
install and a containerized copy.

## Status (2026-10-24)

Validated on the Mac mini against Hermes Agent v0.21.5: every route runs
against the real CLI (`scripts/smoke_test.sh` green), the stub CLI parses the
real argument shapes (`tests/`, 22 tests, in CI), and
`scripts/cli_reference.sh --check` flags any drift after a Hermes update.
The observed CLI state rules are in `docs/cli-reference.md`; the full Phase 0
record is `docs/phase0-report.md`.

## Why this exists

team-portal and hermes-team-bots' cron jobs both need to call `hermes
kanban ...` / `hermes send telegram ...` as writes. Once those run in
Docker containers, they can't exec the host's CLI directly. Two options
were on the table (see the architecture discussion that led here): bundle
a second Hermes install into every container image (version-skew risk,
doesn't shrink going into K8s), or put one thin bridge natively next to
the one real Hermes install and have every container just call it over
HTTP. This repo is that second option.

## Architecture

```
app/
  main.py              wiring only — creates the app, includes routers,
                        attaches the auth dependency. No business logic.
  config.py             env-driven settings (HERMES_BRIDGE_* prefix),
                        fail-closed: no default API key.
  auth.py               one dependency: shared-secret X-API-Key header.
  core/
    process_runner.py   the ONE subprocess wrapper every domain uses.
    logging.py
  domains/
    kanban/              router.py + service.py + schemas.py
    messaging/           router.py + service.py + schemas.py
    people/              /people: runs HERMES_BRIDGE_PEOPLE_HOOK (add/update/remove a person)
```

Adding a new capability (e.g. writing to MEMORY.md, triggering a cron run,
attaching files) means a new `domains/<name>/` subpackage following the
exact same three-file shape, plus one `include_router()` line in
`main.py`. Nothing else changes — that's the whole point of the layering.

This bridge also exposes authenticated task-edit and transition routes for
Team Portal: `PATCH /kanban/tasks/{id}` edits title/body/priority through
`hermes kanban edit`; `POST /kanban/tasks/{id}/transition` maps board moves
to Hermes CLI commands; and multipart `POST /kanban/tasks/{id}/attachments`
uses `hermes kanban attach` (25 MB cap). They never update SQLite directly.
The launchd installer resolves the absolute Hermes CLI path and writes it as
`HERMES_BRIDGE_HERMES_BIN`, since launchd does not inherit an interactive
shell's PATH. It bootouts/reloads the LaunchAgent on updates and refreshes
requirements. The API-key-protected `/diagnostics` endpoint reports the
configured CLI path and whether it is executable. Re-run the installer after
pulling bridge updates, reusing the existing API key.

The messaging domain follows the current Hermes CLI form
`hermes send --to telegram:<chat_id> <message>`; it does not use the obsolete
`hermes send telegram --chat-id ...` form. See RUNBOOK.md's Telegram test and
troubleshooting section.

Reads are NOT proxied through here — team-portal and the cron scripts
already read `kanban.db` directly via a bind-mounted file (SQLite WAL is
safe for concurrent external readers). This bridge is write-path only,
since that was the actual gap.

## Running it

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
export HERMES_BRIDGE_API_KEY=$(openssl rand -hex 32)
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8765
```

Or install as a launchd service (same supervision pattern as Hermes' own
gateway):

```bash
export HERMES_BRIDGE_API_KEY=$(openssl rand -hex 32)
bash scripts/install_launchd.sh
```

On Linux (Profile S) use `scripts/install_systemd.sh` instead: a systemd
**user** unit (`systemctl --user status hermes-bridge`), API key in
`~/.config/hermes-bridge/env` (0600), same `HERMES_BRIDGE_*` variables.
Checked in a Debian 12 container (install, tests, start command); not yet on
a real hoster VM.

Every kanban call is pinned to `HERMES_BRIDGE_KANBAN_BOARD` (the installer
defaults it to `team` and creates the board if needed); `/diagnostics` reports
the board in use. Non-default boards keep their DB in
`~/.hermes/kanban/boards/<slug>/`, which the Team Portal mounts read-only as a
directory: mounting the DB file alone hides the WAL, so the Portal would only
see writes after a checkpoint.

Set `HERMES_BRIDGE_NOTIFY_ROUTES_FILE` to a JSON map of tenant → chat route
(`{"tech": {"platform": "matrix", "chat_id": "!room:server", "chat_type":
"group", "notifier_profile": "tech"}}`) and every card the bridge creates is
subscribed to its tenant room (`hermes kanban notify-subscribe`), so the
department bot posts when it finishes or blocks. The file is re-read on each
create; harness-kit's `connect_profile.sh` maintains it.

## Tests

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests          # FastAPI app against scripts/stub_hermes
HERMES_BRIDGE_API_KEY=... scripts/smoke_test.sh   # live bridge + real CLI + Portal
```

`scripts/stub_hermes` parses the argument shapes of the real CLI and models
the state rules recorded in `docs/cli-reference.md`; refresh both when Hermes
is updated.

## Never expose this publicly

Default bind is `127.0.0.1`. If you need Docker containers on the same
Mac to reach it, that already works via `host.docker.internal:8765` — no
rebind needed, same pattern as the Telegram/tailnet work earlier. Only
consider a tailnet bind if a remote container genuinely needs it, and even
then this is pure write-access-to-your-whole-board-and-Telegram-bot — keep
the API key as guarded as the gateway's own `API_SERVER_KEY`.

## Validation checklist (run on the real machine)

1. `bash scripts/install_launchd.sh` (creates `.venv`, installs deps,
   registers the launchd service).
2. `curl http://127.0.0.1:8765/healthz` — expect `{"ok": true}`.
3. `curl -X POST http://127.0.0.1:8765/kanban/tasks -H "X-API-Key: $HERMES_BRIDGE_API_KEY" -H "Content-Type: application/json" -d '{"title":"test","tenant":"tech"}'`
   — confirm it actually creates a real task (check `hermes kanban list --tenant tech`).
4. Wire team-portal and hermes-team-bots' cron scripts to it — set
   `HERMES_BRIDGE_URL=http://host.docker.internal:8765` and
   `HERMES_BRIDGE_API_KEY=<same key>` in their environments. Both already
   support this (see their README "Hermes Bridge" sections).
