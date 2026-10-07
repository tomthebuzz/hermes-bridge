from __future__ import annotations

from ...core.process_runner import CLIResult, run_hermes


def send_telegram(chat_id: str, text: str) -> CLIResult:
    # Current Hermes CLI uses `send --to telegram:<chat_id> <message>`.
    return run_hermes("send", "--to", f"telegram:{chat_id}", text)
