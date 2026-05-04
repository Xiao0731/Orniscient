"""Parse AviList checklist rows."""

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

EXPECTED_SHEET = "AviList v2025 extended"
REQUIRED_COLUMNS = {
    "Taxon_rank",
    "Order",
    "Family",
    "Family_English_name",
    "Scientific_name",
    "English_name_AviList",
    "English_name_Clements_v2024",
    "Proposal_number",
    "Decision_summary",
    "Range",
    "IUCN_Red_List_Category",
    "Species_code_Cornell_Lab",
    "Birds_of_the_World_URL",
    "AvibaseID",
}


def parse_avilist_xlsx(
    input_path: str | Path,
    output_path: str | Path,
    release: str,
) -> tuple[list[dict], str]:
    file_path = Path(input_path)
    xl = pd.ExcelFile(file_path)
    if EXPECTED_SHEET not in xl.sheet_names:
        raise ValueError(f"AviList sheet '{EXPECTED_SHEET}' not found in {file_path}. Available: {xl.sheet_names}")
    df = pd.read_excel(file_path, sheet_name=EXPECTED_SHEET)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"AviList missing required columns: {sorted(missing)}")

    rows: list[dict] = []
    for raw in df.fillna("").to_dict(orient="records"):
        scientific_name = normalize_scientific_name(raw["Scientific_name"])
        rank = normalize_rank(raw["Taxon_rank"])
        rows.append(
            {
                "source": "AviList",
                "release": release,
                "rank": rank,
                "order_name": normalize_order_name(raw["Order"]),
                "family_name": normalize_family_name(raw["Family"]),
                "family_english_name": normalize_english_name(raw["Family_English_name"]),
                "scientific_name": scientific_name,
                "english_name_primary": normalize_english_name(raw["English_name_AviList"]),
                "english_name_clements_v2024": normalize_english_name(raw["English_name_Clements_v2024"]),
                "proposal_number": str(raw["Proposal_number"]).strip(),
                "decision_summary": str(raw["Decision_summary"]).strip(),
                "range_text": str(raw["Range"]).strip(),
                "iucn_status": str(raw["IUCN_Red_List_Category"]).strip(),
                "cornell_species_code": normalize_code(raw["Species_code_Cornell_Lab"]),
                "bow_url": str(raw["Birds_of_the_World_URL"]).strip(),
                "avibase_id": normalize_avibase_id(raw["AvibaseID"]),
                "genus_name": extract_genus_from_scientific_name(scientific_name),
            }
        )
    write_jsonl(output_path, rows)
    return rows, EXPECTED_SHEET
