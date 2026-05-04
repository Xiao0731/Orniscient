"""Parse family/order-level Excel data into merged records and chapter chunks."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pandas as pd

from kg_v2.parsers.chapter_utils import get_explicit_chapter_value, is_probable_heading_row, split_text_into_sections
from kg_v2.parsers.normalize_text import clean_text
from kg_v2.schema.aspect_taxonomy import normalize_family_chapter
from kg_v2.schema.ontology_v2 import INTERMEDIATE_DIR, ensure_output_dirs, write_jsonl

BASE_FAMILY_COLUMNS = {"Family", "family", "Order", "order", "Common_name", "common_name", "text"}


def _safe_text(value: object) -> str:
    if value is None:
        return ""
    if pd.isna(value):
        return ""
    return str(value).strip()


def _parse_wide_family_table(df: pd.DataFrame, source_file: Path) -> tuple[list[dict], list[dict]]:
    chunks: list[dict] = []
    records: list[dict] = []
    chunk_counter = 0

    for _, row in df.iterrows():
        family_name = _safe_text(row.get("Family") or row.get("family"))
        order_name = _safe_text(row.get("Order") or row.get("order"))
        if not family_name:
            continue
        full_text_parts: list[str] = []
        for column in df.columns:
            if column in BASE_FAMILY_COLUMNS:
                continue
            raw_value = _safe_text(row.get(column))
            if not raw_value:
                continue
            section_text = clean_text(raw_value)
            if not section_text:
                continue
            chunk_counter += 1
            chunks.append(
                {
                    "chunk_id": f"family_chunk_{chunk_counter:08d}",
                    "family_name": family_name,
                    "order_name": order_name,
                    "source_db": "BOW_FAMILY",
                    "source_file": source_file.name,
                    "source_chapter": normalize_family_chapter(column),
                    "source_subchapter": "Unknown",
                    "source_chapter_raw": column,
                    "raw_text": section_text,
                }
            )
            full_text_parts.append(f"{column}\n{section_text}")
        records.append({"family_name": family_name, "order_name": order_name, "full_text": "\n\n".join(full_text_parts).strip()})
    return records, chunks


def _parse_long_family_table(df: pd.DataFrame, source_file: Path) -> tuple[list[dict], list[dict]]:
    for column in ["Family", "family", "Order", "order"]:
        if column not in df.columns:
            df[column] = ""
    if "text" not in df.columns:
        raise ValueError("Long family table must contain a text column")

    if "Family" in df.columns:
        df["Family"] = df["Family"].ffill()
    if "family" in df.columns:
        df["family"] = df["family"].ffill()
    if "Order" in df.columns:
        df["Order"] = df["Order"].ffill()
    if "order" in df.columns:
        df["order"] = df["order"].ffill()

    grouped_segments: dict[tuple[str, str], list[dict]] = defaultdict(list)
    chunk_counter = 0
    chapter_context: dict[tuple[str, str], str] = {}

    for _, row in df.iterrows():
        family_name = _safe_text(row.get("Family") or row.get("family"))
        order_name = _safe_text(row.get("Order") or row.get("order"))
        if not family_name:
            continue
        record_key = (family_name, order_name)
        explicit_chapter = get_explicit_chapter_value(row.to_dict())
        raw_text = _safe_text(row.get("text"))
        if explicit_chapter:
            chapter_context[record_key] = explicit_chapter
        if not raw_text:
            continue
        if not explicit_chapter and is_probable_heading_row(raw_text):
            chapter_context[record_key] = raw_text.strip()
            continue
        sections = split_text_into_sections(
            raw_text,
            level="family",
            default_chapter_raw=explicit_chapter or chapter_context.get(record_key),
            fallback_chapter_raw="Unknown",
        )
        for section in sections:
            section_text = clean_text(section["raw_text"])
            if not section_text:
                continue
            chunk_counter += 1
            grouped_segments[record_key].append(
                {
                    "chunk_id": f"family_chunk_{chunk_counter:08d}",
                    "family_name": family_name,
                    "order_name": order_name,
                    "source_db": "BOW_FAMILY",
                    "source_file": source_file.name,
                    "source_chapter": section["source_chapter"] or "Unknown",
                    "source_subchapter": section.get("source_subchapter", "Unknown"),
                    "source_chapter_raw": section["source_chapter_raw"] or "Unknown",
                    "raw_text": section_text,
                }
            )

    records: list[dict] = []
    chunks: list[dict] = []
    for (family_name, order_name), segment_list in grouped_segments.items():
        chapter_buckets: dict[tuple[str, str], list[str]] = defaultdict(list)
        for segment in segment_list:
            chapter_buckets[(segment["source_chapter"], segment["source_chapter_raw"])].append(segment["raw_text"])
        full_text_parts: list[str] = []
        for chapter_index, ((source_chapter, source_chapter_raw), texts) in enumerate(chapter_buckets.items(), start=1):
            merged_text = "\n\n".join(texts).strip()
            chunks.append(
                {
                    "chunk_id": f"{family_name}::{chapter_index}",
                    "family_name": family_name,
                    "order_name": order_name,
                    "source_db": "BOW_FAMILY",
                    "source_file": source_file.name,
                    "source_chapter": source_chapter or "Unknown",
                    "source_subchapter": "Unknown",
                    "source_chapter_raw": source_chapter_raw or "Unknown",
                    "raw_text": merged_text,
                }
            )
            heading = source_chapter if source_chapter and source_chapter != "Unknown" else source_chapter_raw
            full_text_parts.append(f"{heading}\n{merged_text}")
        records.append({"family_name": family_name, "order_name": order_name, "full_text": "\n\n".join(full_text_parts).strip()})
    return records, chunks


def parse_family_order_xlsx(file_path: str | Path = "data/Order.xlsx") -> tuple[list[dict], list[dict]]:
    ensure_output_dirs()
    source_file = Path(file_path)
    df = pd.read_excel(source_file)
    if "text" in df.columns:
        records, chunks = _parse_long_family_table(df, source_file)
    else:
        records, chunks = _parse_wide_family_table(df, source_file)
    write_jsonl(INTERMEDIATE_DIR / "family_records.jsonl", records)
    write_jsonl(INTERMEDIATE_DIR / "family_chunks.jsonl", chunks)
    return records, chunks


def filter_family_records(
    records: list[dict],
    sample_family_names: set[str] | None,
    sample_order_names: set[str] | None,
    family_scope: str,
) -> list[dict]:
    if family_scope == "full":
        return list(records)
    family_names = sample_family_names or set()
    order_names = sample_order_names or set()
    filtered: list[dict] = []
    for record in records:
        family_name = record.get("family_name")
        order_name = record.get("order_name")
        if family_name and family_name in family_names:
            filtered.append(record)
        elif not family_name and order_name and order_name in order_names:
            filtered.append(record)
    return filtered


def filter_family_chunks(
    chunks: list[dict],
    sample_family_names: set[str] | None,
    sample_order_names: set[str] | None,
    family_scope: str,
) -> list[dict]:
    if family_scope == "full":
        return list(chunks)
    family_names = sample_family_names or set()
    order_names = sample_order_names or set()
    filtered: list[dict] = []
    for chunk in chunks:
        family_name = chunk.get("family_name")
        order_name = chunk.get("order_name")
        if family_name and family_name in family_names:
            filtered.append(chunk)
        elif not family_name and order_name and order_name in order_names:
            filtered.append(chunk)
    return filtered


if __name__ == "__main__":
    parse_family_order_xlsx()
