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
    from subjective_common import SUPPORTED_PROMPT_MODES, ensure_dir
except ModuleNotFoundError:
    from evaluation.subjective_common import SUPPORTED_PROMPT_MODES, ensure_dir

from text_rag_run_subjective_pipeline import main as subjective_pipeline_main
from text_rag_structured_eval import main as structured_eval_main

REMAINING_FOUR_DATASETS = ["List-Global", "Bird-ID", "Bird-Con", "Bird-Classify"]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run unified Text-RAG evaluation for List-Global, Bird-ID, Bird-Con, and Bird-Classify.")
    parser.add_argument("--question-root", type=str, default="question")
    parser.add_argument("--structured-out-dir", type=str, default="evaluation/results_structured_text_rag")
    parser.add_argument("--subjective-out-dir", type=str, default="evaluation/results_subjective_text_rag")
    parser.add_argument("--results-all-dir", type=str, default="evaluation/results_all_text_rag")
    parser.add_argument("--fewshot-root", type=str, default="evaluation/fewshot_examples")
    parser.add_argument("--models", nargs="*", default=None)
    parser.add_argument("--datasets", nargs="*", default=REMAINING_FOUR_DATASETS)
    parser.add_argument("--modes", nargs="*", default=list(SUPPORTED_PROMPT_MODES))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true")

    parser.add_argument("--answer-question-workers", type=int, default=4)
    parser.add_argument("--structured-max-tokens", type=int, default=512)
    parser.add_argument("--structured-temperature", type=float, default=None)
    parser.add_argument("--structured-retries", type=int, default=2)
    parser.add_argument("--structured-print-every", type=int, default=20)

    parser.add_argument("--subjective-answer-max-tokens", type=int, default=1024)
    parser.add_argument("--subjective-answer-temperature", type=float, default=0.0)
    parser.add_argument("--subjective-answer-retries", type=int, default=2)
    parser.add_argument("--subjective-answer-print-every", type=int, default=20)

    parser.add_argument("--judge-question-workers", type=int, default=4)
    parser.add_argument("--judge-workers", type=int, default=2)
    parser.add_argument("--judge-max-tokens", type=int, default=512)
    parser.add_argument("--judge-temperature", type=float, default=0.0)
    parser.add_argument("--judge-request-retries", type=int, default=2)
    parser.add_argument("--judge-parse-retries", type=int, default=1)
    parser.add_argument("--judge-print-every", type=int, default=20)

    parser.add_argument("--bow-glob", type=str, default="")
    parser.add_argument("--order-xlsx", type=str, default="")
    parser.add_argument("--cache-jsonl", type=str, default="evaluation/cache/text_rag_chunks.jsonl")
    parser.add_argument("--species-chunks-jsonl", type=str, default="kg_v2/outputs/intermediate/species_chunks.jsonl")
    parser.add_argument("--family-chunks-jsonl", type=str, default="kg_v2/outputs/intermediate/family_chunks.jsonl")
    parser.add_argument("--chunk-chars", type=int, default=1200)
    parser.add_argument("--chunk-overlap", type=int, default=200)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--max-context-chars", type=int, default=3500)
    parser.add_argument("--no-restrict-to-target", action="store_true")

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
                "setting": "text_rag",
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
                "setting": "text_rag",
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


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)

    structured_datasets = [d for d in args.datasets if d in {"List-Global", "Bird-ID", "Bird-Classify"}]
    subjective_datasets = [d for d in args.datasets if d in {"Bird-Con", "Bird-Classify"}]

    if not args.skip_structured and structured_datasets:
        cmd = [
            "--question-root", args.question_root,
            "--out-dir", args.structured_out_dir,
            "--datasets", *(["Bird-Classify__Feature-to-Family" if d == "Bird-Classify" else d for d in structured_datasets]),
            "--max-workers", str(args.answer_question_workers),
            "--max-tokens", str(args.structured_max_tokens),
            "--retries", str(args.structured_retries),
            "--print-every", str(args.structured_print_every),
            "--bow-glob", args.bow_glob,
            "--cache-jsonl", args.cache_jsonl,
            "--chunk-chars", str(args.chunk_chars),
            "--chunk-overlap", str(args.chunk_overlap),
            "--top-k", str(args.top_k),
            "--max-context-chars", str(args.max_context_chars),
        ]
        if args.models:
            cmd = cmd[:4] + ["--models", *args.models] + cmd[4:]
        if args.limit > 0:
            cmd.extend(["--limit", str(args.limit)])
        if args.resume:
            cmd.append("--resume")
        if args.structured_temperature is not None:
            cmd.extend(["--temperature", str(args.structured_temperature)])
        if args.order_xlsx:
            cmd.extend(["--order-xlsx", args.order_xlsx])
        if args.no_restrict_to_target:
            cmd.append("--no-restrict-to-target")
        print("[PIPELINE] Structured Text-RAG stage")
        structured_eval_main(cmd)

    if not args.skip_subjective and subjective_datasets:
        cmd = [
            "--question-root", args.question_root,
            "--out-dir", args.subjective_out_dir,
            "--fewshot-root", args.fewshot_root,
            "--datasets", *subjective_datasets,
            "--modes", *args.modes,
            "--answer-question-workers", str(args.answer_question_workers),
            "--answer-max-tokens", str(args.subjective_answer_max_tokens),
            "--answer-temperature", str(args.subjective_answer_temperature),
            "--answer-retries", str(args.subjective_answer_retries),
            "--answer-print-every", str(args.subjective_answer_print_every),
            "--judge-question-workers", str(args.judge_question_workers),
            "--judge-workers", str(args.judge_workers),
            "--judge-max-tokens", str(args.judge_max_tokens),
            "--judge-temperature", str(args.judge_temperature),
            "--judge-request-retries", str(args.judge_request_retries),
            "--judge-parse-retries", str(args.judge_parse_retries),
            "--judge-print-every", str(args.judge_print_every),
            "--bow-glob", args.bow_glob,
            "--cache-jsonl", args.cache_jsonl,
            "--chunk-chars", str(args.chunk_chars),
            "--chunk-overlap", str(args.chunk_overlap),
            "--top-k", str(args.top_k),
            "--max-context-chars", str(args.max_context_chars),
        ]
        if args.models:
            cmd = cmd[:6] + ["--models", *args.models] + cmd[6:]
        if args.limit > 0:
            cmd.extend(["--limit", str(args.limit)])
        if args.resume:
            cmd.append("--resume")
        if args.order_xlsx:
            cmd.extend(["--order-xlsx", args.order_xlsx])
        if args.no_restrict_to_target:
            cmd.append("--no-restrict-to-target")
        print("[PIPELINE] Subjective Text-RAG stage")
        subjective_pipeline_main(cmd)

    if not args.skip_overview:
        results_all_dir = Path(args.results_all_dir)
        ensure_dir(results_all_dir)
        rows = build_overview_rows(args)
        write_csv(
            results_all_dir / "summary_overview_text_rag.csv",
            rows,
            ["setting", "dataset", "dataset_group", "model", "mode", "primary_metric", "primary_score"],
        )
        print(f"[OVERVIEW] wrote {results_all_dir / 'summary_overview_text_rag.csv'}")


if __name__ == "__main__":
    main()
