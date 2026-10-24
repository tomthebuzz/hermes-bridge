from __future__ import annotations

from pydantic import BaseModel, Field

LOCALPART = r"^[a-z0-9][a-z0-9._=-]{0,63}$"
TENANT = r"^[a-z0-9][a-z0-9_-]{0,63}$"


class AddPersonRequest(BaseModel):
    localpart: str = Field(pattern=LOCALPART)
    name: str = Field(min_length=1, max_length=60, pattern=r'^[^\x00-\x1f\x7f"\\]+$')
    tenants: list[str] = Field(min_length=1, max_length=50)
    approve: list[str] = Field(default_factory=list, max_length=50)


class UpdatePersonRequest(BaseModel):
    tenants: list[str] = Field(min_length=1, max_length=50)
    approve: list[str] = Field(default_factory=list, max_length=50)


class PersonResult(BaseModel):
    ok: bool
    matrix_id: str = ""
    # Only on add: shown once to the person managing people, never logged.
    initial_password: str | None = None
