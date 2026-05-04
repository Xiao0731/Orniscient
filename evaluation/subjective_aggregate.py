from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any, Dict, Sequence

try:
    from subjective_common import load_existing_jsonl_map, load_jsonl, ensure_dir
    from subjective_rubrics import DEFAULT_SUBJECTIVE_DATASET_ORDER
except ModuleNotFoundError:
    from evaluation.subjective_common import load_existing_jsonl_map, load_jsonl, ensure_dir
    from evaluation.subjective_rubrics import DEFAULT_SUBJECTIVE_DATASET_ORDER


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate minimal subjective judge outputs into summary tables.")
    parser.add_argument("--out-dir", type=str, default="evaluation/results_subjective")
    parser.add_argument("--models", nargs="*", default=None)
    parser.add_argument("--datasets", nargs="*", default=DEFAULT_SUBJECTIVE_DATASET_ORDER)
    parser.add_argument("--modes", nargs="*", default=["zero_shot", "few_shot", "cot"])
    return parser.parse_args(argv)


def safe_average(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def format_score(value: float | None) -> str:
    return "" if value is None else f"{value:.2f}"


def write_csv(path: Path, rows: list[Dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def discover_models(answer_root: Path, modes: list[str], datasets: list[str], selected_models: list[str] | None) -> list[str]:
    if selected_models:
        return sorted(dict.fromkeys(selected_models))
    discovered: set[str] = set()
    if not answer_root.exists():
        return []
    for mode_dir in answer_root.iterdir():
        if not mode_dir.is_dir() or mode_dir.name not in modes:
            continue
        for model_dir in mode_dir.iterdir():
            if not model_dir.is_dir():
                continue
            if any((model_dir / f"{dataset}.jsonl").exists() for dataset in datasets):
                discovered.add(model_dir.name)
    return sorted(discovered)


def summarize_one_file(
    answer_path: Path,
    qwen_path: Path,
    dataset: str,
    mode: str,
    model: str,
) -> Dict[str, Any]:
    answer_rows = load_jsonl(answer_path) if answer_path.exists() else []
    answer_qids = [str(row.get("question_id", "")).strip() for row in answer_rows if str(row.get("question_id", "")).strip()]
    qwen_map = load_existing_jsonl_map(qwen_path) if qwen_path.exists() else {}

    scores: list[float] = []
    n_scored = 0

    for qid in answer_qids:
        qwen_row = qwen_map.get(qid)
        if not qwen_row:
            continue
        final_score = round(float(qwen_row["score_total"]), 2)
        scores.append(final_score)
        n_scored += 1

    return {
        "dataset": dataset,
        "mode": mode,
        "model": model,
        "n_total": len(answer_qids),
        "n_scored": n_scored,
        "n_disputed": 0,
        "disputed_rate": 0.0,
        "avg_score_including_disputed": safe_average(scores),
        "avg_score_excluding_disputed": safe_average(scores),
    }


def build_core_table(summary_rows: list[Dict[str, Any]], datasets: list[str], modes: list[str]) -> list[Dict[str, Any]]:
    grouped: Dict[tuple[str, str], Dict[str, Any]] = {}
    for row in summary_rows:
        key = (row["model"], row["mode"])
        grouped.setdefault(key, {"model": row["model"], "mode": row["mode"]})
        grouped[key][row["dataset"]] = row["avg_score_excluding_disputed"]

    table_rows: list[Dict[str, Any]] = []
    for mode in modes:
        for (model, row_mode), payload in sorted(grouped.items()):
            if row_mode != mode:
                continue
            numeric_scores = [payload.get(dataset) for dataset in datasets if payload.get(dataset) is not None]
            row = {"mode": mode, "model": model}
            for dataset in datasets:
                row[dataset] = format_score(payload.get(dataset))
            row["macro_avg"] = format_score(safe_average(numeric_scores))
            table_rows.append(row)
    return table_rows


def build_full_table(summary_rows: list[Dict[str, Any]], datasets: list[str], modes: list[str]) -> list[Dict[str, Any]]:
    grouped: Dict[tuple[str, str], Dict[str, Any]] = {}
    for row in summary_rows:
        key = (row["model"], row["mode"])
        grouped.setdefault(key, {"model": row["model"], "mode": row["mode"]})
        grouped[key][row["dataset"]] = row["avg_score_including_disputed"]
        grouped[key][f"{row['dataset']}_disputed"] = row["n_disputed"]

    table_rows: list[Dict[str, Any]] = []
    for mode in modes:
        for (model, row_mode), payload in sorted(grouped.items()):
            if row_mode != mode:
                continue
            numeric_scores = [payload.get(dataset) for dataset in datasets if payload.get(dataset) is not None]
            row = {"mode": mode, "model": model}
            total_disputed = 0
            for dataset in datasets:
                row[dataset] = format_score(payload.get(dataset))
                disputed_count = int(payload.get(f"{dataset}_disputed", 0))
                row[f"{dataset}_disputed"] = disputed_count
                total_disputed += disputed_count
            row["macro_avg"] = format_score(safe_average(numeric_scores))
            row["total_disputed"] = total_disputed
            table_rows.append(row)
    return table_rows


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    out_dir = Path(args.out_dir)
    answer_root = out_dir / "answers"
    judge_qwen_root = out_dir / "judge_qwen"
    summary_root = out_dir / "summaries"
    ensure_dir(summary_root)

    models = discover_models(answer_root, args.modes, args.datasets, args.models)
    summary_rows: list[Dict[str, Any]] = []

    for mode in args.modes:
        for model in models:
            for dataset in args.datasets:
                answer_path = answer_root / mode / model / f"{dataset}.jsonl"
                if not answer_path.exists():
                    continue
                summary_rows.append(
                    summarize_one_file(
                        answer_path=answer_path,
                        qwen_path=judge_qwen_root / mode / model / f"{dataset}.jsonl",
                        dataset=dataset,
                        mode=mode,
                        model=model,
                    )
                )

    summary_rows.sort(key=lambda row: (row["mode"], row["model"], row["dataset"]))
    write_csv(
        summary_root / "summary_by_model_dataset_mode.csv",
        summary_rows,
        [
            "dataset",
            "mode",
            "model",
            "n_total",
            "n_scored",
            "n_disputed",
            "disputed_rate",
            "avg_score_including_disputed",
            "avg_score_excluding_disputed",
        ],
    )

    core_rows = build_core_table(summary_rows, args.datasets, args.modes)
    write_csv(
        summary_root / "summary_core_table.csv",
        core_rows,
        ["mode", "model", *args.datasets, "macro_avg"],
    )

    full_rows = build_full_table(summary_rows, args.datasets, args.modes)
    full_fieldnames = ["mode", "model"]
    for dataset in args.datasets:
        full_fieldnames.append(dataset)
        full_fieldnames.append(f"{dataset}_disputed")
    full_fieldnames.extend(["macro_avg", "total_disputed"])
    write_csv(summary_root / "summary_full_table.csv", full_rows, full_fieldnames)

    print(f"Done. Summaries saved to {summary_root}")


if __name__ == "__main__":
    main()
