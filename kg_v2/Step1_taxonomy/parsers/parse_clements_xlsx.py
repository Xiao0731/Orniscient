"""Parse Clements checklist rows from the first sheet."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from kg_v2.Step1_taxonomy.common import write_jsonl
from kg_v2.Step1_taxonomy.parsers.normalize_taxonomy_names import (
    extract_genus_from_scientific_name,
    normalize_avibase_id,
    normalize_code,
    normalize_english_name,
    normalize_family_name,
    normalize_order_name,
    normalize_rank,
    normalize_scientific_name,
)

REQUIRED_COLUMNS = {
    "species_code",
    "taxon concept ID",
    "Clements v2025 change",
    "text for website v2025",
    "category",
    "English name",
    "scientific name",
    "range",
    "order",
    "family",
}


def parse_clements_xlsx(
    input_path: str | Path,
    output_path: str | Path,
    release: str,
) -> tuple[list[dict], str]:
    file_path = Path(input_path)
    xl = pd.ExcelFile(file_path)
    if not xl.sheet_names:
        raise ValueError(f"No sheets found in {file_path}")
    sheet_name = xl.sheet_names[0]
    df = pd.read_excel(file_path, sheet_name=sheet_name)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Clements missing required columns: {sorted(missing)}")

    rows: list[dict] = []
    for raw in df.fillna("").to_dict(orient="records"):
        rank = normalize_rank(raw["category"])
        scientific_name = normalize_scientific_name(raw["scientific name"])
        normalized_row = {
            "source": "Clements",
            "release": release,
            "rank": rank,
            "species_code": normalize_code(raw["species_code"]),
            "external_id": normalize_avibase_id(raw["taxon concept ID"]),
            "change_note": str(raw["Clements v2025 change"]).strip(),
            "website_note": str(raw["text for website v2025"]).strip(),
            "english_name": normalize_english_name(raw["English name"]),
            "scientific_name": scientific_name,
            "range_text": str(raw["range"]).strip(),
            "order_name": normalize_order_name(raw["order"]),
            "family_name": normalize_family_name(raw["family"]),
            "genus_name": extract_genus_from_scientific_name(scientific_name),
        }
        meaningful = any(
            normalized_row.get(field)
            for field in ("rank", "species_code", "external_id", "scientific_name", "english_name", "family_name", "order_name")
        )
        if meaningful:
            rows.append(normalized_row)
    write_jsonl(output_path, rows)
    return rows, sheet_name
