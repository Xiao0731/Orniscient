"""Reusable text normalization helpers."""

from __future__ import annotations

import re

_VISUAL_PATTERNS = (
    r"\b[Ff]ig\.?\s*\d+[A-Za-z-]*",
    r"\b[Pp]late\s*\d+[A-Za-z-]*",
    r"\b[Pp]hoto\b",
    r"\b[Vv]ideo\b",
    r"\b[Mm]acaulay Library\b",
)

_CITATION_PATTERNS = (
    r"\(\s*[A-Z][A-Za-z'’`-]+(?: et al\.)?,\s*\d{4}[a-z]?\s*\)",
    r"\[\s*\d+(?:\s*,\s*\d+)*\s*\]",
    r"\bClose\b",
)


def normalize_unicode_punctuation(text: str) -> str:
    replacements = {
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u00a0": " ",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def strip_visual_markers(text: str) -> str:
    for pattern in _VISUAL_PATTERNS:
        text = re.sub(pattern, " ", text)
    return text


def strip_inline_citations(text: str) -> str:
    for pattern in _CITATION_PATTERNS:
        text = re.sub(pattern, " ", text)
    text = re.sub(r"\(\s*\d+(?:\s*,\s*\d+)*\s*\)", " ", text)
    return text


def collapse_whitespace(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def clean_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    cleaned = normalize_unicode_punctuation(text)
    cleaned = strip_visual_markers(cleaned)
    cleaned = strip_inline_citations(cleaned)
    cleaned = cleaned.replace("\t", " ")
    return collapse_whitespace(cleaned)
