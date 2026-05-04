from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Sequence

try:
    from model_registry import enabled_specs, subjective_candidate_specs
    from subjective_common import (
        DEFAULT_JUDGE_ALIASES,
        build_client,
        build_judge_messages,
        call_with_retries,
        discover_dataset_file,
        ensure_dir,
        has_nonempty_answer,
        has_nonempty_score,
        load_existing_jsonl_map,
        load_jsonl,
        load_subjective_dataset,
        parse_judge_response,
        resolve_worker_count,
        seed_everything,
        write_jsonl,
    )
    from subjective_rubrics import DEFAULT_SUBJECTIVE_DATASET_ORDER
except ModuleNotFoundError:
    from evaluation.model_registry import enabled_specs, subjective_candidate_specs
    from evaluation.subjective_common import (
        DEFAULT_JUDGE_ALIASES,
        build_client,
        build_judge_messages,
        call_with_retries,
        discover_dataset_file,
        ensure_dir,
        has_nonempty_answer,
        has_nonempty_score,
        load_existing_jsonl_map,
        load_jsonl,
        load_subjective_dataset,
        parse_judge_response,
        resolve_worker_count,
        seed_everything,
        write_jsonl,
    )
    from evaluation.subjective_rubrics import DEFAULT_SUBJECTIVE_DATASET_ORDER


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run minimal single-judge subjective scoring with qwen3-max.")
    parser.add_argument("--question-root", type=str, default="question")
    parser.add_argument("--out-dir", type=str, default="evaluation/results_subjective")
    parser.add_argument("--models", nargs="*", default=None)
    parser.add_argument("--datasets", nargs="*", default=DEFAULT_SUBJECTIVE_DATASET_ORDER)
    parser.add_argument("--modes", nargs="*", default=["zero_shot", "few_shot", "cot"])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--only-question-ids", type=str, default="")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--judge-question-workers", type=int, default=None)
    parser.add_argument("--judge-workers", type=int, default=2)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--judge-retries", type=int, default=1)
    parser.add_argument("--print-every", type=int, default=20)
    return parser.parse_args(argv)


def score_one_judge(
    client,
    spec,
    item,
    candidate_answer: str,
    retries: int,
    judge_retries: int,
    temperature: float,
    max_tokens: int,
) -> Dict[str, int]:
    last_error: Exception | None = None
    for attempt in range(judge_retries + 1):
        try:
            raw_response = call_with_retries(
                client=client,
                spec=spec,
                messages=build_judge_messages(item=item, candidate_answer=candidate_answer),
                temperature=temperature,
                max_tokens=max_tokens,
                retries=retries,
            )
            return parse_judge_response(raw_response, dataset=item.dataset, expected_qid=item.qid)
        except Exception as exc:
            last_error = exc
            print(
                f"[JUDGE-ERROR] judge={spec.alias} qid={item.qid} "
                f"attempt={attempt + 1}/{judge_retries + 1} err={exc}"
            )
    raise RuntimeError(f"Judge failed for {spec.alias} qid={item.qid}: {last_error}") from last_error


def judge_one_answer(
    judge_clients,
    judge_specs,
    item,
    answer_row: Dict[str, str],
    retries: int,
    judge_retries: int,
    temperature: float,
    max_tokens: int,
    judge_workers: int,
) -> Dict[str, Dict[str, int]]:
    candidate_answer = str(answer_row.get("answer", "")).strip()
    if not candidate_answer:
        raise ValueError(f"Missing candidate answer for qid={item.qid}")

    print(
        f"[JUDGE-START] qid={item.qid} judges={','.join(spec.alias for spec in judge_specs)} "
        f"launch_mode={'parallel' if judge_workers > 1 and len(judge_specs) > 1 else 'sequential'}"
    )

    results: Dict[str, Dict[str, int]] = {}
    if judge_workers > 1 and len(judge_specs) > 1:
        with ThreadPoolExecutor(max_workers=min(judge_workers, len(judge_specs))) as executor:
            futures = {
                executor.submit(
                    score_one_judge,
                    judge_clients[spec.alias],
                    spec,
                    item,
                    candidate_answer,
                    retries,
                    judge_retries,
                    temperature,
                    max_tokens,
                ): spec.alias
                for spec in judge_specs
            }
            for future in as_completed(futures):
                alias = futures[future]
                try:
                    results[alias] = future.result()
                    print(f"[JUDGE-DONE] judge={alias} qid={item.qid} score_total={results[alias]['score_total']}")
                except Exception as exc:
                    print(f"[JUDGE-SKIP] judge={alias} qid={item.qid} err={exc}")
    else:
        for spec in judge_specs:
            try:
                results[spec.alias] = score_one_judge(
                    judge_clients[spec.alias],
                    spec,
                    item,
                    candidate_answer,
                    retries,
                    judge_retries,
                    temperature,
                    max_tokens,
                )
                print(f"[JUDGE-DONE] judge={spec.alias} qid={item.qid} score_total={results[spec.alias]['score_total']}")
            except Exception as exc:
                print(f"[JUDGE-SKIP] judge={spec.alias} qid={item.qid} err={exc}")
    return results


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    seed_everything()
    question_root = Path(args.question_root)
    out_dir = Path(args.out_dir)
    only_question_ids = {qid.strip() for qid in args.only_question_ids.split(",") if qid.strip()}
    judge_question_workers = resolve_worker_count(args.judge_question_workers, args.max_workers)
    judge_workers = max(1, int(args.judge_workers))

    candidate_specs = subjective_candidate_specs(args.models)
    if not candidate_specs:
        raise SystemExit("No candidate models found for judge stage. Run answers first or check --models.")

    judge_specs = enabled_specs(list(DEFAULT_JUDGE_ALIASES))
    if len(judge_specs) != 1 or judge_specs[0].alias != "qwen3-max":
        raise SystemExit("qwen3-max must be enabled in .env for the subjective judge stage")
    judge_clients = {spec.alias: build_client(spec) for spec in judge_specs}

    dataset_payloads = {}
    for dataset_name in args.datasets:
        path = discover_dataset_file(question_root, dataset_name)
        if not path:
            raise SystemExit(f"Dataset file not found for {dataset_name}")
        items = load_subjective_dataset(path, limit=args.limit)
        if only_question_ids:
            items = [item for item in items if item.qid in only_question_ids]
        dataset_payloads[dataset_name] = {item.qid: item for item in items}

    judge_qwen_root = out_dir / "judge_qwen"

    for spec in candidate_specs:
        for mode in args.modes:
            for dataset_name in args.datasets:
                answer_path = out_dir / "answers" / mode / spec.alias / f"{dataset_name}.jsonl"
                if not answer_path.exists():
                    print(f"[JUDGE-INPUT-SKIP] missing answer file: {answer_path}")
                    continue

                answer_rows = load_jsonl(answer_path)
                if args.limit > 0:
                    answer_rows = answer_rows[: args.limit]
                if only_question_ids:
                    answer_rows = [row for row in answer_rows if str(row.get("question_id", "")).strip() in only_question_ids]
                answer_rows = [row for row in answer_rows if has_nonempty_answer(row)]

                question_map = dataset_payloads[dataset_name]
                qwen_path = judge_qwen_root / mode / spec.alias / f"{dataset_name}.jsonl"
                ensure_dir(qwen_path.parent)

                existing_qwen = load_existing_jsonl_map(qwen_path) if args.resume else {}

                pending_rows = [
                    row
                    for row in answer_rows
                    if str(row.get("question_id", "")) in question_map
                    and not has_nonempty_score(existing_qwen.get(str(row.get("question_id", "")), {}))
                ]
                print(
                    f"[JUDGE] model={spec.alias} dataset={dataset_name} mode={mode} "
                    f"answers={len(answer_rows)} pending={len(pending_rows)} "
                    f"question_workers={judge_question_workers} judge_workers={judge_workers}"
                )
                if not pending_rows and args.resume:
                    print(f"[JUDGE-SKIP] model={spec.alias} dataset={dataset_name} mode={mode}")
                    continue

                new_qwen: Dict[str, Dict[str, int]] = {}
                with ThreadPoolExecutor(max_workers=judge_question_workers) as executor:
                    futures = {
                        executor.submit(
                            judge_one_answer,
                            judge_clients,
                            judge_specs,
                            question_map[str(row["question_id"])],
                            row,
                            args.retries,
                            args.judge_retries,
                            args.temperature,
                            args.max_tokens,
                            judge_workers,
                        ): str(row["question_id"])
                        for row in pending_rows
                    }
                    for idx, future in enumerate(as_completed(futures), start=1):
                        qid = futures[future]
                        try:
                            result_map = future.result()
                        except Exception as exc:
                            print(f"[JUDGE-QUESTION-ERROR] qid={qid} err={exc}")
                        else:
                            if "qwen3-max" in result_map:
                                new_qwen[qid] = result_map["qwen3-max"]
                        if idx % args.print_every == 0 or idx == len(futures):
                            print(
                                f"[JUDGE-PROGRESS] model={spec.alias} dataset={dataset_name} "
                                f"mode={mode} completed={idx}/{len(futures)}"
                            )

                merged_qwen = existing_qwen.copy()
                merged_qwen.update(new_qwen)

                ordered_qwen = [merged_qwen[str(row["question_id"])] for row in answer_rows if str(row["question_id"]) in merged_qwen and has_nonempty_score(merged_qwen[str(row["question_id"])])]
                write_jsonl(qwen_path, ordered_qwen)
                print(f"[JUDGE-WRITE] path={qwen_path} rows={len(ordered_qwen)}")

    print(f"Done. Judge results saved to {out_dir}")


if __name__ == "__main__":
    main()
