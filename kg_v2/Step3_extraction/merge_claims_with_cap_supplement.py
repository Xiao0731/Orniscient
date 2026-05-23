"""Merge claim-cap supplementary additional claims into the official Claim layer.

Inputs are read-only:
- KG/intermediate/claims_final_global
- KG/intermediate/claims_cap_supplement_full

Outputs are written to:
- KG/intermediate/claims_final_global_v2
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kg_v2.Step3_extraction.normalizers import QUALIFIER_KEYS
from kg_v2.utils.jsonl_utils import write_json, write_jsonl


EXPECTED_OLD_CLAIMS = 589334
EXPECTED_SPECIES_CLAIMS = 584664
EXPECTED_FAMILY_CLAIMS = 4670
EXPECTED_PROCESSED_CHUNKS = 309369
EXPECTED_SUPPLEMENT_CLAIMS = 331940
EXPECTED_SUPPLEMENT_CHUNKS = 93542
EXPECTED_HIT_SOFT_CAP = 33211


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_configure_stdio()


def _resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return (ROOT / path).resolve()


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except Exception:
        return str(path)


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required JSONL: {path}")
    rows: list[dict] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL row in {path}: line={line_no} error={exc.msg}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Non-object JSONL row in {path}: line={line_no}")
            rows.append(row)
    return rows


def _sha1_id(*parts: object, prefix: str, length: int = 24) -> str:
    raw = "||".join("" if part is None else str(part) for part in parts)
    return prefix + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:length]


def _norm_text(value: object) -> str:
    return " ".join(str(value or "").split())


def _norm_qualifiers(value: object) -> dict[str, str]:
    raw = value if isinstance(value, dict) else {}
    return {key: str(raw.get(key, "") or "") for key in QUALIFIER_KEYS}


def _stable_json_value(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def _strict_signature(claim: dict) -> tuple:
    qualifiers = _norm_qualifiers(claim.get("qualifiers_raw", {}))
    return (
        str(claim.get("subject_taxon_id", "") or ""),
        str(claim.get("subject_rank", "") or ""),
        str(claim.get("fact_domain", "") or ""),
        str(claim.get("predicate", "") or ""),
        str(claim.get("object_type", "") or ""),
        _norm_text(claim.get("object_text", "")),
        str(claim.get("object_canonical_id", "") or ""),
        _norm_text(claim.get("object_canonical_name", "")),
        _stable_json_value(claim.get("value_min")),
        _stable_json_value(claim.get("value_max")),
        str(claim.get("unit", "") or ""),
        json.dumps(qualifiers, sort_keys=True, ensure_ascii=False),
        str(claim.get("source_db", "") or ""),
        str(claim.get("source_release", "") or ""),
        str(claim.get("source_doc_id", "") or ""),
        str(claim.get("source_chunk_id", "") or ""),
        str(claim.get("source_chapter", "") or ""),
        str(claim.get("source_subchapter", "") or ""),
        _norm_text(claim.get("evidence_quote", "")),
    )


def _claim_sort_key(row: dict) -> tuple[str, str, str, str, str, str, str]:
    return (
        str(row.get("subject_rank", "") or row.get("record_type", "") or ""),
        str(row.get("subject_taxon_id", "") or ""),
        str(row.get("source_doc_id", "") or ""),
        str(row.get("source_chunk_id", "") or ""),
        str(row.get("fact_domain", "") or ""),
        str(row.get("predicate", "") or ""),
        str(row.get("claim_id", "") or ""),
    )


def _audit_row(source: str, file: str, row_no: int, claim: dict, reason: str, duplicate_of: dict | None = None) -> dict:
    return {
        "reason": reason,
        "source": source,
        "file": file,
        "row_no": row_no,
        "claim_id": claim.get("claim_id", ""),
        "supplement_claim_id": claim.get("supplement_claim_id", ""),
        "source_chunk_id": claim.get("source_chunk_id", ""),
        "subject_taxon_id": claim.get("subject_taxon_id", ""),
        "subject_rank": claim.get("subject_rank", ""),
        "fact_domain": claim.get("fact_domain", ""),
        "predicate": claim.get("predicate", ""),
        "object_text": claim.get("object_text", ""),
        "evidence_quote": claim.get("evidence_quote", ""),
        "duplicate_of": duplicate_of or {},
    }


def _load_old_claims(claims_dir: Path) -> tuple[list[dict], list[dict], list[dict]]:
    species = _read_jsonl(claims_dir / "species_claims.jsonl")
    family = _read_jsonl(claims_dir / "family_claims.jsonl")
    return species, family, species + family


def _load_supplement_claims(supplement_dir: Path, expected_shards: int) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    per_shard = []
    for shard_index in range(expected_shards):
        path = supplement_dir / f"shard_{shard_index:02d}" / "additional_claims.jsonl"
        shard_rows = _read_jsonl(path)
        for row_no, row in enumerate(shard_rows, start=1):
            claim = dict(row)
            claim["_supplement_source_file"] = str(path)
            claim["_supplement_row_no"] = row_no
            rows.append(claim)
        per_shard.append({"shard_index": shard_index, "additional_claims": len(shard_rows), "path": _display_path(path)})
    return rows, {"per_shard": per_shard}


def _prepare_supplement_claim(claim: dict) -> dict:
    payload = {key: value for key, value in claim.items() if not key.startswith("_")}
    payload["qualifiers_raw"] = _norm_qualifiers(payload.get("qualifiers_raw", {}))
    payload["extraction_method"] = payload.get("extraction_method") or "claim_cap_supplement"
    payload["claim_id"] = _sha1_id(*_strict_signature(payload), prefix="claim_supp_", length=24)
    return payload


def _build_taxon_index(sorted_claims: list[dict]) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for row_index, claim in enumerate(sorted_claims):
        taxon_id = str(claim.get("subject_taxon_id", "") or "__missing_subject_taxon_id__")
        entry = index.setdefault(
            taxon_id,
            {
                "subject_taxon_id": taxon_id,
                "subject_rank": claim.get("subject_rank", ""),
                "claim_count": 0,
                "chunk_count": 0,
                "source_chunk_ids": [],
                "start_row": row_index,
                "end_row": row_index,
            },
        )
        entry["claim_count"] += 1
        entry["end_row"] = row_index
        chunk_id = str(claim.get("source_chunk_id", "") or "")
        if chunk_id and chunk_id not in entry["source_chunk_ids"]:
            entry["source_chunk_ids"].append(chunk_id)
            entry["chunk_count"] += 1
    return index


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _near_duplicate_supplements(supplement_claims: list[dict], *, max_rows: int = 20000) -> list[dict]:
    """Lightweight audit only; output is not used for merge decisions."""
    rows = []
    by_chunk_predicate: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for claim in supplement_claims:
        by_chunk_predicate[(str(claim.get("source_chunk_id", "")), str(claim.get("predicate", "")))].append(claim)
    for (chunk_id, predicate), claims in by_chunk_predicate.items():
        if len(claims) < 2:
            continue
        for i, left in enumerate(claims):
            left_obj = _norm_text(left.get("object_text", "")).casefold()
            for right in claims[i + 1 :]:
                score = _similarity(left_obj, _norm_text(right.get("object_text", "")).casefold())
                if score >= 0.9 and left.get("claim_id") != right.get("claim_id"):
                    rows.append(
                        {
                            "source_chunk_id": chunk_id,
                            "predicate": predicate,
                            "left_claim_id": left.get("claim_id", ""),
                            "right_claim_id": right.get("claim_id", ""),
                            "left_object_text": left.get("object_text", ""),
                            "right_object_text": right.get("object_text", ""),
                            "object_similarity": round(score, 4),
                        }
                    )
                    if len(rows) >= max_rows:
                        return rows
    return rows


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value).replace("|", "\\|") for value in row) + " |")
    return "\n".join(lines)


def _fmt_int(value: int) -> str:
    return f"{value:,}"


def _build_markdown(summary: dict) -> str:
    overview_rows = [
        ["Audit status", summary["audit_status"]],
        ["Old official claims", _fmt_int(summary["old_official_claims_count"])],
        ["Supplement raw claims", _fmt_int(summary["supplement_raw_claims_count"])],
        ["Supplement strict duplicates dropped", _fmt_int(summary["supplement_strict_duplicates_dropped"])],
        ["Merged official claims", _fmt_int(summary["merged_official_claims_count"])],
        ["Species claims", _fmt_int(summary["species_claims_count"])],
        ["Family claims", _fmt_int(summary["family_claims_count"])],
        ["Taxon count", _fmt_int(summary["taxon_count"])],
        ["Processed unique chunks", _fmt_int(summary["processed_unique_chunks_count"])],
        ["Supplement covered chunks", _fmt_int(summary["supplement_covered_unique_chunks"])],
        ["Supplement hit-soft-cap chunks", _fmt_int(summary["supplement_hit_soft_cap_chunk_count"])],
        ["Supplement failures", _fmt_int(summary["supplement_run_failures_count"])],
        ["Invalid supplement chunk refs", _fmt_int(summary["invalid_supplement_chunk_ref_count"])],
        ["Merged duplicate claim_id count", _fmt_int(summary["merged_duplicate_claim_id_count"])],
    ]
    failure_rows = [[item] for item in summary["audit_failures"]] or [["None"]]
    output_rows = [[key, value] for key, value in summary["output_files"].items()]
    return "\n\n".join(
        [
            "# Claim Cap Supplement Merge Audit",
            "Supplementary additional claims were merged as an additive Claim-layer v2. Old claims were retained.",
            "## Overview\n\n" + _markdown_table(["Metric", "Value"], overview_rows),
            "## Audit Failures\n\n" + _markdown_table(["Failure"], failure_rows),
            "## Outputs\n\n" + _markdown_table(["Artifact", "Path"], output_rows),
        ]
    )


def merge_claims_with_supplement(
    *,
    claims_dir: Path,
    supplement_dir: Path,
    supplement_audit_path: Path,
    out_dir: Path,
    expected_shards: int,
) -> dict:
    audit_failures: list[str] = []
    supplement_audit = _read_json(supplement_audit_path)
    supplement_global = supplement_audit.get("global", {}) if isinstance(supplement_audit.get("global"), dict) else {}
    supplement_failures = int(supplement_global.get("failures_count", -1))
    supplement_hit_soft_cap = int(supplement_global.get("hit_soft_cap_chunks_count", 0))
    supplement_reviewed_chunks = int(supplement_global.get("ok_review_count", 0) or 0)
    if supplement_global and not supplement_global.get("ready_to_merge", False):
        audit_failures.append("supplement full run audit is not ready_to_merge")
    if supplement_failures != 0:
        audit_failures.append(f"supplement run failures count is {supplement_failures}, expected 0")

    species_old, family_old, old_claims = _load_old_claims(claims_dir)
    processed_rows = _read_jsonl(claims_dir / "processed_unique_chunks.jsonl")
    processed_chunk_ids = {str(row.get("chunk_id", "") or row.get("source_chunk_id", "") or "") for row in processed_rows}
    processed_chunk_ids.discard("")
    supplement_raw, supplement_meta = _load_supplement_claims(supplement_dir, expected_shards)
    supplement_prepared = [_prepare_supplement_claim(row) for row in supplement_raw]

    old_signature_map: dict[tuple, dict] = {}
    old_claim_ids = set()
    for row_no, claim in enumerate(old_claims, start=1):
        old_signature_map.setdefault(_strict_signature(claim), {"source": "old", "row_no": row_no, "claim_id": claim.get("claim_id", "")})
        claim_id = str(claim.get("claim_id", "") or "")
        if claim_id:
            old_claim_ids.add(claim_id)

    duplicate_rows = []
    accepted_supplement: list[dict] = []
    seen_supp_signatures: dict[tuple, dict] = {}
    invalid_chunk_ref_rows = []
    supplement_duplicate_internal = 0
    supplement_duplicate_old = 0
    supplement_claim_id_conflicts_with_old = 0
    for raw_claim, claim in zip(supplement_raw, supplement_prepared):
        source_file = raw_claim.get("_supplement_source_file", "")
        row_no = int(raw_claim.get("_supplement_row_no", 0) or 0)
        chunk_id = str(claim.get("source_chunk_id", "") or "")
        if chunk_id not in processed_chunk_ids:
            invalid_chunk_ref_rows.append(_audit_row("supplement", source_file, row_no, claim, "supplement_source_chunk_not_in_processed"))
            continue
        signature = _strict_signature(claim)
        old_dup = old_signature_map.get(signature)
        if old_dup:
            supplement_duplicate_old += 1
            duplicate_rows.append(_audit_row("supplement", source_file, row_no, claim, "strict_duplicate_of_old_claim", old_dup))
            continue
        supp_dup = seen_supp_signatures.get(signature)
        if supp_dup:
            supplement_duplicate_internal += 1
            duplicate_rows.append(_audit_row("supplement", source_file, row_no, claim, "strict_duplicate_within_supplement", supp_dup))
            continue
        if str(claim.get("claim_id", "") or "") in old_claim_ids:
            supplement_claim_id_conflicts_with_old += 1
            duplicate_rows.append(_audit_row("supplement", source_file, row_no, claim, "claim_id_conflict_with_old"))
            continue
        seen_supp_signatures[signature] = {
            "source": "supplement",
            "file": source_file,
            "row_no": row_no,
            "claim_id": claim.get("claim_id", ""),
            "supplement_claim_id": claim.get("supplement_claim_id", ""),
        }
        accepted_supplement.append(claim)

    merged_claims = sorted(old_claims + accepted_supplement, key=_claim_sort_key)
    claim_id_counts = Counter(str(row.get("claim_id", "") or "") for row in merged_claims if str(row.get("claim_id", "") or ""))
    duplicate_claim_ids = {claim_id: count for claim_id, count in claim_id_counts.items() if count > 1}
    missing_claim_id_count = sum(1 for row in merged_claims if not str(row.get("claim_id", "") or ""))
    species_claims = [row for row in merged_claims if str(row.get("subject_rank", "") or "") == "species"]
    family_claims = [row for row in merged_claims if str(row.get("subject_rank", "") or "") == "family"]
    taxon_index = _build_taxon_index(merged_claims)
    near_dup_rows = _near_duplicate_supplements(accepted_supplement)

    if len(old_claims) != EXPECTED_OLD_CLAIMS:
        audit_failures.append(f"old official claims count {len(old_claims)} != expected {EXPECTED_OLD_CLAIMS}")
    if len(species_old) != EXPECTED_SPECIES_CLAIMS:
        audit_failures.append(f"old species claims count {len(species_old)} != expected {EXPECTED_SPECIES_CLAIMS}")
    if len(family_old) != EXPECTED_FAMILY_CLAIMS:
        audit_failures.append(f"old family claims count {len(family_old)} != expected {EXPECTED_FAMILY_CLAIMS}")
    if len(processed_rows) != EXPECTED_PROCESSED_CHUNKS or len(processed_chunk_ids) != EXPECTED_PROCESSED_CHUNKS:
        audit_failures.append(
            f"processed unique chunks count rows={len(processed_rows)} unique={len(processed_chunk_ids)} expected {EXPECTED_PROCESSED_CHUNKS}"
        )
    if len(supplement_raw) != EXPECTED_SUPPLEMENT_CLAIMS:
        audit_failures.append(f"supplement raw claims count {len(supplement_raw)} != expected {EXPECTED_SUPPLEMENT_CLAIMS}")
    supplement_claim_bearing_chunks = len({str(row.get("source_chunk_id", "") or "") for row in supplement_prepared})
    if supplement_reviewed_chunks != EXPECTED_SUPPLEMENT_CHUNKS:
        audit_failures.append(f"supplement reviewed unique chunks {supplement_reviewed_chunks} != expected {EXPECTED_SUPPLEMENT_CHUNKS}")
    if supplement_hit_soft_cap != EXPECTED_HIT_SOFT_CAP:
        audit_failures.append(f"supplement hit_soft_cap {supplement_hit_soft_cap} != expected {EXPECTED_HIT_SOFT_CAP}")
    if invalid_chunk_ref_rows:
        audit_failures.append(f"{len(invalid_chunk_ref_rows)} supplement claims reference chunks outside processed_unique_chunks")
    if duplicate_claim_ids:
        audit_failures.append(f"merged output has {len(duplicate_claim_ids)} duplicate claim_id values")
    if missing_claim_id_count:
        audit_failures.append(f"merged output has {missing_claim_id_count} missing claim_id rows")
    if len(species_claims) + len(family_claims) != len(merged_claims):
        audit_failures.append("merged species + family counts do not equal total merged claims")

    audit_status = "ok" if not audit_failures else "fail"
    out_dir.mkdir(parents=True, exist_ok=True)
    output_files = {
        "species_claims": out_dir / "species_claims.jsonl",
        "family_claims": out_dir / "family_claims.jsonl",
        "all_claims": out_dir / "all_claims.jsonl",
        "processed_unique_chunks": out_dir / "processed_unique_chunks.jsonl",
        "taxon_claim_index": out_dir / "taxon_claim_index.json",
        "claim_merge_summary": out_dir / "claim_merge_summary.json",
        "claim_merge_audit": out_dir / "claim_merge_audit.md",
        "duplicate_claim_rows": out_dir / "duplicate_claim_rows.jsonl",
        "supplement_merge_summary": out_dir / "supplement_merge_summary.json",
        "supplement_merge_summary_md": out_dir / "supplement_merge_summary.md",
        "possible_near_duplicate_supplement_claims": out_dir / "possible_near_duplicate_supplement_claims.jsonl",
    }
    write_jsonl(output_files["species_claims"], species_claims)
    write_jsonl(output_files["family_claims"], family_claims)
    write_jsonl(output_files["all_claims"], merged_claims)
    shutil.copyfile(claims_dir / "processed_unique_chunks.jsonl", output_files["processed_unique_chunks"])
    write_json(output_files["taxon_claim_index"], taxon_index)
    write_jsonl(output_files["duplicate_claim_rows"], duplicate_rows + invalid_chunk_ref_rows)
    write_jsonl(output_files["possible_near_duplicate_supplement_claims"], near_dup_rows)

    summary = {
        "audit_status": audit_status,
        "audit_failures": audit_failures,
        "claims_dir": _display_path(claims_dir),
        "supplement_dir": _display_path(supplement_dir),
        "out_dir": _display_path(out_dir),
        "old_official_claims_count": len(old_claims),
        "old_species_claims_count": len(species_old),
        "old_family_claims_count": len(family_old),
        "supplement_raw_claims_count": len(supplement_raw),
        "supplement_accepted_claims_count": len(accepted_supplement),
        "supplement_strict_duplicates_dropped": supplement_duplicate_internal + supplement_duplicate_old,
        "supplement_internal_strict_duplicates_dropped": supplement_duplicate_internal,
        "supplement_old_strict_duplicates_dropped": supplement_duplicate_old,
        "supplement_claim_id_conflicts_with_old": supplement_claim_id_conflicts_with_old,
        "invalid_supplement_chunk_ref_count": len(invalid_chunk_ref_rows),
        "merged_official_claims_count": len(merged_claims),
        "species_claims_count": len(species_claims),
        "family_claims_count": len(family_claims),
        "taxon_count": len(taxon_index),
        "processed_unique_chunks_count": len(processed_rows),
        "processed_unique_chunk_id_count": len(processed_chunk_ids),
        "supplement_covered_unique_chunks": supplement_reviewed_chunks,
        "supplement_claim_bearing_unique_chunks": supplement_claim_bearing_chunks,
        "supplement_hit_soft_cap_chunk_count": supplement_hit_soft_cap,
        "supplement_run_failures_count": supplement_failures,
        "merged_duplicate_claim_id_count": len(duplicate_claim_ids),
        "merged_duplicate_claim_id_row_excess": sum(count - 1 for count in duplicate_claim_ids.values()),
        "missing_claim_id_count": missing_claim_id_count,
        "duplicate_claim_rows_count": len(duplicate_rows) + len(invalid_chunk_ref_rows),
        "possible_near_duplicate_supplement_claims_count": len(near_dup_rows),
        "claim_count_by_rank": dict(Counter(str(row.get("subject_rank", "") or "") for row in merged_claims)),
        "supplement_meta": supplement_meta,
        "output_files": {key: _display_path(path) for key, path in output_files.items()},
        "note": "claims_final_global_v2 is additive: all old official claims are retained; strict duplicate supplement rows are dropped.",
    }
    write_json(output_files["claim_merge_summary"], summary)
    write_json(output_files["supplement_merge_summary"], summary)
    output_files["claim_merge_audit"].write_text(_build_markdown(summary), encoding="utf-8")
    output_files["supplement_merge_summary_md"].write_text(_build_markdown(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge cap supplementary claims into claims_final_global_v2.")
    parser.add_argument("--claims-dir", default="KG/intermediate/claims_final_global")
    parser.add_argument("--supplement-dir", default="KG/intermediate/claims_cap_supplement_full")
    parser.add_argument("--supplement-audit", default="KG/reports/claim_cap_supplement_full_run_audit.json")
    parser.add_argument("--out-dir", default="KG/intermediate/claims_final_global_v2")
    parser.add_argument("--expected-shards", type=int, default=16)
    args = parser.parse_args()
    summary = merge_claims_with_supplement(
        claims_dir=_resolve_path(args.claims_dir),
        supplement_dir=_resolve_path(args.supplement_dir),
        supplement_audit_path=_resolve_path(args.supplement_audit),
        out_dir=_resolve_path(args.out_dir),
        expected_shards=args.expected_shards,
    )
    print(f"[Step3][CLAIM_CAP_SUPPLEMENT_MERGE] summary={summary['output_files']['claim_merge_summary']}")
    print(f"[Step3][CLAIM_CAP_SUPPLEMENT_MERGE] audit={summary['output_files']['claim_merge_audit']}")
    print(
        "[Step3][CLAIM_CAP_SUPPLEMENT_MERGE] "
        f"old={summary['old_official_claims_count']} supplement_raw={summary['supplement_raw_claims_count']} "
        f"supplement_accepted={summary['supplement_accepted_claims_count']} "
        f"duplicates_dropped={summary['supplement_strict_duplicates_dropped']} "
        f"merged={summary['merged_official_claims_count']} "
        f"species={summary['species_claims_count']} family={summary['family_claims_count']} "
        f"status={summary['audit_status']}"
    )
    if summary["audit_status"] != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
