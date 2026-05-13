"""Merge Step 3 claim extraction shard outputs."""

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

from kg_v2.Step3_extraction.reporting import build_extraction_summary
from kg_v2.utils.jsonl_utils import write_json, write_jsonl


JSONL_NAMES = [
    "species_claims.jsonl",
    "family_claims.jsonl",
    "species_facts.jsonl",
    "family_facts.jsonl",
    "evidences.jsonl",
    "fact_evidence_links.jsonl",
    "extractor_failures.jsonl",
    "processed_chunks.jsonl",
]


def _resolve_under_kg(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return (KG_ROOT / path).resolve()


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def discover_shards(shards_dir: Path) -> list[Path]:
    return sorted(path for path in shards_dir.iterdir() if path.is_dir() and path.name.startswith("shard_"))


def validate_coverage(shard_dirs: list[Path], shard_summaries: list[dict]) -> dict:
    errors: list[str] = []
    total_globals = {int(summary.get("total_global", 0)) for summary in shard_summaries if summary}
    num_shards_values = {int(summary.get("num_shards", 0)) for summary in shard_summaries if summary}
    if len(total_globals) != 1:
        errors.append(f"inconsistent total_global values: {sorted(total_globals)}")
    if len(num_shards_values) != 1:
        errors.append(f"inconsistent num_shards values: {sorted(num_shards_values)}")

    expected_total = next(iter(total_globals), 0)
    expected_num_shards = next(iter(num_shards_values), len(shard_dirs))
    observed_shard_indexes = sorted(
        int(summary.get("shard_index", -1)) for summary in shard_summaries if summary.get("shard_index", -1) != -1
    )
    missing_shard_indexes = sorted(set(range(expected_num_shards)) - set(observed_shard_indexes))
    if missing_shard_indexes:
        errors.append(f"missing shard indexes: {missing_shard_indexes}")

    per_shard_counts: dict[str, int] = {}
    chunk_counter: Counter = Counter()
    for shard_dir in shard_dirs:
        processed_path = shard_dir / "processed_chunks.jsonl"
        if not processed_path.exists():
            errors.append(f"missing processed_chunks.jsonl in {shard_dir}")
        rows = read_jsonl(processed_path)
        per_shard_counts[shard_dir.name] = len(rows)
        for row in rows:
            chunk_id = str(row.get("chunk_id", "") or "").strip()
            if chunk_id:
                chunk_counter[chunk_id] += 1

    duplicate_chunk_count = sum(count - 1 for count in chunk_counter.values() if count > 1)
    missing_chunk_count = max(expected_total - len(chunk_counter), 0)
    if duplicate_chunk_count:
        errors.append(f"duplicate chunk ids detected: {duplicate_chunk_count}")
    if missing_chunk_count:
        errors.append(f"missing chunk ids detected: {missing_chunk_count}")

    return {
        "ok": not errors,
        "duplicate_chunk_count": duplicate_chunk_count,
        "missing_chunk_count": missing_chunk_count,
        "per_shard_counts": per_shard_counts,
        "total_global": expected_total,
        "unique_chunk_count": len(chunk_counter),
        "observed_chunk_record_count": sum(chunk_counter.values()),
        "expected_num_shards": expected_num_shards,
        "observed_shard_indexes": observed_shard_indexes,
        "missing_shard_indexes": missing_shard_indexes,
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge Step 3 claim extraction shard directories.")
    parser.add_argument("--shards-dir", required=True)
    parser.add_argument("--claims-out-dir", required=True)
    args = parser.parse_args()

    shards_dir = _resolve_under_kg(args.shards_dir)
    claims_out_dir = _resolve_under_kg(args.claims_out_dir)
    shard_dirs = discover_shards(shards_dir)
    shard_summaries = [read_json(shard_dir / "extraction_summary.json") for shard_dir in shard_dirs]
    coverage = validate_coverage(shard_dirs, shard_summaries)
    if not coverage["ok"]:
        print(json.dumps({"status": "fail", "coverage": coverage}, ensure_ascii=False, indent=2), flush=True)
        raise SystemExit(1)

    claims_out_dir.mkdir(parents=True, exist_ok=True)

    merged: dict[str, list[dict]] = {}
    for name in JSONL_NAMES:
        rows: list[dict] = []
        for shard_dir in shard_dirs:
            rows.extend(read_jsonl(shard_dir / name))
        merged[name] = rows
        write_jsonl(claims_out_dir / name, rows)

    dropped_reasons: Counter = Counter()
    extractor_mode = ""
    species_chunks_processed = 0
    family_chunks_processed = 0
    species_chunk_total = 0
    family_chunk_total = 0
    for summary in shard_summaries:
        extractor_mode = extractor_mode or summary.get("extractor_mode", "")
        species_chunks_processed += int(summary.get("species_chunks_processed", 0))
        family_chunks_processed += int(summary.get("family_chunks_processed", 0))
        species_chunk_total = max(species_chunk_total, int(summary.get("species_chunk_total", 0)))
        family_chunk_total = max(family_chunk_total, int(summary.get("family_chunk_total", 0)))
        for item in summary.get("dropped_claim_reasons", []):
            dropped_reasons[item.get("reason", "")] += int(item.get("count", 0))

    summary = build_extraction_summary(
        species_chunk_total=species_chunk_total,
        family_chunk_total=family_chunk_total,
        species_chunks_processed=species_chunks_processed,
        family_chunks_processed=family_chunks_processed,
        species_claims=merged["species_claims.jsonl"],
        family_claims=merged["family_claims.jsonl"],
        species_facts=merged["species_facts.jsonl"],
        family_facts=merged["family_facts.jsonl"],
        evidences=merged["evidences.jsonl"],
        fact_evidence_links=merged["fact_evidence_links.jsonl"],
        dropped_reasons=dropped_reasons,
        extractor_mode=extractor_mode,
    )
    summary.update(
        {
            "merge_source": str(shards_dir),
            "claims_out_dir": str(claims_out_dir),
            "shard_count": len(shard_dirs),
            "shards": [str(path) for path in shard_dirs],
            "coverage": coverage,
            "duplicate_chunk_count": coverage["duplicate_chunk_count"],
            "missing_chunk_count": coverage["missing_chunk_count"],
            "per_shard_counts": coverage["per_shard_counts"],
        }
    )
    write_json(claims_out_dir / "extraction_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
