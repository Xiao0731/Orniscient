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
    from subjective_aggregate import main as subjective_aggregate_main
    from subjective_common import SUPPORTED_PROMPT_MODES, ensure_dir
    from subjective_judge import main as subjective_judge_main
except ModuleNotFoundError:
    from evaluation.subjective_aggregate import main as subjective_aggregate_main
    from evaluation.subjective_common import SUPPORTED_PROMPT_MODES, ensure_dir
    from evaluation.subjective_judge import main as subjective_judge_main

from text_rag_remaining_kb_structured_eval import main as structured_main
from text_rag_remaining_kb_subjective_answer import main as subjective_answer_main


REMAINING_FOUR_DATASETS = ["List-Global", "Bird-ID", "Bird-Con", "Bird-Classify"]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run task-adapted remaining-four KB/Text-RAG evaluation.")
    parser.add_argument("--question-root", type=str, default="question")
    parser.add_argument("--structured-out-dir", type=str, default="evaluation/output/results_structured_remaining_kb")
    parser.add_argument("--subjective-out-dir", type=str, default="evaluation/output/results_subjective_remaining_kb")
    parser.add_argument("--results-all-dir", type=str, default="evaluation/output/results_all_remaining_kb")
    parser.add_argument("--fewshot-root", type=str, default="evaluation/fewshot_examples")
    parser.add_argument("--models", nargs="*", default=None)
    parser.add_argument("--datasets", nargs="*", default=REMAINING_FOUR_DATASETS)
    parser.add_argument("--modes", nargs="*", default=list(SUPPORTED_PROMPT_MODES))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--only-question-ids", type=str, default="")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--birdbase-xlsx", type=str, default="data/BIRDBASE.xlsx")
    parser.add_argument("--order-xlsx", type=str, default="data/Order.xlsx")
    parser.add_argument("--species-chunks-jsonl", type=str, default="kg_v2/outputs/intermediate/species_chunks.jsonl")
    parser.add_argument("--family-chunks-jsonl", type=str, default="kg_v2/outputs/intermediate/family_chunks.jsonl")
    parser.add_argument("--candidate-k", type=int, default=30)
    parser.add_argument("--evidence-per-candidate", type=int, default=3)
    parser.add_argument("--list-global-constraint-source", type=str, default="question", choices=["question", "provenance"])
    parser.add_argument("--ambiguous-realm-policy", type=str, default="skip", choices=["skip", "union"])
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
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--max-context-chars", type=int, default=3500)
    parser.add_argument("--debug", action="store_true")
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


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    structured_datasets: list[str] = []
    if "List-Global" in args.datasets:
        structured_datasets.append("List-Global")
    if "Bird-ID" in args.datasets:
        structured_datasets.append("Bird-ID")
    if "Bird-Classify" in args.datasets:
        structured_datasets.append("Bird-Classify__Feature-to-Family")

    subjective_datasets: list[str] = []
    if "Bird-Con" in args.datasets:
        subjective_datasets.append("Bird-Con")
    if "Bird-Classify" in args.datasets:
        subjective_datasets.append("Bird-Classify")

    if structured_datasets:
        print("[PIPELINE] Remaining structured KB/Text-RAG stage")
        cmd = [
            "--question-root", args.question_root,
            "--out-dir", args.structured_out_dir,
            "--datasets", *structured_datasets,
            "--max-workers", str(args.answer_question_workers),
            "--answer-question-workers", str(args.answer_question_workers),
            "--max-tokens", str(args.structured_max_tokens),
            "--retries", str(args.structured_retries),
            "--print-every", str(args.structured_print_every),
            "--birdbase-xlsx", args.birdbase_xlsx,
            "--order-xlsx", args.order_xlsx,
            "--species-chunks-jsonl", args.species_chunks_jsonl,
            "--family-chunks-jsonl", args.family_chunks_jsonl,
            "--top-k", str(args.top_k),
            "--max-context-chars", str(args.max_context_chars),
            "--candidate-k", str(args.candidate_k),
            "--evidence-per-candidate", str(args.evidence_per_candidate),
            "--list-global-constraint-source", args.list_global_constraint_source,
            "--ambiguous-realm-policy", args.ambiguous_realm_policy,
        ]
        if args.models:
            cmd = cmd[:4] + ["--models", *args.models] + cmd[4:]
        if args.limit > 0:
            cmd.extend(["--limit", str(args.limit)])
        if args.only_question_ids:
            cmd.extend(["--only-question-ids", args.only_question_ids])
        if args.resume:
            cmd.append("--resume")
        if args.structured_temperature is not None:
            cmd.extend(["--temperature", str(args.structured_temperature)])
        if args.debug:
            cmd.append("--debug")
        structured_main(cmd)

    if subjective_datasets:
        print("[PIPELINE] Remaining subjective KB/Text-RAG answer stage")
        answer_cmd = [
            "--question-root", args.question_root,
            "--out-dir", args.subjective_out_dir,
            "--fewshot-root", args.fewshot_root,
            "--datasets", *subjective_datasets,
            "--modes", *args.modes,
            "--answer-question-workers", str(args.answer_question_workers),
            "--max-workers", str(args.answer_question_workers),
            "--max-tokens", str(args.subjective_answer_max_tokens),
            "--temperature", str(args.subjective_answer_temperature),
            "--retries", str(args.subjective_answer_retries),
            "--print-every", str(args.subjective_answer_print_every),
            "--species-chunks-jsonl", args.species_chunks_jsonl,
            "--family-chunks-jsonl", args.family_chunks_jsonl,
            "--top-k", str(max(args.top_k, 8)),
            "--max-context-chars", str(max(args.max_context_chars, 9000)),
            "--exclude-types", "Feature-to-Family",
        ]
        if args.models:
            answer_cmd = answer_cmd[:6] + ["--models", *args.models] + answer_cmd[6:]
        if args.limit > 0:
            answer_cmd.extend(["--limit", str(args.limit)])
        if args.only_question_ids:
            answer_cmd.extend(["--only-question-ids", args.only_question_ids])
        if args.resume:
            answer_cmd.append("--resume")
        if args.debug:
            answer_cmd.append("--debug")
        subjective_answer_main(answer_cmd)

        print("[PIPELINE] Remaining subjective judge stage")
        judge_cmd = [
            "--question-root", args.question_root,
            "--out-dir", args.subjective_out_dir,
            "--datasets", *subjective_datasets,
            "--modes", *args.modes,
            "--judge-question-workers", str(args.judge_question_workers),
            "--max-workers", str(args.judge_question_workers),
            "--judge-workers", str(args.judge_workers),
            "--max-tokens", str(args.judge_max_tokens),
            "--temperature", str(args.judge_temperature),
            "--retries", str(args.judge_request_retries),
            "--judge-retries", str(args.judge_parse_retries),
            "--print-every", str(args.judge_print_every),
        ]
        if args.models:
            judge_cmd = judge_cmd[:4] + ["--models", *args.models] + judge_cmd[4:]
        if args.limit > 0:
            judge_cmd.extend(["--limit", str(args.limit)])
        if args.only_question_ids:
            judge_cmd.extend(["--only-question-ids", args.only_question_ids])
        if args.resume:
            judge_cmd.append("--resume")
        subjective_judge_main(judge_cmd)

        print("[PIPELINE] Remaining subjective aggregate stage")
        aggregate_cmd = ["--out-dir", args.subjective_out_dir, "--datasets", *subjective_datasets, "--modes", *args.modes]
        if args.models:
            aggregate_cmd.extend(["--models", *args.models])
        subjective_aggregate_main(aggregate_cmd)

    results_all_dir = Path(args.results_all_dir)
    ensure_dir(results_all_dir)
    rows = build_overview_rows(args)
    write_csv(
        results_all_dir / "summary_overview_remaining_kb.csv",
        rows,
        ["dataset", "dataset_group", "model", "mode", "primary_metric", "primary_score"],
    )
    print(f"[OVERVIEW] wrote {results_all_dir / 'summary_overview_remaining_kb.csv'}")


if __name__ == "__main__":
    main()
