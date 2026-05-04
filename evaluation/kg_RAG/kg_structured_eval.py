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
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Sequence

try:
    from model_registry import enabled_specs, resolve_max_workers, resolve_objective_temperature
    from structured_eval import (
        KIMI_MODEL_NAME,
        RETRYABLE_ERROR_PATTERNS,
        build_client,
        build_request_kwargs,
        build_structured_messages,
        call_model,
        discover_dataset_file,
        has_bird_id_score,
        has_feature_score,
        has_list_global_score,
        has_nonempty_feature_answer,
        has_nonempty_list_answer,
        load_jsonl,
        load_structured_items,
        parse_bird_id_answer,
        parse_feature_to_family_answer,
        parse_list_global_answer,
        score_bird_id,
        score_feature_to_family,
        score_list_global,
        summarize_bird_id,
        summarize_feature_to_family,
        summarize_list_global,
        write_csv,
    )
    from subjective_common import ensure_dir, load_existing_jsonl_map, write_jsonl
except ModuleNotFoundError:
    from evaluation.model_registry import enabled_specs, resolve_max_workers, resolve_objective_temperature
    from evaluation.structured_eval import (
        KIMI_MODEL_NAME,
        RETRYABLE_ERROR_PATTERNS,
        build_client,
        build_request_kwargs,
        build_structured_messages,
        call_model,
        discover_dataset_file,
        has_bird_id_score,
        has_feature_score,
        has_list_global_score,
        has_nonempty_feature_answer,
        has_nonempty_list_answer,
        load_jsonl,
        load_structured_items,
        parse_bird_id_answer,
        parse_feature_to_family_answer,
        parse_list_global_answer,
        score_bird_id,
        score_feature_to_family,
        score_list_global,
        summarize_bird_id,
        summarize_feature_to_family,
        summarize_list_global,
        write_csv,
    )
    from evaluation.subjective_common import ensure_dir, load_existing_jsonl_map, write_jsonl

from bird_id_reverse_retriever import close_all_drivers, retrieve_bird_id_candidates
from family_table_retriever import retrieve_family_table_context
from list_global_table_retriever import retrieve_list_global_table_context

STRUCTURED_DATASET_ORDER = [
    "List-Global",
    "Bird-ID",
    "Bird-Classify__Feature-to-Family",
]


@dataclass(frozen=True)
class KGStructuredDatasetConfig:
    dataset_key: str
    source_dataset: str
    type_filter: set[str] | None
    context_type: str
    context_builder: Callable[[Dict[str, Any], argparse.Namespace], str]
    prompt_builder: Callable[[Dict[str, Any], str], str]
    answer_parser: Callable[[str], Dict[str, Any]]
    answer_is_nonempty: Callable[[Dict[str, Any]], bool]
    score_builder: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]
    score_is_nonempty: Callable[[Dict[str, Any]], bool]
    summary_builder: Callable[[list[Dict[str, Any]], str], Dict[str, Any]]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run KG/KB-augmented structured evaluation for the remaining four datasets.")
    parser.add_argument("--question-root", type=str, default="question")
    parser.add_argument("--out-dir", type=str, default="evaluation/results_structured_kg_rag")
    parser.add_argument("--models", nargs="*", default=None)
    parser.add_argument("--datasets", nargs="*", default=STRUCTURED_DATASET_ORDER)
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
    parser.add_argument("--kg-uri", type=str, default="bolt://127.0.0.1:7688")
    parser.add_argument("--kg-user", type=str, default="neo4j")
    parser.add_argument("--kg-password", type=str, default="")
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
    parser.add_argument("--list-global-direct-output", action="store_true")
    parser.add_argument("--kb-top-k", type=int, default=80)
    parser.add_argument("--family-top-k", type=int, default=12)
    parser.add_argument("--bird-id-top-k", type=int, default=30)
    parser.add_argument("--bird-id-evidence-per-species", type=int, default=5)
    parser.add_argument("--max-cell-chars", type=int, default=160)
    parser.add_argument("--family-max-cell-chars", type=int, default=240)
    parser.add_argument("--context-log-dir", type=str, default="")
    return parser.parse_args(argv)


def _render_context_block(context: str, fallback: str) -> str:
    text = str(context or "").strip()
    if not text or text.startswith("[NO_"):
        return fallback
    return text


def build_list_global_kb_prompt(item: Dict[str, Any], table_context: str) -> str:
    return "\n".join(
        [
            "You are answering a structured bird retrieval query using BIRDBASE as a table knowledge base.",
            "Use the candidate rows below as open-book evidence.",
            "Return strict JSON only.",
            'Use this schema: {"answer": ["species_a", "species_b"]}',
            "Return only species names, preferably canonical scientific species names.",
            "Do not include explanations or extra keys.",
            "",
            "[Table-KB Context]",
            _render_context_block(table_context, "No table context was retrieved."),
            "",
            "[Question]",
            str(item.get("question", "")).strip(),
        ]
    )


def build_bird_id_reverse_kg_prompt(item: Dict[str, Any], candidate_context: str) -> str:
    return "\n".join(
        [
            "You are solving a masked bird identification task.",
            "Do not assume the target species name is known.",
            "Use the retrieved candidate species below as open-book evidence.",
            "Return strict JSON only.",
            'Use this schema: {"answer": ["guess1", "guess2", "guess3", "guess4", "guess5"]}',
            "Provide at most 5 guesses, ordered from highest confidence to lowest.",
            "Do not include explanations or extra keys.",
            "",
            "[Reverse KG Candidate Context]",
            _render_context_block(candidate_context, "No reverse candidate context was retrieved."),
            "",
            "[Question]",
            str(item.get("question", "")).strip(),
            "",
            "[Clue text]",
            str(item.get("clue_text", "")).strip(),
        ]
    )


def build_feature_to_family_kb_prompt(item: Dict[str, Any], family_context: str) -> str:
    return "\n".join(
        [
            "Identify the avian order and family described below using the family-level table knowledge base.",
            "Return strict JSON only.",
            'Use this schema: {"order": "...", "family": "..."}',
            "Do not include explanations or extra keys.",
            "",
            "[Family-level Table-KB Context]",
            _render_context_block(family_context, "No family-level table context was retrieved."),
            "",
            "[Question]",
            str(item.get("question", "")).strip(),
        ]
    )


def build_list_global_context(item: Dict[str, Any], args: argparse.Namespace) -> str:
    return retrieve_list_global_table_context(
        item=item,
        birdbase_xlsx=args.birdbase_xlsx,
        top_k=args.kb_top_k,
        max_cell_chars=args.max_cell_chars,
    )


def build_bird_id_context(item: Dict[str, Any], args: argparse.Namespace) -> str:
    return retrieve_bird_id_candidates(
        question=str(item.get("question", "")).strip(),
        clue_text=str(item.get("clue_text", "")).strip(),
        top_k=args.bird_id_top_k,
        evidence_per_species=args.bird_id_evidence_per_species,
        kg_uri=args.kg_uri,
        kg_user=args.kg_user,
        kg_password=args.kg_password,
    )


def build_feature_to_family_context(item: Dict[str, Any], args: argparse.Namespace) -> str:
    return retrieve_family_table_context(
        item=item,
        order_xlsx=args.order_xlsx,
        top_k=args.family_top_k,
        max_cell_chars=args.family_max_cell_chars,
    )


DATASET_CONFIGS: Dict[str, KGStructuredDatasetConfig] = {
    "List-Global": KGStructuredDatasetConfig(
        dataset_key="List-Global",
        source_dataset="List-Global",
        type_filter=None,
        context_type="birdbase_table",
        context_builder=build_list_global_context,
        prompt_builder=build_list_global_kb_prompt,
        answer_parser=parse_list_global_answer,
        answer_is_nonempty=has_nonempty_list_answer,
        score_builder=score_list_global,
        score_is_nonempty=has_list_global_score,
        summary_builder=summarize_list_global,
    ),
    "Bird-ID": KGStructuredDatasetConfig(
        dataset_key="Bird-ID",
        source_dataset="Bird-ID",
        type_filter=None,
        context_type="reverse_kg",
        context_builder=build_bird_id_context,
        prompt_builder=build_bird_id_reverse_kg_prompt,
        answer_parser=parse_bird_id_answer,
        answer_is_nonempty=has_nonempty_list_answer,
        score_builder=score_bird_id,
        score_is_nonempty=has_bird_id_score,
        summary_builder=summarize_bird_id,
    ),
    "Bird-Classify__Feature-to-Family": KGStructuredDatasetConfig(
        dataset_key="Bird-Classify__Feature-to-Family",
        source_dataset="Bird-Classify",
        type_filter={"Feature-to-Family"},
        context_type="family_table",
        context_builder=build_feature_to_family_context,
        prompt_builder=build_feature_to_family_kb_prompt,
        answer_parser=parse_feature_to_family_answer,
        answer_is_nonempty=has_nonempty_feature_answer,
        score_builder=score_feature_to_family,
        score_is_nonempty=has_feature_score,
        summary_builder=summarize_feature_to_family,
    ),
}


def answer_one_item(
    client,
    spec,
    item: Dict[str, Any],
    config: KGStructuredDatasetConfig,
    args: argparse.Namespace,
    temperature: float | None,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    qid = str(item["question_id"])
    print(f"[KG-STRUCTURED-ANSWER-START] model={spec.alias} dataset={config.dataset_key} qid={qid}")
    context = config.context_builder(item, args)
    context_status = "no_context" if str(context or "").startswith("[NO_") else "ok"
    prompt = config.prompt_builder(item, context)
    raw_response = call_model(
        client=client,
        spec=spec,
        messages=build_structured_messages(prompt),
        temperature=temperature,
        max_tokens=args.max_tokens,
        retries=args.retries,
    )
    parsed_answer = config.answer_parser(raw_response)
    if not config.answer_is_nonempty(parsed_answer):
        raise ValueError(f"Parsed empty answer for {config.dataset_key} qid={qid}")
    answer_row = {"question_id": qid, **parsed_answer}
    context_row = {
        "question_id": qid,
        "dataset": config.dataset_key,
        "context_type": config.context_type,
        "context_status": context_status,
        "context": context,
    }
    print(f"[KG-STRUCTURED-ANSWER-DONE] model={spec.alias} dataset={config.dataset_key} qid={qid}")
    return answer_row, context_row


def run_answer_stage(
    client,
    spec,
    items: list[Dict[str, Any]],
    config: KGStructuredDatasetConfig,
    answers_path: Path,
    context_log_path: Path,
    answer_question_workers: int,
    temperature: float | None,
    args: argparse.Namespace,
) -> list[Dict[str, Any]]:
    ensure_dir(answers_path.parent)
    ensure_dir(context_log_path.parent)
    existing_answers = load_existing_jsonl_map(answers_path) if args.resume else {}
    existing_context_logs = load_existing_jsonl_map(context_log_path) if args.resume else {}
    completed_qids = {qid for qid, row in existing_answers.items() if config.answer_is_nonempty(row)}
    pending_items = [item for item in items if str(item["question_id"]) not in completed_qids]

    print(
        f"[KG-STRUCTURED-ANSWER] model={spec.alias} dataset={config.dataset_key} "
        f"total={len(items)} pending={len(pending_items)} workers={answer_question_workers}"
    )
    if pending_items:
        new_answers: Dict[str, Dict[str, Any]] = {}
        new_context_logs: Dict[str, Dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=answer_question_workers) as executor:
            futures = {
                executor.submit(
                    answer_one_item,
                    client,
                    spec,
                    item,
                    config,
                    args,
                    temperature,
                ): str(item["question_id"])
                for item in pending_items
            }
            for idx, future in enumerate(as_completed(futures), start=1):
                qid = futures[future]
                try:
                    answer_row, context_row = future.result()
                except Exception as exc:
                    print(f"[KG-STRUCTURED-ANSWER-ERROR] model={spec.alias} dataset={config.dataset_key} qid={qid} err={exc}")
                else:
                    new_answers[qid] = answer_row
                    new_context_logs[qid] = context_row
                if idx % args.print_every == 0 or idx == len(futures):
                    print(
                        f"[KG-STRUCTURED-ANSWER-PROGRESS] model={spec.alias} dataset={config.dataset_key} "
                        f"completed={idx}/{len(futures)}"
                    )
        existing_answers.update(new_answers)
        existing_context_logs.update(new_context_logs)

    ordered_answers = [
        existing_answers[str(item["question_id"])]
        for item in items
        if str(item["question_id"]) in existing_answers and config.answer_is_nonempty(existing_answers[str(item["question_id"])])
    ]
    ordered_context_logs = [
        existing_context_logs[str(item["question_id"])]
        for item in items
        if str(item["question_id"]) in existing_context_logs
    ]
    write_jsonl(answers_path, ordered_answers)
    write_jsonl(context_log_path, ordered_context_logs)
    print(f"[KG-STRUCTURED-ANSWER-WRITE] path={answers_path} rows={len(ordered_answers)}")
    print(f"[KG-STRUCTURED-CONTEXT-WRITE] path={context_log_path} rows={len(ordered_context_logs)}")
    return ordered_answers


def run_score_stage(
    items: list[Dict[str, Any]],
    answers_rows: list[Dict[str, Any]],
    config: KGStructuredDatasetConfig,
    scores_path: Path,
    resume: bool,
) -> list[Dict[str, Any]]:
    ensure_dir(scores_path.parent)
    existing = load_existing_jsonl_map(scores_path) if resume else {}
    item_map = {str(item["question_id"]): item for item in items}
    answer_map = {str(row["question_id"]): row for row in answers_rows}

    for qid, answer_row in answer_map.items():
        if resume and config.score_is_nonempty(existing.get(qid, {})):
            continue
        existing[qid] = config.score_builder(item_map[qid], answer_row)

    ordered_rows = [
        existing[str(item["question_id"])]
        for item in items
        if str(item["question_id"]) in existing and config.score_is_nonempty(existing[str(item["question_id"])])
    ]
    write_jsonl(scores_path, ordered_rows)
    print(f"[KG-STRUCTURED-SCORE-WRITE] path={scores_path} rows={len(ordered_rows)}")
    return ordered_rows


def build_summary_rows(scored_root: Path, model_aliases: list[str], dataset_keys: list[str]) -> list[Dict[str, Any]]:
    rows: list[Dict[str, Any]] = []
    for model in model_aliases:
        for dataset_key in dataset_keys:
            config = DATASET_CONFIGS[dataset_key]
            scored_path = scored_root / model / f"{dataset_key}.jsonl"
            if not scored_path.exists():
                continue
            scored_rows = load_jsonl(scored_path)
            summary_row = config.summary_builder(scored_rows, dataset_key)
            summary_row["model"] = model
            rows.append(summary_row)
    rows.sort(key=lambda row: (row["dataset"], row["model"]))
    return rows


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    question_root = Path(args.question_root)
    out_dir = Path(args.out_dir)
    answer_root = out_dir / "answers"
    scored_root = out_dir / "scored"
    summary_root = out_dir / "summaries"
    context_root = Path(args.context_log_dir) if args.context_log_dir else out_dir / "context_logs"
    ensure_dir(answer_root)
    ensure_dir(scored_root)
    ensure_dir(summary_root)
    ensure_dir(context_root)

    dataset_keys: list[str] = []
    for dataset_key in args.datasets:
        if dataset_key not in DATASET_CONFIGS:
            raise SystemExit(f"Unsupported structured dataset: {dataset_key}")
        if dataset_key not in dataset_keys:
            dataset_keys.append(dataset_key)

    dataset_payloads = {
        dataset_key: load_structured_items(question_root, DATASET_CONFIGS[dataset_key], args.limit)
        for dataset_key in dataset_keys
    }
    answer_question_workers = max(1, args.answer_question_workers or args.max_workers)

    specs = enabled_specs(args.models)
    if not specs:
        raise SystemExit("No enabled models found. Check .env API keys or --models selection.")

    try:
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

            print(
                f"[KG-STRUCTURED-MODEL] model={spec.alias} workers={effective_workers} "
                f"temperature={'<provider-default>' if effective_temperature is None else effective_temperature}"
            )
            for dataset_key in dataset_keys:
                config = DATASET_CONFIGS[dataset_key]
                items = dataset_payloads[dataset_key]
                answers_path = model_answer_dir / f"{dataset_key}.jsonl"
                scores_path = model_scored_dir / f"{dataset_key}.jsonl"
                context_log_path = model_context_dir / f"{dataset_key}.jsonl"
                answer_rows = run_answer_stage(
                    client=client,
                    spec=spec,
                    items=items,
                    config=config,
                    answers_path=answers_path,
                    context_log_path=context_log_path,
                    answer_question_workers=effective_workers,
                    temperature=effective_temperature,
                    args=args,
                )
                run_score_stage(
                    items=items,
                    answers_rows=answer_rows,
                    config=config,
                    scores_path=scores_path,
                    resume=args.resume,
                )
    finally:
        close_all_drivers()

    summary_rows = build_summary_rows(scored_root, [spec.alias for spec in specs], dataset_keys)
    write_csv(
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
    print(f"Done. KG-structured evaluation results saved to {out_dir}")


if __name__ == "__main__":
    main()
