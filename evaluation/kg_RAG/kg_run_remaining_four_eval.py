from __future__ import annotations

from pathlib import Path as _Path
import sys as _sys

_THIS_DIR = _Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent.parent
_EVAL_ROOT = _THIS_DIR.parent
for _p in (_PROJECT_ROOT, _EVAL_ROOT, _THIS_DIR):
    _s = str(_p)
    if _s not in _sys.path:
        _sys.path.insert(0, _s)

import argparse
import csv
from pathlib import Path
from typing import Any, Dict, Sequence

try:
    from kg_structured_eval import main as kg_structured_eval_main
    from kg_subjective_answer import main as kg_subjective_answer_main
    from subjective_aggregate import main as subjective_aggregate_main
    from subjective_common import SUPPORTED_PROMPT_MODES, ensure_dir
    from subjective_judge import main as subjective_judge_main
except ModuleNotFoundError:
    from evaluation.kg_RAG.kg_structured_eval import main as kg_structured_eval_main
    from evaluation.kg_RAG.kg_subjective_answer import main as kg_subjective_answer_main
    from evaluation.subjective_aggregate import main as subjective_aggregate_main
    from evaluation.subjective_common import SUPPORTED_PROMPT_MODES, ensure_dir
    from evaluation.subjective_judge import main as subjective_judge_main

REMAINING_FOUR_DATASETS = ["List-Global", "Bird-ID", "Bird-Con", "Bird-Classify"]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run KG/KB-RAG evaluation for List-Global, Bird-ID, Bird-Con, and Bird-Classify.")
    parser.add_argument("--question-root", type=str, default="question")
    parser.add_argument("--structured-out-dir", type=str, default="evaluation/results_structured_kg_rag_remaining")
    parser.add_argument("--subjective-out-dir", type=str, default="evaluation/results_subjective_kg_rag_remaining")
    parser.add_argument("--results-all-dir", type=str, default="evaluation/results_all_kg_rag_remaining")
    parser.add_argument("--fewshot-root", type=str, default="evaluation/fewshot_examples")
    parser.add_argument("--models", nargs="*", default=None)
    parser.add_argument("--datasets", nargs="*", default=REMAINING_FOUR_DATASETS)
    parser.add_argument("--modes", nargs="*", default=list(SUPPORTED_PROMPT_MODES))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--answer-question-workers", type=int, default=4)
    parser.add_argument("--judge-question-workers", type=int, default=4)
    parser.add_argument("--judge-workers", type=int, default=2)
    parser.add_argument("--structured-max-tokens", type=int, default=512)
    parser.add_argument("--structured-temperature", type=float, default=None)
    parser.add_argument("--structured-retries", type=int, default=2)
    parser.add_argument("--structured-print-every", type=int, default=20)
    parser.add_argument("--subjective-answer-max-tokens", type=int, default=2048)
    parser.add_argument("--subjective-answer-temperature", type=float, default=0.0)
    parser.add_argument("--subjective-answer-retries", type=int, default=2)
    parser.add_argument("--subjective-answer-print-every", type=int, default=20)
    parser.add_argument("--judge-max-tokens", type=int, default=512)
    parser.add_argument("--judge-temperature", type=float, default=0.0)
    parser.add_argument("--judge-request-retries", type=int, default=2)
    parser.add_argument("--judge-parse-retries", type=int, default=1)
    parser.add_argument("--judge-print-every", type=int, default=20)
    parser.add_argument("--birdbase-xlsx", type=str, default="data/BIRDBASE.xlsx")
    parser.add_argument("--order-xlsx", type=str, default="data/Order.xlsx")
    parser.add_argument("--kg-uri", type=str, default="bolt://127.0.0.1:7688")
    parser.add_argument("--kg-user", type=str, default="neo4j")
    parser.add_argument("--kg-password", type=str, default="")
    parser.add_argument("--kg-version", choices=["v1_directed", "v3_fact_graph"], default="v3_fact_graph")
    parser.add_argument("--kg-backend", choices=["neo4j", "lightrag", "hybrid"], default="hybrid")
    parser.add_argument("--kg-query-mode", choices=["local", "global", "hybrid", "mix"], default="mix")
    parser.add_argument("--embedding-provider", choices=["bge_m3", "api_compatible", "disabled"], default="bge_m3")
    parser.add_argument("--embedding-model", type=str, default="BAAI/bge-m3")
    parser.add_argument("--embedding-dim", type=int, default=1024)
    parser.add_argument("--reranker-provider", choices=["bge_reranker", "api_compatible", "disabled"], default="bge_reranker")
    parser.add_argument("--reranker-model", type=str, default="BAAI/bge-reranker-v2-m3")
    parser.add_argument("--enable-reranker", action="store_true")
    parser.add_argument("--reranker-top-n", type=int, default=12)
    parser.add_argument("--lightrag-working-dir", type=str, default="kg_v2/outputs/lightrag_v3")
    parser.add_argument("--rebuild-vector-index", action="store_true")
    parser.add_argument("--kg-limit", type=int, default=30)
    parser.add_argument("--kg-neighbor-limit", type=int, default=160)
    parser.add_argument("--kg-max-node-notes", type=int, default=6)
    parser.add_argument("--kg-node-note-max-chars", type=int, default=0)
    parser.add_argument("--kb-top-k", type=int, default=80)
    parser.add_argument("--family-top-k", type=int, default=12)
    parser.add_argument("--bird-id-top-k", type=int, default=30)
    parser.add_argument("--bird-id-evidence-per-species", type=int, default=5)
    parser.add_argument("--skip-structured", action="store_true")
    parser.add_argument("--skip-subjective", action="store_true")
    parser.add_argument("--skip-overview", action="store_true")
    return parser.parse_args(argv)


def read_csv_rows(path: Path) -> list[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[Dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def format_two_decimals(value: Any) -> str:
    if value in ("", None):
        return ""
    return f"{float(value):.2f}"


def build_overview_rows(args: argparse.Namespace) -> list[Dict[str, Any]]:
    rows: list[Dict[str, Any]] = []

    structured_summary = read_csv_rows(Path(args.structured_out_dir) / "summaries" / "summary_structured.csv")
    structured_metric_map = {
        "List-Global": "avg_f1",
        "Bird-ID": "weighted_top5_accuracy",
        "Bird-Classify__Feature-to-Family": "hierarchical_accuracy",
    }
    for row in structured_summary:
        dataset = row.get("dataset", "")
        primary_metric = structured_metric_map.get(dataset)
        if not primary_metric:
            continue
        rows.append(
            {
                "dataset": dataset,
                "dataset_group": "structured",
                "model": row.get("model", ""),
                "mode": "",
                "primary_metric": primary_metric,
                "primary_score": format_two_decimals(row.get(primary_metric, "")),
            }
        )

    subjective_summary = read_csv_rows(Path(args.subjective_out_dir) / "summaries" / "summary_by_model_dataset_mode.csv")
    for row in subjective_summary:
        dataset = row.get("dataset", "")
        if dataset not in {"Bird-Con", "Bird-Classify"}:
            continue
        rows.append(
            {
                "dataset": dataset,
                "dataset_group": "subjective",
                "model": row.get("model", ""),
                "mode": row.get("mode", ""),
                "primary_metric": "avg_score_excluding_disputed",
                "primary_score": format_two_decimals(row.get("avg_score_excluding_disputed", "")),
            }
        )

    rows.sort(key=lambda row: (row["dataset_group"], row["dataset"], row["model"], row["mode"]))
    return rows


def build_structured_argv(args: argparse.Namespace, structured_datasets: list[str]) -> list[str]:
    cmd = [
        "--question-root",
        args.question_root,
        "--out-dir",
        args.structured_out_dir,
        "--datasets",
        *structured_datasets,
        "--max-workers",
        str(args.answer_question_workers),
        "--answer-question-workers",
        str(args.answer_question_workers),
        "--max-tokens",
        str(args.structured_max_tokens),
        "--retries",
        str(args.structured_retries),
        "--print-every",
        str(args.structured_print_every),
        "--birdbase-xlsx",
        args.birdbase_xlsx,
        "--order-xlsx",
        args.order_xlsx,
        "--kg-uri",
        args.kg_uri,
        "--kg-user",
        args.kg_user,
        "--kg-password",
        args.kg_password,
        "--kb-top-k",
        str(args.kb_top_k),
        "--family-top-k",
        str(args.family_top_k),
        "--bird-id-top-k",
        str(args.bird_id_top_k),
        "--bird-id-evidence-per-species",
        str(args.bird_id_evidence_per_species),
    ]
    if args.models:
        cmd.extend(["--models", *args.models])
    if args.limit > 0:
        cmd.extend(["--limit", str(args.limit)])
    if args.resume:
        cmd.append("--resume")
    if args.structured_temperature is not None:
        cmd.extend(["--temperature", str(args.structured_temperature)])
    return cmd


def build_subjective_answer_argv(args: argparse.Namespace, subjective_datasets: list[str]) -> list[str]:
    cmd = [
        "--question-root",
        args.question_root,
        "--out-dir",
        args.subjective_out_dir,
        "--fewshot-root",
        args.fewshot_root,
        "--datasets",
        *subjective_datasets,
        "--modes",
        *args.modes,
        "--max-workers",
        str(args.answer_question_workers),
        "--answer-question-workers",
        str(args.answer_question_workers),
        "--max-tokens",
        str(args.subjective_answer_max_tokens),
        "--temperature",
        str(args.subjective_answer_temperature),
        "--retries",
        str(args.subjective_answer_retries),
        "--print-every",
        str(args.subjective_answer_print_every),
        "--kg-uri",
        args.kg_uri,
        "--kg-user",
        args.kg_user,
        "--kg-password",
        args.kg_password,
        "--kg-limit",
        str(args.kg_limit),
        "--kg-neighbor-limit",
        str(args.kg_neighbor_limit),
        "--kg-max-node-notes",
        str(args.kg_max_node_notes),
        "--kg-node-note-max-chars",
        str(args.kg_node_note_max_chars),
        "--exclude-types",
        "Feature-to-Family",
    ]
    if args.models:
        cmd.extend(["--models", *args.models])
    if args.limit > 0:
        cmd.extend(["--limit", str(args.limit)])
    if args.resume:
        cmd.append("--resume")
    return cmd


def build_subjective_judge_argv(args: argparse.Namespace, subjective_datasets: list[str]) -> list[str]:
    cmd = [
        "--question-root",
        args.question_root,
        "--out-dir",
        args.subjective_out_dir,
        "--datasets",
        *subjective_datasets,
        "--modes",
        *args.modes,
        "--judge-question-workers",
        str(args.judge_question_workers),
        "--max-workers",
        str(args.judge_question_workers),
        "--judge-workers",
        str(args.judge_workers),
        "--max-tokens",
        str(args.judge_max_tokens),
        "--temperature",
        str(args.judge_temperature),
        "--retries",
        str(args.judge_request_retries),
        "--judge-retries",
        str(args.judge_parse_retries),
        "--print-every",
        str(args.judge_print_every),
    ]
    if args.models:
        cmd.extend(["--models", *args.models])
    if args.limit > 0:
        cmd.extend(["--limit", str(args.limit)])
    if args.resume:
        cmd.append("--resume")
    return cmd


def build_subjective_aggregate_argv(args: argparse.Namespace, subjective_datasets: list[str]) -> list[str]:
    cmd = [
        "--out-dir",
        args.subjective_out_dir,
        "--datasets",
        *subjective_datasets,
        "--modes",
        *args.modes,
    ]
    if args.models:
        cmd.extend(["--models", *args.models])
    return cmd


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)

    dataset_selection: list[str] = []
    for dataset in args.datasets:
        if dataset not in REMAINING_FOUR_DATASETS:
            raise SystemExit(f"Unsupported dataset for this runner: {dataset}")
        if dataset not in dataset_selection:
            dataset_selection.append(dataset)

    structured_datasets: list[str] = []
    if "List-Global" in dataset_selection:
        structured_datasets.append("List-Global")
    if "Bird-ID" in dataset_selection:
        structured_datasets.append("Bird-ID")
    if "Bird-Classify" in dataset_selection:
        structured_datasets.append("Bird-Classify__Feature-to-Family")

    subjective_datasets: list[str] = []
    if "Bird-Con" in dataset_selection:
        subjective_datasets.append("Bird-Con")
    if "Bird-Classify" in dataset_selection:
        subjective_datasets.append("Bird-Classify")

    if structured_datasets and not args.skip_structured:
        print("[KG-REMAINING-FOUR] Structured stage")
        kg_structured_eval_main(build_structured_argv(args, structured_datasets))

    if subjective_datasets and not args.skip_subjective:
        print("[KG-REMAINING-FOUR] Subjective answer stage")
        kg_subjective_answer_main(build_subjective_answer_argv(args, subjective_datasets))
        print("[KG-REMAINING-FOUR] Subjective judge stage")
        subjective_judge_main(build_subjective_judge_argv(args, subjective_datasets))
        print("[KG-REMAINING-FOUR] Subjective aggregate stage")
        subjective_aggregate_main(build_subjective_aggregate_argv(args, subjective_datasets))

    if not args.skip_overview:
        overview_root = Path(args.results_all_dir)
        ensure_dir(overview_root)
        overview_rows = build_overview_rows(args)
        write_csv(
            overview_root / "summary_overview.csv",
            overview_rows,
            ["dataset", "dataset_group", "model", "mode", "primary_metric", "primary_score"],
        )
        print(f"[KG-REMAINING-FOUR] Overview saved to {overview_root / 'summary_overview.csv'}")

    print("Done. KG/KB remaining four evaluation completed.")


if __name__ == "__main__":
    main()
