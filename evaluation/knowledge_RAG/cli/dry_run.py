from __future__ import annotations

import importlib.util
import json
from argparse import Namespace
from pathlib import Path

from evaluation.knowledge_RAG.cli.common import config_from_args, default_out_dir, resolve_datasets
from evaluation.knowledge_RAG.registry import build_retriever
from evaluation.knowledge_RAG.retrievers.base import RetrievalRequest


def _status(ok: bool, label: str, detail: str = "") -> tuple[bool, str]:
    prefix = "[OK]" if ok else "[WARN]"
    return ok, f"{prefix} {label}{(': ' + detail) if detail else ''}"


def _question_file_exists(question_root: str, dataset: str) -> bool:
    root = Path(question_root)
    candidates = [
        root / dataset / f"{dataset}_questions.jsonl",
        root / dataset / f"{dataset}.jsonl",
        root / f"{dataset}.jsonl",
    ]
    return any(path.exists() for path in candidates)


def run_dry_run(args: Namespace, task_type: str, modes: list[str] | None = None) -> int:
    datasets = resolve_datasets(args, task_type)
    args.datasets = datasets
    cfg = config_from_args(args)
    out_dir = args.out_dir or default_out_dir(task_type, args.knowledge_mode, args.question_root, args.out_root)
    checks: list[tuple[bool, str]] = []

    checks.append(_status(Path(args.question_root).exists(), "question root", args.question_root))
    checks.append(_status(bool(datasets), "datasets resolved", ", ".join(datasets)))
    for dataset in datasets:
        checks.append(_status(_question_file_exists(args.question_root, dataset), f"question file for {dataset}"))

    checks.append(_status(bool(args.models), "models resolved", ", ".join(args.models or [])))
    if any(str(model).lower() == "deepseek" for model in (args.models or [])):
        env_text = Path(".env").read_text(encoding="utf-8", errors="ignore") if Path(".env").exists() else ""
        checks.append(_status("DEEPSEEK_API_KEY=" in env_text, "DeepSeek key configured", "suffix hidden"))

    if args.knowledge_mode == "text_rag":
        checks.append(_status(Path("kg_v2/outputs/intermediate/species_chunks.jsonl").exists(), "species chunks"))
        checks.append(_status(Path("kg_v2/outputs/intermediate/family_chunks.jsonl").exists(), "family chunks"))
    if args.knowledge_mode in {"kg_v3", "hybrid"}:
        checks.append(_status(cfg.embedding_provider != "disabled" or cfg.kg_backend == "neo4j", "embedding availability for selected backend"))
        if cfg.embedding_provider == "api_compatible":
            checks.append(_status(bool(cfg.embedding_model), "embedding model configured", cfg.embedding_model))
            import os

            checks.append(_status(bool(os.environ.get("EMBEDDING_API_BASE", "").strip()), "EMBEDDING_API_BASE configured"))
            checks.append(_status(bool(os.environ.get("EMBEDDING_API_KEY", "").strip()), "EMBEDDING_API_KEY configured", "suffix hidden"))
        if cfg.enable_reranker and cfg.reranker_provider == "api_compatible":
            import os

            checks.append(_status(bool(os.environ.get("RERANKER_API_BASE", "").strip()), "RERANKER_API_BASE configured"))
            checks.append(_status(bool(os.environ.get("RERANKER_API_KEY", "").strip()), "RERANKER_API_KEY configured", "suffix hidden"))
        if cfg.kg_backend in {"neo4j", "hybrid"}:
            checks.append(_status(importlib.util.find_spec("neo4j") is not None, "neo4j package"))
        if cfg.kg_backend in {"lightrag", "hybrid"}:
            checks.append(_status(Path(cfg.lightrag_working_dir, "docs.jsonl").exists(), "LightRAG docs.jsonl"))
            checks.append(_status(Path(cfg.lightrag_working_dir, "embedding_manifest.json").exists(), "LightRAG embedding manifest"))

    try:
        sample_dataset = datasets[0] if datasets else ""
        if args.knowledge_mode == "text_rag":
            # Avoid loading the full raw chunk index during smoke checks.
            retriever_name = "TextChunkRetriever(path-check only)"
        elif args.knowledge_mode == "hybrid" or cfg.kg_backend in {"lightrag", "hybrid"}:
            # Avoid touching LightRAG storage/manifest or remote embedding/reranker APIs in dry-run.
            retriever_name = f"{args.knowledge_mode}:{sample_dataset or 'generic'} (config-check only)"
        else:
            build_retriever(cfg, dataset=sample_dataset)
            retriever_name = f"{args.knowledge_mode}:{sample_dataset or 'generic'}"
        checks.append(_status(True, "retriever initialization", retriever_name))
    except Exception as exc:
        checks.append(_status(False, "retriever initialization", str(exc)))

    request = RetrievalRequest(
        question_id="dry-run",
        dataset=datasets[0] if datasets else "",
        question="Dry-run question; no LLM call will be made.",
        target_entity="Dry-run target",
        mode=(modes or ["zero_shot"])[0],
        raw_item={"question_id": "dry-run", "dataset": datasets[0] if datasets else ""},
    )
    checks.append(_status(bool(request.question), "request object"))
    checks.append(_status(True, "output directory planned", out_dir))

    print(json.dumps(
        {
            "dry_run": True,
            "task_type": task_type,
            "dataset_group": getattr(args, "dataset_group", ""),
            "knowledge_mode": args.knowledge_mode,
            "out_dir": out_dir,
            "datasets": datasets,
            "modes": modes or [],
        },
        ensure_ascii=False,
        indent=2,
    ))
    for ok, line in checks:
        print(line)
    warn_count = sum(1 for ok, _ in checks if not ok)
    print(f"[DRY-RUN] completed with {warn_count} warning(s); no LLM/API calls were made.")
    return 0
