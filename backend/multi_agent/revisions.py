"""Extract document-edition codes from user text without treating part numbers as editions."""
import re

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
