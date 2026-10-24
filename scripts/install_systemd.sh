#!/usr/bin/env bash
# Installs the Hermes Bridge as a systemd user service on Linux (Profile S),
# the counterpart of install_launchd.sh. Run as the Hermes user on the host.
# The API key lives in ~/.config/hermes-bridge/env (0600), not in the unit.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_SRC="${REPO_ROOT}/systemd/hermes-bridge.service"
UNIT_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/systemd/user"
ENV_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/hermes-bridge"

[ -d "${REPO_ROOT}/.venv" ] || python3 -m venv "${REPO_ROOT}/.venv"
"${REPO_ROOT}/.venv/bin/pip" install -q -r "${REPO_ROOT}/requirements.txt"

HERMES_BIN_PATH="${HERMES_BRIDGE_HERMES_BIN:-$(command -v hermes || true)}"
if [ -z "${HERMES_BIN_PATH}" ] || [ ! -x "${HERMES_BIN_PATH}" ]; then
  echo "Could not resolve the hermes CLI; rerun with HERMES_BRIDGE_HERMES_BIN=/absolute/path/to/hermes" >&2
  exit 1
fi
if [ -z "${HERMES_BRIDGE_API_KEY:-}" ]; then
  echo "Set HERMES_BRIDGE_API_KEY first, e.g. export HERMES_BRIDGE_API_KEY=\$(openssl rand -hex 32)" >&2
  exit 1
fi

KANBAN_BOARD="${HERMES_BRIDGE_KANBAN_BOARD:-team}"
if ! "${HERMES_BIN_PATH}" kanban boards list 2>/dev/null | grep -qE "^[^a-z]*${KANBAN_BOARD}[[:space:]]"; then
  "${HERMES_BIN_PATH}" kanban boards create "${KANBAN_BOARD}"
fi

mkdir -p "${UNIT_DIR}" "${ENV_DIR}"; chmod 700 "${ENV_DIR}"
umask 077
{
  echo "HERMES_BRIDGE_API_KEY=${HERMES_BRIDGE_API_KEY}"
  echo "HERMES_BRIDGE_HERMES_BIN=${HERMES_BIN_PATH}"
  echo "HERMES_BRIDGE_KANBAN_BOARD=${KANBAN_BOARD}"
  if [ -n "${HERMES_BRIDGE_NOTIFY_ROUTES_FILE:-}" ]; then
    echo "HERMES_BRIDGE_NOTIFY_ROUTES_FILE=${HERMES_BRIDGE_NOTIFY_ROUTES_FILE}"
  fi
} > "${ENV_DIR}/env"
sed -e "s#REPLACE_WITH_REPO_PATH#${REPO_ROOT}#g" "${UNIT_SRC}" > "${UNIT_DIR}/hermes-bridge.service"
umask 022

if command -v systemd-analyze >/dev/null 2>&1; then
  # Needs a running user manager; without one (containers, no linger yet)
  # only warn.
  systemd-analyze --user verify "${UNIT_DIR}/hermes-bridge.service" \
    || echo "warning: could not verify the unit (no systemd user manager?)" >&2
fi
if [ "${HERMES_BRIDGE_NO_START:-0}" = 1 ]; then
  echo "Unit written to ${UNIT_DIR}; HERMES_BRIDGE_NO_START=1, not starting."
  exit 0
fi
# Keep the user's services running without an open login session.
loginctl enable-linger "$(id -un)" 2>/dev/null || echo "note: run 'sudo loginctl enable-linger $(id -un)' so the bridge survives logout"
systemctl --user daemon-reload
systemctl --user enable --now hermes-bridge.service
systemctl --user restart hermes-bridge.service
for _ in $(seq 1 20); do
  curl -fsS http://127.0.0.1:8765/healthz >/dev/null 2>&1 && break
  sleep 1
done
curl -fsS -H "X-API-Key: ${HERMES_BRIDGE_API_KEY}" http://127.0.0.1:8765/diagnostics
echo
echo "Installed. Status: systemctl --user status hermes-bridge; logs: journalctl --user -u hermes-bridge"
