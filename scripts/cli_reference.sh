#!/usr/bin/env bash
# cli_reference.sh [--check] — the `--help` of every hermes command the bridge
# calls, in docs/cli-reference.md's format. Without flags it rewrites the help
# part of that file (the observed-behaviour notes above it are kept); with
# --check it only diffs, and exits 1 when the installed Hermes differs, e.g.
# after `hermes update`. Re-check the bridge (and scripts/stub_hermes) then.
set -euo pipefail
cd "$(dirname "$0")/.."
DOC=docs/cli-reference.md
HERMES="${HERMES_BRIDGE_HERMES_BIN:-hermes}"
VERBS=(create edit attach comment claim assign promote reclaim reopen-review block unblock
       request-review request-changes complete archive specify assignees notify-subscribe)

render() {
  section() { printf '\n## `%s` --help\n\n```\n' "$1"; shift; "$HERMES" "$@" --help 2>&1 | sed 's/[[:space:]]*$//'; printf '```\n'; }
  section "hermes" ; section "hermes kanban" kanban; section "hermes kanban boards" kanban boards
  section "hermes send" send
  for v in "${VERBS[@]}"; do section "hermes kanban $v" kanban "$v"; done
}

HEAD="$(sed -n '1,/^## `hermes` --help/p' "$DOC" | sed '$d')"
NEW="$(render)"
if [[ "${1:-}" == --check ]]; then
  if diff <(sed -n '/^## `hermes` --help/,$p' "$DOC" | sed 's/[[:space:]]*$//') <(printf '%s\n' "$NEW" | sed '1d') >/dev/null; then
    echo "hermes CLI matches $DOC ($("$HERMES" --version 2>/dev/null | head -1))"
  else
    echo "hermes CLI differs from $DOC:" >&2
    diff <(sed -n '/^## `hermes` --help/,$p' "$DOC" | sed 's/[[:space:]]*$//') <(printf '%s\n' "$NEW" | sed '1d') | head -40 >&2
    exit 1
  fi
else
  printf '%s\n%s\n' "$HEAD" "$NEW" > "$DOC"
  echo "rewrote the help part of $DOC"
fi
