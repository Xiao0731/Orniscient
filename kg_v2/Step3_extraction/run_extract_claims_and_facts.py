"""Run Step 3 claim, fact, and evidence extraction."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KG_ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kg_v2.Step3_extraction.chapter_router import route_chapter
from kg_v2.Step3_extraction.fact_builder import build_facts_and_evidence
from kg_v2.Step3_extraction.llm_extractors import MockStructuredExtractor, StructuredLLMExtractor
from kg_v2.Step3_extraction.loaders import load_step3_inputs
from kg_v2.Step3_extraction.normalizers import QUALIFIER_KEYS, canonicalize_object, short_quote
from kg_v2.Step3_extraction.reporting import build_extraction_summary
from kg_v2.utils.hash_utils import stable_hash
from kg_v2.utils.jsonl_utils import write_json, write_jsonl
from kg_v2.utils.llm_utils import LLMResponseError
from kg_v2.utils.llm_utils import load_openai_compatible_config


def _debug_print(text: str) -> None:
    try:
        print(text, flush=True)
    except OSError:
        pass


def _resolve_under_kg(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return (KG_ROOT / path).resolve()


def _safe_doc_name(value: str) -> str:
    return "_".join((value or "unknown").split())


def _source_doc_id(subject_rank: str, link: dict) -> str:
    if subject_rank == "species":
        name = link.get("canonical_scientific_name") or link.get("species_name", "")
        return f"bow_species_{_safe_doc_name(name)}"
    name = link.get("canonical_family_name") or link.get("family_name", "")
    return f"bow_family_{_safe_doc_name(name)}"


def _select_extractor(mode: str, *, debug_llm: bool = False):
    if mode == "mock":
        return MockStructuredExtractor(), "mock"
    if mode == "llm":
        return StructuredLLMExtractor(debug=debug_llm), "llm"
    config = load_openai_compatible_config()
    if config:
        return StructuredLLMExtractor(config=config, debug=debug_llm), "llm"
    return MockStructuredExtractor(), "mock"


def _print_runtime_debug(extractor: object, extractor_mode: str) -> None:
    if extractor_mode != "llm" or not hasattr(extractor, "runtime_debug_info"):
        return
    info = extractor.runtime_debug_info()
    _debug_print("[DEBUG_LLM_RUNTIME]")
    _debug_print(json.dumps(info, ensure_ascii=False, indent=2))


def _failure_payload(metadata: dict, exc: Exception) -> dict:
    return {
        "source_chunk_id": metadata.get("source_chunk_id", ""),
        "source_chapter": metadata.get("source_chapter", ""),
        "subject_taxon_id": metadata.get("subject_taxon_id", ""),
        "error_type": exc.__class__.__name__,
        "error_message": str(exc),
        "raw_response_preview": getattr(exc, "raw_response_preview", "")[:500],
    }


def _metadata_for_chunk(*, link: dict, source_chunk: dict, subject_rank: str, source_release: str) -> dict:
    if subject_rank == "species":
        subject_taxon_id = link.get("canonical_taxon_id", "")
    else:
        subject_taxon_id = link.get("canonical_family_id", "")
    return {
        "source_db": "BOW",
        "source_release": source_release,
        "source_doc_id": _source_doc_id(subject_rank, link),
        "source_chunk_id": link.get("chunk_id", ""),
        "source_chapter": link.get("source_chapter") or source_chunk.get("source_chapter", "Unknown"),
        "source_subchapter": link.get("source_subchapter") or source_chunk.get("source_subchapter", "Unknown"),
        "subject_taxon_id": subject_taxon_id,
        "subject_rank": subject_rank,
    }


def _validate_wrapper(wrapper: dict, metadata: dict, routing: dict, dropped_reasons: Counter) -> list[dict]:
    claims = wrapper.get("claims", [])
    if not isinstance(claims, list):
        dropped_reasons["claims_not_array"] += 1
        return []
    valid_claims: list[dict] = []
    allowed_domains = set(routing["allowed_fact_domains"])
    allowed_predicates = set(routing["allowed_predicates"])
    for claim in claims[: routing["max_claims"]]:
        if claim.get("fact_domain") not in allowed_domains:
            dropped_reasons["invalid_fact_domain"] += 1
            continue
        if claim.get("predicate") not in allowed_predicates:
            dropped_reasons["invalid_predicate"] += 1
            continue
        if not metadata.get("subject_taxon_id"):
            dropped_reasons["empty_subject_taxon_id"] += 1
            continue
        evidence_quote = short_quote(claim.get("evidence_quote", ""))
        if not evidence_quote:
            dropped_reasons["empty_evidence_quote"] += 1
            continue
        try:
            confidence = float(claim.get("confidence"))
        except (TypeError, ValueError):
            dropped_reasons["non_numeric_confidence"] += 1
            continue
        qualifiers_raw = claim.get("qualifiers_raw") if isinstance(claim.get("qualifiers_raw"), dict) else {}
        qualifiers_raw = {key: str(qualifiers_raw.get(key, "") or "") for key in QUALIFIER_KEYS}
        object_type = claim.get("object_type", "text")
        if object_type not in {"concept", "numeric", "text", "relation"}:
            dropped_reasons["invalid_object_type"] += 1
            continue
        object_id, object_name = canonicalize_object(claim)
        claim_payload = {
            "subject_taxon_id": metadata["subject_taxon_id"],
            "subject_rank": metadata["subject_rank"],
            "fact_domain": claim.get("fact_domain", ""),
            "predicate": claim.get("predicate", ""),
            "object_type": object_type,
            "object_text": str(claim.get("object_text", "") or ""),
            "object_canonical_id": object_id,
            "object_canonical_name": object_name,
            "value_min": claim.get("value_min"),
            "value_max": claim.get("value_max"),
            "unit": str(claim.get("unit", "") or ""),
            "qualifiers_raw": qualifiers_raw,
            "source_db": metadata["source_db"],
            "source_release": metadata["source_release"],
            "source_doc_id": metadata["source_doc_id"],
            "source_chunk_id": metadata["source_chunk_id"],
            "source_chapter": metadata["source_chapter"],
            "source_subchapter": metadata["source_subchapter"],
            "evidence_quote": evidence_quote,
            "confidence": max(0.0, min(confidence, 1.0)),
            "extraction_method": wrapper.get("extraction_method", ""),
        }
        claim_payload["claim_id"] = stable_hash(
            claim_payload["subject_taxon_id"],
            claim_payload["source_chunk_id"],
            claim_payload["predicate"],
            claim_payload["object_text"],
            claim_payload["evidence_quote"],
            prefix="claim_",
        )
        valid_claims.append(claim_payload)
    return valid_claims


def _iter_attached_chunks(
    *,
    links: list[dict],
    chunks_by_id: dict[str, dict],
    subject_rank: str,
    source_release: str,
    max_chunks: int,
    max_chars: int,
):
    yielded = 0
    if max_chunks == 0:
        return
    for link in links:
        if link.get("resolution_status") != "attached":
            continue
        chunk = chunks_by_id.get(link.get("chunk_id", ""))
        if not chunk:
            continue
        metadata = _metadata_for_chunk(link=link, source_chunk=chunk, subject_rank=subject_rank, source_release=source_release)
        if not metadata["subject_taxon_id"]:
            continue
        raw_text = chunk.get("raw_text", "")
        if not raw_text:
            continue
        route = route_chapter(metadata["source_chapter"], metadata.get("source_subchapter", ""))
        if route["skip"]:
            continue
        yielded += 1
        yield metadata, route, raw_text[:max_chars]
        if max_chunks > 0 and yielded >= max_chunks:
            break


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract Step 3 claims, facts, and evidence")
    parser.add_argument("--intermediate-dir", default="outputs/intermediate")
    parser.add_argument("--attachments-dir", default="outputs/intermediate/attachments")
    parser.add_argument("--taxonomy-dir", default="outputs/intermediate/taxonomy")
    parser.add_argument("--claims-dir", default="outputs/intermediate/claims")
    parser.add_argument("--source-release", default="bow_2025_snapshot")
    parser.add_argument("--extractor", choices=["auto", "llm", "mock"], default="auto")
    parser.add_argument("--max-species-chunks", type=int, default=-1)
    parser.add_argument("--max-family-chunks", type=int, default=-1)
    parser.add_argument("--max-chars-per-chunk", type=int, default=4500)
    parser.add_argument("--debug-llm", action="store_true")
    args = parser.parse_args()

    intermediate_dir = _resolve_under_kg(args.intermediate_dir)
    attachments_dir = _resolve_under_kg(args.attachments_dir)
    taxonomy_dir = _resolve_under_kg(args.taxonomy_dir)
    claims_dir = _resolve_under_kg(args.claims_dir)
    claims_dir.mkdir(parents=True, exist_ok=True)

    extractor, extractor_mode = _select_extractor(args.extractor, debug_llm=args.debug_llm)
    if args.debug_llm:
        _print_runtime_debug(extractor, extractor_mode)

    inputs = load_step3_inputs(
        intermediate_dir=intermediate_dir,
        attachments_dir=attachments_dir,
        taxonomy_dir=taxonomy_dir,
    )

    dropped_reasons: Counter = Counter()
    species_claims: list[dict] = []
    family_claims: list[dict] = []
    extractor_failures: list[dict] = []
    species_processed = 0
    family_processed = 0

    for metadata, routing, chunk_text in _iter_attached_chunks(
        links=inputs["species_chunk_links"],
        chunks_by_id=inputs["species_chunks_by_id"],
        subject_rank="species",
        source_release=args.source_release,
        max_chunks=args.max_species_chunks,
        max_chars=args.max_chars_per_chunk,
    ):
        species_processed += 1
        try:
            wrapper = extractor.extract(metadata=metadata, routing=routing, chunk_text=chunk_text, canonical_candidates=[])
            wrapper["extraction_method"] = extractor_mode
        except Exception as exc:
            dropped_reasons["extractor_error"] += 1
            extractor_failures.append(_failure_payload(metadata, exc))
            if args.debug_llm:
                _debug_print("[DEBUG_LLM_EXCEPTION]")
                _debug_print(f"{exc.__class__.__name__}: {exc}")
            continue
        species_claims.extend(_validate_wrapper(wrapper, metadata, routing, dropped_reasons))

    for metadata, routing, chunk_text in _iter_attached_chunks(
        links=inputs["family_chunk_links"],
        chunks_by_id=inputs["family_chunks_by_id"],
        subject_rank="family",
        source_release=args.source_release,
        max_chunks=args.max_family_chunks,
        max_chars=args.max_chars_per_chunk,
    ):
        family_processed += 1
        try:
            wrapper = extractor.extract(metadata=metadata, routing=routing, chunk_text=chunk_text, canonical_candidates=[])
            wrapper["extraction_method"] = extractor_mode
        except Exception as exc:
            dropped_reasons["extractor_error"] += 1
            extractor_failures.append(_failure_payload(metadata, exc))
            if args.debug_llm:
                _debug_print("[DEBUG_LLM_EXCEPTION]")
                _debug_print(f"{exc.__class__.__name__}: {exc}")
            continue
        family_claims.extend(_validate_wrapper(wrapper, metadata, routing, dropped_reasons))

    species_facts, species_evidences, species_fact_evidence_links = build_facts_and_evidence(species_claims, subject_rank="species")
    family_facts, family_evidences, family_fact_evidence_links = build_facts_and_evidence(family_claims, subject_rank="family")
    evidences_by_id = {row["evidence_id"]: row for row in species_evidences + family_evidences}
    fact_evidence_links = species_fact_evidence_links + family_fact_evidence_links
    evidences = list(evidences_by_id.values())

    paths = {
        "species_claims": claims_dir / "species_claims.jsonl",
        "family_claims": claims_dir / "family_claims.jsonl",
        "species_facts": claims_dir / "species_facts.jsonl",
        "family_facts": claims_dir / "family_facts.jsonl",
        "evidences": claims_dir / "evidences.jsonl",
        "fact_evidence_links": claims_dir / "fact_evidence_links.jsonl",
        "extractor_failures": claims_dir / "extractor_failures.jsonl",
        "summary": claims_dir / "extraction_summary.json",
    }
    write_jsonl(paths["species_claims"], species_claims)
    write_jsonl(paths["family_claims"], family_claims)
    write_jsonl(paths["species_facts"], species_facts)
    write_jsonl(paths["family_facts"], family_facts)
    write_jsonl(paths["evidences"], evidences)
    write_jsonl(paths["fact_evidence_links"], fact_evidence_links)
    write_jsonl(paths["extractor_failures"], extractor_failures)
    summary = build_extraction_summary(
        species_chunk_total=len(inputs["species_chunk_links"]),
        family_chunk_total=len(inputs["family_chunk_links"]),
        species_chunks_processed=species_processed,
        family_chunks_processed=family_processed,
        species_claims=species_claims,
        family_claims=family_claims,
        species_facts=species_facts,
        family_facts=family_facts,
        evidences=evidences,
        fact_evidence_links=fact_evidence_links,
        dropped_reasons=dropped_reasons,
        extractor_mode=extractor_mode,
    )
    write_json(paths["summary"], summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
