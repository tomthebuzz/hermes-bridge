"""Hidden characters in text that reaches an agent (card titles and bodies,
comments, review notes, messages) can spell out instructions nobody sees in
the Portal or in chat. The bridge removes them before the text reaches the
`hermes` CLI and says so in its response (`sanitized: true`), so the Portal
can tell the person. Same rule as T3 Code applies to its prompt links."""
from __future__ import annotations

import re

from pydantic import BaseModel, PrivateAttr, model_validator

# Zero-width space/non-joiner and marks, word joiner and invisible operators,
# bidi overrides and isolates, the BOM, and the Unicode tag block
# (U+E0000-E007F: renders as nothing, can carry whole sentences). U+200D
# (zero-width joiner) is kept: it is what holds emoji sequences together.
_HIDDEN = re.compile(
    "[​‌‎‏⁠-⁤‪-‮⁦-⁩﻿\U000e0000-\U000e007f]"
)


def strip_hidden(text: str) -> tuple[str, int]:
    """The text without hidden characters, and how many were removed."""
    return _HIDDEN.subn("", text)


def _strip_deep(value):
    """Strings inside nested dicts and lists too (object data for the team store)."""
    if isinstance(value, str):
        return strip_hidden(value)
    if isinstance(value, dict):
        total, out = 0, {}
        for k, v in value.items():
            cv, n = _strip_deep(v)
            out[k] = cv
            total += n
        return out, total
    if isinstance(value, list):
        total, out = 0, []
        for v in value:
            cv, n = _strip_deep(v)
            out.append(cv)
            total += n
        return out, total
    return value, 0


class SanitizedModel(BaseModel):
    """A request body whose string fields are stripped of hidden characters
    on validation. `sanitized` tells the router whether anything was removed."""

    _sanitized: bool = PrivateAttr(default=False)

    @model_validator(mode="after")
    def _strip_hidden_from_strings(self):
        removed = 0
        for name in type(self).model_fields:
            value = getattr(self, name)
            clean, n = _strip_deep(value)
            if n:
                setattr(self, name, clean)
                removed += n
        self._sanitized = removed > 0
        return self

    @property
    def sanitized(self) -> bool:
        return self._sanitized
