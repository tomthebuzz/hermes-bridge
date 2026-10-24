from __future__ import annotations

from pydantic import BaseModel, Field


class SendTelegramRequest(BaseModel):
    chat_id: str
    text: str


class SendRequest(BaseModel):
    # "matrix:!room:server" or "telegram:<chat_id>"; other platforms are refused.
    to: str = Field(pattern=r"^(matrix|telegram):\S+$")
    text: str
    # Send as this Hermes profile (its own bot account); default profile when unset.
    profile: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9_-]*$")


class BridgeResult(BaseModel):
    ok: bool
    detail: str = ""
