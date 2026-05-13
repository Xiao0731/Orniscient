"""Run Step 3 claim, fact, and evidence extraction."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
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


def _sanitize_jsonl_value(value):
    if isinstance(value, list):
        return " ".join(str(_sanitize_jsonl_value(item)) for item in value)
    if isinstance(value, tuple):
        return " ".join(str(_sanitize_jsonl_value(item)) for item in value)
    if isinstance(value, dict):
        return {key: _sanitize_jsonl_value(item) for key, item in value.items()}
    if isinstance(value, str):
        return "".join(char for char in value if ord(char) >= 32)
    return value


def sanitize_row(row: dict) -> dict:
    return {key: _sanitize_jsonl_value(value) for key, value in row.items()}


class JsonlOutputFiles:
    def __init__(self, paths: dict[str, Path], *, shard_index: int, initial_counts: dict[str, int] | None = None) -> None:
        self.paths = paths
        self.shard_index = shard_index
        append_keys = {"species_claims", "family_claims", "extractor_failures", "processed_chunks"}
        self.handles = {
            key: path.open("a" if key in append_keys else "w", encoding="utf-8")
            for key, path in paths.items()
            if path.suffix == ".jsonl"
        }
        self.row_counts = {key: int((initial_counts or {}).get(key, 0)) for key in self.handles}

    def write_row(self, key: str, row: dict) -> None:
        handle = self.handles[key]
        safe_row = sanitize_row(row)
        handle.write(json.dumps(safe_row, ensure_ascii=False) + "\n")
        self.row_counts[key] += 1

    def write_rows(self, key: str, rows: list[dict]) -> None:
        for row in rows:
            self.write_row(key, row)

    def rewrite_rows(self, key: str, rows: list[dict]) -> None:
        handle = self.handles[key]
        handle.seek(0)
        handle.truncate(0)
        self.row_counts[key] = 0
        self.write_rows(key, rows)

    def flush(self, *, processed: int, out_dir: Path, force_log: bool = True) -> None:
        for handle in self.handles.values():
            handle.flush()
            os.fsync(handle.fileno())
        if force_log:
            claims_written = self.row_counts.get("species_claims", 0) + self.row_counts.get("family_claims", 0)
            facts_written = self.row_counts.get("species_facts", 0) + self.row_counts.get("family_facts", 0)
            _debug_print(
                f"[Step3][FLUSH] processed={processed} shard_index={self.shard_index} "
                f"claims_written={claims_written} facts_written={facts_written} "
                f"evidences_written={self.row_counts.get('evidences', 0)} "
                f"links_written={self.row_counts.get('fact_evidence_links', 0)} "
                f"processed_written={self.row_counts.get('processed_chunks', 0)} "
                f"saved outputs to {out_dir}"
            )

    def close(self, *, processed: int, out_dir: Path) -> None:
        try:
            self.flush(processed=processed, out_dir=out_dir, force_log=True)
        finally:
            for handle in self.handles.values():
                handle.close()


def _resolve_under_kg(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return (KG_ROOT / path).resolve()


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _chunk_id_from_metadata(metadata: dict) -> str:
    return str(metadata.get("source_chunk_id", "") or "").strip()


def _processed_chunk_payload(metadata: dict, *, shard_index: int, num_shards: int) -> dict:
    return {
        "chunk_id": metadata.get("source_chunk_id", ""),
        "subject_rank": metadata.get("subject_rank", ""),
        "subject_taxon_id": metadata.get("subject_taxon_id", ""),
        "source_doc_id": metadata.get("source_doc_id", ""),
        "source_chapter": metadata.get("source_chapter", ""),
        "shard_index": shard_index,
        "num_shards": num_shards,
    }


def _find_duplicate_chunk_ids(rows: list[tuple[dict, dict, str]]) -> list[str]:
    counts: Counter = Counter(_chunk_id_from_metadata(metadata) for metadata, _, _ in rows if _chunk_id_from_metadata(metadata))
    return sorted(chunk_id for chunk_id, count in counts.items() if count > 1)


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


def _wrapper_component_counts(wrapper: dict) -> dict:
    return {
        "claims": len(wrapper.get("claims", [])) if isinstance(wrapper.get("claims"), list) else 0,
        "facts": len(wrapper.get("facts", [])) if isinstance(wrapper.get("facts"), list) else 0,
        "evidences": len(wrapper.get("evidences", [])) if isinstance(wrapper.get("evidences"), list) else 0,
        "fact_evidence_links": len(wrapper.get("fact_evidence_links", []))
        if isinstance(wrapper.get("fact_evidence_links"), list)
        else 0,
    }


def _build_current_fact_artifacts(species_claims: list[dict], family_claims: list[dict]) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    species_facts, species_evidences, species_fact_evidence_links = build_facts_and_evidence(species_claims, subject_rank="species")
    family_facts, family_evidences, family_fact_evidence_links = build_facts_and_evidence(family_claims, subject_rank="family")
    evidences_by_id = {row["evidence_id"]: row for row in species_evidences + family_evidences}
    fact_evidence_links = species_fact_evidence_links + family_fact_evidence_links
    evidences = list(evidences_by_id.values())
    return species_facts, family_facts, evidences, fact_evidence_links


def _rewrite_current_fact_artifacts(
    output_files: JsonlOutputFiles,
    species_claims: list[dict],
    family_claims: list[dict],
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    species_facts, family_facts, evidences, fact_evidence_links = _build_current_fact_artifacts(species_claims, family_claims)
    output_files.rewrite_rows("species_facts", species_facts)
    output_files.rewrite_rows("family_facts", family_facts)
    output_files.rewrite_rows("evidences", evidences)
    output_files.rewrite_rows("fact_evidence_links", fact_evidence_links)
    return species_facts, family_facts, evidences, fact_evidence_links


def _format_eta(seconds: float) -> str:
    if seconds < 0 or seconds == float("inf"):
        return "unknown"
    seconds = int(seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _progress_line(*, stats: dict, metadata: dict, prefix: str = "[Step3]") -> str:
    elapsed = max(time.time() - stats["started_at"], 1e-3)
    speed = stats["processed"] / elapsed
    remaining = max(stats["total"] - stats["processed"], 0)
    eta = _format_eta(remaining / speed) if speed > 0 else "unknown"
    return (
        f"{prefix} {stats['processed']}/{stats['total']} "
        f"ok={stats['ok']} fail={stats['fail']} skip={stats['skip']} "
        f"speed={speed:.2f} chunk/s eta={eta} "
        f"chunk_id={metadata.get('source_chunk_id', '')} "
        f"common_name={metadata.get('common_name', '')} "
        f"scientific_name={metadata.get('scientific_name', '')} "
        f"source_chapter={metadata.get('source_chapter', '')}"
    )


def _done_line(*, stats: dict, output_files: JsonlOutputFiles) -> str:
    claims_written = output_files.row_counts.get("species_claims", 0) + output_files.row_counts.get("family_claims", 0)
    facts_written = output_files.row_counts.get("species_facts", 0) + output_files.row_counts.get("family_facts", 0)
    return (
        f"[Step3][DONE] processed={stats['processed']} ok={stats['ok']} fail={stats['fail']} skip={stats['skip']} "
        f"claims_written={claims_written} facts_written={facts_written} "
        f"evidences_written={output_files.row_counts.get('evidences', 0)} "
        f"links_written={output_files.row_counts.get('fact_evidence_links', 0)} "
        f"processed_written={output_files.row_counts.get('processed_chunks', 0)}"
    )


def _maybe_print_progress(*, stats: dict, metadata: dict, log_every: int, force: bool = False) -> None:
    if stats["total"] <= 0:
        return
    interval = max(1, int(log_every))
    if force or stats["processed"] == 1 or stats["processed"] % interval == 0 or stats["processed"] >= stats["total"]:
        _debug_print(_progress_line(stats=stats, metadata=metadata))


def _metadata_for_chunk(*, link: dict, source_chunk: dict, subject_rank: str, source_release: str) -> dict:
    if subject_rank == "species":
        subject_taxon_id = link.get("canonical_taxon_id", "")
        scientific_name = link.get("canonical_scientific_name") or link.get("species_name") or source_chunk.get("species_name", "")
        common_name = link.get("common_name") or source_chunk.get("common_name", "")
    else:
        subject_taxon_id = link.get("canonical_family_id", "")
        scientific_name = link.get("canonical_family_name") or link.get("family_name") or source_chunk.get("family_name", "")
        common_name = source_chunk.get("common_name", "")
    return {
        "source_db": "BOW",
        "source_release": source_release,
        "source_doc_id": _source_doc_id(subject_rank, link),
        "source_chunk_id": link.get("chunk_id", ""),
        "source_chapter": link.get("source_chapter") or source_chunk.get("source_chapter", "Unknown"),
        "source_subchapter": link.get("source_subchapter") or source_chunk.get("source_subchapter", "Unknown"),
        "subject_taxon_id": subject_taxon_id,
        "subject_rank": subject_rank,
        "common_name": common_name,
        "scientific_name": scientific_name,
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


def _collect_attached_chunks(
    *,
    links: list[dict],
    chunks_by_id: dict[str, dict],
    subject_rank: str,
    source_release: str,
    max_chunks: int,
    max_chars: int,
) -> list[tuple[dict, dict, str]]:
    rows = list(
        _iter_attached_chunks(
            links=links,
            chunks_by_id=chunks_by_id,
            subject_rank=subject_rank,
            source_release=source_release,
            max_chunks=max_chunks,
            max_chars=max_chars,
        )
    )
    return sorted(
        rows,
        key=lambda row: (
            row[0].get("subject_rank", ""),
            row[0].get("source_chunk_id", ""),
            row[0].get("source_doc_id", ""),
        ),
    )


def _select_shard(rows: list[tuple[dict, dict, str]], *, shard_index: int, num_shards: int) -> list[tuple[dict, dict, str]]:
    return [row for index, row in enumerate(rows) if index % num_shards == shard_index]


def _candidate_chunk_total(
    *,
    links: list[dict],
    chunks_by_id: dict[str, dict],
    subject_rank: str,
    source_release: str,
    max_chunks: int,
) -> int:
    if max_chunks == 0:
        return 0
    total = 0
    for link in links:
        if link.get("resolution_status") != "attached":
            continue
        chunk = chunks_by_id.get(link.get("chunk_id", ""))
        if not chunk:
            continue
        metadata = _metadata_for_chunk(link=link, source_chunk=chunk, subject_rank=subject_rank, source_release=source_release)
        if not metadata["subject_taxon_id"]:
            continue
        if not chunk.get("raw_text", ""):
            continue
        route = route_chapter(metadata["source_chapter"], metadata.get("source_subchapter", ""))
        if route["skip"]:
            continue
        total += 1
        if max_chunks > 0 and total >= max_chunks:
            break
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract Step 3 claims, facts, and evidence")
    parser.add_argument("--intermediate-dir", default="outputs/intermediate")
    parser.add_argument("--attachments-dir", default="outputs/intermediate/attachments")
    parser.add_argument("--taxonomy-dir", default="outputs/intermediate/taxonomy")
    parser.add_argument("--claims-dir", default="outputs/intermediate/claims")
    parser.add_argument("--claims-out-dir", default=None)
    parser.add_argument("--source-release", default="bow_2025_snapshot")
    parser.add_argument("--extractor", choices=["auto", "llm", "mock"], default="auto")
    parser.add_argument("--max-species-chunks", type=int, default=-1)
    parser.add_argument("--max-family-chunks", type=int, default=-1)
    parser.add_argument("--max-chars-per-chunk", type=int, default=4500)
    parser.add_argument("--log-every", type=int, default=50)
    parser.add_argument("--flush-every", type=int, default=20)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--num-shards", type=int, default=1)
    parser.add_argument("--debug-llm", action="store_true")
    args = parser.parse_args()
    if args.num_shards < 1:
        raise ValueError("--num-shards must be >= 1")
    if args.shard_index < 0 or args.shard_index >= args.num_shards:
        raise ValueError("--shard-index must satisfy 0 <= shard-index < num-shards")
    if args.flush_every < 1:
        raise ValueError("--flush-every must be >= 1")

    intermediate_dir = _resolve_under_kg(args.intermediate_dir)
    attachments_dir = _resolve_under_kg(args.attachments_dir)
    taxonomy_dir = _resolve_under_kg(args.taxonomy_dir)
    if args.claims_out_dir:
        claims_dir = _resolve_under_kg(args.claims_out_dir)
        if args.num_shards > 1 and claims_dir.name != f"shard_{args.shard_index:02d}":
            claims_dir = claims_dir / f"shard_{args.shard_index:02d}"
    elif args.num_shards > 1:
        claims_dir = _resolve_under_kg("outputs/intermediate/claims_shards") / f"shard_{args.shard_index:02d}"
    else:
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
    species_chunks_global = _collect_attached_chunks(
        links=inputs["species_chunk_links"],
        chunks_by_id=inputs["species_chunks_by_id"],
        subject_rank="species",
        source_release=args.source_release,
        max_chunks=args.max_species_chunks,
        max_chars=args.max_chars_per_chunk,
    )
    family_chunks_global = _collect_attached_chunks(
        links=inputs["family_chunk_links"],
        chunks_by_id=inputs["family_chunks_by_id"],
        subject_rank="family",
        source_release=args.source_release,
        max_chunks=args.max_family_chunks,
        max_chars=args.max_chars_per_chunk,
    )
    all_chunks_global = sorted(
        species_chunks_global + family_chunks_global,
        key=lambda row: (
            row[0].get("subject_rank", ""),
            row[0].get("source_chunk_id", ""),
            row[0].get("source_doc_id", ""),
        ),
    )
    paths = {
        "species_claims": claims_dir / "species_claims.jsonl",
        "family_claims": claims_dir / "family_claims.jsonl",
        "species_facts": claims_dir / "species_facts.jsonl",
        "family_facts": claims_dir / "family_facts.jsonl",
        "evidences": claims_dir / "evidences.jsonl",
        "fact_evidence_links": claims_dir / "fact_evidence_links.jsonl",
        "extractor_failures": claims_dir / "extractor_failures.jsonl",
        "processed_chunks": claims_dir / "processed_chunks.jsonl",
        "summary": claims_dir / "extraction_summary.json",
    }
    shard_chunks_all = _select_shard(all_chunks_global, shard_index=args.shard_index, num_shards=args.num_shards)
    duplicate_shard_chunk_ids = _find_duplicate_chunk_ids(shard_chunks_all)
    if duplicate_shard_chunk_ids:
        preview = ", ".join(duplicate_shard_chunk_ids[:10])
        raise RuntimeError(f"Shard input contains duplicate chunk_id rows: {len(duplicate_shard_chunk_ids)} ({preview})")
    shard_metadata_by_chunk_id = {
        _chunk_id_from_metadata(metadata): metadata
        for metadata, _, _ in shard_chunks_all
        if _chunk_id_from_metadata(metadata)
    }
    existing_processed_chunks = _read_jsonl(paths["processed_chunks"])
    processed_chunk_ids = {
        str(row.get("chunk_id", "") or "").strip()
        for row in existing_processed_chunks
        if str(row.get("chunk_id", "") or "").strip()
    }
    duplicate_existing_processed = len(existing_processed_chunks) - len(processed_chunk_ids)
    if duplicate_existing_processed:
        raise RuntimeError(f"Existing processed_chunks.jsonl contains duplicate chunk_id rows: {duplicate_existing_processed}")

    species_claims: list[dict] = _read_jsonl(paths["species_claims"])
    family_claims: list[dict] = _read_jsonl(paths["family_claims"])
    extractor_failures: list[dict] = _read_jsonl(paths["extractor_failures"])
    recovered_chunk_ids = {
        str(row.get("source_chunk_id", "") or "").strip()
        for row in species_claims + family_claims + extractor_failures
        if str(row.get("source_chunk_id", "") or "").strip()
    }
    missing_processed_chunk_ids = sorted(
        chunk_id
        for chunk_id in recovered_chunk_ids - processed_chunk_ids
        if chunk_id in shard_metadata_by_chunk_id
    )
    completed_chunk_ids = processed_chunk_ids | set(missing_processed_chunk_ids)
    initial_counts = {
        "species_claims": len(species_claims),
        "family_claims": len(family_claims),
        "extractor_failures": len(extractor_failures),
        "processed_chunks": len(existing_processed_chunks),
    }
    existing_species_processed = sum(1 for row in existing_processed_chunks if row.get("subject_rank") == "species")
    existing_family_processed = sum(1 for row in existing_processed_chunks if row.get("subject_rank") == "family")
    shard_chunks = [
        row for row in shard_chunks_all if str(row[0].get("source_chunk_id", "") or "").strip() not in completed_chunk_ids
    ]
    remaining_species_total = sum(1 for metadata, _, _ in shard_chunks if metadata.get("subject_rank") == "species")
    remaining_family_total = sum(1 for metadata, _, _ in shard_chunks if metadata.get("subject_rank") == "family")
    _debug_print(f"[Step3][RESUME] loaded_processed_chunks={len(processed_chunk_ids)}")
    if missing_processed_chunk_ids:
        _debug_print(f"[Step3][RESUME] recovered_missing_processed_chunks={len(missing_processed_chunk_ids)}")
    _debug_print(f"[Step3][RESUME] remaining_chunks={len(shard_chunks)}")

    progress_stats = {
        "total": len(shard_chunks),
        "processed": 0,
        "ok": 0,
        "fail": 0,
        "skip": 0,
        "started_at": time.time(),
    }
    _debug_print(
        f"[Step3] start extractor={extractor_mode} total={progress_stats['total']} "
        f"species_total={remaining_species_total} family_total={remaining_family_total} "
        f"total_global={len(all_chunks_global)} total_shard={len(shard_chunks_all)} "
        f"shard_index={args.shard_index} num_shards={args.num_shards} "
        f"claims_dir={claims_dir} log_every={args.log_every} flush_every={args.flush_every}"
    )

    output_files = JsonlOutputFiles(paths, shard_index=args.shard_index, initial_counts=initial_counts)
    for chunk_id in missing_processed_chunk_ids:
        metadata = shard_metadata_by_chunk_id[chunk_id]
        output_files.write_row(
            "processed_chunks",
            _processed_chunk_payload(metadata, shard_index=args.shard_index, num_shards=args.num_shards),
        )
        if metadata.get("subject_rank") == "species":
            existing_species_processed += 1
        elif metadata.get("subject_rank") == "family":
            existing_family_processed += 1
    saved_chunk_count = len(existing_processed_chunks) + len(missing_processed_chunk_ids)
    species_facts: list[dict] = []
    family_facts: list[dict] = []
    evidences: list[dict] = []
    fact_evidence_links: list[dict] = []
    wrapper_component_totals: Counter = Counter()
    chunks_with_wrapper_claims_without_wrapper_facts = 0
    chunks_with_valid_claims_without_current_facts = 0
    species_processed = existing_species_processed
    family_processed = existing_family_processed
    try:
        species_facts, family_facts, evidences, fact_evidence_links = _rewrite_current_fact_artifacts(
            output_files,
            species_claims,
            family_claims,
        )
        output_files.flush(processed=saved_chunk_count, out_dir=claims_dir)
        for metadata, routing, chunk_text in shard_chunks:
            if metadata.get("subject_rank") == "species":
                species_processed += 1
                claim_sink = species_claims
                claims_output_key = "species_claims"
            else:
                family_processed += 1
                claim_sink = family_claims
                claims_output_key = "family_claims"
            progress_stats["processed"] += 1
            processed_chunk = _processed_chunk_payload(metadata, shard_index=args.shard_index, num_shards=args.num_shards)
            try:
                wrapper = extractor.extract(metadata=metadata, routing=routing, chunk_text=chunk_text, canonical_candidates=[])
                wrapper_counts = _wrapper_component_counts(wrapper)
                wrapper_component_totals.update(wrapper_counts)
                if wrapper_counts["claims"] and not (
                    wrapper_counts["facts"] or wrapper_counts["evidences"] or wrapper_counts["fact_evidence_links"]
                ):
                    chunks_with_wrapper_claims_without_wrapper_facts += 1
                if args.debug_llm:
                    _debug_print(
                        "[DEBUG_WRAPPER_COMPONENTS] "
                        f"chunk_id={metadata.get('source_chunk_id', '')} "
                        f"claims={wrapper_counts['claims']} facts={wrapper_counts['facts']} "
                        f"evidences={wrapper_counts['evidences']} "
                        f"fact_evidence_links={wrapper_counts['fact_evidence_links']}"
                    )
                wrapper["extraction_method"] = extractor_mode
            except Exception as exc:
                dropped_reasons["extractor_error"] += 1
                progress_stats["fail"] += 1
                failure = _failure_payload(metadata, exc)
                extractor_failures.append(failure)
                output_files.write_row("extractor_failures", failure)
                output_files.write_row("processed_chunks", processed_chunk)
                saved_chunk_count += 1
                _debug_print(f"[Step3][ERROR] chunk_id={metadata.get('source_chunk_id', '')} {exc.__class__.__name__}: {exc}")
                if args.debug_llm:
                    _debug_print("[DEBUG_LLM_EXCEPTION]")
                    _debug_print(f"{exc.__class__.__name__}: {exc}")
                _maybe_print_progress(stats=progress_stats, metadata=metadata, log_every=args.log_every)
                if progress_stats["processed"] % args.flush_every == 0:
                    output_files.flush(processed=saved_chunk_count, out_dir=claims_dir)
                continue
            valid_claims = _validate_wrapper(wrapper, metadata, routing, dropped_reasons)
            if valid_claims:
                progress_stats["ok"] += 1
            else:
                progress_stats["skip"] += 1
            claim_sink.extend(valid_claims)
            output_files.write_rows(claims_output_key, valid_claims)
            species_facts, family_facts, evidences, fact_evidence_links = _rewrite_current_fact_artifacts(
                output_files,
                species_claims,
                family_claims,
            )
            if valid_claims and not (species_facts or family_facts or evidences or fact_evidence_links):
                chunks_with_valid_claims_without_current_facts += 1
            output_files.write_row("processed_chunks", processed_chunk)
            saved_chunk_count += 1
            _maybe_print_progress(stats=progress_stats, metadata=metadata, log_every=args.log_every)
            if progress_stats["processed"] % args.flush_every == 0:
                output_files.flush(processed=saved_chunk_count, out_dir=claims_dir)

        species_facts, family_facts, evidences, fact_evidence_links = _rewrite_current_fact_artifacts(
            output_files,
            species_claims,
            family_claims,
        )
    except KeyboardInterrupt:
        output_files.flush(processed=saved_chunk_count, out_dir=claims_dir)
        _debug_print(
            f"[Step3][INTERRUPTED] processed={progress_stats['processed']} saved={saved_chunk_count} "
            f"shard_index={args.shard_index} saved outputs to {claims_dir}"
        )
        output_files.close(processed=saved_chunk_count, out_dir=claims_dir)
        raise SystemExit(130)
    finally:
        if not any(handle.closed for handle in output_files.handles.values()):
            output_files.flush(processed=saved_chunk_count, out_dir=claims_dir)

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
    summary.update(
        {
            "shard_index": args.shard_index,
            "num_shards": args.num_shards,
            "total_global": len(all_chunks_global),
            "total_shard": len(shard_chunks_all),
            "remaining_chunks_at_start": len(shard_chunks),
            "loaded_processed_chunks": len(processed_chunk_ids),
            "claims_out_dir": str(claims_dir),
            "wrapper_claims_total": int(wrapper_component_totals.get("claims", 0)),
            "wrapper_facts_total": int(wrapper_component_totals.get("facts", 0)),
            "wrapper_evidences_total": int(wrapper_component_totals.get("evidences", 0)),
            "wrapper_fact_evidence_links_total": int(wrapper_component_totals.get("fact_evidence_links", 0)),
            "chunks_with_wrapper_claims_without_wrapper_facts": chunks_with_wrapper_claims_without_wrapper_facts,
            "chunks_with_valid_claims_without_current_facts": chunks_with_valid_claims_without_current_facts,
        }
    )
    write_json(paths["summary"], summary)
    _debug_print(_done_line(stats=progress_stats, output_files=output_files))
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    output_files.close(processed=saved_chunk_count, out_dir=claims_dir)


if __name__ == "__main__":
    main()
