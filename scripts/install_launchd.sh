#!/usr/bin/env bash
# Installs the Hermes Bridge as a launchd service on macOS — same pattern
# as Hermes' own gateway service. Run on the Mac mini, not in any sandbox.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST_SRC="${REPO_ROOT}/launchd/com.hermes-team.bridge.plist"
PLIST_DST="${HOME}/Library/LaunchAgents/com.hermes-team.bridge.plist"

if [ ! -d "${REPO_ROOT}/.venv" ]; then
  echo "No .venv found. Creating one..."
  python3 -m venv "${REPO_ROOT}/.venv"
fi
"${REPO_ROOT}/.venv/bin/pip" install -q -r "${REPO_ROOT}/requirements.txt"

VENV_PYTHON="${REPO_ROOT}/.venv/bin/python3"
HERMES_BIN_PATH="${HERMES_BRIDGE_HERMES_BIN:-$(type -P hermes || true)}"
if [ -z "${HERMES_BIN_PATH}" ] || [ ! -x "${HERMES_BIN_PATH}" ]; then
  echo "Could not resolve an executable Hermes CLI path from this shell."
  echo "Run 'command -v hermes' in your normal Hermes terminal and rerun with:"
  echo "  HERMES_BRIDGE_HERMES_BIN=/absolute/path/to/hermes bash scripts/install_launchd.sh"
  exit 1
fi

if [ -z "${HERMES_BRIDGE_API_KEY:-}" ]; then
  echo "Set HERMES_BRIDGE_API_KEY in your shell before running this script, e.g.:"
  echo "  export HERMES_BRIDGE_API_KEY=\$(openssl rand -hex 32)"
  exit 1
fi

sed -e "s#REPLACE_WITH_VENV_PYTHON_PATH#${VENV_PYTHON}#" \
    -e "s#REPLACE_WITH_REPO_PATH#${REPO_ROOT}#" \
    -e "s#REPLACE_WITH_REAL_SECRET#${HERMES_BRIDGE_API_KEY}#" \
    -e "s#REPLACE_WITH_HERMES_BIN_PATH#${HERMES_BIN_PATH}#" \
    "${PLIST_SRC}" > "${PLIST_DST}"

if command -v plutil >/dev/null 2>&1; then
  plutil -lint "${PLIST_DST}"
fi

LAUNCHD_DOMAIN="gui/$(id -u)"
LAUNCHD_SERVICE="${LAUNCHD_DOMAIN}/com.hermes-team.bridge"
# Remove older bridge labels too; one may still own port 8765 and shadow this app.
for LEGACY_LABEL in com.futuretree.hermes-bridge com.hermes-team.hermes-bridge; do
  launchctl bootout "${LAUNCHD_DOMAIN}/${LEGACY_LABEL}" 2>/dev/null || true
  LEGACY_PLIST="${HOME}/Library/LaunchAgents/${LEGACY_LABEL}.plist"
  if [ -f "${LEGACY_PLIST}" ]; then
    launchctl bootout "${LAUNCHD_DOMAIN}" "${LEGACY_PLIST}" 2>/dev/null || true
    mv "${LEGACY_PLIST}" "${LEGACY_PLIST}.disabled"
  fi
done
launchctl bootout "${LAUNCHD_DOMAIN}" "${PLIST_DST}" 2>/dev/null || true
launchctl bootstrap "${LAUNCHD_DOMAIN}" "${PLIST_DST}"
launchctl enable "${LAUNCHD_SERVICE}" 2>/dev/null || true
launchctl kickstart -k "${LAUNCHD_SERVICE}"
DIAGNOSTICS="$(curl --retry 10 --retry-delay 1 --retry-connrefused -fsS \
  -H "X-API-Key: ${HERMES_BRIDGE_API_KEY}" http://127.0.0.1:8765/diagnostics)"
"${REPO_ROOT}/.venv/bin/python3" -c 'import json,sys; d=json.loads(sys.argv[1]); print("Hermes CLI:",d.get("resolved_path")); sys.exit(0 if d.get("executable") else 1)' "${DIAGNOSTICS}"

echo "Installed. Check status with:"
echo "  launchctl list | grep hermes-bridge"
echo "  curl http://127.0.0.1:8765/healthz"
echo
echo "IMPORTANT: save this API key somewhere safe — it's the same value"
echo "every caller (team-portal, cron jobs) needs to set as"
echo "HERMES_BRIDGE_API_KEY / HERMES_BRIDGE_URL's companion header:"
echo "  ${HERMES_BRIDGE_API_KEY}"
