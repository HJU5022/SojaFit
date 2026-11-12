"""Extract document-edition codes from user text without treating part numbers as editions."""
import re
from collections.abc import Iterable

# A short code such as F16 is an edition only in an explicit filename or
# edition phrase. Four-digit codes retain the same boundary requirement.
EDITION_AFTER = re.compile(
    r"(?ix)(?<![A-Za-z0-9])([A-Z]\d{2,4})(?=\s*(?:판본|판|개정판|edition))"
)
EDITION_BEFORE = re.compile(
    r"(?ix)(?:판본|판|개정판|edition)\s*([A-Z]\d{2,4})(?![A-Za-z0-9])"
)
EDITION_FILE = re.compile(
    r"(?ix)(?<![A-Za-z0-9])([A-Z]\d{2,4})(?=\.pdf(?:\s|[가-힣]|$))"
)
EDITION_BARE = re.compile(r"(?<![A-Za-z0-9])([A-Z]\d{4})(?![A-Za-z0-9])", re.I)

# Generic revision spellings are normalized so the request and the document
# filename can be compared without making a short letter/number look like a
# part number.  These patterns require an explicit revision/version marker.
REVISION_LETTER = re.compile(
    r"(?ix)(?:\brev(?:ision)?\.?\s*)([A-Z])\b"
)
VERSION_NUMBER = re.compile(
    r"(?ix)(?:\bversion\b|\bver(?:sion)?\.?|버전)\s*([0-9]+(?:\.[0-9]+)?)"
)
YEAR_EDITION = re.compile(
    r"(?ix)(?<![A-Za-z0-9])((?:19|20)\d{2})\s*(?:년\s*(?:판|개정판|버전)?|edition|ed\.?)"
)


def _generic_revisions(text: str) -> set[str]:
    """Return normalized explicit Rev./version/year editions.

    ``REV_B`` and ``VERSION_2`` are internal comparison keys.  Bare years are
    intentionally excluded; only an edition/version marker makes them a
    revision, preventing dates and part numbers from becoming constraints.
    """
    found = {f"REV_{match.upper()}" for match in REVISION_LETTER.findall(text)}
    found.update(f"VERSION_{match}" for match in VERSION_NUMBER.findall(text))
    found.update(f"YEAR_{match}" for match in YEAR_EDITION.findall(text))
    return found


def requested_revisions(text: str) -> set[str]:
    value = text or ""
    matches = (EDITION_AFTER.findall(value) + EDITION_BEFORE.findall(value)
               + EDITION_FILE.findall(value) + EDITION_BARE.findall(value))
    return {match.upper() for match in matches} | _generic_revisions(value)


def document_revision(filename: object) -> str:
    text = str(filename or "")
    match = re.search(r"(?:_|\b)([A-Za-z]\d{2,4})(?=\.pdf$)", text, re.I)
    if match:
        return match.group(1).upper()
    generic = _generic_revisions(text.removesuffix(".pdf"))
    if generic:
        # A filename contains one final revision in this contract.  Preserve
        # deterministic behavior if an upstream title contains a date too.
        return sorted(generic)[-1]
    # Common filename spellings that omit the word 'version' but retain its
    # explicit marker: ``..._Rev_B.pdf`` and ``..._v2.pdf``.
    match = re.search(r"(?ix)(?:^|[_\-\s])v(?:ersion)?[_\-\s]?([0-9]+(?:\.[0-9]+)?)(?=\.pdf$)", text)
    if match:
        return f"VERSION_{match.group(1)}"
    match = re.search(r"(?ix)(?:^|[_\-\s])rev(?:ision)?[_\-\s.]?([A-Z])(?=\.pdf$)", text)
    if match:
        return f"REV_{match.group(1).upper()}"
    match = re.search(r"(?ix)(?:^|[_\-\s])((?:19|20)\d{2})(?:[_\-\s]?(?:edition|ed|판|개정판))?(?=\.pdf$)", text)
    if match:
        return f"YEAR_{match.group(1)}"
    return ""


# Deliberately narrower than the retrieval parser: this is only for linking
# an explicitly named edition to a part in the same clause.
_PART_TOKEN = re.compile(
    r"(?ix)(?<![A-Za-z0-9])"
    r"(?=[A-Z0-9_-]*[A-Z])(?=[A-Z0-9_-]*\d)"
    r"([A-Z0-9][A-Z0-9_-]{1,30}[A-Z0-9])"
    r"(?![A-Za-z0-9])"
)
_CLAUSE = re.compile(r"[^,;|\n]+")


def _revision_occurrences(text: str) -> list[tuple[int, int, str]]:
    """Return revision values and spans used for part/edition association."""
    occurrences: list[tuple[int, int, str]] = []
    for pattern in (EDITION_AFTER, EDITION_BEFORE, EDITION_FILE, EDITION_BARE):
        for match in pattern.finditer(text):
            occurrences.append((match.start(1), match.end(1), match.group(1).upper()))
    for match in REVISION_LETTER.finditer(text):
        occurrences.append((match.start(1), match.end(1), f"REV_{match.group(1).upper()}"))
    for match in VERSION_NUMBER.finditer(text):
        occurrences.append((match.start(1), match.end(1), f"VERSION_{match.group(1)}"))
    for match in YEAR_EDITION.finditer(text):
        occurrences.append((match.start(1), match.end(1), f"YEAR_{match.group(1)}"))
    unique: list[tuple[int, int, str]] = []
    seen: set[tuple[int, int, str]] = set()
    for item in sorted(occurrences):
        if item not in seen:
            unique.append(item)
            seen.add(item)
    return unique


def _part_revision_map(text: str) -> tuple[dict[str, set[str]], set[str]]:
    """Build unambiguous ``part -> revisions`` associations from clauses.

    A single edition shared by several explicitly named parts is a clear group
    clause. Several editions in one clause are ambiguous and are fail-closed.
    """
    value = text or ""
    mapped: dict[str, set[str]] = {}
    ambiguous: set[str] = set()
    source_clause: dict[str, int] = {}
    occurrences = _revision_occurrences(value)
    for clause in _CLAUSE.finditer(value):
        start, end = clause.span()
        revisions = [item for item in occurrences if start <= item[0] < end]
        if not revisions:
            continue
        revision_spans = {(item[0], item[1]) for item in revisions}
        parts: list[str] = []
        for match in _PART_TOKEN.finditer(clause.group(0)):
            absolute = (start + match.start(1), start + match.end(1))
            if absolute in revision_spans:
                continue
            part = match.group(1).upper()
            if part not in parts:
                parts.append(part)
        if not parts:
            continue
        values = {item[2] for item in revisions}
        # One named part with several explicitly requested editions is a
        # deliberate same-part comparison, not an unknown association.  Only
        # several parts and several editions in one clause are ambiguous.
        if len(values) > 1 and len(parts) > 1:
            ambiguous.update(parts)
            continue
        for part in parts:
            prior = mapped.setdefault(part, set())
            prior.update(values)
            if len(prior) > 1 and source_clause.get(part, start) != start:
                ambiguous.add(part)
            source_clause.setdefault(part, start)
    # When the whole question names only one part, separate clauses with
    # different editions are still an intentional same-part comparison.  Keep
    # the fail-closed rule for multi-part questions where the association is
    # genuinely unknown.
    parts_seen = set(mapped) | ambiguous
    if ambiguous and len(parts_seen) == 1:
        ambiguous.clear()
    return mapped, ambiguous


def revisions_for_part(text: str, part: str) -> set[str] | None:
    """Return editions explicitly associated with ``part``.

    ``None`` means no single safe association exists. A single global edition
    remains compatible with the historical single-part API; multiple global
    editions require an explicit association.
    """
    key = str(part or "").strip().upper()
    if not key:
        return None
    mapped, ambiguous = _part_revision_map(text or "")
    if key in ambiguous:
        return None
    if key in mapped:
        return set(mapped[key])
    global_revisions = requested_revisions(text or "")
    return set(global_revisions) if len(global_revisions) == 1 else None


def revision_matches(
    text: str,
    filename: object,
    doc_parts: Iterable[object] | None = None,
    requested_parts: Iterable[object] | None = None,
) -> bool:
    """Check an edition without crossing part-specific associations.

    Unknown or ambiguous part/edition associations are rejected rather than
    guessed. With no explicit edition, the document is accepted.
    """
    requested = requested_revisions(text or "")
    if not requested:
        return True
    document = document_revision(filename)
    if not document:
        return False
    doc_keys = {str(part).strip().upper() for part in (doc_parts or ()) if str(part).strip()}
    asked_keys = {str(part).strip().upper() for part in (requested_parts or ()) if str(part).strip()}
    if asked_keys and doc_keys and not (asked_keys & doc_keys):
        return False

    mapped, ambiguous = _part_revision_map(text or "")
    candidates = (doc_keys & asked_keys) if asked_keys else set(doc_keys)
    if candidates:
        known = [part for part in candidates if part in mapped or part in ambiguous]
        if known:
            if any(part in ambiguous or document not in mapped.get(part, set()) for part in known):
                return False
            return True

    # Legacy locators may not carry ``doc_parts``.  A single explicitly
    # requested edition is still a safe global constraint; part selection is
    # performed by the caller's normal document/part filter.
    if not doc_keys and len(requested) == 1:
        return document in requested

    # Without document metadata, only one named association is safe.
    if mapped or ambiguous:
        if len(mapped) + len(ambiguous) != 1:
            return False
        only_part = next(iter(mapped or ambiguous))
        return only_part not in ambiguous and document in mapped[only_part]

    # Preserve the original single-edition behavior; a global set has no safe
    # way to choose among part-specific documents.
    return len(requested) == 1 and document in requested
