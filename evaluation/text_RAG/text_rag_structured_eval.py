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
from pathlib import Path
from typing import Any, Dict, Sequence

try:
    import structured_eval as base
    from model_registry import enabled_specs, resolve_max_workers, resolve_objective_temperature
    from subjective_common import build_client, ensure_dir, load_existing_jsonl_map, write_jsonl
except ModuleNotFoundError:
    from evaluation import structured_eval as base
    from evaluation.model_registry import enabled_specs, resolve_max_workers, resolve_objective_temperature
    from evaluation.subjective_common import build_client, ensure_dir, load_existing_jsonl_map, write_jsonl

from text_rag_runtime import TextRAGCorpus, build_text_rag_bundle


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run structured evaluation with Text-RAG baseline.")
    parser.add_argument("--question-root", type=str, default="question")
    parser.add_argument("--out-dir", type=str, default="evaluation/results_structured_text_rag")
    parser.add_argument("--models", nargs="*", default=None)
    parser.add_argument("--datasets", nargs="*", default=base.STRUCTURED_DATASET_ORDER)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-workers", type=int, default=8)
    parser.add_argument("--answer-question-workers", type=int, default=None)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--print-every", type=int, default=20)

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
    return parser.parse_args(argv)


def run_answer_stage_with_rag(client, spec, items, config, answers_path: Path, answer_question_workers: int, temperature: float | None, max_tokens: int, retries: int, resume: bool, print_every: int, corpus: TextRAGCorpus, args: argparse.Namespace):
    from concurrent.futures import ThreadPoolExecutor, as_completed

    ensure_dir(answers_path.parent)
    existing = load_existing_jsonl_map(answers_path) if resume else {}
    pending_items = [item for item in items if not config.answer_is_nonempty(existing.get(str(item["question_id"]), {}))]

    print(
        f"[STRUCTURED-ANSWER] model={spec.alias} dataset={config.dataset_key} total={len(items)} "
        f"pending={len(pending_items)} workers={answer_question_workers}"
    )
    if not pending_items and resume:
        print(f"[STRUCTURED-ANSWER-SKIP] model={spec.alias} dataset={config.dataset_key}")
        ordered_rows = [existing[str(item['question_id'])] for item in items if str(item['question_id']) in existing and config.answer_is_nonempty(existing[str(item['question_id'])])]
        return ordered_rows

    new_rows: Dict[str, Dict[str, Any]] = {}

    def one(item: Dict[str, Any]) -> Dict[str, Any]:
        base_prompt = config.prompt_builder(item)
        bundle = build_text_rag_bundle(
            corpus,
            item,
            top_k=args.top_k,
            max_total_chars=args.max_context_chars,
            restrict_to_target=not args.no_restrict_to_target,
        )
        if bundle.context:
            base_prompt = base_prompt + "\n\n" + bundle.context + "\n\nUse the retrieved evidence if relevant, but return only the required JSON schema."
        raw_response = base.call_model(
            client=client,
            spec=spec,
            messages=base.build_structured_messages(base_prompt),
            temperature=temperature,
            max_tokens=max_tokens,
            retries=retries,
        )
        row = config.answer_parser(raw_response)
        row["question_id"] = str(item["question_id"])
        row["retrieved_chunk_ids"] = [r.chunk.chunk_id for r in bundle.results]
        row["retrieved_context"] = bundle.context
        row["retrieval_policy"] = bundle.retrieval_policy
        row["retrieved_context_status"] = bundle.status
        row["retrieved_debug"] = bundle.debug_rows
        return row

    with ThreadPoolExecutor(max_workers=answer_question_workers) as executor:
        futures = {executor.submit(one, item): str(item["question_id"]) for item in pending_items}
        for idx, future in enumerate(as_completed(futures), start=1):
            qid = futures[future]
            try:
                row = future.result()
            except Exception as exc:
                print(f"[STRUCTURED-ANSWER-ERROR] model={spec.alias} dataset={config.dataset_key} qid={qid} err={exc}")
            else:
                new_rows[qid] = row
            if idx % print_every == 0 or idx == len(futures):
                print(
                    f"[STRUCTURED-ANSWER-PROGRESS] model={spec.alias} dataset={config.dataset_key} "
                    f"completed={idx}/{len(futures)}"
                )

    merged = existing.copy()
    merged.update(new_rows)
    ordered_rows = [merged[str(item["question_id"])] for item in items if str(item["question_id"]) in merged and config.answer_is_nonempty(merged[str(item["question_id"])])]
    write_jsonl(answers_path, ordered_rows)
    print(f"[STRUCTURED-ANSWER-WRITE] path={answers_path} rows={len(ordered_rows)}")
    return ordered_rows


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    question_root = Path(args.question_root)
    out_dir = Path(args.out_dir)
    answer_root = out_dir / "answers"
    scored_root = out_dir / "scored"
    summary_root = out_dir / "summaries"
    ensure_dir(answer_root)
    ensure_dir(scored_root)
    ensure_dir(summary_root)

    corpus = TextRAGCorpus.from_paths(
        bow_glob=args.bow_glob,
        order_xlsx=args.order_xlsx or None,
        cache_jsonl=args.cache_jsonl,
        chunk_chars=args.chunk_chars,
        chunk_overlap=args.chunk_overlap,
        top_k=args.top_k,
        max_chars_per_chunk=min(args.chunk_chars, 1400),
        default_restrict_to_target=not args.no_restrict_to_target,
        species_chunks_jsonl=args.species_chunks_jsonl,
        family_chunks_jsonl=args.family_chunks_jsonl,
    )
    print(f"[TEXT-RAG] loaded chunks={len(corpus.chunks)}")

    dataset_keys = []
    for dataset_key in args.datasets:
        if dataset_key not in base.DATASET_CONFIGS:
            raise SystemExit(f"Unsupported structured dataset: {dataset_key}")
        if dataset_key not in dataset_keys:
            dataset_keys.append(dataset_key)

    dataset_payloads = {dataset_key: base.load_structured_items(question_root, base.DATASET_CONFIGS[dataset_key], args.limit) for dataset_key in dataset_keys}
    answer_question_workers = max(1, args.answer_question_workers or args.max_workers)

    specs = enabled_specs(args.models)
    if not specs:
        raise SystemExit("No enabled models found. Check .env API keys or --models selection.")

    for spec in specs:
        client = build_client(spec)
        effective_workers = resolve_max_workers(spec, answer_question_workers)
        effective_temperature = args.temperature if args.temperature is not None else resolve_objective_temperature(spec)
        model_answer_dir = answer_root / spec.alias
        model_scored_dir = scored_root / spec.alias
        ensure_dir(model_answer_dir)
        ensure_dir(model_scored_dir)

        print(
            f"[STRUCTURED-MODEL] model={spec.alias} workers={effective_workers} "
            f"temperature={'<provider-default>' if effective_temperature is None else effective_temperature} | setting=text_rag"
        )
        for dataset_key in dataset_keys:
            config = base.DATASET_CONFIGS[dataset_key]
            items = dataset_payloads[dataset_key]
            answers_path = model_answer_dir / f"{dataset_key}.jsonl"
            scores_path = model_scored_dir / f"{dataset_key}.jsonl"
            answer_rows = run_answer_stage_with_rag(
                client=client,
                spec=spec,
                items=items,
                config=config,
                answers_path=answers_path,
                answer_question_workers=effective_workers,
                temperature=effective_temperature,
                max_tokens=args.max_tokens,
                retries=args.retries,
                resume=args.resume,
                print_every=args.print_every,
                corpus=corpus,
                args=args,
            )
            base.run_score_stage(
                items=items,
                answers_rows=answer_rows,
                config=config,
                scores_path=scores_path,
                resume=args.resume,
            )

    summary_rows = base.build_summary_rows(scored_root, [spec.alias for spec in specs], dataset_keys)
    base.write_csv(
        summary_root / "summary_structured.csv",
        summary_rows,
        [
            "dataset",
            "model",
            "n_total",
            "avg_precision",
            "avg_recall",
            "avg_f1",
            "set_em",
            "top1_accuracy",
            "top5_hit_rate",
            "weighted_top5_accuracy",
            "order_accuracy",
            "family_accuracy",
            "hierarchical_accuracy",
        ],
    )
    print(f"Done. Text-RAG structured evaluation results saved to {out_dir}")


if __name__ == "__main__":
    main()
