from difflib import SequenceMatcher
from typing import Mapping, Sequence

from app.importer.models import Resolution, Tannery
from app.importer.normalize import nkey, split_party


def _index(tanneries: Sequence[Tannery]) -> dict[str, Tannery]:
    return {nkey(tannery.name): tannery for tannery in tanneries}


def resolve(party: str, tanneries: Sequence[Tannery], aliases: Mapping[str, int] | None = None) -> Resolution:
    parts = split_party(party)
    by_name = _index(tanneries)
    by_sno = {tannery.sno: tannery for tannery in tanneries}
    alias_index = {nkey(name): sno for name, sno in (aliases or {}).items()}
    alias_sno = alias_index.get(nkey(parts.cleaned))
    if alias_sno is not None:
        return Resolution(by_sno.get(alias_sno), parts.left, parts.is_step, "alias")
    if direct := by_name.get(nkey(parts.cleaned)):
        return Resolution(direct, parts.left, parts.is_step, "direct")
    matches = []
    for side in (parts.left, parts.right):
        if side and (match := by_name.get(nkey(side))):
            matches.append(match)
    unique = {match.sno: match for match in matches}
    if len(unique) == 1:
        return Resolution(next(iter(unique.values())), parts.left, parts.is_step, "care_of")
    return Resolution(None, parts.left, parts.is_step, "queue")


def suggest(party: str, tanneries: Sequence[Tannery], limit: int = 3) -> list[Tannery]:
    parts = split_party(party)
    candidates = (parts.left, parts.right or "", parts.cleaned)
    scored = []
    for tannery in tanneries:
        score = max(SequenceMatcher(None, nkey(candidate), nkey(tannery.name)).ratio() for candidate in candidates)
        scored.append((score, -tannery.sno, tannery))
    scored.sort(reverse=True)
    return [item[2] for item in scored[:limit]]

