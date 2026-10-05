from __future__ import annotations

from ...core.process_runner import CLIResult, run_hermes


def send_telegram(chat_id: str, text: str) -> CLIResult:
    return run_hermes("send", "telegram", "--chat-id", chat_id, text)
