"""Chapter detection, heading recognition, and chapter normalization."""

from __future__ import annotations

import re
from typing import Callable

from kg_v2.schema.aspect_taxonomy import normalize_family_chapter, normalize_species_chapter, normalize_species_subchapter

EXPLICIT_CHAPTER_COLUMNS = ("Chapter", "chapter", "Section", "section", "Title", "title")

_KNOWN_HEADING_PATTERNS = [
    r"Introduction",
    r"Field Identification",
    r"Identification",
    r"Plumages, Molts, and Structure",
    r"Systematics(?: History)?",
    r"Systematicas History",
    r"Subspecies",
    r"Geographic Variation",
    r"Distribution",
    r"General Habitat",
    r"Habitat",
    r"Movements and Migration",
    r"Migration",
    r"Diet and Foraging",
    r"Sounds and Vocal Behavior",
    r"Behavior",
    r"Breeding",
    r"Demography and Populations",
    r"Conservation(?: Status| and Management)?",
    r"Relationships with People",
    r"Priorities for Future Research",
    r"Other",
    r"Acknowledgements",
    r"About the Author\(s\)",
]
_KNOWN_HEADING_RE = re.compile(rf"^\s*(?:{'|'.join(_KNOWN_HEADING_PATTERNS)})\s*$", flags=re.IGNORECASE)


def is_probable_heading_row(text: str) -> bool:
    candidate = re.sub(r"\s+", " ", (text or "").strip())
    if not candidate:
        return False
    if _KNOWN_HEADING_RE.fullmatch(candidate):
        return True
    if len(candidate) > 80:
        return False
    if any(char in candidate for char in ".!?;:"):
        return False
    if re.search(r"\d{4}", candidate):
        return False
    words = candidate.split()
    if not words or len(words) > 8:
        return False
    return all(word[:1].isupper() or word.isupper() for word in words if word)


def get_explicit_chapter_value(row: dict) -> str:
    for column in EXPLICIT_CHAPTER_COLUMNS:
        value = str(row.get(column, "") or "").strip()
        if value:
            return value
    return ""


def normalize_chapter(raw_name: str, level: str) -> str:
    if level == "family":
        return normalize_family_chapter(raw_name)
    return normalize_species_chapter(raw_name)


def split_text_into_sections(
    text: str,
    level: str,
    default_chapter_raw: str | None = None,
    fallback_chapter_raw: str | None = None,
) -> list[dict]:
    """Split a text block into chapter-aware segments."""

    raw_text = (text or "").replace("\r", "\n")
    lines = raw_text.split("\n")
    segments: list[dict] = []
    current_raw = default_chapter_raw or fallback_chapter_raw or "Unknown"
    current_subchapter = "Unknown"
    current_lines: list[str] = []
    found_heading = False

    def flush() -> None:
        body = "\n".join(current_lines).strip()
        if not body:
            return
        normalized = normalize_chapter(current_raw, level)
        segments.append(
            {
                "source_chapter_raw": current_raw if current_raw else "Unknown",
                "source_chapter": normalized if normalized != "Unknown" else "Unknown",
                "source_subchapter": current_subchapter if current_subchapter else "Unknown",
                "raw_text": body,
            }
        )

    for line in lines:
        stripped = re.sub(r"\s+", " ", line.strip())
        if not stripped:
            if current_lines:
                current_lines.append("")
            continue
        if is_probable_heading_row(stripped):
            normalized_heading = normalize_chapter(stripped, level)
            flush()
            current_lines = []
            if normalized_heading != "Unknown":
                current_raw = stripped
                current_subchapter = "Unknown"
            else:
                current_subchapter = normalize_species_subchapter(stripped, parent_chapter=normalize_chapter(current_raw, level))
            found_heading = True
            continue
        current_lines.append(line.strip())

    flush()
    if segments:
        return segments
    if found_heading:
        return []
    fallback = default_chapter_raw or fallback_chapter_raw or "Unknown"
    normalized = normalize_chapter(fallback, level)
    return [
        {
            "source_chapter_raw": fallback,
            "source_chapter": normalized if normalized != "Unknown" else "Unknown",
            "source_subchapter": "Unknown",
            "raw_text": raw_text.strip(),
        }
    ]


def choose_normalizer(level: str) -> Callable[[str], str]:
    return normalize_family_chapter if level == "family" else normalize_species_chapter
