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
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
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
        discover_dataset_file,
        ensure_dir,
        load_jsonl,
        parse_json_answer,
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
        discover_dataset_file,
        ensure_dir,
        load_jsonl,
        parse_json_answer,
        run_one,
        score_answer,
        write_jsonl,
    )

from kg_prompting import build_kg_augmented_prompt
from kg_target_utils import (
    build_kg_cache_key,
    classify_kg_context_status,
    get_target_entity,
    load_kg_cache,
    save_kg_cache,
)
from neo4j_direct_retriever import close_all_drivers, retrieve_kg_context

load_dotenv(override=True)


class KGContextCache:
    def __init__(self, initial_payload: dict[str, Any] | None = None) -> None:
        self._payload: dict[str, Any] = dict(initial_payload or {})
        self._lock = threading.Lock()

    def get_or_retrieve(
        self,
        target_entity: str,
        question: str,
        limit: int,
        neighbor_limit: int,
        debug: bool,
    ) -> tuple[str, str]:
        cache_key = build_kg_cache_key(target_entity, question)
        with self._lock:
            cached = self._payload.get(cache_key)
        if isinstance(cached, dict):
            kg_context = str(cached.get("kg_context", ""))
            status = str(cached.get("status", "")) or classify_kg_context_status(target_entity, kg_context)
            return kg_context, status

        if not str(target_entity or "").strip():
            kg_context = "[NO_KG_CONTEXT: missing target_entity]"
        else:
            kg_context = retrieve_kg_context(
                target_entity=target_entity,
                question=question,
                limit=limit,
                neighbor_limit=neighbor_limit,
                debug=debug,
            )
        status = classify_kg_context_status(target_entity, kg_context)
        entry = {
            "target_entity": target_entity,
            "question": question,
            "kg_context": kg_context,
            "status": status,
        }
        with self._lock:
            self._payload[cache_key] = entry
        return kg_context, status

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._payload)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Objective evaluation with Neo4j one-hop KG-RAG.")
    parser.add_argument("--question-root", type=str, default="question")
    parser.add_argument("--out-dir", type=str, default="evaluation/results_objective_kg_rag")
    parser.add_argument("--models", nargs="*", default=["deepseek", "qwen", "kimi", "glm", "doubao", "hunyuan", "wenxin", "minimax"])
    parser.add_argument("--datasets", nargs="*", default=DEFAULT_DATASET_ORDER)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-workers", type=int, default=8)
    parser.add_argument("--print-every", type=int, default=20)
    parser.add_argument("--save-predictions", action="store_true")
    parser.add_argument("--kg-uri", type=str, default="")
    parser.add_argument("--kg-user", type=str, default="")
    parser.add_argument("--kg-password", type=str, default="")
    parser.add_argument("--kg-limit", type=int, default=30)
    parser.add_argument("--kg-neighbor-limit", type=int, default=160)
    parser.add_argument("--kg-debug", action="store_true")
    parser.add_argument("--kg-cache-path", type=str, default=None)
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
    return parser.parse_args()


def evaluate_item_with_kg(
    client,
    spec,
    item: Dict[str, Any],
    cache: KGContextCache,
    args: argparse.Namespace,
) -> EvalResult:
    dataset = item.get("dataset", "")
    gold = str(item.get("answer", "")).strip()
    item_type = str(item.get("type", "")).strip()
    question = str(item.get("question", "")).strip()
    target_entity = get_target_entity(item)

    kg_context, kg_context_status = cache.get_or_retrieve(
        target_entity=target_entity,
        question=question,
        limit=args.kg_limit,
        neighbor_limit=args.kg_neighbor_limit,
        debug=args.kg_debug,
    )
    prompt = build_kg_augmented_prompt(item, kg_context)

    try:
        raw = run_one(client, spec, prompt)
        pred = parse_json_answer(raw) or ""
        score_em, score_f1, correct = score_answer(dataset, item_type, pred, gold)
        result = EvalResult(
            question_id=item.get("question_id", ""),
            dataset=dataset,
            model_alias=spec.alias,
            target_entity=target_entity,
            prediction_raw=raw,
            prediction_answer=pred,
            gold_answer=gold,
            score_em=score_em,
            score_f1=score_f1,
            is_correct=correct,
        )
    except Exception as exc:
        result = EvalResult(
            question_id=item.get("question_id", ""),
            dataset=dataset,
            model_alias=spec.alias,
            target_entity=target_entity,
            prediction_raw="",
            prediction_answer="",
            gold_answer=gold,
            score_em=0.0,
            score_f1=0.0,
            is_correct=0,
            error=str(exc),
        )

    setattr(result, "kg_context_status", kg_context_status)
    setattr(result, "kg_context", kg_context)
    setattr(result, "kg_prompt", prompt)
    return result


def _serialize_result(result: EvalResult) -> Dict[str, Any]:
    row = asdict(result)
    row["kg_context_status"] = getattr(result, "kg_context_status", "")
    row["kg_context"] = getattr(result, "kg_context", "")
    return row


def run_dataset_for_model(
    client,
    spec,
    ds_name: str,
    rows: List[Dict[str, Any]],
    out_dir: Path,
    max_workers: int,
    print_every: int,
    save_predictions: bool,
    cache: KGContextCache,
    args: argparse.Namespace,
) -> Dict[str, Any]:
    results: List[EvalResult] = []
    completed = 0
    errors = 0
    metric_sum = 0.0
    kg_stats = {"ok": 0, "no_context": 0, "missing_target_entity": 0}

    temperature = resolve_objective_temperature(spec)
    effective_workers = resolve_max_workers(spec, max_workers)

    with ThreadPoolExecutor(max_workers=effective_workers) as executor:
        futures = [executor.submit(evaluate_item_with_kg, client, spec, item, cache, args) for item in rows]
        total = len(futures)
        for fut in as_completed(futures):
            res = fut.result()
            results.append(res)
            completed += 1
            kg_status = getattr(res, "kg_context_status", "")
            if kg_status in kg_stats:
                kg_stats[kg_status] += 1
            if res.error:
                errors += 1
            else:
                metric_sum += res.score_f1 if ds_name in {"QA-MC", "QA-SA", "Bird-Taxonomy"} else float(res.is_correct)

            if completed % print_every == 0 or completed == total:
                denom = max(1, completed - errors)
                live_score = (metric_sum / denom) * 100
                print(
                    f"  [{spec.alias} | {ds_name} | kg-rag] {completed}/{total} | "
                    f"valid={completed - errors} | errors={errors} | workers={effective_workers} | "
                    f"temperature={'<provider-default>' if temperature is None else temperature} | "
                    f"score={live_score:.2f}"
                )

    results.sort(key=lambda item: item.question_id)
    valid = [result for result in results if not result.error]

    if ds_name in {"QA-MC", "QA-SA", "Bird-Taxonomy"}:
        final_score = (sum(result.score_f1 for result in valid) / len(valid) * 100) if valid else 0.0
    else:
        final_score = (sum(result.is_correct for result in valid) / len(valid) * 100) if valid else 0.0

    print("KG context stats:")
    print(f"- ok: {kg_stats['ok']}")
    print(f"- no_context: {kg_stats['no_context']}")
    print(f"- missing_target_entity: {kg_stats['missing_target_entity']}")

    summary = {
        "provider": spec.provider,
        "model": spec.model,
        "base_url": spec.base_url,
        "dataset": ds_name,
        "setting": "neo4j_kg_rag",
        "retrieval_source": "neo4j_one_hop_directed_edges",
        "total": len(results),
        "completed": len(valid),
        "errors": len(results) - len(valid),
        "correct": sum(result.is_correct for result in valid),
        "avg_em": round((sum(result.score_em for result in valid) / len(valid) * 100), 2) if valid else 0.0,
        "avg_f1": round((sum(result.score_f1 for result in valid) / len(valid) * 100), 2) if valid else 0.0,
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
            "kg_limit": args.kg_limit,
            "kg_neighbor_limit": args.kg_neighbor_limit,
            "kg_debug": args.kg_debug,
        },
        "kg_context_stats": kg_stats,
    }

    if save_predictions:
        write_jsonl(out_dir / f"{ds_name}_predictions.jsonl", [_serialize_result(result) for result in results])
    return summary


def main() -> None:
    args = parse_args()
    question_root = Path(args.question_root)
    out_dir = Path(args.out_dir)
    ensure_dir(out_dir)

    if args.kg_uri:
        _sys.modules["neo4j_direct_retriever"].NEO4J_URI = args.kg_uri
    if args.kg_user:
        _sys.modules["neo4j_direct_retriever"].NEO4J_USERNAME = args.kg_user
    if args.kg_password:
        _sys.modules["neo4j_direct_retriever"].NEO4J_PASSWORD = args.kg_password

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

    cache = KGContextCache(load_kg_cache(args.kg_cache_path))
    all_summary: Dict[str, Dict[str, Any]] = {}

    try:
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
                "setting": "neo4j_kg_rag",
                "datasets": {},
                "retrieval_policy": {
                    "kg_limit": args.kg_limit,
                    "kg_neighbor_limit": args.kg_neighbor_limit,
                    "kg_cache_path": args.kg_cache_path,
                },
                "runtime_policy": {
                    "temperature": model_temperature,
                    "workers": model_workers,
                    "official_default_temperature": spec.official_default_temperature,
                    "public_max_concurrency": spec.max_concurrency,
                    "public_rpm_limit": spec.rpm_limit,
                    "public_tpm_limit": spec.tpm_limit,
                    "rate_limit_dynamic": spec.rate_limit_dynamic,
                    "rate_limit_tiered": spec.rate_limit_tiered,
                },
            }
            print(f"\n=== MODEL: {spec.alias} | {spec.model} | kg-rag ===")
            print(
                f"[POLICY] temperature={'<provider-default>' if model_temperature is None else model_temperature} | "
                f"workers={model_workers} | kg_limit={args.kg_limit} | kg_neighbor_limit={args.kg_neighbor_limit}"
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
                    cache=cache,
                    args=args,
                )
                model_summary["datasets"][ds_name] = ds_summary
                print(f"[DONE] {spec.alias} | {ds_name} | score={ds_summary['score']:.2f}")

            (model_dir / "summary.json").write_text(json.dumps(model_summary, ensure_ascii=False, indent=2), encoding="utf-8")
            all_summary[spec.alias] = model_summary
    finally:
        save_kg_cache(args.kg_cache_path, cache.snapshot())
        close_all_drivers()

    (out_dir / "summary_all.json").write_text(json.dumps(all_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDone. KG-RAG objective results saved to {out_dir}")


if __name__ == "__main__":
    main()
