from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from audit_unused_files import ARCHIVE_KEEP_PATTERNS, PROJECT_ROOT, _matches


ARCHIVE_ROOT = PROJECT_ROOT / "_archive_unused" / os.environ.get("ARCHIVE_DATE", "2026-05-01")


def _rel(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _load_report(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Audit report must be a list.")
    return payload


def _eligible(row: dict) -> bool:
    rel = str(row.get("path", "")).replace("\\", "/")
    if not rel:
        return False
    if _matches(ARCHIVE_KEEP_PATTERNS, rel):
        return False
    return row.get("confidence") == "high" and row.get("suggested_action") == "archive"


def _run_verification() -> tuple[bool, list[str]]:
    commands = [
        [sys.executable, "-m", "compileall", "evaluation/kg_RAG", "evaluation/text_RAG", "evaluation/knowledge_RAG", "kg_v2/Step4_graph", "scripts"],
        [sys.executable, "evaluation/knowledge_RAG/cli/run_objective.py", "--help"],
        [sys.executable, "evaluation/knowledge_RAG/cli/run_subjective.py", "--help"],
        [sys.executable, "evaluation/knowledge_RAG/cli/run_structured.py", "--help"],
        [sys.executable, "evaluation/knowledge_RAG/cli/run_all.py", "--help"],
    ]
    logs: list[str] = []
    for cmd in commands:
        proc = subprocess.run(cmd, cwd=PROJECT_ROOT, text=True, capture_output=True)
        logs.append(f"$ {' '.join(cmd)}\n{proc.stdout}\n{proc.stderr}")
        if proc.returncode != 0:
            return False, logs
    return True, logs


def _rollback(moved: list[tuple[Path, Path]]) -> None:
    for src, dst in reversed(moved):
        if dst.exists():
            src.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dst), str(src))


def archive(report_path: Path, *, execute: bool) -> int:
    rows = _load_report(report_path)
    selected = [row for row in rows if _eligible(row)]
    print(f"[ARCHIVE] eligible high-confidence files: {len(selected)}")
    if not execute:
        for row in selected:
            print(f"[DRY-RUN] {row['path']} -> {ARCHIVE_ROOT / 'files' / row['path']}")
        print("[DRY-RUN] no files moved. Re-run with --execute after manual review.")
        return 0

    moved: list[tuple[Path, Path]] = []
    manifest = {
        "created_at": datetime.now().isoformat(),
        "report_path": _rel(report_path),
        "files": [],
    }
    try:
        for row in selected:
            rel = str(row["path"]).replace("\\", "/")
            src = PROJECT_ROOT / rel
            if not src.exists():
                continue
            dst = ARCHIVE_ROOT / "files" / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            moved.append((src, dst))
            manifest["files"].append(
                {
                    "path": rel,
                    "archived_to": _rel(dst),
                    "reason": row.get("reason", ""),
                    "confidence": row.get("confidence", ""),
                }
            )
        ARCHIVE_ROOT.mkdir(parents=True, exist_ok=True)
        (ARCHIVE_ROOT / "archive_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        (ARCHIVE_ROOT / "original_path_manifest.json").write_text(json.dumps(manifest["files"], ensure_ascii=False, indent=2), encoding="utf-8")
        ok, logs = _run_verification()
        (ARCHIVE_ROOT / "verification.log").write_text("\n\n".join(logs), encoding="utf-8")
        if not ok:
            print("[ERROR] verification failed; rolling back archived files.")
            _rollback(moved)
            return 1
    except Exception:
        _rollback(moved)
        raise
    print(f"[OK] archived {len(moved)} file(s) to {_rel(ARCHIVE_ROOT)}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Archive high-confidence files from audit report with rollback.")
    parser.add_argument("--report", type=str, default="reports/unused_file_audit.json")
    parser.add_argument("--execute", action="store_true", help="Actually move files. Without this flag, only dry-runs.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return archive(PROJECT_ROOT / args.report, execute=args.execute)


if __name__ == "__main__":
    raise SystemExit(main())
