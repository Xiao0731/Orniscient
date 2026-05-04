from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from evaluation.knowledge_RAG.config import KnowledgeRAGConfig, env, load_env
from evaluation.knowledge_RAG.logging.run_manifest import build_run_manifest, write_run_manifest
from evaluation.knowledge_RAG.routing.route_configs import DATASET_GROUPS


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--question-root", type=str, default="question")
    parser.add_argument("--out-dir", type=str, default="")
    parser.add_argument("--out-root", type=str, default="evaluation/output")
    parser.add_argument("--dataset-group", choices=["objective", "subjective", "structured", "all"], default="")
    parser.add_argument("--knowledge-mode", choices=["none", "text_rag", "kg_v1", "kg_v3", "hybrid"], default="hybrid")
    parser.add_argument("--kg-backend", choices=["neo4j", "lightrag", "hybrid"], default="hybrid")
    parser.add_argument("--kg-version", choices=["v1_directed", "v3_fact_graph"], default="v3_fact_graph")
    parser.add_argument("--retrieval-backend", choices=["text", "graph", "table", "hybrid"], default="hybrid")
    parser.add_argument("--query-mode", "--kg-query-mode", choices=["local", "global", "hybrid", "mix"], default="mix")
    parser.add_argument("--embedding-provider", choices=["bge_m3", "api_compatible", "disabled"], default="bge_m3")
    parser.add_argument("--embedding-model", type=str, default="BAAI/bge-m3")
    parser.add_argument("--embedding-dim", type=int, default=1024)
    parser.add_argument("--reranker-provider", choices=["bge_reranker", "api_compatible", "disabled"], default="bge_reranker")
    parser.add_argument("--reranker-model", type=str, default="BAAI/bge-reranker-v2-m3")
    parser.add_argument("--enable-reranker", dest="enable_reranker", action="store_true", default=True)
    parser.add_argument("--disable-reranker", dest="enable_reranker", action="store_false")
    parser.add_argument("--reranker-top-n", type=int, default=12)
    parser.add_argument("--lightrag-working-dir", type=str, default="kg_v2/outputs/lightrag_v3")
    parser.add_argument("--rebuild-vector-index", action="store_true")
    parser.add_argument("--models", nargs="*", default=["deepseek"])
    parser.add_argument("--datasets", nargs="*", default=None)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--save-predictions", action="store_true")
    parser.add_argument("--dry-run", action="store_true")


def config_from_args(args: argparse.Namespace) -> KnowledgeRAGConfig:
    load_env()
    def env_or_arg(env_name: str, arg_value, parser_default):
        return None if os.environ.get(env_name, "").strip() and arg_value == parser_default else arg_value

    return KnowledgeRAGConfig.from_env(
        knowledge_mode=args.knowledge_mode,
        kg_backend=args.kg_backend,
        kg_version=args.kg_version,
        retrieval_backend=args.retrieval_backend,
        query_mode=args.query_mode,
        embedding_provider=env_or_arg("EMBEDDING_PROVIDER", args.embedding_provider, "bge_m3"),
        embedding_model=env_or_arg("EMBEDDING_MODEL", args.embedding_model, "BAAI/bge-m3"),
        embedding_dim=env_or_arg("EMBEDDING_DIM", args.embedding_dim, 1024),
        reranker_provider=env_or_arg("RERANKER_PROVIDER", args.reranker_provider, "bge_reranker"),
        reranker_model=env_or_arg("RERANKER_MODEL", args.reranker_model, "BAAI/bge-reranker-v2-m3"),
        enable_reranker=args.enable_reranker,
        reranker_top_n=args.reranker_top_n,
        lightrag_working_dir=env_or_arg("LIGHTRAG_WORKING_DIR", args.lightrag_working_dir, "kg_v2/outputs/lightrag_v3"),
        rebuild_vector_index=args.rebuild_vector_index,
    )


def default_out_dir(task_type: str, knowledge_mode: str, question_root: str, out_root: str) -> str:
    tag = Path(question_root).name or "question"
    return str(Path(out_root) / f"results_{task_type}_{knowledge_mode}_{tag}")


def default_dataset_group(task_type: str) -> str:
    if task_type in {"objective", "subjective", "structured"}:
        return task_type
    return "all"


def resolve_datasets(args: argparse.Namespace, task_type: str) -> list[str]:
    if args.datasets:
        return list(args.datasets)
    group = getattr(args, "dataset_group", "") or default_dataset_group(task_type)
    if group == "all" and task_type in DATASET_GROUPS:
        group = task_type
    return list(DATASET_GROUPS.get(group, []))


def write_manifest_for_args(args: argparse.Namespace, task_type: str, modes: list[str] | None = None) -> str:
    args.datasets = resolve_datasets(args, task_type)
    if not getattr(args, "dataset_group", ""):
        args.dataset_group = default_dataset_group(task_type)
    cfg = config_from_args(args)
    cfg.validate()
    if any(str(model).lower() == "deepseek" for model in (args.models or [])) and not env("DEEPSEEK_API_KEY"):
        raise RuntimeError("Missing .env or missing required key: DEEPSEEK_API_KEY")
    out_dir = args.out_dir or default_out_dir(task_type, args.knowledge_mode, args.question_root, args.out_root)
    manifest = build_run_manifest(
        cfg,
        question_root=args.question_root,
        models=list(args.models or []),
        datasets=list(args.datasets or []),
        dataset_group=args.dataset_group,
        modes=modes or [],
    )
    write_run_manifest(out_dir, manifest)
    return out_dir


def run_command(cmd: list[str]) -> int:
    print("[knowledge_RAG] " + " ".join(cmd))
    return subprocess.call(cmd)


def legacy_script_for(task_type: str, knowledge_mode: str) -> str:
    if task_type == "objective":
        if knowledge_mode == "none":
            return "evaluation/objective_eval.py"
        if knowledge_mode == "text_rag":
            return "evaluation/text_RAG/text_rag_objective_eval.py"
        return "evaluation/kg_RAG/kg_objective_eval.py"
    if task_type == "subjective":
        if knowledge_mode == "none":
            return "evaluation/run_subjective_pipeline.py"
        if knowledge_mode == "text_rag":
            return "evaluation/text_RAG/text_rag_run_subjective_pipeline.py"
        return "evaluation/kg_RAG/kg_subjective_answer.py"
    if task_type == "structured":
        if knowledge_mode == "none":
            return "evaluation/structured_eval.py"
        if knowledge_mode == "text_rag":
            return "evaluation/text_RAG/text_rag_remaining_kb_structured_eval.py"
        return "evaluation/kg_RAG/kg_structured_eval.py"
    raise ValueError(task_type)


def base_legacy_cmd(args: argparse.Namespace, task_type: str, out_dir: str) -> list[str]:
    cmd = [sys.executable, legacy_script_for(task_type, args.knowledge_mode)]
    cfg = config_from_args(args)
    cmd.extend(["--question-root", args.question_root, "--out-dir", out_dir])
    if args.models:
        cmd.extend(["--models", *args.models])
    if args.datasets:
        cmd.extend(["--datasets", *args.datasets])
    if args.limit:
        cmd.extend(["--limit", str(args.limit)])
    if args.resume:
        cmd.append("--resume")
    if getattr(args, "save_predictions", False):
        cmd.append("--save-predictions")
    if args.knowledge_mode in {"kg_v1", "kg_v3", "hybrid"}:
        cmd.extend(
            [
                "--kg-version", args.kg_version,
                "--kg-backend", args.kg_backend,
                "--kg-query-mode", args.query_mode,
                "--embedding-provider", cfg.embedding_provider,
                "--embedding-model", cfg.embedding_model,
                "--embedding-dim", str(cfg.embedding_dim),
                "--reranker-provider", cfg.reranker_provider,
                "--reranker-model", cfg.reranker_model,
                "--reranker-top-n", str(cfg.reranker_top_n),
                "--lightrag-working-dir", cfg.lightrag_working_dir,
            ]
        )
        if args.enable_reranker:
            cmd.append("--enable-reranker")
        if args.rebuild_vector_index:
            cmd.append("--rebuild-vector-index")
    return cmd
