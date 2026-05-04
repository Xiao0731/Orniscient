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
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

try:
    from model_registry import enabled_specs, resolve_max_workers, resolve_objective_temperature
    from objective_eval import (
        EvalResult,
        SUPPORTED_OBJECTIVE_DATASETS,
        DEFAULT_DATASET_ORDER,
        build_client,
        build_objective_prompt,
        discover_dataset_file,
        ensure_dir,
        evaluate_item,
        load_jsonl,
        parse_json_answer,
        resolve_objective_temperature as _unused_resolve_temp,
        run_one,
        score_answer,
        write_jsonl,
    )
except ModuleNotFoundError:
    from evaluation.model_registry import enabled_specs, resolve_max_workers, resolve_objective_temperature
    from evaluation.objective_eval import (
        EvalResult,
        SUPPORTED_OBJECTIVE_DATASETS,
        DEFAULT_DATASET_ORDER,
        build_client,
        build_objective_prompt,
        discover_dataset_file,
        ensure_dir,
        load_jsonl,
        parse_json_answer,
        run_one,
        score_answer,
        write_jsonl,
    )

from text_rag_runtime import TextRAGCorpus, build_text_rag_bundle

load_dotenv(override=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Objective evaluation with Text-RAG baseline over raw BOW chunks.")
    parser.add_argument("--question-root", type=str, default="question")
    parser.add_argument("--out-dir", type=str, default="evaluation/results_objective_text_rag")
    parser.add_argument("--models", nargs="*", default=["deepseek", "qwen", "kimi", "glm", "doubao", "hunyuan", "wenxin", "minimax"])
    parser.add_argument("--datasets", nargs="*", default=DEFAULT_DATASET_ORDER)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-workers", type=int, default=8)
    parser.add_argument("--print-every", type=int, default=20)
    parser.add_argument("--save-predictions", action="store_true")

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
    return parser.parse_args()


def evaluate_item_with_text_rag(client, spec, item: Dict[str, Any], corpus: TextRAGCorpus, args: argparse.Namespace) -> EvalResult:
    dataset = item.get("dataset", "")
    task_type = SUPPORTED_OBJECTIVE_DATASETS[dataset]
    base_prompt = build_objective_prompt(item, task_type)
    bundle = build_text_rag_bundle(
        corpus,
        item,
        top_k=args.top_k,
        max_total_chars=args.max_context_chars,
        restrict_to_target=not args.no_restrict_to_target,
    )
    prompt = base_prompt if not bundle.context else base_prompt + "\n\n" + bundle.context
    gold = str(item.get("answer", "")).strip()
    item_type = str(item.get("type", "")).strip()
    try:
        raw = run_one(client, spec, prompt)
        pred = parse_json_answer(raw) or ""
        score_em, score_f1, correct = score_answer(dataset, item_type, pred, gold)
        result = EvalResult(
            question_id=item.get("question_id", ""),
            dataset=dataset,
            model_alias=spec.alias,
            target_entity=item.get("target_entity", ""),
            prediction_raw=raw,
            prediction_answer=pred,
            gold_answer=gold,
            score_em=score_em,
            score_f1=score_f1,
            is_correct=correct,
        )
        setattr(result, "retrieved_context", bundle.context)
        setattr(result, "retrieved_chunk_ids", [r.chunk.chunk_id for r in bundle.results])
        setattr(result, "retrieval_policy", bundle.retrieval_policy)
        setattr(result, "retrieved_context_status", bundle.status)
        setattr(result, "retrieved_debug", bundle.debug_rows)
        return result
    except Exception as e:
        return EvalResult(
            question_id=item.get("question_id", ""),
            dataset=dataset,
            model_alias=spec.alias,
            target_entity=item.get("target_entity", ""),
            prediction_raw="",
            prediction_answer="",
            gold_answer=gold,
            score_em=0.0,
            score_f1=0.0,
            is_correct=0,
            error=str(e),
        )


def run_dataset_for_model(client, spec, ds_name: str, rows: List[Dict[str, Any]], out_dir: Path, max_workers: int, print_every: int, save_predictions: bool, corpus: TextRAGCorpus, args: argparse.Namespace) -> Dict[str, Any]:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results: List[EvalResult] = []
    completed = 0
    errors = 0
    metric_sum = 0.0

    temperature = resolve_objective_temperature(spec)
    effective_workers = resolve_max_workers(spec, max_workers)

    with ThreadPoolExecutor(max_workers=effective_workers) as executor:
        futures = [executor.submit(evaluate_item_with_text_rag, client, spec, item, corpus, args) for item in rows]
        total = len(futures)
        for fut in as_completed(futures):
            res = fut.result()
            results.append(res)
            completed += 1
            if res.error:
                errors += 1
            else:
                metric_sum += res.score_f1 if ds_name in {"QA-MC", "QA-SA", "Bird-Taxonomy"} else float(res.is_correct)
            if completed % print_every == 0 or completed == total:
                denom = max(1, completed - errors)
                live_score = (metric_sum / denom) * 100
                print(
                    f"  [{spec.alias} | {ds_name} | text-rag] {completed}/{total} | "
                    f"valid={completed - errors} | errors={errors} | workers={effective_workers} | "
                    f"temperature={'<provider-default>' if temperature is None else temperature} | score={live_score:.2f}"
                )

    results.sort(key=lambda x: x.question_id)
    valid = [r for r in results if not r.error]
    if ds_name in {"QA-MC", "QA-SA", "Bird-Taxonomy"}:
        final_score = (sum(r.score_f1 for r in valid) / len(valid) * 100) if valid else 0.0
    else:
        final_score = (sum(r.is_correct for r in valid) / len(valid) * 100) if valid else 0.0

    summary = {
        "provider": spec.provider,
        "model": spec.model,
        "base_url": spec.base_url,
        "dataset": ds_name,
        "setting": "text_rag",
        "retrieval_source": "raw_bow_text_chunks",
        "total": len(results),
        "completed": len(valid),
        "errors": len(results) - len(valid),
        "correct": sum(r.is_correct for r in valid),
        "avg_em": round((sum(r.score_em for r in valid) / len(valid) * 100), 2) if valid else 0.0,
        "avg_f1": round((sum(r.score_f1 for r in valid) / len(valid) * 100), 2) if valid else 0.0,
        "score": round(final_score, 2),
        "runtime_policy": {
            "temperature": temperature,
            "workers": effective_workers,
            "official_default_temperature": spec.official_default_temperature,
            "public_max_concurrency": spec.max_concurrency,
            "public_rpm_limit": spec.rpm_limit,
            "public_tpm_limit": spec.tpm_limit,
            "rate_limit_dynamic": spec.rate_limit_dynamic,
            "rate_limit_tiered": spec.rate_limit_tiered,
        },
        "retrieval_policy": {
            "top_k": args.top_k,
            "chunk_chars": args.chunk_chars,
            "chunk_overlap": args.chunk_overlap,
            "max_context_chars": args.max_context_chars,
            "restrict_to_target": not args.no_restrict_to_target,
        },
    }

    if save_predictions:
        serialized = []
        for r in results:
            row = asdict(r)
            row["retrieved_context"] = getattr(r, "retrieved_context", "")
            row["retrieved_chunk_ids"] = getattr(r, "retrieved_chunk_ids", [])
            row["retrieval_policy"] = getattr(r, "retrieval_policy", "")
            row["retrieved_context_status"] = getattr(r, "retrieved_context_status", "")
            row["retrieved_debug"] = getattr(r, "retrieved_debug", [])
            serialized.append(row)
        write_jsonl(out_dir / f"{ds_name}_predictions.jsonl", serialized)
    return summary


def main() -> None:
    args = parse_args()
    question_root = Path(args.question_root)
    out_dir = Path(args.out_dir)
    ensure_dir(out_dir)

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

    selected_specs = enabled_specs(args.models)
    if not selected_specs:
        raise SystemExit("No enabled models found. Check .env API keys.")

    dataset_payloads: Dict[str, List[Dict[str, Any]]] = {}
    for ds in args.datasets:
        if ds not in SUPPORTED_OBJECTIVE_DATASETS:
            print(f"[SKIP] Unsupported objective dataset for this script: {ds}")
            continue
        path = discover_dataset_file(question_root, ds)
        if not path:
            print(f"[MISS] Dataset file not found for {ds}")
            continue
        rows = load_jsonl(path)
        if args.limit > 0:
            rows = rows[: args.limit]
        dataset_payloads[ds] = rows
        print(f"[LOAD] {ds}: {len(rows)} questions from {path}")

    if not dataset_payloads:
        raise SystemExit("No dataset files loaded.")

    all_summary: Dict[str, Dict[str, Any]] = {}
    for spec in selected_specs:
        client = build_client(spec)
        model_dir = out_dir / spec.alias
        ensure_dir(model_dir)

        model_temperature = resolve_objective_temperature(spec)
        model_workers = resolve_max_workers(spec, args.max_workers)
        model_summary: Dict[str, Any] = {
            "provider": spec.provider,
            "model": spec.model,
            "base_url": spec.base_url,
            "setting": "text_rag",
            "datasets": {},
        }
        print(f"\n=== MODEL: {spec.alias} | {spec.model} | text-rag ===")
        print(
            f"[POLICY] temperature={'<provider-default>' if model_temperature is None else model_temperature} | "
            f"workers={model_workers} | top_k={args.top_k} | max_context_chars={args.max_context_chars}"
        )

        for ds_name, rows in dataset_payloads.items():
            print(f"[RUN] model={spec.alias} dataset={ds_name} n={len(rows)}")
            ds_summary = run_dataset_for_model(
                client=client,
                spec=spec,
                ds_name=ds_name,
                rows=rows,
                out_dir=model_dir,
                max_workers=args.max_workers,
                print_every=args.print_every,
                save_predictions=args.save_predictions,
                corpus=corpus,
                args=args,
            )
            model_summary["datasets"][ds_name] = ds_summary
            print(f"[DONE] {spec.alias} | {ds_name} | score={ds_summary['score']:.2f}")

        (model_dir / "summary.json").write_text(json.dumps(model_summary, ensure_ascii=False, indent=2), encoding="utf-8")
        all_summary[spec.alias] = model_summary

    (out_dir / "summary_all.json").write_text(json.dumps(all_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDone. Text-RAG objective results saved to {out_dir}")


if __name__ == "__main__":
    main()
