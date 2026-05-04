"""Parse species-level BOW Excel files into merged records and chapter chunks."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pandas as pd

from kg_v2.parsers.chapter_utils import get_explicit_chapter_value, is_probable_heading_row, split_text_into_sections
from kg_v2.parsers.normalize_labels import canonical_status
from kg_v2.parsers.normalize_text import clean_text
from kg_v2.schema.ontology_v2 import INTERMEDIATE_DIR, ensure_output_dirs, write_jsonl
from kg_v2.utils.taxonomy_utils import clean_bow_scientific_name


def _safe_text(value: object) -> str:
    if value is None:
        return ""
    if pd.isna(value):
        return ""
    return str(value).strip()


def _clean_species_name(value: object) -> str:
    raw = _safe_text(value).replace("\r", "\n")
    if not raw:
        return ""
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if "scientific name definitions" in line.lower():
            continue
        return " ".join(line.split())
    return ""


def _species_key(record: dict) -> tuple[str, str, str, str, str]:
    return (
        record["common_name"],
        record["species_name"],
        record["genus_name"],
        record["family_name"],
        record["order_name"],
    )


def parse_species_file(file_path: str | Path) -> tuple[list[dict], list[dict]]:
    source_file = Path(file_path)
    df = pd.read_excel(source_file)
    for column in ["Common_name", "Species", "Genus", "Family", "Order", "Level"]:
        if column not in df.columns:
            df[column] = ""
    if "text" not in df.columns:
        raise ValueError(f"Missing required text column in {source_file}")

    df["Common_name"] = df["Common_name"].ffill()
    df["Species"] = df["Species"].ffill().astype(str).apply(clean_bow_scientific_name)
    df["Genus"] = df["Genus"].ffill()
    df["Family"] = df["Family"].ffill()
    df["Order"] = df["Order"].ffill()
    df["Level"] = df["Level"].ffill()

    grouped_segments: dict[tuple[str, str, str, str, str], list[dict]] = defaultdict(list)
    grouped_meta: dict[tuple[str, str, str, str, str], dict] = {}
    chunk_counter = 0
    chapter_context: dict[tuple[str, str, str, str, str], str] = {}

    for _, row in df.iterrows():
        record = {
            "common_name": _safe_text(row.get("Common_name")),
            "species_name": _clean_species_name(row.get("Species")),
            "genus_name": _safe_text(row.get("Genus")),
            "family_name": _safe_text(row.get("Family")),
            "order_name": _safe_text(row.get("Order")),
            "iucn_status": canonical_status(_safe_text(row.get("Level"))),
        }
        if not record["common_name"] and not record["species_name"]:
            continue
        key = _species_key(record)
        grouped_meta[key] = record

        explicit_chapter = get_explicit_chapter_value(row.to_dict())
        raw_text = _safe_text(row.get("text"))
        if not raw_text:
            continue

        if explicit_chapter:
            chapter_context[key] = explicit_chapter

        if not explicit_chapter and is_probable_heading_row(raw_text):
            chapter_context[key] = raw_text.strip()
            continue

        sections = split_text_into_sections(
            raw_text,
            level="species",
            default_chapter_raw=explicit_chapter or chapter_context.get(key),
            fallback_chapter_raw="Unknown",
        )
        for section in sections:
            text_block = clean_text(section["raw_text"])
            if not text_block:
                continue
            chapter_raw = section["source_chapter_raw"] or "Unknown"
            chapter_context[key] = chapter_raw
            chunk_counter += 1
            grouped_segments[key].append(
                {
                    "chunk_id": f"species_chunk_{chunk_counter:08d}",
                    **record,
                    "source_db": "BOW",
                    "source_file": source_file.name,
                    "source_chapter": section["source_chapter"] or "Unknown",
                    "source_subchapter": section.get("source_subchapter", "Unknown"),
                    "source_chapter_raw": chapter_raw,
                    "raw_text": text_block,
                }
            )

    merged_records: list[dict] = []
    merged_chunks: list[dict] = []
    for key, segments in grouped_segments.items():
        meta = grouped_meta[key]
        chapter_buckets: dict[tuple[str, str, str], list[str]] = defaultdict(list)
        for segment in segments:
            chapter_key = (
                segment["source_chapter"],
                segment.get("source_subchapter", "Unknown"),
                segment["source_chapter_raw"],
            )
            chapter_buckets[chapter_key].append(segment["raw_text"])
        full_text_parts: list[str] = []
        for chapter_index, ((source_chapter, source_subchapter, source_chapter_raw), texts) in enumerate(chapter_buckets.items(), start=1):
            merged_text = "\n\n".join(texts).strip()
            merged_chunks.append(
                {
                    "chunk_id": f"{meta['species_name'] or meta['common_name']}::{chapter_index}",
                    **meta,
                    "source_db": "BOW",
                    "source_file": source_file.name,
                    "source_chapter": source_chapter or "Unknown",
                    "source_subchapter": source_subchapter or "Unknown",
                    "source_chapter_raw": source_chapter_raw or "Unknown",
                    "raw_text": merged_text,
                }
            )
            heading = source_chapter if source_chapter and source_chapter != "Unknown" else source_chapter_raw
            full_text_parts.append(f"{heading}\n{merged_text}".strip())
        merged_records.append({**meta, "full_text": "\n\n".join(full_text_parts).strip()})

    return merged_records, merged_chunks


def parse_species_xlsx_files(
    bow_dir: str | Path = "data/BOW",
    limit_files: int | None = None,
    species_limit: int | None = None,
) -> tuple[list[dict], list[dict]]:
    ensure_output_dirs()
    all_records: list[dict] = []
    all_chunks: list[dict] = []
    for file_index, path in enumerate(sorted(Path(bow_dir).glob("*.xlsx")), start=1):
        if limit_files is not None and file_index > limit_files:
            break
        records, chunks = parse_species_file(path)
        all_records.extend(records)
        all_chunks.extend(chunks)
        if species_limit is not None and len(all_records) >= species_limit:
            all_records = all_records[:species_limit]
            allowed_species = {record["species_name"] for record in all_records}
            all_chunks = [chunk for chunk in all_chunks if chunk["species_name"] in allowed_species]
            break

    write_jsonl(INTERMEDIATE_DIR / "species_records.jsonl", all_records)
    write_jsonl(INTERMEDIATE_DIR / "species_chunks.jsonl", all_chunks)
    return all_records, all_chunks


if __name__ == "__main__":
    parse_species_xlsx_files()
