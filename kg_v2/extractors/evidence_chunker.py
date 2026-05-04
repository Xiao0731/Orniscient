"""Unify species and family chunks into EvidenceChunk records."""

from __future__ import annotations

from kg_v2.parsers.normalize_text import clean_text
from kg_v2.schema.ontology_v2 import INTERMEDIATE_DIR, load_jsonl, write_jsonl


def build_evidence_chunks(
    species_chunks_path=INTERMEDIATE_DIR / "species_chunks.jsonl",
    family_chunks_path=INTERMEDIATE_DIR / "family_chunks.jsonl",
    output_path=INTERMEDIATE_DIR / "evidence_chunks.jsonl",
) -> list[dict]:
    species_chunks = load_jsonl(species_chunks_path)
    family_chunks = load_jsonl(family_chunks_path)
    evidence_rows: list[dict] = []

    for row in species_chunks + family_chunks:
        evidence_rows.append(
            {
                "chunk_id": row["chunk_id"],
                "raw_text": row.get("raw_text", ""),
                "cleaned_text": clean_text(row.get("raw_text", "")),
                "source_db": row.get("source_db", ""),
                "source_file": row.get("source_file", ""),
                "source_chapter": row.get("source_chapter", "Unknown"),
                "source_subchapter": row.get("source_subchapter", "Unknown"),
                "source_chapter_raw": row.get("source_chapter_raw", "Unknown"),
                "species_name": row.get("species_name"),
                "family_name": row.get("family_name"),
                "order_name": row.get("order_name"),
                "offset_start": None,
                "offset_end": None,
            }
        )

    write_jsonl(output_path, evidence_rows)
    return evidence_rows


if __name__ == "__main__":
    build_evidence_chunks()
