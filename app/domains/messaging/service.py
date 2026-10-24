from __future__ import annotations

from ...core.process_runner import CLIResult, run_hermes


def send(to: str, text: str, profile: str | None = None) -> CLIResult:
    """`hermes [-p profile] send --to <platform:target> -- <text>`: the message
    goes out as that profile's own bot (e.g. a department bot in its room)."""
    prefix = ["-p", profile] if profile else []
    return run_hermes(*prefix, "send", "--to", to, "--", text)


def send_telegram(chat_id: str, text: str) -> CLIResult:
    # Current Hermes CLI uses `send --to telegram:<chat_id> <message>`; "--"
    # keeps a message starting with "-" from being parsed as a flag.
    return run_hermes("send", "--to", f"telegram:{chat_id}", "--", text)
