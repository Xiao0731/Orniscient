"""Build chunk-level evidence artifacts for Step 3 facts."""

from __future__ import annotations

from kg_v2.Step3_extraction.normalizers import short_quote
from kg_v2.utils.hash_utils import stable_hash


def evidence_id_for_claim(claim: dict) -> str:
    return stable_hash(
        claim.get("source_db", ""),
        claim.get("source_release", ""),
        claim.get("source_chunk_id", ""),
        claim.get("evidence_quote", ""),
        prefix="evidence_",
    )


def build_evidence_record(claim: dict) -> dict:
    quote = short_quote(claim.get("evidence_quote", ""))
    evidence_hash = stable_hash(
        claim.get("source_db", ""),
        claim.get("source_release", ""),
        claim.get("source_chunk_id", ""),
        quote,
        prefix="evhash_",
    )
    return {
        "evidence_id": evidence_id_for_claim({**claim, "evidence_quote": quote}),
        "source_db": claim.get("source_db", ""),
        "source_release": claim.get("source_release", ""),
        "source_doc_id": claim.get("source_doc_id", ""),
        "source_chunk_id": claim.get("source_chunk_id", ""),
        "source_chapter": claim.get("source_chapter", ""),
        "source_subchapter": claim.get("source_subchapter", ""),
        "evidence_quote": quote,
        "evidence_hash": evidence_hash,
    }

