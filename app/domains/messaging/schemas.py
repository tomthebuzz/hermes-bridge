from __future__ import annotations

from pydantic import BaseModel


class SendTelegramRequest(BaseModel):
    chat_id: str
    text: str


class BridgeResult(BaseModel):
    ok: bool
    detail: str = ""
