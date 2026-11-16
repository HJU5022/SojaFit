"""Fail-closed English/Korean gate for complete PDF page text.

The caller supplies all extracted pages in memory. URLs, filenames, and page
numbers are intentionally not used as language evidence.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from langid.langid import LanguageIdentifier, model

_WORD = re.compile(r"[A-Za-z]{2,}|[가-힣]{2,}")
_TECHNICAL_GREEK = frozenset("µμΩΩΔαβγδθπτ")
_POSITIVE = frozenset({"en", "ko"})
_MIN_PROBABILITY = 0.90


@lru_cache(maxsize=1)
def _identifier() -> LanguageIdentifier:
    # Do not restrict the model to en/ko: doing so would force French/German/
    # Spanish prose into one of the allowed labels.
    return LanguageIdentifier.from_modelstring(model, norm_probs=True)


def _script_flags(text: str) -> tuple[bool, int]:
    foreign = False
    greek_symbols = 0
    for char in text:
        if not unicodedata.category(char).startswith("L"):
            continue
        name = unicodedata.name(char, "")
        if "HANGUL" in name:
            continue
        elif char in _TECHNICAL_GREEK:
            greek_symbols += 1
        elif "LATIN" in name or ("A" <= char <= "Z") or ("a" <= char <= "z"):
            continue
        else:
            # CJK, kana, Cyrillic, Arabic, and other foreign scripts are not
            # accepted. Technical Greek symbols are handled above.
            foreign = True
    return foreign, greek_symbols


def _classify(text: str) -> tuple[str, float] | None:
    letters = [char for char in text if unicodedata.category(char).startswith("L")]
    if len(letters) < 20:
        return None
    label, probability = _identifier().classify(text)
    return label, probability


def _prose_spans(page: str) -> list[str]:
    """Extract sufficiently long prose spans while ignoring table fragments."""
    spans: list[str] = []

    def is_symbol_heavy(text: str) -> bool:
        letters = [c for c in text if unicodedata.category(c).startswith("L")]
        greek = sum(c in _TECHNICAL_GREEK for c in text)
        # A line dominated by Greek unit/symbol tokens is a technical row, not
        # prose. It is allowed globally but must not become language evidence.
        return greek >= 3 and greek / max(1, len(letters)) > 0.08

    def is_prose_candidate(text: str) -> bool:
        if is_symbol_heavy(text):
            return False
        letters = [c for c in text if unicodedata.category(c).startswith("L")]
        words = _WORD.findall(text)
        if len(letters) < 24 or len(words) < 4:
            return False
        # pdfplumber often removes paragraph blank lines. Several lowercase
        # words distinguish prose from title-case figure captions, copyright
        # lines, all-cap tables, and package/diagram rows. Sentence punctuation
        # alone is not enough because decimal-heavy diagrams contain periods.
        lowercase_words = re.findall(r"\b[a-z][a-z'-]{2,}\b", text)
        return (
            len(lowercase_words) >= 5
            or (len(lowercase_words) >= 4 and bool(re.search(r"[!?]|\.$", text)))
            or any("가" <= c <= "힣" for c in text)
        )

    def is_layout_fragment(text: str) -> bool:
        """Exclude table/figure/package strings before language classification."""
        lower = text.casefold()
        layout_terms = (
            "package outline", "board layout", "stencil design", "figure ",
            "copyright", "style ", "characteristic symbol max unit",
            "sot-", "to-92", "to-can", "seating plane", "scale ",
            "publication ipc", "ipc-7351",
        )
        if any(term in lower for term in layout_terms):
            return True
        if "|" in text and any(term in lower for term in ("status", "package", "carrier", "rohs", "part marking")):
            return True
        words = _WORD.findall(text)
        if not words:
            return True
        digit_count = sum(char.isdigit() for char in text)
        # Numeric-heavy rows and pin/package labels are not prose evidence.
        return digit_count >= 6

    for paragraph in re.split(r"\n\s*\n", page):
        lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
        if not lines:
            continue
        joined = " ".join(lines)
        # PDF text often has no blank line between paragraphs. Split sentence
        # boundaries first so a short foreign sentence appended to a long
        # English paragraph cannot be diluted by the English text.
        sentence_parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", joined) if part.strip()]
        candidates = sentence_parts if len(sentence_parts) > 1 else [joined]
        sentence_spans = [part for part in candidates if is_prose_candidate(part) and not is_layout_fragment(part)]
        if sentence_spans:
            spans.extend(sentence_spans)
            continue
        for line in lines:
            if is_prose_candidate(line) and not is_layout_fragment(line):
                spans.append(line)
    return spans


def language_for_pages(texts: list[str]) -> str | None:
    """Classify all extracted pages as ``en``, ``ko``, ``en-ko``, or reject.

    Every sufficiently long prose span is checked, so a foreign paragraph on
    a later page cannot be hidden by a long English prefix. Sparse diagram and
    table pages contribute no positive language evidence; a document with no
    prose evidence is rejected. Korean technical documents may contain English
    manufacturer names, part numbers, units, and symbols.
    """
    if not isinstance(texts, list) or not texts or any(not isinstance(page, str) or not page.strip() for page in texts):
        return None
    pages = [unicodedata.normalize("NFKC", page) for page in texts]
    corpus = "\n".join(pages)
    foreign, greek_count = _script_flags(corpus)
    letters = [char for char in corpus if unicodedata.category(char).startswith("L")]
    if foreign or len(letters) < 20 or greek_count / max(1, len(letters)) > 0.25:
        return None

    labels: list[str] = []
    for page in pages:
        for span in _prose_spans(page):
            result = _classify(span)
            # Layout fragments were excluded before classification. An
            # uncertain natural-language span is therefore unknown and must
            # fail closed rather than silently pass behind English prose.
            if result is None or result[1] < _MIN_PROBABILITY:
                return None
            label, _ = result
            if label not in _POSITIVE:
                return None
            labels.append(label)
    if not labels:
        return None
    distinct = set(labels)
    return "en-ko" if distinct == _POSITIVE else next(iter(distinct))
