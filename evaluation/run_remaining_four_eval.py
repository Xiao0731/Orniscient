from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any, Dict, Sequence

try:
    from run_subjective_pipeline import main as subjective_pipeline_main
    from structured_eval import STRUCTURED_DATASET_ORDER, main as structured_eval_main
    from subjective_common import SUPPORTED_PROMPT_MODES, ensure_dir
except ModuleNotFoundError:
    from evaluation.run_subjective_pipeline import main as subjective_pipeline_main
    from evaluation.structured_eval import STRUCTURED_DATASET_ORDER, main as structured_eval_main
    from evaluation.subjective_common import SUPPORTED_PROMPT_MODES, ensure_dir

REMAINING_FOUR_DATASETS = ["List-Global", "Bird-ID", "Bird-Con", "Bird-Classify"]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run unified evaluation for List-Global, Bird-ID, Bird-Con, and Bird-Classify.")
    parser.add_argument("--question-root", type=str, default="question")
    parser.add_argument("--structured-out-dir", type=str, default="evaluation/results_structured")
    parser.add_argument("--subjective-out-dir", type=str, default="evaluation/results_subjective")
    parser.add_argument("--results-all-dir", type=str, default="evaluation/results_all")
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
    cmd: list[str] = [
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


def build_subjective_argv(args: argparse.Namespace, subjective_datasets: list[str]) -> list[str]:
    cmd: list[str] = [
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
        "--answer-question-workers",
        str(args.answer_question_workers),
        "--answer-max-tokens",
        str(args.subjective_answer_max_tokens),
        "--answer-temperature",
        str(args.subjective_answer_temperature),
        "--answer-retries",
        str(args.subjective_answer_retries),
        "--answer-print-every",
        str(args.subjective_answer_print_every),
        "--judge-question-workers",
        str(args.judge_question_workers),
        "--judge-workers",
        str(args.judge_workers),
        "--judge-max-tokens",
        str(args.judge_max_tokens),
        "--judge-temperature",
        str(args.judge_temperature),
        "--judge-request-retries",
        str(args.judge_request_retries),
        "--judge-parse-retries",
        str(args.judge_parse_retries),
        "--judge-print-every",
        str(args.judge_print_every),
    ]
    if args.models:
        cmd.extend(["--models", *args.models])
    if args.limit > 0:
        cmd.extend(["--limit", str(args.limit)])
    if args.resume:
        cmd.append("--resume")
    return cmd


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)

    dataset_selection = []
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
        print("[REMAINING-FOUR] Structured stage")
        structured_eval_main(build_structured_argv(args, structured_datasets))

    if subjective_datasets and not args.skip_subjective:
        print("[REMAINING-FOUR] Subjective stage")
        subjective_pipeline_main(build_subjective_argv(args, subjective_datasets))

    if not args.skip_overview:
        overview_root = Path(args.results_all_dir)
        ensure_dir(overview_root)
        overview_rows = build_overview_rows(args)
        write_csv(
            overview_root / "summary_overview.csv",
            overview_rows,
            ["dataset", "dataset_group", "model", "mode", "primary_metric", "primary_score"],
        )
        print(f"[REMAINING-FOUR] Overview saved to {overview_root / 'summary_overview.csv'}")

    print("Done. Remaining four datasets evaluation completed.")


if __name__ == "__main__":
    main()
