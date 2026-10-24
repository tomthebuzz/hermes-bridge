#!/usr/bin/env bash
# hermes-bridge smoke test — exercises every bridge route against the REAL
# hermes CLI, plus Team Portal liveness. Creates one tagged test task in a
# test tenant and archives it on exit, pass or fail.
#
# Usage:
#   HERMES_BRIDGE_API_KEY=... scripts/smoke_test.sh
# Options (env):
#   BRIDGE_URL      default http://127.0.0.1:8765
#   PORTAL_URL      default http://127.0.0.1:8080   (empty string = skip portal checks)
#   SMOKE_TENANT    default tech
#   KANBAN_DB       default ~/.hermes/kanban.db      (read-only status checks)
#   SMOKE_FULL=1    also test the 25 MB upload limit (sends ~26 MB)
#   SMOKE_TELEGRAM_CHAT_ID=<id>   also test /messaging/telegram/send
#
# Exit code: number of failed checks (0 = green).
set -uo pipefail

BRIDGE_URL="${BRIDGE_URL:-http://127.0.0.1:8765}"
PORTAL_URL="${PORTAL_URL-http://127.0.0.1:8080}"
SMOKE_TENANT="${SMOKE_TENANT:-tech}"
KANBAN_DB="${KANBAN_DB:-$HOME/.hermes/kanban.db}"
KEY="${HERMES_BRIDGE_API_KEY:?set HERMES_BRIDGE_API_KEY}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TMP="$(mktemp -d)"; TASK_ID=""
pass=0; fail=0

ok()   { printf '  \033[32mPASS\033[0m %s\n' "$1"; pass=$((pass+1)); }
bad()  { printf '  \033[31mFAIL\033[0m %s\n' "$1"; [[ -n "${2:-}" ]] && printf '       %s\n' "${2:0:400}"; fail=$((fail+1)); }
step() { printf '\n\033[1m%s\033[0m\n' "$1"; }

# req <method> <path> [json-body]  -> sets CODE and BODY
req() {
  local m="$1" p="$2" d="${3:-}"
  local args=(-sS -o "$TMP/body" -w '%{http_code}' -X "$m" -H "X-API-Key: $KEY")
  [[ -n "$d" ]] && args+=(-H 'Content-Type: application/json' --data "$d")
  CODE="$(curl "${args[@]}" "$BRIDGE_URL$p" 2>"$TMP/err")" || CODE="000"
  BODY="$(cat "$TMP/body" 2>/dev/null)"
}
expect() { # expect <code> <label>
  if [[ "$CODE" == "$1" ]]; then ok "$2"; else bad "$2 (HTTP $CODE, expected $1)" "$BODY"; fi
}
db_status() { # prints the task's status from kanban.db, or empty
  command -v sqlite3 >/dev/null && [[ -r "$KANBAN_DB" && -n "$TASK_ID" ]] || return 0
  sqlite3 -readonly "$KANBAN_DB" "SELECT status FROM tasks WHERE id='$TASK_ID';" 2>/dev/null
}
expect_status() { # expect_status <status...> — passes if db status is any of them
  local s; s="$(db_status)"
  if [[ -z "$s" ]]; then printf '  \033[33mSKIP\033[0m status check (sqlite3 or kanban.db unavailable)\n'; return; fi
  for want in "$@"; do [[ "$s" == "$want" ]] && { ok "task status is $s"; return; }; done
  bad "task status is '$s', expected one of: $*"
}
cleanup() {
  if [[ -n "$TASK_ID" ]]; then
    req POST "/kanban/tasks/$TASK_ID/transition" "{\"status\":\"archived\",\"reason\":\"smoke test cleanup\",\"current_status\":\"$(db_status)\"}"
    if [[ "$CODE" != 200 ]] && command -v hermes >/dev/null; then
      hermes kanban archive "$TASK_ID" >/dev/null 2>&1 || true
    fi
  fi
  rm -rf "$TMP"
}
trap cleanup EXIT

step "1. Liveness and auth"
CODE="$(curl -sS -o /dev/null -w '%{http_code}' "$BRIDGE_URL/healthz" 2>/dev/null)" || CODE=000
expect 200 "bridge /healthz"
CODE="$(curl -sS -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' --data '{}' "$BRIDGE_URL/kanban/tasks" 2>/dev/null)" || CODE=000
expect 401 "write route rejects missing API key"
req GET /diagnostics
expect 200 "bridge /diagnostics"
grep -q '"executable":true' <<<"$BODY" && ok "bridge resolves an executable hermes CLI" || bad "hermes CLI not executable" "$BODY"

step "2. Create"
req POST /kanban/tasks "{\"title\":\"SMOKE $STAMP\",\"tenant\":\"$SMOKE_TENANT\",\"body\":\"Automated smoke test; safe to archive.\",\"status\":\"running\",\"priority\":0}"
expect 200 "create task in tenant '$SMOKE_TENANT'"
TASK_ID="$(python3 - "$BODY" <<'PY'
import json, re, sys
try:
    detail = json.loads(sys.argv[1]).get("detail", "")
except Exception:
    detail = sys.argv[1]
try:
    o = json.loads(detail)
    tid = o.get("id") or o.get("task_id") or (o.get("task") or {}).get("id")
    if tid: print(tid); sys.exit()
except Exception:
    pass
m = re.search(r"\bt_[A-Za-z0-9_-]+\b", detail)
print(m.group(0) if m else "")
PY
)"
if [[ -z "$TASK_ID" ]]; then bad "parse task id from create output" "$BODY"; echo; echo "Cannot continue without a task id."; exit $((fail))
else ok "task id $TASK_ID"; fi
expect_status running

step "3. Edit, comment, assign, attach"
req PATCH "/kanban/tasks/$TASK_ID" '{"title":"SMOKE '"$STAMP"' (edited)","body":"Edited by smoke test","priority":1}'
expect 200 "edit title, body, priority"
req PATCH "/kanban/tasks/$TASK_ID" '{}'
expect 422 "edit with no fields is rejected"
req POST "/kanban/tasks/$TASK_ID/comments" '{"text":"smoke comment","author":"smoke-test"}'
expect 200 "comment"
printf 'smoke attachment %s\n' "$STAMP" > "$TMP/smoke.txt"
CODE="$(curl -sS -o "$TMP/body" -w '%{http_code}' -H "X-API-Key: $KEY" -F "file=@$TMP/smoke.txt" "$BRIDGE_URL/kanban/tasks/$TASK_ID/attachments")" || CODE=000
BODY="$(cat "$TMP/body")"; expect 200 "attach small file"
: > "$TMP/empty.txt"
CODE="$(curl -sS -o "$TMP/body" -w '%{http_code}' -H "X-API-Key: $KEY" -F "file=@$TMP/empty.txt" "$BRIDGE_URL/kanban/tasks/$TASK_ID/attachments")" || CODE=000
BODY="$(cat "$TMP/body")"; expect 400 "empty attachment is rejected"
if [[ "${SMOKE_FULL:-0}" == 1 ]]; then
  head -c $((26*1024*1024)) /dev/zero > "$TMP/big.bin"
  CODE="$(curl -sS -o "$TMP/body" -w '%{http_code}' -H "X-API-Key: $KEY" -F "file=@$TMP/big.bin" "$BRIDGE_URL/kanban/tasks/$TASK_ID/attachments")" || CODE=000
  BODY="$(cat "$TMP/body")"; expect 413 "attachment over 25 MB is rejected"
fi

step "4. Review loop: publish, request changes, publish, approve"
req POST "/kanban/tasks/$TASK_ID/publish-for-review" '{"summary":"smoke artifact"}'
expect 200 "publish for review"
expect_status review
req POST "/kanban/tasks/$TASK_ID/reject" '{"reason":"smoke: request changes"}'
expect 200 "request changes"
CUR="$(db_status)"
if [[ -n "$CUR" && "$CUR" != running ]]; then
  req POST "/kanban/tasks/$TASK_ID/transition" "{\"status\":\"running\",\"current_status\":\"$CUR\"}"
  expect 200 "transition $CUR -> running"
fi
req POST "/kanban/tasks/$TASK_ID/publish-for-review" '{"summary":"smoke artifact v2"}'
expect 200 "publish for review again"
req POST "/kanban/tasks/$TASK_ID/approve" '{"note":"smoke approve"}'
expect 200 "approve"
expect_status "done"

step "5. Transitions"
req POST "/kanban/tasks/$TASK_ID/transition" '{"status":"todo","current_status":"done"}'
[[ "$CODE" == 502 || "$CODE" == 200 ]] && ok "illegal move done -> todo handled (HTTP $CODE)" || bad "done -> todo returned HTTP $CODE" "$BODY"
req POST "/kanban/tasks/$TASK_ID/transition" '{"status":"archived","current_status":"done"}'
expect 200 "archive"
expect_status archived
[[ "$CODE" == 200 ]] && TASK_ID=""   # nothing left to clean up

step "6. Messaging"
if [[ -n "${SMOKE_TELEGRAM_CHAT_ID:-}" ]]; then
  req POST /messaging/telegram/send "{\"chat_id\":\"$SMOKE_TELEGRAM_CHAT_ID\",\"text\":\"hermes-bridge smoke test $STAMP\"}"
  expect 200 "telegram send"
else
  printf '  \033[33mSKIP\033[0m telegram send (set SMOKE_TELEGRAM_CHAT_ID)\n'
fi

step "7. Team Portal"
if [[ -n "$PORTAL_URL" ]]; then
  CODE="$(curl -sS -o /dev/null -w '%{http_code}' "$PORTAL_URL/healthz" 2>/dev/null)" || CODE=000
  expect 200 "portal /healthz"
  CODE="$(curl -sS -o /dev/null -w '%{http_code}' "$PORTAL_URL/login" 2>/dev/null)" || CODE=000
  [[ "$CODE" == 200 || "$CODE" == 405 ]] && ok "portal /login reachable (HTTP $CODE)" || bad "portal /login HTTP $CODE"
else
  printf '  \033[33mSKIP\033[0m portal checks (PORTAL_URL empty)\n'
fi

printf '\n%s passed, %s failed\n' "$pass" "$fail"
exit "$fail"
