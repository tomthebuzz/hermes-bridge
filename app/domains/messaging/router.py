from __future__ import annotations

from fastapi import APIRouter, HTTPException

from . import service
from .schemas import BridgeResult, SendRequest, SendTelegramRequest

router = APIRouter()


@router.post("/send", response_model=BridgeResult)
def send(body: SendRequest) -> BridgeResult:
    result = service.send(body.to, body.text, body.profile)
    if not result.ok:
        raise HTTPException(status_code=502, detail=result.stderr[:500] or "hermes send failed")
    return BridgeResult(ok=True, detail=result.stdout[:2000], sanitized=body.sanitized)


@router.post("/telegram/send", response_model=BridgeResult)
def send_telegram(body: SendTelegramRequest) -> BridgeResult:
    result = service.send_telegram(body.chat_id, body.text)
    if not result.ok:
        raise HTTPException(status_code=502, detail=result.stderr[:500] or "hermes send failed")
    return BridgeResult(ok=True, detail=result.stdout[:2000], sanitized=body.sanitized)
