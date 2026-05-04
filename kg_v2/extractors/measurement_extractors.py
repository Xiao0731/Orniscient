"""Numeric measurement extraction for V2.1 claims."""

from __future__ import annotations

import re

_RANGE = r"(?P<min>\d+(?:\.\d+)?)\s*(?:-|to|–|—)\s*(?P<max>\d+(?:\.\d+)?)"
_VALUE = r"(?P<value>\d+(?:\.\d+)?)"

MEASUREMENT_PATTERNS = [
    ("BODY_LENGTH", re.compile(rf"{_RANGE}\s*cm\b", flags=re.IGNORECASE), "cm"),
    ("BODY_LENGTH", re.compile(rf"{_VALUE}\s*cm\b", flags=re.IGNORECASE), "cm"),
    ("BODY_MASS", re.compile(rf"{_RANGE}\s*kg\b", flags=re.IGNORECASE), "kg"),
    ("BODY_MASS", re.compile(rf"{_VALUE}\s*kg\b", flags=re.IGNORECASE), "kg"),
    ("BODY_MASS", re.compile(rf"{_RANGE}\s*g\b", flags=re.IGNORECASE), "g"),
    ("BODY_MASS", re.compile(rf"{_VALUE}\s*g\b", flags=re.IGNORECASE), "g"),
    ("ELEVATION_RANGE", re.compile(rf"(?:elevation|altitude)[^\d]{{0,20}}{_RANGE}\s*m\b", flags=re.IGNORECASE), "m"),
    ("CLUTCH_SIZE", re.compile(rf"(?:lay|lays?|clutch(?: of)?)[^\d]{{0,20}}{_RANGE}\s*eggs?\b", flags=re.IGNORECASE), "eggs"),
    ("CLUTCH_SIZE", re.compile(rf"(?:lay|lays?|clutch(?: of)?)[^\d]{{0,20}}{_VALUE}\s*eggs?\b", flags=re.IGNORECASE), "eggs"),
    ("INCUBATION_PERIOD", re.compile(rf"(?:incubation|incubate[sd]?)[^\d]{{0,30}}{_RANGE}\s*days?\b", flags=re.IGNORECASE), "days"),
    ("INCUBATION_PERIOD", re.compile(rf"(?:incubation|incubate[sd]?)[^\d]{{0,30}}{_VALUE}\s*days?\b", flags=re.IGNORECASE), "days"),
    ("FLEDGING_PERIOD", re.compile(rf"(?:fledg(?:ing)? period|fledge[sd]?)[^\d]{{0,30}}{_RANGE}\s*(?:days?|months?)\b", flags=re.IGNORECASE), None),
    ("LIFESPAN", re.compile(rf"(?:life expectancy|lifespan)[^\d]{{0,20}}{_RANGE}\s*years?\b", flags=re.IGNORECASE), "years"),
]


def extract_measurements(text: str) -> list[dict]:
    results: list[dict] = []
    source = text or ""
    covered_spans: list[tuple[int, int]] = []
    for predicate, pattern, default_unit in MEASUREMENT_PATTERNS:
        for match in pattern.finditer(source):
            span = match.span()
            if any(span[0] >= start and span[1] <= end for start, end in covered_spans):
                continue
            if match.groupdict().get("min") is not None and match.groupdict().get("max") is not None:
                value_min = float(match.group("min"))
                value_max = float(match.group("max"))
                value_text = match.group(0)
                covered_spans.append(span)
            else:
                value_min = float(match.group("value"))
                value_max = float(match.group("value"))
                value_text = match.group(0)
            unit = default_unit
            if unit is None:
                unit_match = re.search(r"(days?|months?|years?)", match.group(0), flags=re.IGNORECASE)
                unit = unit_match.group(1).lower() if unit_match else None
            results.append(
                {
                    "predicate": predicate,
                    "value_type": "numeric",
                    "value_min": value_min,
                    "value_max": value_max,
                    "value_text": value_text,
                    "unit": unit,
                    "qualifiers": {},
                }
            )
    unique: dict[tuple[str, float, float, str | None], dict] = {}
    for result in results:
        key = (result["predicate"], result["value_min"], result["value_max"], result["unit"])
        unique.setdefault(key, result)
    return list(unique.values())
