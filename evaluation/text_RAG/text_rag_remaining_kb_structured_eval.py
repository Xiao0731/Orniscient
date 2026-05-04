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
from concurrent.futures import ThreadPoolExecutor, as_completed
import statistics
from pathlib import Path
from typing import Any, Dict, Sequence

try:
    import structured_eval as base
    from model_registry import enabled_specs, resolve_max_workers, resolve_objective_temperature
    from subjective_common import build_client, ensure_dir, load_existing_jsonl_map, load_jsonl, write_jsonl
except ModuleNotFoundError:
    from evaluation import structured_eval as base
    from evaluation.model_registry import enabled_specs, resolve_max_workers, resolve_objective_temperature
    from evaluation.subjective_common import build_client, ensure_dir, load_existing_jsonl_map, load_jsonl, write_jsonl

from birdbase_table_utils import enrich_column_map_with_values, load_birdbase_table
from remaining_bird_classify import build_feature_to_family_candidates
from remaining_bird_id import build_bird_id_candidate_context
from remaining_list_global import answer_list_global_item
from text_rag_runtime import TextRAGCorpus


SUPPORTED_DATASETS = ["List-Global", "Bird-ID", "Bird-Classify__Feature-to-Family"]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run remaining-four task-adapted KB/Text-RAG structured evaluation.")
    parser.add_argument("--question-root", type=str, default="question")
    parser.add_argument("--out-dir", type=str, default="evaluation/output/results_structured_remaining_kb")
    parser.add_argument("--models", nargs="*", default=None)
    parser.add_argument("--datasets", nargs="*", default=SUPPORTED_DATASETS)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-workers", type=int, default=8)
    parser.add_argument("--answer-question-workers", type=int, default=None)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--print-every", type=int, default=20)
    parser.add_argument("--birdbase-xlsx", type=str, default="data/BIRDBASE.xlsx")
    parser.add_argument("--order-xlsx", type=str, default="data/Order.xlsx")
    parser.add_argument("--species-chunks-jsonl", type=str, default="kg_v2/outputs/intermediate/species_chunks.jsonl")
    parser.add_argument("--family-chunks-jsonl", type=str, default="kg_v2/outputs/intermediate/family_chunks.jsonl")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--max-context-chars", type=int, default=3500)
    parser.add_argument("--candidate-k", type=int, default=30)
    parser.add_argument("--evidence-per-candidate", type=int, default=3)
    parser.add_argument("--list-global-constraint-source", type=str, default="question", choices=["question", "provenance"])
    parser.add_argument("--ambiguous-realm-policy", type=str, default="skip", choices=["skip", "union"])
    parser.add_argument("--only-question-ids", type=str, default="")
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args(argv)


def build_bird_id_prompt(item: Dict[str, Any], candidate_context: str) -> str:
    parts = [
        "You are solving a masked bird identification task.",
        "The gold target species name was NOT used for retrieval.",
        "Return strict JSON only.",
        'Use this schema: {"answer": ["guess1", "guess2", "guess3", "guess4", "guess5"]}',
        "Provide at most 5 guesses, ordered from highest confidence to lowest.",
        "Do not include explanations or extra keys.",
        "",
    ]
    if candidate_context:
        parts.extend([candidate_context, ""])
    parts.append(f"Question: {item.get('question', '')}")
    clue_text = str(item.get("clue_text", "")).strip()
    if clue_text:
        parts.extend(["", f"Clue text: {clue_text}"])
    return "\n".join(parts)


def build_feature_prompt(item: Dict[str, Any], candidate_context: str) -> str:
    lines = [
        "Identify the avian order and family described below using the candidate family evidence.",
        "Return strict JSON only.",
        'Use this schema: {"order": "...", "family": "..."}',
        "Do not include explanations or extra keys.",
        "",
    ]
    if candidate_context:
        lines.extend([candidate_context, ""])
    lines.append(f"Question: {item.get('question', '')}")
    return "\n".join(lines)


def load_items(question_root: Path, dataset_key: str, limit: int, only_question_ids: set[str] | None = None) -> list[Dict[str, Any]]:
    items = base.load_structured_items(question_root, base.DATASET_CONFIGS[dataset_key], limit=0)
    if only_question_ids:
        items = [item for item in items if str(item.get("question_id", "")).strip() in only_question_ids]
    if limit > 0:
        items = items[:limit]
    return items


def run_answer_stage(
    client,
    spec,
    items: list[Dict[str, Any]],
    dataset_key: str,
    answers_path: Path,
    context_log_path: Path,
    answer_question_workers: int,
    temperature: float | None,
    max_tokens: int,
    retries: int,
    resume: bool,
    print_every: int,
    corpus: TextRAGCorpus | None,
    birdbase_df,
    column_map: dict | None,
    args: argparse.Namespace,
) -> list[Dict[str, Any]]:
    ensure_dir(answers_path.parent)
    ensure_dir(context_log_path.parent)
    config = base.DATASET_CONFIGS[dataset_key]
    existing_answers = load_existing_jsonl_map(answers_path) if resume else {}
    existing_context = load_existing_jsonl_map(context_log_path) if resume else {}
    pending_items = [item for item in items if not config.answer_is_nonempty(existing_answers.get(str(item["question_id"]), {}))]

    print(
        f"[REMAINING-STRUCTURED-ANSWER] model={spec.alias} dataset={dataset_key} "
        f"total={len(items)} pending={len(pending_items)} workers={answer_question_workers}"
    )
    if not pending_items and resume:
        ordered_rows = [
            existing_answers[str(item["question_id"])]
            for item in items
            if str(item["question_id"]) in existing_answers and config.answer_is_nonempty(existing_answers[str(item["question_id"])])
        ]
        return ordered_rows

    def one(item: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
        qid = str(item["question_id"])
        if dataset_key == "List-Global":
            answer_row = answer_list_global_item(
                item=item,
                birdbase_df=birdbase_df,
                column_map=column_map or {},
                constraint_source=args.list_global_constraint_source,
                ambiguous_realm_policy=args.ambiguous_realm_policy,
            )
            context_row = {
                "question_id": qid,
                "dataset": dataset_key,
                "context_type": "birdbase_rule_query",
                "context_status": answer_row.get("status", "ok" if answer_row.get("answer") else "no_context"),
                "context": "",
                "condition_text": answer_row.get("condition_text", ""),
                "answer_preview": answer_row.get("answer_preview", []),
                "matched_rows": answer_row.get("matched_rows", 0),
                "ambiguous_realm_policy": answer_row.get("ambiguous_realm_policy", args.ambiguous_realm_policy),
                "applied_ambiguous_realm_codes": answer_row.get("applied_ambiguous_realm_codes", []),
                "debug": answer_row.get("debug", {}),
                "parsed_constraints": answer_row.get("parsed_constraints", {}),
                "unresolved_constraints": answer_row.get("unresolved_constraints", []),
            }
            return answer_row, context_row

        if dataset_key == "Bird-ID":
            assert corpus is not None
            payload = build_bird_id_candidate_context(
                item=item,
                corpus=corpus,
                birdbase_df=birdbase_df,
                column_map=column_map,
                candidate_k=args.candidate_k,
                evidence_per_candidate=args.evidence_per_candidate,
            )
            prompt = build_bird_id_prompt(item, payload.get("retrieved_context", ""))
            raw_response = base.call_model(
                client=client,
                spec=spec,
                messages=base.build_structured_messages(prompt),
                temperature=temperature,
                max_tokens=max_tokens,
                retries=retries,
            )
            parsed = base.parse_bird_id_answer(raw_response)
            answer_row = {
                "question_id": qid,
                **parsed,
                **payload,
            }
            context_row = {
                "question_id": qid,
                "dataset": dataset_key,
                "context_type": "bird_id_candidates",
                "context_status": payload.get("retrieved_context_status", ""),
                "context": payload.get("retrieved_context", ""),
                "debug": payload.get("candidate_debug", []),
                "parsed_constraints": payload.get("parsed_constraints", {}),
                "unresolved_constraints": payload.get("unresolved_constraints", []),
            }
            return answer_row, context_row

        assert corpus is not None
        payload = build_feature_to_family_candidates(
            corpus=corpus,
            item=item,
            order_xlsx=args.order_xlsx,
            top_k=max(args.top_k, 10),
        )
        prompt = build_feature_prompt(item, payload.get("context", ""))
        raw_response = base.call_model(
            client=client,
            spec=spec,
            messages=base.build_structured_messages(prompt),
            temperature=temperature,
            max_tokens=max_tokens,
            retries=retries,
        )
        parsed = base.parse_feature_to_family_answer(raw_response)
        answer_row = {
            "question_id": qid,
            **parsed,
            **payload,
        }
        context_row = {
            "question_id": qid,
            "dataset": dataset_key,
            "context_type": "feature_family_candidates",
            "context_status": payload.get("retrieved_context_status", ""),
            "context": payload.get("context", ""),
            "debug": payload.get("retrieved_debug", []),
            "parsed_constraints": {},
            "gold_family_in_candidates": payload.get("gold_family_in_candidates", 0),
            "order_xlsx_fallback_used": payload.get("order_xlsx_fallback_used", 0),
        }
        return answer_row, context_row

    new_answers: Dict[str, Dict[str, Any]] = {}
    new_context: Dict[str, Dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=answer_question_workers) as executor:
        futures = {executor.submit(one, item): str(item["question_id"]) for item in pending_items}
        for idx, future in enumerate(as_completed(futures), start=1):
            qid = futures[future]
            try:
                answer_row, context_row = future.result()
            except Exception as exc:
                print(f"[REMAINING-STRUCTURED-ANSWER-ERROR] model={spec.alias} dataset={dataset_key} qid={qid} err={exc}")
            else:
                new_answers[qid] = answer_row
                new_context[qid] = context_row
            if idx % print_every == 0 or idx == len(futures):
                print(
                    f"[REMAINING-STRUCTURED-ANSWER-PROGRESS] model={spec.alias} dataset={dataset_key} "
                    f"completed={idx}/{len(futures)}"
                )

    merged_answers = existing_answers.copy()
    merged_answers.update(new_answers)
    merged_context = existing_context.copy()
    merged_context.update(new_context)
    ordered_answers = [
        merged_answers[str(item["question_id"])]
        for item in items
        if str(item["question_id"]) in merged_answers and config.answer_is_nonempty(merged_answers[str(item["question_id"])])
    ]
    ordered_context = [merged_context[str(item["question_id"])] for item in items if str(item["question_id"]) in merged_context]
    write_jsonl(answers_path, ordered_answers)
    write_jsonl(context_log_path, ordered_context)
    print(f"[REMAINING-STRUCTURED-ANSWER-WRITE] path={answers_path} rows={len(ordered_answers)}")
    print(f"[REMAINING-STRUCTURED-CONTEXT-WRITE] path={context_log_path} rows={len(ordered_context)}")
    return ordered_answers


def run_score_stage(
    items: list[Dict[str, Any]],
    answers_rows: list[Dict[str, Any]],
    dataset_key: str,
    scores_path: Path,
    resume: bool,
) -> list[Dict[str, Any]]:
    ensure_dir(scores_path.parent)
    config = base.DATASET_CONFIGS[dataset_key]
    existing = load_existing_jsonl_map(scores_path) if resume else {}
    item_map = {str(item["question_id"]): item for item in items}
    answer_map = {str(row["question_id"]): row for row in answers_rows}
    for qid, answer_row in answer_map.items():
        if resume and config.score_is_nonempty(existing.get(qid, {})):
            continue
        score_row = config.score_builder(item_map[qid], answer_row)
        if dataset_key == "Bird-ID":
            gold_aliases = set()
            gold_aliases.update(base.build_alias_variants(item_map[qid].get("answer")))
            gold_aliases.update(base.build_alias_variants(item_map[qid].get("target_entity")))
            candidate_species = answer_row.get("candidate_species", []) or []
            gold_rank = None
            for idx, candidate in enumerate(candidate_species, start=1):
                aliases = set()
                aliases.update(base.build_alias_variants(candidate.get("scientific_name")))
                aliases.update(base.build_alias_variants(candidate.get("common_name")))
                if aliases & gold_aliases:
                    gold_rank = idx
                    break
            score_row["gold_in_candidates"] = int(gold_rank is not None)
            score_row["gold_rank_before_llm"] = gold_rank if gold_rank is not None else ""
            score_row["candidate_recall_at_30"] = int(gold_rank is not None and gold_rank <= 30)
            score_row["candidate_recall_at_50"] = int(gold_rank is not None and gold_rank <= 50)
            score_row["candidate_recall_at_80"] = int(gold_rank is not None and gold_rank <= 80)
        existing[qid] = score_row

    ordered_rows = [
        existing[str(item["question_id"])]
        for item in items
        if str(item["question_id"]) in existing and config.score_is_nonempty(existing[str(item["question_id"])])
    ]
    write_jsonl(scores_path, ordered_rows)
    print(f"[REMAINING-STRUCTURED-SCORE-WRITE] path={scores_path} rows={len(ordered_rows)}")
    return ordered_rows


def write_bird_id_candidate_recall_summary(
    summary_path: Path,
    *,
    model_alias: str,
    candidate_k: int,
    scored_rows: list[Dict[str, Any]],
) -> None:
    ensure_dir(summary_path.parent)
    n_total = len(scored_rows)
    gold_ranks = [int(row["gold_rank_before_llm"]) for row in scored_rows if str(row.get("gold_rank_before_llm", "")).strip()]
    row = {
        "dataset": "Bird-ID",
        "model": model_alias,
        "n_total": n_total,
        "candidate_k": candidate_k,
        "gold_in_candidates_count": sum(int(row.get("gold_in_candidates", 0)) for row in scored_rows),
        "candidate_recall_at_k": round(sum(int(row.get("gold_in_candidates", 0)) for row in scored_rows) / n_total, 4) if n_total else 0.0,
        "candidate_recall_at_30": round(sum(int(row.get("candidate_recall_at_30", 0)) for row in scored_rows) / n_total, 4) if n_total else 0.0,
        "candidate_recall_at_50": round(sum(int(row.get("candidate_recall_at_50", 0)) for row in scored_rows) / n_total, 4) if n_total else 0.0,
        "candidate_recall_at_80": round(sum(int(row.get("candidate_recall_at_80", 0)) for row in scored_rows) / n_total, 4) if n_total else 0.0,
        "avg_gold_rank": round(sum(gold_ranks) / len(gold_ranks), 4) if gold_ranks else "",
        "median_gold_rank": round(statistics.median(gold_ranks), 4) if gold_ranks else "",
    }
    base.write_csv(
        summary_path,
        [row],
        [
            "dataset",
            "model",
            "n_total",
            "candidate_k",
            "gold_in_candidates_count",
            "candidate_recall_at_k",
            "candidate_recall_at_30",
            "candidate_recall_at_50",
            "candidate_recall_at_80",
            "avg_gold_rank",
            "median_gold_rank",
        ],
    )
    return row


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    only_question_ids = {qid.strip() for qid in args.only_question_ids.split(",") if qid.strip()}
    question_root = Path(args.question_root)
    out_dir = Path(args.out_dir)
    answer_root = out_dir / "answers"
    scored_root = out_dir / "scored"
    summary_root = out_dir / "summaries"
    context_root = out_dir / "context_logs"
    ensure_dir(answer_root)
    ensure_dir(scored_root)
    ensure_dir(summary_root)
    ensure_dir(context_root)

    dataset_keys: list[str] = []
    for dataset_key in args.datasets:
        if dataset_key not in SUPPORTED_DATASETS:
            raise SystemExit(f"Unsupported dataset: {dataset_key}")
        if dataset_key not in dataset_keys:
            dataset_keys.append(dataset_key)

    birdbase_df = None
    column_map = None
    if any(dataset in {"List-Global", "Bird-ID"} for dataset in dataset_keys):
        birdbase_df, column_map = load_birdbase_table(args.birdbase_xlsx)
        column_map = enrich_column_map_with_values(birdbase_df, column_map)

    corpus = None
    if any(dataset in {"Bird-ID", "Bird-Classify__Feature-to-Family"} for dataset in dataset_keys):
        corpus = TextRAGCorpus.from_paths(
            species_chunks_jsonl=args.species_chunks_jsonl,
            family_chunks_jsonl=args.family_chunks_jsonl,
            top_k=args.top_k,
            max_chars_per_chunk=1400,
            default_restrict_to_target=False,
        )
        print(f"[TEXT-RAG-KB] loaded chunks={len(corpus.chunks)}")

    dataset_payloads = {
        dataset_key: load_items(question_root, dataset_key, args.limit, only_question_ids or None)
        for dataset_key in dataset_keys
    }
    answer_question_workers = max(1, args.answer_question_workers or args.max_workers)
    specs = enabled_specs(args.models)
    if not specs:
        raise SystemExit("No enabled models found. Check .env API keys or --models selection.")

    bird_id_recall_rows: list[Dict[str, Any]] = []
    for spec in specs:
        client = build_client(spec)
        effective_workers = resolve_max_workers(spec, answer_question_workers)
        effective_temperature = args.temperature if args.temperature is not None else resolve_objective_temperature(spec)
        model_answer_dir = answer_root / spec.alias
        model_scored_dir = scored_root / spec.alias
        model_context_dir = context_root / spec.alias
        ensure_dir(model_answer_dir)
        ensure_dir(model_scored_dir)
        ensure_dir(model_context_dir)
        print(f"[REMAINING-STRUCTURED-MODEL] model={spec.alias} workers={effective_workers}")
        for dataset_key in dataset_keys:
            items = dataset_payloads[dataset_key]
            answers_path = model_answer_dir / f"{dataset_key}.jsonl"
            scores_path = model_scored_dir / f"{dataset_key}.jsonl"
            context_log_path = model_context_dir / f"{dataset_key}.jsonl"
            answer_rows = run_answer_stage(
                client=client,
                spec=spec,
                items=items,
                dataset_key=dataset_key,
                answers_path=answers_path,
                context_log_path=context_log_path,
                answer_question_workers=effective_workers,
                temperature=effective_temperature,
                max_tokens=args.max_tokens,
                retries=args.retries,
                resume=args.resume,
                print_every=args.print_every,
                corpus=corpus,
                birdbase_df=birdbase_df,
                column_map=column_map,
                args=args,
            )
            scored_rows = run_score_stage(
                items=items,
                answers_rows=answer_rows,
                dataset_key=dataset_key,
                scores_path=scores_path,
                resume=args.resume,
            )
            if dataset_key == "Bird-ID":
                summary_row = write_bird_id_candidate_recall_summary(
                    summary_root / f"bird_id_candidate_recall_summary__{spec.alias}.csv",
                    model_alias=spec.alias,
                    candidate_k=args.candidate_k,
                    scored_rows=scored_rows,
                )
                bird_id_recall_rows.append(summary_row)

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
    if bird_id_recall_rows:
        base.write_csv(
            summary_root / "bird_id_candidate_recall_summary.csv",
            bird_id_recall_rows,
            [
                "dataset",
                "model",
                "n_total",
                "candidate_k",
                "gold_in_candidates_count",
                "candidate_recall_at_k",
                "candidate_recall_at_30",
                "candidate_recall_at_50",
                "candidate_recall_at_80",
                "avg_gold_rank",
                "median_gold_rank",
            ],
        )
    print(f"Done. Remaining-four structured KB/Text-RAG results saved to {out_dir}")


if __name__ == "__main__":
    main()
