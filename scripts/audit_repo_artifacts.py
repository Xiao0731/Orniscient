"""Audit repository artifacts for Step3/KG cleanup planning.

This script is intentionally read-only with respect to existing project files.
It scans selected repository areas and writes a cleanup plan under KG/reports.
It does not move, delete, or rewrite any scanned artifact.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]

SCAN_ROOTS = [
    Path("KG"),
    Path("kg_v2/Step3_extraction"),
    Path("evaluation/knowledge_RAG"),
    Path("docs/reports"),
    Path("docs/Echarts"),
    Path("docs/assets"),
]

REPORT_JSON = Path("KG/reports/repo_artifact_cleanup_plan.json")
REPORT_MD = Path("KG/reports/repo_artifact_cleanup_plan.md")


KEEP_IN_PIPELINE = {
    "run_extract_claims_and_facts.py",
    "llm_extractors.py",
    "chapter_router.py",
    "predicate_registry.py",
    "fact_builder.py",
    "merge_old_and_repair_claims.py",
    "merge_claims_with_cap_supplement.py",
    "rebuild_global_facts_from_claims.py",
    "summarize_final_kg_v2_stats.py",
    "demo_compare.py",
    "run_claim_cap_supplement_full.py",
    "merge_claim_shards.py",
    "summarize_claim_shards.py",
    "loaders.py",
    "normalizers.py",
    "evidence_builder.py",
    "reporting.py",
    "registry.py",
    "runtime.py",
    "config.py",
    "__init__.py",
}

METHOD_AUDIT_STEMS = {
    "claim_extraction_policy_audit",
    "claim_cap_chunk_review",
    "supplement_claim_quality_comparison_6_vs_12",
    "supplement_round2_quality_6plus6_vs_12extra",
    "fact_builder_selection_policy_audit",
    "fact_id_collision_audit",
    "final_kg_v2_stats",
    "claim_cap_supplement_review_compaction",
    "claim_cap_supplement_full_run_audit",
    "step3_candidate_selection_audit",
    "supplement_max12_verification",
}

MOVE_TO_AUDITS_DIR = {
    "audit_claim_extraction_policy.py",
    "review_claim_cap_chunks.py",
    "verify_supplement_max12.py",
    "audit_supplement_quality_6_vs_12.py",
    "audit_supplement_round2_6plus6_vs_12extra.py",
    "audit_fact_builder_selection_policy.py",
    "compact_claim_cap_supplement_reviews.py",
    "audit_claim_cap_supplement_full_run.py",
    "audit_step3_candidate_selection.py",
    "plan_step3_repair.py",
}

IGNORE_DIR_PARTS = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

LARGE_LOCAL_PREFIXES = (
    "KG/intermediate/",
    "KG/archive/",
    "KG/logs/",
)

TEMP_NAME_MARKERS = (
    "dry_run",
    "partial",
    "smoke",
    "retry",
    "cache",
    "run.err.log",
    "run.log",
    "broken",
    "duplicate_shard",
    ".tmp",
    ".temp",
)

SENSITIVE_OR_LARGE_MARKERS = (
    "neo4j",
    "vector",
    "embedding",
    "embeddings",
    "lightrag",
    "bow",
    "raw_text",
    "chunks_raw",
)


@dataclass(frozen=True)
class ArtifactEntry:
    path: str
    size_bytes: int
    size: str
    modified_time: str
    suggested_action: str
    reason: str


def rel_posix(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def human_size(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{size} B"


def stem_without_known_suffixes(path: Path) -> str:
    name = path.name
    for suffix in (".jsonl", ".json", ".md", ".csv", ".txt", ".log"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return name


def iter_files() -> Iterable[Path]:
    seen: set[Path] = set()
    for root in SCAN_ROOTS:
        abs_root = REPO_ROOT / root
        if not abs_root.exists():
            continue
        if abs_root.is_file():
            files = [abs_root]
        else:
            files = [p for p in abs_root.rglob("*") if p.is_file()]
        for file_path in files:
            resolved = file_path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            yield file_path


def classify(path: Path, size: int) -> tuple[str, str]:
    rel = rel_posix(path)
    rel_lower = rel.lower()
    name = path.name
    name_lower = name.lower()
    parts_lower = {part.lower() for part in path.parts}
    stem = stem_without_known_suffixes(path)

    if any(part in IGNORE_DIR_PARTS for part in parts_lower):
        return "ignore_from_git", "Python/tool cache directory should be ignored from version control."

    if rel == REPORT_JSON.as_posix() or rel == REPORT_MD.as_posix():
        return "keep_as_method_audit", "Generated cleanup audit report."

    if rel.replace("\\", "/").startswith(LARGE_LOCAL_PREFIXES):
        if any(marker in name_lower for marker in TEMP_NAME_MARKERS):
            return (
                "ignore_from_git",
                "Local intermediate/cache artifact under KG/intermediate; keep only if needed locally, do not commit.",
            )
        return (
            "ignore_from_git",
            "Large local KG artifact or shard output; keep locally as needed but exclude from git.",
        )

    if any(marker in rel_lower for marker in SENSITIVE_OR_LARGE_MARKERS):
        return "ignore_from_git", "Path suggests raw text, vector/embedding, Neo4j, BOW, or LightRAG artifact."

    if name in KEEP_IN_PIPELINE:
        return "keep_in_pipeline", "Main pipeline, registry, builder, merge, rebuild, summary, or demo script."

    if name in MOVE_TO_AUDITS_DIR:
        return "move_to_audits_dir", "One-off audit/review/verification script; preserve but move out of pipeline namespace."

    if rel.startswith("docs/Echarts/") and path.suffix.lower() == ".js":
        return "keep_in_pipeline", "README/chart data source kept in docs."

    if rel.startswith("docs/assets/"):
        return "keep_in_pipeline", "Documentation visual source or rendered asset."

    if rel.startswith("evaluation/knowledge_RAG/"):
        return "keep_in_pipeline", "Knowledge-RAG evaluation/demo package file."

    if rel.startswith("KG/reports/"):
        if any(marker in name_lower for marker in TEMP_NAME_MARKERS) or size == 0:
            return (
                "candidate_delete_after_manual_confirm",
                "Temporary, cache, dry-run, smoke, partial, run log, or empty report artifact.",
            )
        if stem in METHOD_AUDIT_STEMS:
            return "keep_as_method_audit", "Method-selection or final-statistics audit report worth preserving."
        return "move_to_archive", "Older or auxiliary KG report; preserve outside the active reports surface unless still referenced."

    if name_lower.endswith((".err.log", ".log")) or any(marker in name_lower for marker in TEMP_NAME_MARKERS):
        return "candidate_delete_after_manual_confirm", "Temporary run/cache/log artifact."

    if rel.startswith("kg_v2/Step3_extraction/") and path.suffix.lower() == ".py":
        return "move_to_archive", "Step3 helper script not classified as active pipeline or method audit."

    return "move_to_archive", "Scanned artifact without an explicit active-pipeline role."


def make_entry(path: Path) -> ArtifactEntry:
    stat = path.stat()
    action, reason = classify(path, stat.st_size)
    modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
    return ArtifactEntry(
        path=rel_posix(path),
        size_bytes=stat.st_size,
        size=human_size(stat.st_size),
        modified_time=modified,
        suggested_action=action,
        reason=reason,
    )


def summarize(entries: list[ArtifactEntry]) -> dict:
    by_action = Counter(entry.suggested_action for entry in entries)
    bytes_by_action: Counter[str] = Counter()
    for entry in entries:
        bytes_by_action[entry.suggested_action] += entry.size_bytes

    top_largest = sorted(entries, key=lambda item: item.size_bytes, reverse=True)[:30]
    missing_scan_roots = [
        root.as_posix() for root in SCAN_ROOTS if not (REPO_ROOT / root).exists()
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(REPO_ROOT),
        "scan_roots": [root.as_posix() for root in SCAN_ROOTS],
        "missing_scan_roots": missing_scan_roots,
        "total_files": len(entries),
        "total_size_bytes": sum(entry.size_bytes for entry in entries),
        "total_size": human_size(sum(entry.size_bytes for entry in entries)),
        "counts_by_suggested_action": dict(sorted(by_action.items())),
        "size_by_suggested_action": {
            action: {
                "bytes": bytes_by_action[action],
                "human": human_size(bytes_by_action[action]),
            }
            for action in sorted(bytes_by_action)
        },
        "top_largest_files": [asdict(entry) for entry in top_largest],
        "guardrail_patterns": {
            "large_or_sensitive": [
                "KG/intermediate/",
                "KG/archive/",
                "Neo4j dump/data",
                "vector DB / embeddings",
                "LightRAG cache",
                "BOW chunks/raw text",
                "eval large outputs/logs",
                ".env/API keys",
                "__pycache__",
            ],
            "manual_delete_candidates": list(TEMP_NAME_MARKERS),
        },
    }


def markdown_table(entries: list[ArtifactEntry]) -> str:
    lines = [
        "| File path | Size | Modified time (UTC) | Suggested action | Reason |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for entry in entries:
        reason = entry.reason.replace("|", "\\|")
        lines.append(
            f"| `{entry.path}` | {entry.size} | {entry.modified_time} | "
            f"`{entry.suggested_action}` | {reason} |"
        )
    return "\n".join(lines)


def write_markdown(entries: list[ArtifactEntry], summary: dict) -> str:
    by_action: dict[str, list[ArtifactEntry]] = defaultdict(list)
    for entry in entries:
        by_action[entry.suggested_action].append(entry)

    lines = [
        "# Repository Artifact Cleanup Plan",
        "",
        "Read-only audit for Step3 / KG repository cleanup. This report is a planning",
        "artifact only: no files were moved, deleted, or rewritten by the audit scan.",
        "",
        "## Summary",
        "",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Total scanned files: {summary['total_files']:,}",
        f"- Total scanned size: {summary['total_size']}",
        f"- Scan roots: {', '.join(f'`{root}`' for root in summary['scan_roots'])}",
    ]
    if summary["missing_scan_roots"]:
        lines.append(
            f"- Missing scan roots: {', '.join(f'`{root}`' for root in summary['missing_scan_roots'])}"
        )
    lines.extend(["", "## Counts by Suggested Action", ""])
    lines.extend(
        [
            "| Suggested action | Files | Size |",
            "| --- | ---: | ---: |",
        ]
    )
    for action, count in summary["counts_by_suggested_action"].items():
        size = summary["size_by_suggested_action"][action]["human"]
        lines.append(f"| `{action}` | {count:,} | {size} |")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `keep_in_pipeline`: active pipeline, docs data source, or demo/evaluation file.",
            "- `keep_as_method_audit`: method-selection or final-statistics audit report worth preserving.",
            "- `move_to_audits_dir`: one-off audit scripts that can be moved out of the active Step3 namespace after confirmation.",
            "- `move_to_archive`: auxiliary or older artifacts worth preserving outside the active surface.",
            "- `ignore_from_git`: large, local, generated, sensitive, or cache-like artifacts that should stay out of version control.",
            "- `candidate_delete_after_manual_confirm`: likely temporary files, caches, smoke outputs, logs, or empty artifacts; delete only after manual confirmation.",
            "",
            "## Largest Files",
            "",
        ]
    )
    lines.append(markdown_table([ArtifactEntry(**item) for item in summary["top_largest_files"]]))

    for action in sorted(by_action):
        lines.extend(["", f"## {action}", ""])
        entries_for_action = sorted(by_action[action], key=lambda item: item.path)
        lines.append(markdown_table(entries_for_action))

    return "\n".join(lines) + "\n"


def main() -> None:
    entries = sorted((make_entry(path) for path in iter_files()), key=lambda item: item.path)
    summary = summarize(entries)
    payload = {
        "summary": summary,
        "artifacts": [asdict(entry) for entry in entries],
    }

    json_path = REPO_ROOT / REPORT_JSON
    md_path = REPO_ROOT / REPORT_MD
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(write_markdown(entries, summary), encoding="utf-8")

    print(f"Wrote {REPORT_JSON.as_posix()}")
    print(f"Wrote {REPORT_MD.as_posix()}")
    print(f"Scanned files: {summary['total_files']}")
    for action, count in summary["counts_by_suggested_action"].items():
        print(f"{action}: {count}")


if __name__ == "__main__":
    main()
