# Phase 0 report — Mac mini (2026-10-24)

**Exit gate reached.** The step 6 flow works end to end (Portal create →
claimed by a department profile → artifact attached → review → reject →
rework → approve in the Portal), and `scripts/smoke_test.sh` is green
(25 passed, 0 failed; Telegram send skipped). Step 8 (Matrix spike) is done
and was taken further: all six department bots are on Matrix, Kanban events
post into the tenant rooms, and the Portal can log users in over Matrix.

Hermes Agent v0.21.5+6841.g8b66a51 · macOS 26.5.2 arm64 · Docker 29.7.2.
Every repo: `main` tagged `v0-macmini`, work on `dev`. hermes-bridge,
hermes-wrappers and hermes-team are pushed; harness-kit and hermes-ontology
have no remote yet (local commits only).

## What runs now

| Component | Where | Notes |
|---|---|---|
| hermes-bridge | launchd `com.hermes-team.bridge`, 127.0.0.1:8765 | pinned to board `team`, holds its DB open, notify routes from harness-kit |
| Hermes gateway | launchd `ai.hermes.gateway` | one process for all profiles; `kanban.review_dispatch: false` |
| Kanban | board `team` (`~/.hermes/kanban/boards/team/`) | the old `default` board is untouched |
| Department profiles | tech, marketing, sales, finance, ops, leadership | model `gpt-5.6-luna-900k`; scoped tools; Matrix bots |
| Cron | `artifact-sla-sweep` (15m), `tenant-digest` (08:00) | `hermes cron list`; digest skips tenants without a Telegram chat id |
| harness-kit `macmini` | Docker project `macmini` | Tuwunel :8008, Team Portal :8081, Element Web :8082 — loopback + tailnet IP |
| hermes-ontology | `hermes-ontology:dev` image, MCP for `tech` only | synthetic data only |
| Old Portal | `docker-team-portal-1` on **0.0.0.0:8080** | untouched as asked; stale code, has the WAL bug below |

`harness-kit/scripts/check.sh macmini` checks all of it (22 checks, green).

## Bugs found and fixed (selection)

1. **Department bots had terminal and code execution** (hermes-team
   `29ca83b`). `toolsets: {enabled, disabled}` is not a Hermes schema, so the
   intended scope never applied — on Telegram and Matrix alike — and the bots
   had no Kanban tools. Now `platform_toolsets` + `agent.disabled_toolsets`;
   `scripts/verify_profile_tools.sh` proves it.
2. **Portal showed stale data** (wrappers `956f2a4`, bridge `f5bb8a5`).
   Mounting `kanban.db` alone hides the WAL; a card created in the Portal
   404'd in the Portal. The Portal now mounts the board directory and the
   bridge keeps the DB open so `-wal`/`-shm` never vanish (15 → 0 errors).
3. **Reject never worked from Review** (bridge `9a7dc42`): `request-changes`
   needs an active reviewer run; the bridge falls back to `reopen-review`.
4. **An agent reviewer approved before any human could**: with
   `review_dispatch` on, the tech agent approved its own artifact 11 s after
   hand-off. Turned off for human review in the Portal.
5. **Portal publish-for-review always failed in Docker** (wrappers `7d49113`):
   `config/` was not in the image.
6. **Workers mangled artifacts** without a terminal: they base64-encoded by
   hand and cut a checklist to "1 Req 2 Clr". SOUL.md now says to hand off via
   the `artifacts` argument (byte-identical, verified with a 322-word doc).
7. Also: `hermes cron add --from` does not exist (installer instead), tenant
   markers in Triage were rewritten and dispatched by the specifier (now
   archived at once), four profiles had no model, cards created as Blocked
   landed in Ready, dash-leading text was parsed as flags, the digest used
   `in_progress` and an obsolete send syntax, native `prompt()`/`alert()` in
   the Portal, "+" assigned cards to a person's display name, Triage cards had
   no exit, worker hand-offs had no SLA deadline, backups tarred live SQLite.

## Still unverified

- Telegram: magic-link login, digest delivery, bot DMs (needs real chat ids).
- Element / Element X login over plain HTTP on the tailnet (login page loads).
- `harness-kit/scripts/restore.sh` for real (drilled non-destructively only).
- macOS Matrix deps were added to Hermes' venv by hand; `hermes update` may
  drop them (see `matrix-spike.md`).
- hermes-ontology beyond one synthetic Organisation; PII rules not reviewed.

## Decisions for Tom

1. **Remotes** for harness-kit and hermes-ontology (GitHub, private?) so they
   can be synced like the other three.
2. **`docker-team-portal-1`** on 0.0.0.0:8080: stop it in favour of the
   harness-kit Portal on :8081, or rebuild it from `dev`?
3. **Human vs agent review**: keep `kanban.review_dispatch: false`
   (global), or let agents pre-review and humans approve?
4. **SLA sweep auto-resolves worker hand-offs after 48 h** now (approve for
   tech/marketing/sales/ops, reject for finance/leadership). Keep?
5. **Workers have the `file` tool** (needed to write artifacts; Hermes
   denies sensitive paths and redacts secrets). Acceptable?
6. Merge `dev` → `main` once you have reviewed.
