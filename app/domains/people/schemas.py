from __future__ import annotations

from pydantic import BaseModel, Field

LOCALPART = r"^[a-z0-9][a-z0-9._=-]{0,63}$"
TENANT = r"^[a-z0-9][a-z0-9_-]{0,63}$"


LANGUAGE = r"^[a-z]{2}$"       # a UI language code the hook knows (en, de); which ones is the hook's business


class AddPersonRequest(BaseModel):
    localpart: str = Field(pattern=LOCALPART)
    name: str = Field(min_length=1, max_length=60, pattern=r'^[^\x00-\x1f\x7f"\\]+$')
    tenants: list[str] = Field(min_length=1, max_length=50)
    approve: list[str] = Field(default_factory=list, max_length=50)
    language: str | None = Field(default=None, pattern=LANGUAGE)


class UpdatePersonRequest(BaseModel):
    tenants: list[str] = Field(min_length=1, max_length=50)
    approve: list[str] = Field(default_factory=list, max_length=50)
    language: str | None = Field(default=None, pattern=LANGUAGE)


class LanguageRequest(BaseModel):
    language: str = Field(default="", pattern=r"^([a-z]{2})?$")   # "" = unset (the browser decides)


class PersonResult(BaseModel):
    ok: bool
    matrix_id: str = ""
    # Only on add: shown once to the person managing people, never logged.
    initial_password: str | None = None
