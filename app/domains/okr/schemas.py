from __future__ import annotations

from pydantic import BaseModel, Field

from ...core.sanitize import SanitizedModel

Actor = Field(min_length=1, max_length=200)
Reason = Field(min_length=1, max_length=500)
ObjectId = Field(pattern=r"^[a-z]+_[0-9a-f]{6,40}$")


class UpsertRequest(SanitizedModel):
    type: str = Field(pattern=r"^(Objective|KeyResult|KPI|Source)$")
    id: str | None = Field(default=None, pattern=r"^[a-z]+_[0-9a-f]{6,40}$")
    data: dict
    # a new KeyResult is linked to this objective in the same call
    objective_id: str | None = Field(default=None, pattern=r"^objective_[0-9a-f]{6,40}$")
    actor: str = Actor
    reason: str = Reason


class LinkRequest(SanitizedModel):
    rel: str = Field(pattern=r"^[a-z_]{1,40}$")
    from_id: str = ObjectId
    to_id: str = ObjectId
    actor: str = Actor
    reason: str = Reason


class DeleteRequest(SanitizedModel):
    actor: str = Actor
    reason: str = Reason


class CheckinRequest(SanitizedModel):
    target_id: str = Field(pattern=r"^(keyresult|kpi)_[0-9a-f]{6,40}$")
    value: float
    at: str | None = None          # ISO 8601; now when omitted
    note: str = Field(default="", max_length=1000)
    actor: str = Actor
    reason: str = Reason


class StoreResponse(BaseModel):
    ok: bool
    object: dict = {}
    sanitized: bool = False
