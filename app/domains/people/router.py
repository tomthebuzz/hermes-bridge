from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path

from . import service
from .schemas import LOCALPART, TENANT, AddPersonRequest, LanguageRequest, PersonResult, UpdatePersonRequest

router = APIRouter()
Localpart = Annotated[str, Path(pattern=LOCALPART)]


def _csv(tenants: list[str]) -> str:
    for t in tenants:
        if not re.fullmatch(TENANT, t):
            raise HTTPException(status_code=422, detail=f"invalid tenant id {t[:40]!r}")
    return ",".join(dict.fromkeys(tenants)) or "-"


def _result(r: service.HookResult) -> PersonResult:
    if not r.ok:
        raise HTTPException(status_code=400, detail=r.error)
    return PersonResult(ok=True, matrix_id=str(r.data.get("matrix_id", "")),
                        initial_password=r.data.get("initial_password"))


def _require_enabled() -> None:
    if not service.enabled():
        raise HTTPException(status_code=503, detail="people management is not configured (HERMES_BRIDGE_PEOPLE_HOOK)")


@router.post("", response_model=PersonResult)
def add_person(body: AddPersonRequest) -> PersonResult:
    _require_enabled()
    extra = [body.language] if body.language else []     # positional, only when given (older hooks take four)
    return _result(service.run("add", body.localpart, body.name, _csv(body.tenants), _csv(body.approve), *extra))


@router.put("/{localpart}", response_model=PersonResult)
def update_person(localpart: Localpart, body: UpdatePersonRequest) -> PersonResult:
    _require_enabled()
    extra = [body.language] if body.language else []
    return _result(service.run("update", localpart, _csv(body.tenants), _csv(body.approve), *extra))


@router.put("/{localpart}/language", response_model=PersonResult)
def set_language(localpart: Localpart, body: LanguageRequest) -> PersonResult:
    """Only the person's UI language; the hook touches no rooms and restarts nothing."""
    _require_enabled()
    return _result(service.run("language", localpart, body.language or "-"))


@router.delete("/{localpart}", response_model=PersonResult)
def remove_person(localpart: Localpart) -> PersonResult:
    _require_enabled()
    return _result(service.run("remove", localpart))
