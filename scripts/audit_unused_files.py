from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = PROJECT_ROOT / "reports"

ARCHIVE_KEEP_PATTERNS = [
    "question/**",
    "data/**",
    "evaluation/fewshot_examples/**",
    "evaluation/output/**",
    "evaluation/results*/**",
    "evaluation/text_RAG/**",
    "evaluation/kg_RAG/**",
    "evaluation/knowledge_RAG/**",
    "kg_v2/Step1*/**",
    "kg_v2/Step2*/**",
    "kg_v2/Step3*/**",
    "kg_v2/Step4_graph/**",
    "kg_v2/outputs/**",
    "image/**",
    "figures/**",
    "tables/**",
    "*.tex",
    "*.bib",
    "*.xlsx",
    "*.csv",
    "*.jsonl",
    "README.md",
    "**/README.md",
    ".env.example",
]

TEXT_REFERENCE_GLOBS = [
    "**/README.md",
    "docs/**/*.md",
    "**/*.bat",
    "**/*.ps1",
    "**/*.sh",
    "**/*.tex",
    "**/*.json",
    "**/*.yaml",
    "**/*.yml",
    "**/*.toml",
    "**/*.py",
]

SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    "LightRAG/lightrag_webui/node_modules",
    "_archive_unused",
    "_archive_deprecated",
    "docker_data",
    "evaluation/output",
    "kg_v2/outputs",
    "reports",
}


@dataclass
class AuditCandidate:
    path: str
    reason: str
    confidence: str
    referenced_by: list[str]
    last_modified: str
    file_type: str
    suggested_action: str


def _rel(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _is_under_skip(path: Path) -> bool:
    rel = _rel(path)
    parts = rel.split("/")
    for skip in SKIP_DIRS:
        if skip in parts:
            return True
        skip_parts = skip.split("/")
        if parts[: len(skip_parts)] == skip_parts:
            return True
    return False


def _matches(patterns: list[str], rel_path: str) -> bool:
    return any(fnmatch.fnmatch(rel_path, pattern) for pattern in patterns)


def _iter_files() -> list[Path]:
    files: list[Path] = []
    for root, dirnames, filenames in os.walk(PROJECT_ROOT):
        root_path = Path(root)
        rel_root = _rel(root_path) if root_path != PROJECT_ROOT else ""
        kept_dirs = []
        for dirname in dirnames:
            child = f"{rel_root}/{dirname}".strip("/")
            if dirname in SKIP_DIRS or child in SKIP_DIRS or _is_under_skip(PROJECT_ROOT / child):
                continue
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs
        for filename in filenames:
            path = root_path / filename
            if _is_under_skip(path):
                continue
            files.append(path)
    return files


def _module_names_for(path: Path) -> set[str]:
    rel = _rel(path)
    if not rel.endswith(".py"):
        return set()
    stem = rel[:-3].replace("/", ".")
    names = {stem, Path(rel).stem}
    if stem.endswith(".__init__"):
        names.add(stem[: -len(".__init__")])
    return names


def _extract_imports(path: Path) -> set[str]:
    if path.suffix != ".py":
        return set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return set()
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
            imports.add(node.module.split(".")[0])
    return imports


def _has_cli_markers(path: Path) -> bool:
    if path.suffix != ".py":
        return False
    text = path.read_text(encoding="utf-8", errors="ignore")
    markers = ['if __name__ == "__main__"', "argparse.ArgumentParser", "click.", "typer."]
    return any(marker in text for marker in markers)


def _string_references(files: list[Path]) -> dict[str, list[str]]:
    refs: dict[str, list[str]] = {}
    reference_files = [
        path
        for path in files
        if _matches(TEXT_REFERENCE_GLOBS, _rel(path)) and path.stat().st_size < 2_000_000
    ]
    file_rels = [_rel(path) for path in files]
    for ref_path in reference_files:
        text = ref_path.read_text(encoding="utf-8", errors="ignore")
        for rel in file_rels:
            if rel == _rel(ref_path):
                continue
            stem = Path(rel).stem
            candidates = {rel, rel.replace("/", "\\"), stem}
            if any(candidate and candidate in text for candidate in candidates):
                refs.setdefault(rel, []).append(_rel(ref_path))
            for match in re.findall(r'["\']((?:evaluation|kg_v2|text_RAG|kg_RAG|scripts)/[^"\']+)["\']', text):
                normalized = match.replace("\\", "/")
                if normalized == rel:
                    refs.setdefault(rel, []).append(_rel(ref_path))
    return refs


def audit() -> list[AuditCandidate]:
    files = _iter_files()
    module_refs: dict[str, list[str]] = {}
    for importer in files:
        for imported in _extract_imports(importer):
            module_refs.setdefault(imported, []).append(_rel(importer))
    string_refs = _string_references(files)

    candidates: list[AuditCandidate] = []
    for path in files:
        rel = _rel(path)
        if _matches(ARCHIVE_KEEP_PATTERNS, rel):
            continue
        suffix = path.suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg", ".svg", ".gif", ".pdf", ".zip", ".xlsx", ".csv", ".jsonl", ".tex", ".bib"}:
            continue
        refs = set(string_refs.get(rel, []))
        for module_name in _module_names_for(path):
            refs.update(module_refs.get(module_name, []))
        cli = _has_cli_markers(path)
        if refs or cli:
            candidates.append(
                AuditCandidate(
                    path=rel,
                    reason="Referenced by imports/text or exposes CLI markers; keep for now.",
                    confidence="low",
                    referenced_by=sorted(refs),
                    last_modified=datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                    file_type=suffix.lstrip(".") or "unknown",
                    suggested_action="keep" if cli else "manual_review",
                )
            )
            continue
        is_cache_or_log = "__pycache__" in rel or suffix in {".pyc", ".log", ".tmp"}
        candidates.append(
            AuditCandidate(
                path=rel,
                reason="No import/text/CLI references found by static audit." + (" Cache/log artifact." if is_cache_or_log else ""),
                confidence="high" if is_cache_or_log else "medium",
                referenced_by=[],
                last_modified=datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                file_type=suffix.lstrip(".") or "unknown",
                suggested_action="archive" if is_cache_or_log else "manual_review",
            )
        )
    return sorted(candidates, key=lambda row: (row.suggested_action, row.path))


def write_reports(candidates: list[AuditCandidate]) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORTS_DIR / "unused_file_audit.json"
    md_path = REPORTS_DIR / "unused_file_audit.md"
    payload = [asdict(candidate) for candidate in candidates]
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Unused File Audit", "", "This report is a dry-run. No files were moved.", ""]
    for candidate in candidates:
        lines.extend(
            [
                f"## `{candidate.path}`",
                f"- reason: {candidate.reason}",
                f"- confidence: {candidate.confidence}",
                f"- suggested_action: {candidate.suggested_action}",
                f"- file_type: {candidate.file_type}",
                f"- last_modified: {candidate.last_modified}",
                f"- referenced_by: {', '.join(candidate.referenced_by) if candidate.referenced_by else '(none)'}",
                "",
            ]
        )
    md_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit potentially unused files without moving anything.")
    parser.add_argument("--dry-run", action="store_true", help="Kept for explicitness; audit never moves files.")
    return parser.parse_args()


def main() -> int:
    parse_args()
    candidates = audit()
    write_reports(candidates)
    high_archive = [c for c in candidates if c.confidence == "high" and c.suggested_action == "archive"]
    print(f"[OK] wrote reports/unused_file_audit.md and reports/unused_file_audit.json")
    print(f"[OK] candidates={len(candidates)} high_confidence_archive={len(high_archive)}")
    for candidate in high_archive[:20]:
        print(f"[ARCHIVE-CANDIDATE] {candidate.path} :: {candidate.reason}")
    if len(high_archive) > 20:
        print(f"[ARCHIVE-CANDIDATE] ... {len(high_archive) - 20} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
