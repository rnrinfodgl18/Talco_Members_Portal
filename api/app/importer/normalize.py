import html
import re

from app.importer.models import PartyParts


_STEP_RE = re.compile(r"[-\s]*STEP\s*$", re.IGNORECASE)
_CARE_OF_RE = re.compile(r"\bC\s*[/.]?\s*O\b[.,]?", re.IGNORECASE)


def nkey(value: str | None) -> str:
    if not value:
        return ""
    normalized = html.unescape(str(value)).upper().replace("&", "AND")
    return re.sub(r"[^A-Z0-9]", "", normalized)


def split_party(value: str) -> PartyParts:
    raw = html.unescape(value).strip()
    is_step = bool(_STEP_RE.search(raw))
    cleaned = _STEP_RE.sub("", raw).strip()
    sides = _CARE_OF_RE.split(cleaned, maxsplit=1)
    left = sides[0].strip(" .,-")
    right = sides[1].strip(" .,-") if len(sides) == 2 else None
    return PartyParts(raw=raw, cleaned=cleaned, left=left, right=right or None, is_step=is_step)

