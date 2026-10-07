# Deployment Runbook — Team Tools

Step-by-step deployment of all three repos, in dependency order, on the
real Hermes host (the Mac mini, or wherever Hermes actually lives). This
is the "do this for real" companion to the three repos' own READMEs,
which each cover their own internals in depth — this doc is the ordering
and the glue between them.

Repos, in the order you deploy them:

  1. hermes-bridge   (this repo)   — native service, no dependencies
  2. hermes-team-bots              — depends on hermes-bridge for writes
  3. hermes-wrappers (team-portal) — depends on hermes-bridge for writes,
                                      depends on hermes-team-bots' kanban
                                      tenant bootstrap for sensible data

## Status: what's verified vs. what isn't

Everything in all three repos was built and tested against **synthetic
data and a stub `hermes` CLI** in a sandbox with no access to a real
Hermes install. The HTTP layer, auth, RBAC, routing, and error handling
are proven. The live Mac mini Kanban schema has now been checked and the
readers in `hermes-wrappers/app/kanban_read.py` and
`hermes-team-bots/cron/kanban_read.py` have been patched for it
(`tasks` has no `updated_at`; `task_comments.body` is aliased as `text`).
The remaining unconfirmed piece is the exact `hermes kanban ...` CLI flag
shape against your installed version — Step 1's bridge smoke test is where
that gets settled for real.

---

## Step 0 — Prerequisites

On the Hermes host:

```bash
hermes doctor                      # confirm base install is healthy
sqlite3 ~/.hermes/kanban.db ".schema"   # already checked: readers patched for live schema
```

The reader patches assume exactly the live schema pasted from the Mac mini:
`tasks` has no `updated_at`, comments are stored in `task_comments.body`,
and `task_events.created_at` is available to synthesize an `updated_at`
sort key. If Hermes changes that schema later, re-check these two files:
`hermes-wrappers/app/kanban_read.py` and
`hermes-team-bots/cron/kanban_read.py`.

```bash
hermes kanban create --help         # confirm the real CLI flag shapes
hermes send --help
```

Compare against `hermes-bridge/app/domains/*/service.py`. Fix the
`run_hermes(...)` argument lists there if anything's drifted from the docs
this was written against.

You'll also want, before starting:
- Python 3.10+ and `git` on the host. Python 3.14 is supported by the current pins (`pydantic>=2.13`); if you ever see PyO3/pydantic-core build errors, pull latest and recreate `.venv`.
- Docker Desktop installed (for Step 4, team-portal)
- A Telegram account with access to @BotFather and @userinfobot (for the
  bot roster's Telegram wiring later, Step 3)

---

## Step 1 — Deploy hermes-bridge (native)

This has to come first — both other repos call it.

```bash
git clone git@github.com:tomthebuzz/hermes-bridge.git
cd hermes-bridge
export HERMES_BRIDGE_API_KEY=$(openssl rand -hex 32)
bash scripts/install_launchd.sh
```

This creates a `.venv`, installs dependencies, and registers a launchd
service (same supervision pattern as Hermes' own gateway). The script
prints the generated API key at the end — **save it somewhere durable**,
every other component needs it.

Verify:

```bash
curl http://127.0.0.1:8765/healthz
# {"ok": true}

curl -X POST http://127.0.0.1:8765/kanban/tasks \
  -H "X-API-Key: $HERMES_BRIDGE_API_KEY" -H "Content-Type: application/json" \
  -d '{"title":"bridge smoke test","tenant":"tech"}'

hermes kanban list --tenant tech   # confirm the task actually landed for real
```

If that last check doesn't show a real task, stop here and fix
`hermes-bridge/app/domains/kanban/service.py`'s CLI argument shapes against
`hermes kanban create --help` before going further — nothing downstream
will work either.

---

## Step 2 — Bootstrap the Kanban board (hermes-team-bots)

```bash
git clone git@github.com:tomthebuzz/hermes-team.git
cd hermes-team
bash scripts/setup_kanban_tenants.sh
```

This seeds one marker task per tenant (tech/marketing/sales/finance/ops/
leadership) so the board has real tenant data to query before anything
else depends on it. Verify:

```bash
hermes kanban list --json | python3 -c "import sys,json; print(sorted({t['tenant'] for t in json.load(sys.stdin)}))"
```

---

## Step 3 — Install the bot roster + wire Telegram (hermes-team-bots)

```bash
bash scripts/install_all_profiles.sh
```

Then per department (repeat for tech, marketing, sales, finance, ops,
leadership):

```bash
bash scripts/wire_telegram.sh tech
# follow the printed checklist: BotFather token, group creation, chat id
```

This step is NOT automatable — BotFather tokens are secrets only you can
create. After each profile:

```bash
hermes -p tech tools                         # confirm the scoped toolset took
hermes -p tech gateway start
hermes -p tech gateway status
```

Once all 6 are wired, fill in `config/tenants.yaml`'s
`telegram_group_chat_id` for each (needed by the digest cron in Step 5).

---

## Step 4 — Point the bot profiles' gateway at hermes-bridge (optional but recommended)

The bot profiles themselves don't need the bridge — they call Kanban tools
directly via the agent's own tool-calling, not subprocess. The bridge
matters for **hermes-team-bots' cron scripts** and **hermes-wrappers**,
both external to the agent loop. Nothing to do here specific to the bot
profiles; this step exists only to flag that the bridge's role is
deliberately narrow (external callers), not "everything talks through it."

---

## Step 5 — Register the cron jobs (hermes-team-bots)

```bash
hermes cron add --from cron/artifact-sla-sweep.job.yaml
hermes cron add --from cron/tenant-digest.job.yaml
```

(Flag shapes here are unverified against your Hermes version — run
`hermes cron add --help` first and adjust if needed.)

If you'd rather run these as plain cron/launchd jobs instead of through
Hermes' own scheduler (e.g. if you've resolved to containerize them per
the K8s path later), set `HERMES_BRIDGE_URL=http://127.0.0.1:8765` and
`HERMES_BRIDGE_API_KEY=<the key from Step 1>` in their environment and run
them directly:

```bash
KANBAN_DB_PATH=~/.hermes/kanban.db \
HERMES_BRIDGE_URL=http://127.0.0.1:8765 \
HERMES_BRIDGE_API_KEY=<key> \
python3 cron/artifact-sla-sweep.py --dry-run   # confirm it sees real data before dropping --dry-run
```

---

## Step 6 — Deploy Team Portal (hermes-wrappers)

```bash
git clone git@github.com:tomthebuzz/hermes-wrappers.git
cd hermes-wrappers
cp users.yaml.example users.yaml
# edit users.yaml: real Telegram @usernames, numeric user IDs/chat IDs
# (via @userinfobot), tenant/role/approval scopes for all 8-12 wider-team
# people. UI login is by @username; delivery is still best by numeric chat_id.
```

```bash
export HERMES_BRIDGE_API_KEY=<the key from Step 1>
export SESSION_SECRET=$(openssl rand -hex 32)
docker compose -f docker/docker-compose.yml up --build -d
```

This bind-mounts your real `~/.hermes/kanban.db` (read-only) and
`users.yaml` into the container, and points writes at
`http://host.docker.internal:8765` (hermes-bridge) — no Hermes install
needed inside this container at all.

Verify:

```bash
curl http://127.0.0.1:8080/healthz
```

Then from a browser: `http://127.0.0.1:8080`, log in with a real Telegram
`@username` from `users.yaml`, confirm the magic-link DM arrives via Telegram
(this proves the bridge's `/messaging/telegram/send` route works against
real Telegram, not just the stub), click through, and confirm the Kanban
board renders as columns (Triage/Todo/Ready/In Progress/Review/Blocked/Done)
and Artifact Review shows real, tenant-scoped data.

If no Telegram DM arrives:

```bash
# The API now returns 502 when the bridge reports a send failure.
curl -s -X POST http://127.0.0.1:8080/login \
  -H 'Content-Type: application/json' -d '{"login":"@yourusername"}' | python3 -m json.tool

# Check bridge logs and verify direct bridge send.
tail -100 /tmp/hermes-bridge.log
tail -100 /tmp/hermes-bridge.error.log
curl -s -X POST http://127.0.0.1:8765/messaging/telegram/send \
  -H "X-API-Key: $HERMES_BRIDGE_API_KEY" -H 'Content-Type: application/json' \
  -d '{"chat_id":"<numeric chat/user id>","text":"bridge telegram smoke test"}'
```

For DMs, make sure the user has started the bot at least once. Telegram bots
usually cannot initiate a DM to an arbitrary `@username`; keep `telegram_chat_id`
numeric even though the portal login field is handle-first.

---

## Step 7 — End-to-end smoke test

1. In the Team Portal web UI, create a task in one tenant.
2. `hermes kanban show <id>` on the host — confirm it's real, not a stub
   artifact.
3. Publish an artifact for review with a short SLA (`sla_hours: 0.01` ≈ 36
   seconds) via the API, wait, then run the SLA sweep manually
   (`python3 cron/artifact-sla-sweep.py`) and confirm it auto-resolves per
   the configured `on_miss` direction for that tenant.
4. Check a department Telegram group receives the next daily digest (or
   trigger `tenant-digest.py` manually to not wait for 8am).

If all four land, the system is genuinely live end-to-end, not just
individually-verified-against-stubs.

---

## Rollback / stopping everything

```bash
# Team Portal
docker compose -f hermes-wrappers/docker/docker-compose.yml down

# Bot roster gateways
for p in tech marketing sales finance ops leadership; do hermes -p $p gateway stop; done

# hermes-bridge
launchctl unload ~/Library/LaunchAgents/com.hermes-team.bridge.plist

# Cron jobs
hermes cron pause artifact-sla-sweep
hermes cron pause tenant-digest
```

Nothing here deletes data — `kanban.db`, `users.yaml`, and all config stay
on disk untouched by a stop/rollback.

---

## Later: moving to K8s

Each repo's `infra/` directory has a Kustomize base for this (Phase 4 in
the original plan). hermes-bridge itself stays native even in that world —
see its README's "Running it" section — only team-portal and the
hermes-team-bots cron jobs containerize; both already point at
`HERMES_BRIDGE_URL` as a plain env var, so the only change moving to K8s
is what that URL resolves to (a Service/ExternalName instead of
`host.docker.internal`), not any code.
