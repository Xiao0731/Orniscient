from __future__ import annotations

import re
from functools import lru_cache
from typing import Any, Iterable

import pandas as pd

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "their",
    "them", "have", "has", "had", "are", "was", "were", "been", "being",
    "will", "would", "could", "should", "about", "across", "which", "what",
    "when", "where", "who", "whose", "while", "during", "among", "within",
    "based", "using", "according", "identify", "species", "bird", "birds",
    "family", "order", "return", "only", "strict", "json", "below", "these",
    "those", "most", "more", "less", "than", "into", "over", "under", "also",
}

IMPORTANT_QUERY_WEIGHTS = {
    "habitat": 2.0,
    "diet": 2.0,
    "island": 2.0,
    "endangered": 2.0,
    "family": 2.0,
    "order": 2.0,
    "range": 1.8,
    "migration": 1.8,
    "migratory": 1.8,
    "wetland": 1.8,
    "forest": 1.6,
    "savanna": 1.6,
    "grassland": 1.6,
    "riparian": 1.8,
    "realm": 1.5,
    "nearctic": 1.8,
    "neotropics": 1.8,
    "critical": 1.5,
    "critically": 2.0,
    "threatened": 1.8,
    "vulnerable": 1.8,
    "flightless": 1.8,
    "nocturnal": 1.8,
    "coastal": 1.6,
    "montane": 1.6,
    "river": 1.5,
}


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_colname(name: str) -> str:
    text = clean_text(name).lower()
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def _dedupe_column_names(names: Iterable[str]) -> list[str]:
    seen: dict[str, int] = {}
    output: list[str] = []
    for raw_name in names:
        name = clean_text(raw_name) or "unnamed"
        count = seen.get(name, 0)
        seen[name] = count + 1
        output.append(name if count == 0 else f"{name}_{count + 1}")
    return output


def _looks_like_embedded_header_row(df: pd.DataFrame) -> bool:
    if df.empty:
        return False
    first_row = [clean_text(value) for value in df.iloc[0].tolist()]
    nonempty = [value for value in first_row if value]
    if len(nonempty) < max(6, len(df.columns) // 4):
        return False
    unnamed_ratio = sum(1 for column in df.columns if str(column).lower().startswith("unnamed")) / max(1, len(df.columns))
    header_markers = {
        "order", "family", "species", "source", "primary habitat", "primary diet",
        "english name", "latin", "genus", "taxonomy", "migration",
    }
    marker_hits = sum(1 for value in nonempty if clean_text(value).lower() in header_markers)
    return unnamed_ratio >= 0.25 and marker_hits >= 4


@lru_cache(maxsize=8)
def load_excel_table(path: str) -> pd.DataFrame:
    """
    Load an Excel table with lightweight header normalization and caching.

    BIRDBASE stores an extra embedded header row under generic column names.
    When detected, we merge the top-level Excel header and the first data row
    into more informative column labels, then drop that embedded header row.
    """

    df = pd.read_excel(path, dtype=str)
    df = df.fillna("")
    df.columns = [clean_text(column) for column in df.columns]

    if _looks_like_embedded_header_row(df):
        embedded = df.iloc[0].to_dict()
        merged_names: list[str] = []
        for column in df.columns:
            top = clean_text(column)
            sub = clean_text(embedded.get(column, ""))
            if sub:
                if top.lower().startswith("unnamed"):
                    merged_names.append(sub)
                elif normalize_colname(top) == normalize_colname(sub):
                    merged_names.append(top)
                else:
                    merged_names.append(f"{top} {sub}")
            else:
                merged_names.append(top)
        df = df.iloc[1:].reset_index(drop=True)
        df.columns = _dedupe_column_names(merged_names)
    else:
        df.columns = _dedupe_column_names(df.columns)

    for column in df.columns:
        df[column] = df[column].map(clean_text)
    return df


def find_columns(df: pd.DataFrame, candidates: list[str]) -> list[str]:
    candidate_norms = [normalize_colname(candidate) for candidate in candidates if normalize_colname(candidate)]
    if not candidate_norms:
        return []

    matches: list[str] = []
    for column in df.columns:
        column_norm = normalize_colname(column)
        if any(column_norm == candidate or candidate in column_norm or column_norm in candidate for candidate in candidate_norms):
            matches.append(column)
    return matches


def get_first_existing_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    matches = find_columns(df, candidates)
    return matches[0] if matches else None


def tokenize_query(text: str) -> list[str]:
    lowered = clean_text(text).lower()
    tokens = re.findall(r"[a-z][a-z\-]{2,}", lowered)
    filtered = [token for token in tokens if token not in STOPWORDS and len(token) >= 3]
    deduped: list[str] = []
    seen: set[str] = set()
    for token in filtered:
        if token not in seen:
            seen.add(token)
            deduped.append(token)
    return deduped


def score_row_by_query(row_text: str, query_tokens: list[str]) -> float:
    text = clean_text(row_text).lower()
    if not text:
        return 0.0

    score = 0.0
    for token in query_tokens:
        if token in text:
            score += IMPORTANT_QUERY_WEIGHTS.get(token, 1.0)
            occurrences = text.count(token)
            if occurrences > 1:
                score += min(0.6, 0.1 * (occurrences - 1))

    phrases = [" ".join(query_tokens[idx: idx + 2]) for idx in range(max(0, len(query_tokens) - 1))]
    for phrase in phrases:
        if phrase and phrase in text:
            score += 1.2
    return score


def render_table_rows(
    rows: list[dict[str, Any]],
    columns: list[str],
    max_rows: int,
    max_cell_chars: int,
    header: str,
) -> str:
    if not rows:
        return header

    lines = [header]
    for index, row in enumerate(rows[:max_rows], start=1):
        lines.append(f"{index}.")
        for column in columns:
            value = clean_text(row.get(column, ""))
            if not value:
                continue
            if max_cell_chars > 0 and len(value) > max_cell_chars:
                value = value[:max_cell_chars].rstrip() + "..."
            lines.append(f"   {column}: {value}")
    return "\n".join(lines)
