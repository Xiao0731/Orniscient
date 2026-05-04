from __future__ import annotations

from typing import Any

from table_kb_utils import clean_text, load_excel_table, render_table_rows, score_row_by_query, tokenize_query

FAMILY_TEXT_COLUMNS = [
    "Order",
    "Family",
    "Common_name",
    "Introduction",
    "GeneralHabitat",
    "DietandForaging",
    "Breeding",
    "ConservationStatus",
    "SystematicsHistory",
    "SystematicasHistory",
]


def retrieve_family_table_context(
    item: dict,
    order_xlsx: str,
    top_k: int = 12,
    max_cell_chars: int = 240,
) -> str:
    df = load_excel_table(order_xlsx)
    if df.empty:
        return "[NO_FAMILY_TABLE_CONTEXT]"

    available_columns = [column for column in FAMILY_TEXT_COLUMNS if column in df.columns]
    query_text = clean_text(item.get("question", ""))
    query_tokens = tokenize_query(query_text)

    scored_rows: list[tuple[float, dict[str, Any]]] = []
    for row in df.to_dict(orient="records"):
        row_text = " | ".join(
            f"{column}: {clean_text(row.get(column, ''))}"
            for column in available_columns
            if clean_text(row.get(column, ""))
        )
        score = score_row_by_query(row_text, query_tokens)
        if score <= 0:
            continue

        compact_row = {
            "Order": clean_text(row.get("Order", "")),
            "Family": clean_text(row.get("Family", "")),
            "Common name": clean_text(row.get("Common_name", "")),
            "Evidence": " | ".join(
                f"{label}: {clean_text(row.get(source, ''))}"
                for label, source in (
                    ("Introduction", "Introduction"),
                    ("Habitat", "GeneralHabitat"),
                    ("Diet", "DietandForaging"),
                    ("Breeding", "Breeding"),
                    ("Conservation", "ConservationStatus"),
                    ("Systematics", "SystematicsHistory" if "SystematicsHistory" in row else "SystematicasHistory"),
                )
                if clean_text(row.get(source, ""))
            ),
        }
        scored_rows.append((score, compact_row))

    scored_rows.sort(key=lambda pair: pair[0], reverse=True)
    top_rows = [row for _, row in scored_rows[:max(1, int(top_k))]]
    if not top_rows:
        return "[NO_FAMILY_TABLE_CONTEXT]"

    header = "\n".join(
        [
            "[Family-level Table-KB Context]",
            "The following candidate families are retrieved from Order.xlsx according to the diagnostic features in the question.",
        ]
    )
    return render_table_rows(
        top_rows,
        ["Order", "Family", "Common name", "Evidence"],
        max_rows=top_k,
        max_cell_chars=max_cell_chars,
        header=header,
    )
