# Matrix spike (Phase 0 step 8, Mac mini, 2026-10-24)

Goal: Tuwunel in Docker with registration closed, and ONE Hermes profile on
the bundled Matrix plugin. Result: **works**, and was then extended to all
six department profiles: each answers in its tenant room within 5–10 s
(roll call 14:50), reads its Kanban board from chat, and has no shell.

## What runs

| Piece | Where | How |
|---|---|---|
| Tuwunel `ghcr.io/matrix-construct/tuwunel:v1.9.4` | `macmini-tuwunel-1`, 127.0.0.1 + tailnet IP, port 8008 | `harness-kit/scripts/bootstrap.sh macmini` |
| Accounts + rooms | `@admin`, one bot per department (`@tech` … `@leadership`), one private room per tenant | `harness-kit/scripts/matrix_provision.py macmini` |
| Hermes Matrix plugin | all six department profiles (`~/.hermes/profiles/<id>/.env`) | `harness-kit/scripts/connect_profile.sh macmini <id>` (`NO_RESTART=1` for all but the last) |

Server name `lobsys-mac-mini.tailad642b.ts.net`, federation off, E2EE off.
Credentials live in `harness-kit/.vault/macmini/` (chmod 600, git-ignored).

## Findings

1. **Registration closed works, with a bootstrap step.** With
   `allow_registration=false` the only way in is the server console:
   `tuwunel --execute "users create-user admin <pw>"` (the first user is
   granted server admin), then `!admin users create-user <bot> <pw>` in the
   `#admins` room. Tuwunel prints the password of a console-created user to
   its log, so the admin is created by a one-off `docker compose run --rm …
   --execute "server shutdown"` (log gone with the container) and every
   password, admin included, is rotated through `/account/password` straight
   after creation. The long-running container's log has no password lines.
2. **Hermes' Matrix extra is Linux-only.** `pyproject.toml` gates
   `matrix = [mautrix[encryption], …]` on `sys_platform == 'linux'` because
   `python-olm` does not build on macOS. Without E2EE the adapter only needs
   the pure packages, installed by hand into Hermes' managed venv:
   `uv pip install --python <hermes venv>/bin/python mautrix==0.21.1
   aiosqlite==0.22.1 asyncpg==0.31.0 aiohttp-socks==0.11.0 Markdown`
   (venv path: `aiohttp.__file__` under Hermes' runtime). **`hermes update`
   may rebuild the venv and drop them** — re-run the command after updates.
   E2EE (`MATRIX_E2EE_MODE=optional|required`) is not possible on macOS.
3. **One gateway serves every profile.** Enabling Matrix for one profile
   means `hermes gateway restart`, which restarts all bots.
4. **The department tool scope was never applied** (found here, fixed in
   hermes-team `29ca83b`): the profiles' `toolsets: {enabled, disabled}` is
   not a Hermes schema, so every bot had terminal, file, code execution,
   computer use and browser on Telegram and Matrix, and no Kanban tools.
   Verify with `hermes-team/scripts/verify_profile_tools.sh`.
5. **First message in a new room** gets a "No home channel is set" notice;
   `connect_profile.sh` sets `MATRIX_HOME_CHANNEL` to the tenant room.
6. **Kanban notifications work.** The bridge subscribes every card it
   creates to its tenant room (`HERMES_BRIDGE_NOTIFY_ROUTES_FILE`, written by
   `connect_profile.sh`); approving in the Portal made `@tech` post
   "✔ [team] @tech Kanban t_… done — …" in `#tech`.
7. Two-member rooms count as DMs (no mention needed, room allowlist
   bypassed); add a third member for room semantics.

## Not verified yet

- Element / Element X login (they may insist on HTTPS for non-localhost
  servers: `tailscale serve --https=8448 http://127.0.0.1:8008`).
- Portal login over Matrix (`magic_link_matrix`, Phase 1).
