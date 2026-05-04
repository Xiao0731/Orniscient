from __future__ import annotations

import argparse
import csv
import json
import math
import random
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


OBJECTIVE_DATASETS = [
    "QA-SC",
    "QA-MC",
    "QA-SA",
    "Bird-Geo",
    "Bird-Taxonomy",
]

SUBJECTIVE_DATASETS = [
    "Bird-Comp",
    "Bird-Eco",
    "Bird-Life",
    "Bird-Reason",
    "Bird-Plan",
]

SPECIAL_DATASETS = [
    "List-Global",
    "Bird-ID",
    "Bird-Con",
    "Bird-Classify",
]

ALL_DATASETS = OBJECTIVE_DATASETS + SUBJECTIVE_DATASETS + SPECIAL_DATASETS
DATASET_GROUP = {dataset: "objective" for dataset in OBJECTIVE_DATASETS}
DATASET_GROUP.update({dataset: "subjective" for dataset in SUBJECTIVE_DATASETS})
DATASET_GROUP.update({dataset: "special" for dataset in SPECIAL_DATASETS})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a fixed sampled question-root for fair benchmark comparisons.")
    parser.add_argument("--question-root", type=str, default="question")
    parser.add_argument("--out-root", type=str, default="question_sample_seed42_obj300_subj77")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--objective-size", type=int, default=300)
    parser.add_argument("--subjective-size", type=int, default=77)
    parser.add_argument("--special-size", type=int, default=77)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stratify-bird-classify", dest="stratify_bird_classify", action="store_true")
    parser.add_argument("--no-stratify-bird-classify", dest="stratify_bird_classify", action="store_false")
    parser.add_argument("--stratify-field", type=str, default="")
    parser.set_defaults(stratify_bird_classify=True)
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def stable_dataset_seed(seed: int, dataset: str) -> int:
    return seed + sum(ord(ch) for ch in dataset)


def question_id_for_row(row: dict[str, Any], dataset: str, original_index: int) -> str:
    question_id = str(row.get("question_id", "")).strip()
    if question_id:
        return question_id
    return f"{dataset}_idx_{original_index:06d}"


def value_preview(value: Any, limit: int = 120) -> str:
    text = str(value if value is not None else "").replace("\n", " ").strip()
    return text[:limit]


def distribution_json(rows: list[dict[str, Any]], field: str) -> str:
    counter = Counter()
    for row in rows:
        value = str(row.get(field, "") if row.get(field, "") is not None else "").strip() or "<EMPTY>"
        counter[value] += 1
    ordered = {key: counter[key] for key in sorted(counter)}
    return json.dumps(ordered, ensure_ascii=False, sort_keys=True)


def annotate_rows(rows: list[dict[str, Any]], dataset: str) -> list[dict[str, Any]]:
    annotated: list[dict[str, Any]] = []
    for original_index, row in enumerate(rows):
        annotated.append(
            {
                "row": row,
                "original_index": original_index,
                "question_id": question_id_for_row(row, dataset, original_index),
            }
        )
    annotated.sort(key=lambda item: item["question_id"])
    return annotated


def resolve_stratify_field(args: argparse.Namespace, dataset: str, rows: list[dict[str, Any]]) -> str | None:
    candidate = str(args.stratify_field or "").strip()
    if candidate and any(str(row.get(candidate, "")).strip() for row in rows):
        return candidate
    if dataset == "Bird-Classify" and args.stratify_bird_classify:
        if any(str(row.get("type", "")).strip() for row in rows):
            return "type"
    return None


def _random_sample_annotated(
    rows: list[dict[str, Any]],
    sample_size: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    if sample_size >= len(rows):
        return list(rows)
    sampled = rng.sample(rows, sample_size)
    sampled.sort(key=lambda item: item["question_id"])
    return sampled


def _compute_group_allocations(
    groups: dict[str, list[dict[str, Any]]],
    sample_size: int,
) -> dict[str, int]:
    group_names = sorted(groups)
    if sample_size >= len(group_names):
        allocations = {name: 1 for name in group_names}
        remaining = sample_size - len(group_names)
        if remaining <= 0:
            return allocations
        residual_caps = {name: len(groups[name]) - 1 for name in group_names}
        raw_extra: dict[str, float] = {}
        floor_extra: dict[str, int] = {}
        fractions: dict[str, float] = {}
        total_rows = sum(len(groups[name]) for name in group_names)
        for name in group_names:
            desired = (len(groups[name]) / total_rows) * remaining if total_rows else 0.0
            capped = min(desired, residual_caps[name])
            raw_extra[name] = capped
            floor_extra[name] = int(math.floor(capped))
            fractions[name] = capped - floor_extra[name]
            allocations[name] += floor_extra[name]
        assigned = sum(allocations.values())
        leftovers = sample_size - assigned
        if leftovers > 0:
            order = sorted(group_names, key=lambda name: (-fractions[name], name))
            while leftovers > 0:
                progressed = False
                for name in order:
                    if allocations[name] < len(groups[name]):
                        allocations[name] += 1
                        leftovers -= 1
                        progressed = True
                        if leftovers == 0:
                            break
                if not progressed:
                    break
        return allocations

    total_rows = sum(len(groups[name]) for name in group_names)
    raw: dict[str, float] = {}
    allocations: dict[str, int] = {}
    fractions: dict[str, float] = {}
    for name in group_names:
        desired = (len(groups[name]) / total_rows) * sample_size if total_rows else 0.0
        capped = min(desired, len(groups[name]))
        raw[name] = capped
        allocations[name] = int(math.floor(capped))
        fractions[name] = capped - allocations[name]

    assigned = sum(allocations.values())
    leftovers = sample_size - assigned
    if leftovers > 0:
        order = sorted(group_names, key=lambda name: (-fractions[name], name))
        while leftovers > 0:
            progressed = False
            for name in order:
                if allocations[name] < len(groups[name]):
                    allocations[name] += 1
                    leftovers -= 1
                    progressed = True
                    if leftovers == 0:
                        break
            if not progressed:
                break
    return allocations


def sample_rows(
    rows: list[dict[str, Any]],
    sample_size: int,
    seed: int,
    dataset: str,
    stratify_field: str | None = None,
) -> list[dict[str, Any]]:
    if sample_size <= 0 or len(rows) <= sample_size:
        return list(rows)

    rng = random.Random(seed)
    if not stratify_field:
        return _random_sample_annotated(rows, sample_size, rng)

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        value = str(row["row"].get(stratify_field, "") if row["row"].get(stratify_field, "") is not None else "").strip()
        key = value or "<EMPTY>"
        groups[key].append(row)

    nonempty_groups = {key: value for key, value in groups.items() if value}
    if len(nonempty_groups) <= 1:
        return _random_sample_annotated(rows, sample_size, rng)

    allocations = _compute_group_allocations(nonempty_groups, sample_size)
    sampled: list[dict[str, Any]] = []
    for group_name in sorted(nonempty_groups):
        group_rows = sorted(nonempty_groups[group_name], key=lambda item: item["question_id"])
        group_sample_size = min(allocations.get(group_name, 0), len(group_rows))
        if group_sample_size <= 0:
            continue
        group_seed = seed + sum(ord(ch) for ch in f"{dataset}::{stratify_field}::{group_name}")
        group_rng = random.Random(group_seed)
        sampled.extend(_random_sample_annotated(group_rows, group_sample_size, group_rng))

    sampled.sort(key=lambda item: item["question_id"])
    if len(sampled) > sample_size:
        sampled = sampled[:sample_size]
    elif len(sampled) < sample_size:
        picked = {item["question_id"] for item in sampled}
        remaining = [item for item in rows if item["question_id"] not in picked]
        remaining.sort(key=lambda item: item["question_id"])
        filler_rng = random.Random(seed + 99991)
        filler = _random_sample_annotated(remaining, sample_size - len(sampled), filler_rng)
        sampled.extend(filler)
        sampled.sort(key=lambda item: item["question_id"])
    return sampled


def sample_size_for_dataset(args: argparse.Namespace, dataset: str) -> int:
    group = DATASET_GROUP[dataset]
    if group == "objective":
        return args.objective_size
    if group == "subjective":
        return args.subjective_size
    return args.special_size


def build_manifest_row(
    dataset: str,
    group: str,
    row: dict[str, Any],
    sample_size: int,
    total_size: int,
    seed: int,
    dataset_seed: int,
    sampled_rank: int,
) -> dict[str, Any]:
    payload = row["row"]
    return {
        "dataset": dataset,
        "group": group,
        "question_id": row["question_id"],
        "original_index": row["original_index"],
        "sampled_rank": sampled_rank,
        "sample_size_for_dataset": sample_size,
        "total_size_for_dataset": total_size,
        "seed": seed,
        "dataset_seed": dataset_seed,
        "type": str(payload.get("type", "") if payload.get("type", "") is not None else "").strip(),
        "knowledge_domain": str(payload.get("knowledge_domain", "") if payload.get("knowledge_domain", "") is not None else "").strip(),
        "target_entity": str(payload.get("target_entity", "") if payload.get("target_entity", "") is not None else "").strip(),
        "answer_preview": value_preview(payload.get("answer", "")),
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    question_root = Path(args.question_root)
    out_root = Path(args.out_root)

    if not args.dry_run and out_root.exists():
        if not args.overwrite:
            raise SystemExit(f"Output directory already exists: {out_root}. Use --overwrite or choose another --out-root.")
        print(f"[OVERWRITE] removing existing output root: {out_root}")
        shutil.rmtree(out_root)

    manifest_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    processed_any = False

    for dataset in ALL_DATASETS:
        group = DATASET_GROUP[dataset]
        requested_size = sample_size_for_dataset(args, dataset)
        dataset_seed = stable_dataset_seed(args.seed, dataset)
        input_path = question_root / dataset / f"{dataset}_questions.jsonl"
        output_path = out_root / dataset / f"{dataset}_questions.jsonl"

        if not input_path.exists():
            print(f"[MISS] dataset={dataset} path={input_path}")
            summary_rows.append(
                {
                    "dataset": dataset,
                    "group": group,
                    "input_path": str(input_path),
                    "output_path": str(output_path),
                    "total_rows": 0,
                    "sampled_rows": 0,
                    "sample_size_requested": requested_size,
                    "seed": args.seed,
                    "dataset_seed": dataset_seed,
                    "stratify_field": "",
                    "type_distribution_original": "{}",
                    "type_distribution_sampled": "{}",
                    "knowledge_domain_distribution_original": "{}",
                    "knowledge_domain_distribution_sampled": "{}",
                    "status": "missing",
                }
            )
            continue

        processed_any = True
        raw_rows = load_jsonl(input_path)
        annotated_rows = annotate_rows(raw_rows, dataset)
        stratify_field = resolve_stratify_field(args, dataset, raw_rows)
        sampled_rows = sample_rows(
            annotated_rows,
            sample_size=requested_size,
            seed=dataset_seed,
            dataset=dataset,
            stratify_field=stratify_field,
        )
        sampled_payload_rows = [item["row"] for item in sampled_rows]

        print(
            f"[SAMPLE] dataset={dataset} group={group} total={len(raw_rows)} "
            f"requested={requested_size} sampled={len(sampled_rows)} "
            f"seed={args.seed} dataset_seed={dataset_seed} stratify_field={stratify_field or '<none>'}"
        )

        if not args.dry_run:
            write_jsonl(output_path, sampled_payload_rows)

        for sampled_rank, sampled_row in enumerate(sampled_rows, start=1):
            manifest_rows.append(
                build_manifest_row(
                    dataset=dataset,
                    group=group,
                    row=sampled_row,
                    sample_size=requested_size,
                    total_size=len(raw_rows),
                    seed=args.seed,
                    dataset_seed=dataset_seed,
                    sampled_rank=sampled_rank,
                )
            )

        summary_rows.append(
            {
                "dataset": dataset,
                "group": group,
                "input_path": str(input_path),
                "output_path": str(output_path),
                "total_rows": len(raw_rows),
                "sampled_rows": len(sampled_rows),
                "sample_size_requested": requested_size,
                "seed": args.seed,
                "dataset_seed": dataset_seed,
                "stratify_field": stratify_field or "",
                "type_distribution_original": distribution_json(raw_rows, "type"),
                "type_distribution_sampled": distribution_json(sampled_payload_rows, "type"),
                "knowledge_domain_distribution_original": distribution_json(raw_rows, "knowledge_domain"),
                "knowledge_domain_distribution_sampled": distribution_json(sampled_payload_rows, "knowledge_domain"),
                "status": "ok",
            }
        )

    if not processed_any:
        raise SystemExit("No dataset files were processed. Check --question-root.")

    manifest_rows.sort(key=lambda row: (row["group"], row["dataset"], row["question_id"]))
    summary_rows.sort(key=lambda row: (row["group"], row["dataset"]))

    config = {
        "question_root": str(question_root),
        "out_root": str(out_root),
        "seed": args.seed,
        "objective_size": args.objective_size,
        "subjective_size": args.subjective_size,
        "special_size": args.special_size,
        "objective_datasets": OBJECTIVE_DATASETS,
        "subjective_datasets": SUBJECTIVE_DATASETS,
        "special_datasets": SPECIAL_DATASETS,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "notes": "Stable sampled question-root for fair Vanilla/Text-RAG/KG-RAG comparisons. Output files preserve original JSONL rows.",
        "stratify_bird_classify": bool(args.stratify_bird_classify),
        "stratify_field": str(args.stratify_field or ""),
        "dry_run": bool(args.dry_run),
    }

    if args.dry_run:
        print("[DRY-RUN] no files were written.")
        print(f"[DRY-RUN] would write manifest rows={len(manifest_rows)} summary rows={len(summary_rows)}")
        return

    out_root.mkdir(parents=True, exist_ok=True)
    write_csv(
        out_root / "sample_manifest.csv",
        manifest_rows,
        [
            "dataset",
            "group",
            "question_id",
            "original_index",
            "sampled_rank",
            "sample_size_for_dataset",
            "total_size_for_dataset",
            "seed",
            "dataset_seed",
            "type",
            "knowledge_domain",
            "target_entity",
            "answer_preview",
        ],
    )
    write_csv(
        out_root / "sample_summary.csv",
        summary_rows,
        [
            "dataset",
            "group",
            "input_path",
            "output_path",
            "total_rows",
            "sampled_rows",
            "sample_size_requested",
            "seed",
            "dataset_seed",
            "stratify_field",
            "type_distribution_original",
            "type_distribution_sampled",
            "knowledge_domain_distribution_original",
            "knowledge_domain_distribution_sampled",
            "status",
        ],
    )
    (out_root / "sample_config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[DONE] wrote sampled question root to {out_root}")


if __name__ == "__main__":
    main()
