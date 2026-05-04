from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, Sequence

try:
    from model_registry import subjective_candidate_specs
    from subjective_common import (
        SUPPORTED_PROMPT_MODES,
        build_candidate_messages,
        build_client,
        call_with_retries,
        discover_dataset_file,
        ensure_dir,
        has_nonempty_answer,
        load_existing_jsonl_map,
        load_fewshot_examples,
        load_subjective_dataset,
        parse_candidate_response,
        prepare_candidate_question,
        resolve_worker_count,
        seed_everything,
        write_jsonl,
    )
    from subjective_rubrics import DEFAULT_SUBJECTIVE_DATASET_ORDER
except ModuleNotFoundError:
    from evaluation.model_registry import subjective_candidate_specs
    from evaluation.subjective_common import (
        SUPPORTED_PROMPT_MODES,
        build_candidate_messages,
        build_client,
        call_with_retries,
        discover_dataset_file,
        ensure_dir,
        has_nonempty_answer,
        load_existing_jsonl_map,
        load_fewshot_examples,
        load_subjective_dataset,
        parse_candidate_response,
        prepare_candidate_question,
        resolve_worker_count,
        seed_everything,
        write_jsonl,
    )
    from evaluation.subjective_rubrics import DEFAULT_SUBJECTIVE_DATASET_ORDER


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run minimal subjective-answer generation.")
    parser.add_argument("--question-root", type=str, default="question")
    parser.add_argument("--out-dir", type=str, default="evaluation/results_subjective")
    parser.add_argument("--fewshot-root", type=str, default="evaluation/fewshot_examples")
    parser.add_argument("--models", nargs="*", default=None)
    parser.add_argument("--datasets", nargs="*", default=DEFAULT_SUBJECTIVE_DATASET_ORDER)
    parser.add_argument("--modes", nargs="*", default=list(SUPPORTED_PROMPT_MODES))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--answer-question-workers", type=int, default=None)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--print-every", type=int, default=20)
    return parser.parse_args(argv)


def validate_modes(modes: list[str]) -> list[str]:
    normalized: list[str] = []
    for mode in modes:
        if mode not in SUPPORTED_PROMPT_MODES:
            raise SystemExit(f"Unsupported mode: {mode}. Supported: {', '.join(SUPPORTED_PROMPT_MODES)}")
        if mode not in normalized:
            normalized.append(mode)
    return normalized


def answer_one(
    client,
    spec,
    item,
    mode: str,
    fewshot_examples: list[Dict[str, Any]] | None,
    temperature: float,
    max_tokens: int,
    retries: int,
) -> Dict[str, str]:
    print(f"[ANSWER-START] model={spec.alias} mode={mode} qid={item.qid}")
    question_for_model = prepare_candidate_question(item)
    messages = build_candidate_messages(
        item=item,
        mode=mode,
        question_for_model=question_for_model,
        fewshot_examples=fewshot_examples,
    )
    raw_response = call_with_retries(
        client=client,
        spec=spec,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        retries=retries,
    )
    # print(f"[RAW-RESPONSE] model={spec.alias} qid={item.qid} raw={raw_response!r}")
    answer = parse_candidate_response(raw_response)
    # print(f"[PARSED-ANSWER] model={spec.alias} qid={item.qid} answer={answer!r}")
    if not answer:
        raise ValueError(f"Empty answer after parsing for qid={item.qid}")
    print(f"[ANSWER-DONE] model={spec.alias} mode={mode} qid={item.qid}")
    return {"question_id": item.qid, "answer": answer}


def run_mode_dataset(
    client,
    spec,
    dataset_name: str,
    items,
    mode: str,
    out_path: Path,
    fewshot_root: Path,
    resume: bool,
    answer_question_workers: int,
    temperature: float,
    max_tokens: int,
    retries: int,
    print_every: int,
) -> None:
    ensure_dir(out_path.parent)
    existing = load_existing_jsonl_map(out_path) if resume else {}
    completed_qids = {qid for qid, row in existing.items() if has_nonempty_answer(row)}
    pending_items = [item for item in items if item.qid not in completed_qids]

    fewshot_examples = None
    if mode == "few_shot":
        fewshot_examples = load_fewshot_examples(fewshot_root, dataset_name)

    print(
        f"[ANSWER] model={spec.alias} dataset={dataset_name} mode={mode} "
        f"total={len(items)} pending={len(pending_items)} workers={answer_question_workers}"
    )
    if not pending_items and resume:
        print(f"[ANSWER-SKIP] model={spec.alias} dataset={dataset_name} mode={mode}")
        return

    new_rows: Dict[str, Dict[str, str]] = {}
    with ThreadPoolExecutor(max_workers=answer_question_workers) as executor:
        futures = {
            executor.submit(
                answer_one,
                client,
                spec,
                item,
                mode,
                fewshot_examples,
                temperature,
                max_tokens,
                retries,
            ): item.qid
            for item in pending_items
        }
        for idx, future in enumerate(as_completed(futures), start=1):
            qid = futures[future]
            try:
                row = future.result()
            except Exception as exc:
                print(f"[ANSWER-ERROR] model={spec.alias} mode={mode} qid={qid} err={exc}")
            else:
                new_rows[row["question_id"]] = row
            if idx % print_every == 0 or idx == len(futures):
                print(
                    f"[ANSWER-PROGRESS] model={spec.alias} dataset={dataset_name} "
                    f"mode={mode} completed={idx}/{len(futures)}"
                )

    merged = existing.copy()
    merged.update(new_rows)
    ordered_rows = [{"question_id": item.qid, "answer": merged[item.qid]["answer"]} for item in items if item.qid in merged and has_nonempty_answer(merged[item.qid])]
    write_jsonl(out_path, ordered_rows)
    print(f"[ANSWER-WRITE] path={out_path} rows={len(ordered_rows)}")


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    seed_everything()
    question_root = Path(args.question_root)
    out_dir = Path(args.out_dir)
    fewshot_root = Path(args.fewshot_root)
    modes = validate_modes(args.modes)
    answer_question_workers = resolve_worker_count(args.answer_question_workers, args.max_workers)

    specs = subjective_candidate_specs(args.models)
    if not specs:
        raise SystemExit("No enabled candidate models found. Check .env API keys or --models selection.")

    dataset_payloads = {}
    for dataset_name in args.datasets:
        path = discover_dataset_file(question_root, dataset_name)
        if not path:
            raise SystemExit(f"Dataset file not found for {dataset_name}")
        dataset_payloads[dataset_name] = load_subjective_dataset(path, limit=args.limit)
        print(f"[LOAD] dataset={dataset_name} questions={len(dataset_payloads[dataset_name])} path={path}")

    for spec in specs:
        client = build_client(spec)
        for mode in modes:
            for dataset_name, items in dataset_payloads.items():
                out_path = out_dir / "answers" / mode / spec.alias / f"{dataset_name}.jsonl"
                run_mode_dataset(
                    client=client,
                    spec=spec,
                    dataset_name=dataset_name,
                    items=items,
                    mode=mode,
                    out_path=out_path,
                    fewshot_root=fewshot_root,
                    resume=args.resume,
                    answer_question_workers=answer_question_workers,
                    temperature=args.temperature,
                    max_tokens=args.max_tokens,
                    retries=args.retries,
                    print_every=args.print_every,
                )

    print(f"Done. Subjective answers saved to {out_dir / 'answers'}")


if __name__ == "__main__":
    main()
