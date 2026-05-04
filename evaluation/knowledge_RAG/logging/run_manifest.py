from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evaluation.knowledge_RAG.config import KnowledgeRAGConfig


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def build_run_manifest(
    config: KnowledgeRAGConfig,
    *,
    question_root: str,
    models: list[str],
    datasets: list[str],
    dataset_group: str = "",
    modes: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "question_root": question_root,
        "knowledge_mode": config.knowledge_mode,
        "kg_backend": config.kg_backend,
        "kg_version": config.kg_version,
        "embedding_model": config.embedding_model,
        "embedding_dim": config.embedding_dim,
        "reranker_model": config.reranker_model,
        "reranker_enabled": config.enable_reranker,
        "models": models,
        "datasets": datasets,
        "dataset_group": dataset_group,
        "modes": modes or [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
    }
    if extra:
        payload.update(extra)
    return payload


def write_run_manifest(out_dir: str | Path, manifest: dict[str, Any]) -> Path:
    path = Path(out_dir) / "run_manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    for name in ["context_logs", "answers", "judge_results", "predictions", "summaries", "errors"]:
        (Path(out_dir) / name).mkdir(parents=True, exist_ok=True)
    return path
