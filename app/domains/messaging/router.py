from __future__ import annotations

from fastapi import APIRouter, HTTPException

from . import service
from .schemas import BridgeResult, SendTelegramRequest

router = APIRouter()


@router.post("/telegram/send", response_model=BridgeResult)
def send_telegram(body: SendTelegramRequest) -> BridgeResult:
    result = service.send_telegram(body.chat_id, body.text)
    if not result.ok:
        raise HTTPException(status_code=502, detail=result.stderr[:500] or "hermes send failed")
    return BridgeResult(ok=True, detail=result.stdout[:2000])
