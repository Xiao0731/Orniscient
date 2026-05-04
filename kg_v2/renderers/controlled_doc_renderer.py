"""Render species claims into controlled LightRAG docs."""

from __future__ import annotations

from collections import defaultdict
import re

from kg_v2.parsers.normalize_text import clean_text
from kg_v2.schema.ontology_v2 import CONTROLLED_DOCS_PATH, INTERMEDIATE_DIR, load_jsonl, write_jsonl

DOC_LAYOUT = [
    ("taxonomy_and_identification", {"TAXONOMY_NOTE", "HAS_STATUS", "BODY_LENGTH", "BODY_MASS"}),
    ("distribution_and_habitat", {"INHABITS", "OCCURS_IN", "BREEDS_IN", "WINTERS_IN", "ELEVATION_RANGE"}),
    ("diet_behavior_and_vocalization", {"EATS", "FORAGES_BY", "HAS_TRAIT", "HAS_VOCALIZATION"}),
    ("breeding", {"BREEDING_PROFILE", "NESTS_AT", "CLUTCH_SIZE", "INCUBATION_PERIOD", "FLEDGING_PERIOD"}),
    ("demography_and_conservation", {"CONSERVATION_PROFILE", "THREATENED_BY", "HAS_STATUS", "LIFESPAN", "MANAGED_BY"}),
    ("future_research", {"FUTURE_RESEARCH", "REQUIRES_RESEARCH"}),
]


def _evidence_snippet(chunk_lookup: dict[str, dict], chunk_ids: list[str]) -> str:
    for chunk_id in chunk_ids[:1]:
        chunk = chunk_lookup.get(chunk_id)
        if not chunk:
            continue
        text = clean_text(chunk.get("cleaned_text") or chunk.get("raw_text", ""))
        text = re.sub(r"(photo|video)", " ", text, flags=re.IGNORECASE)
        text = " ".join(text.split())
        text = re.sub(r"\b[A-Z][a-z]+(?:,?\s+[A-Z]\.)+(?:\s+and\s+[A-Z][a-z]+)?", " ", text)
        text = re.sub(r"\b\d{4}\b", " ", text)
        text = " ".join(text.split())
        if text:
            return text[:180]
    return ""


def _render_claim_line(claim: dict, chunk_lookup: dict[str, dict]) -> str:
    predicate = claim.get("predicate")
    if claim.get("value_type") == "entity":
        core = f"{predicate}: {claim.get('object_name')}"
    elif claim.get("value_type") == "numeric":
        if claim.get("value_min") == claim.get("value_max"):
            value = f"{claim.get('value_min')} {claim.get('unit') or ''}".strip()
        else:
            value = f"{claim.get('value_min')}-{claim.get('value_max')} {claim.get('unit') or ''}".strip()
        core = f"{predicate}: {value}"
    else:
        core = f"{predicate}: {claim.get('value_text')}"
    snippet = _evidence_snippet(chunk_lookup, claim.get("supported_chunk_ids", []))
    if snippet:
        return f"- {core}. Evidence: {snippet}"
    return f"- {core}."


def render_controlled_docs(
    species_records_path=INTERMEDIATE_DIR / "species_records.jsonl",
    claims_path=INTERMEDIATE_DIR / "species_claims.jsonl",
    evidence_chunks_path=INTERMEDIATE_DIR / "evidence_chunks.jsonl",
    family_records_path=INTERMEDIATE_DIR / "family_records.jsonl",
    family_chunks_path=INTERMEDIATE_DIR / "family_chunks.jsonl",
    family_summaries_path=INTERMEDIATE_DIR / "family_summaries.jsonl",
    output_path=CONTROLLED_DOCS_PATH,
) -> list[dict]:
    species_records = {row["species_name"]: row for row in load_jsonl(species_records_path)}
    claims = load_jsonl(claims_path)
    chunk_lookup = {row["chunk_id"]: row for row in load_jsonl(evidence_chunks_path)}
    family_records = load_jsonl(family_records_path)
    family_chunks = load_jsonl(family_chunks_path)
    family_summaries = load_jsonl(family_summaries_path)
    grouped_claims: dict[str, list[dict]] = defaultdict(list)
    for claim in claims:
        grouped_claims[claim["subject_name"]].append(claim)

    docs: list[dict] = []
    for species_name, species_claims in grouped_claims.items():
        species_record = species_records.get(species_name, {})
        for doc_type, predicates in DOC_LAYOUT:
            selected = [claim for claim in species_claims if claim.get("predicate") in predicates]
            if not selected:
                continue
            title = f"{species_record.get('common_name') or species_name} | {doc_type.replace('_', ' ').title()}"
            lines = [
                f"# {title}",
                "",
                f"Species: {species_name}",
                f"Family: {species_record.get('family_name', 'Unknown')}",
                f"Order: {species_record.get('order_name', 'Unknown')}",
                "",
                "## Controlled Claims",
            ]
            for claim in selected[:18]:
                lines.append(_render_claim_line(claim, chunk_lookup))
            content = "\n".join(lines).strip()
            docs.append(
                {
                    "doc_id": f"{species_name}::{doc_type}",
                    "species_name": species_name,
                    "family_name": species_record.get("family_name"),
                    "doc_type": doc_type,
                    "content": content,
                    "claim_ids": [claim["claim_id"] for claim in selected],
                }
            )

    family_chunk_buckets: dict[str, list[dict]] = defaultdict(list)
    for chunk in family_chunks:
        family_name = chunk.get("family_name")
        if family_name:
            family_chunk_buckets[family_name].append(chunk)

    family_summary_lookup = {row["family_name"]: row for row in family_summaries if row.get("family_name")}
    for family_record in family_records:
        family_name = family_record.get("family_name")
        if not family_name:
            continue
        family_evidence = family_chunk_buckets.get(family_name, [])
        if family_evidence:
            lines = [
                f"# {family_name} | Family Direct Evidence",
                "",
                f"Family: {family_name}",
                f"Order: {family_record.get('order_name', 'Unknown')}",
                "",
                "## Canonical Family Aspects",
            ]
            for chunk in family_evidence[:8]:
                snippet = _evidence_snippet({chunk["chunk_id"]: chunk}, [chunk["chunk_id"]])
                chapter = chunk.get("source_chapter") or chunk.get("source_chapter_raw") or "Unknown"
                lines.append(f"- {chapter}: {snippet or 'n/a'}")
            docs.append(
                {
                    "doc_id": f"{family_name}::family_direct_evidence",
                    "family_name": family_name,
                    "doc_type": "family_direct_evidence",
                    "content": "\n".join(lines).strip(),
                    "claim_ids": [],
                }
            )
        family_summary = family_summary_lookup.get(family_name)
        if family_summary:
            lines = [
                f"# {family_name} | Family Derived Summary",
                "",
                f"Family: {family_name}",
                "",
                "## Derived Summary",
                family_summary.get("summary_text", ""),
            ]
            docs.append(
                {
                    "doc_id": f"{family_name}::family_derived_summary",
                    "family_name": family_name,
                    "doc_type": "family_derived_summary",
                    "content": "\n".join(lines).strip(),
                    "claim_ids": [],
                }
            )
    write_jsonl(output_path, docs)
    return docs
