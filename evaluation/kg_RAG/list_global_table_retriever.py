from __future__ import annotations

from typing import Any

from table_kb_utils import (
    clean_text,
    get_first_existing_col,
    load_excel_table,
    render_table_rows,
    score_row_by_query,
    tokenize_query,
)

COMMON_NAME_CANDIDATES = [
    "english name",
    "common name",
    "taxonomy english name",
]
SCIENTIFIC_NAME_CANDIDATES = [
    "latin",
    "scientific name",
    "species id latin",
]
ORDER_CANDIDATES = ["order"]
FAMILY_CANDIDATES = ["family", "family ioc"]
IUCN_CANDIDATES = ["iucn", "red list", "conservation status"]
PRIMARY_HABITAT_CANDIDATES = ["primary habitat", "habitat"]
PRIMARY_DIET_CANDIDATES = ["primary diet", "diet"]


def _row_to_search_text(row: dict[str, Any]) -> str:
    return " | ".join(
        f"{column}: {value}"
        for column, value in row.items()
        if clean_text(value)
    )


def _build_compact_row(row: dict[str, Any], query_tokens: list[str], max_cell_chars: int) -> dict[str, Any]:
    common_col = get_first_existing_col_cached(row, COMMON_NAME_CANDIDATES)
    scientific_col = get_first_existing_col_cached(row, SCIENTIFIC_NAME_CANDIDATES)
    order_col = get_first_existing_col_cached(row, ORDER_CANDIDATES)
    family_col = get_first_existing_col_cached(row, FAMILY_CANDIDATES)
    iucn_col = get_first_existing_col_cached(row, IUCN_CANDIDATES)
    habitat_col = get_first_existing_col_cached(row, PRIMARY_HABITAT_CANDIDATES)
    diet_col = get_first_existing_col_cached(row, PRIMARY_DIET_CANDIDATES)

    search_text = _row_to_search_text(row).lower()
    matched_fields: list[str] = []
    for label, column_name in (
        ("Habitat", habitat_col),
        ("Diet", diet_col),
        ("IUCN", iucn_col),
        ("Order", order_col),
        ("Family", family_col),
    ):
        if column_name and any(token in clean_text(row.get(column_name, "")).lower() for token in query_tokens):
            matched_fields.append(f"{label}: {clean_text(row.get(column_name, ''))}")

    compact_row = {
        "Scientific name": clean_text(row.get(scientific_col, "")) if scientific_col else "",
        "Common name": clean_text(row.get(common_col, "")) if common_col else "",
        "Order": clean_text(row.get(order_col, "")) if order_col else "",
        "Family": clean_text(row.get(family_col, "")) if family_col else "",
        "IUCN": clean_text(row.get(iucn_col, "")) if iucn_col else "",
        "Primary habitat": clean_text(row.get(habitat_col, "")) if habitat_col else "",
        "Primary diet": clean_text(row.get(diet_col, "")) if diet_col else "",
        "Matched fields": "; ".join(matched_fields),
        "_search_text": search_text,
    }
    return compact_row


def get_first_existing_col_cached(row: dict[str, Any], candidates: list[str]) -> str | None:
    for column in row.keys():
        lowered = clean_text(column).lower()
        if any(candidate in lowered for candidate in candidates):
            return column
    return None


def retrieve_list_global_table_context(
    item: dict,
    birdbase_xlsx: str,
    top_k: int = 80,
    max_cell_chars: int = 160,
) -> str:
    df = load_excel_table(birdbase_xlsx)
    if df.empty:
        return "[NO_TABLE_CONTEXT: no candidate rows from BIRDBASE]"

    query_parts = [clean_text(item.get("question", ""))]
    provenance = item.get("provenance", {}) or {}
    search_conditions = clean_text(provenance.get("search_conditions", ""))
    if search_conditions:
        query_parts.append(search_conditions)
    query_text = "\n".join(part for part in query_parts if part)
    query_tokens = tokenize_query(query_text)

    scored_rows: list[tuple[float, dict[str, Any]]] = []
    for row in df.to_dict(orient="records"):
        row_text = _row_to_search_text(row)
        score = score_row_by_query(row_text, query_tokens)
        if score <= 0:
            continue
        compact_row = _build_compact_row(row, query_tokens, max_cell_chars)
        scored_rows.append((score, compact_row))

    scored_rows.sort(key=lambda pair: pair[0], reverse=True)
    top_rows = [row for _, row in scored_rows[:max(1, int(top_k))]]
    if not top_rows:
        return "[NO_TABLE_CONTEXT: no candidate rows from BIRDBASE]"

    header = "\n".join(
        [
            "[Table-KB Context: BIRDBASE candidate rows]",
            "The following rows are retrieved from BIRDBASE according to the question constraints. Use them as open-book evidence, but return only species names required by the question.",
        ]
    )
    display_columns = [
        "Scientific name",
        "Common name",
        "Order",
        "Family",
        "IUCN",
        "Primary habitat",
        "Primary diet",
        "Matched fields",
    ]
    return render_table_rows(top_rows, display_columns, max_rows=top_k, max_cell_chars=max_cell_chars, header=header)
