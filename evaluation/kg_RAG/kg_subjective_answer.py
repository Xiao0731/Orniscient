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
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Sequence

try:
    from model_registry import subjective_candidate_specs
    from subjective_common import (
        SUPPORTED_PROMPT_MODES,
        build_client,
        call_with_retries,
        discover_dataset_file,
        ensure_dir,
        get_subjective_allowed_types,
        has_nonempty_answer,
        load_existing_jsonl_map,
        load_fewshot_examples,
        load_jsonl,
        normalize_whitespace,
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
        build_client,
        call_with_retries,
        discover_dataset_file,
        ensure_dir,
        get_subjective_allowed_types,
        has_nonempty_answer,
        load_existing_jsonl_map,
        load_fewshot_examples,
        load_jsonl,
        normalize_whitespace,
        parse_candidate_response,
        prepare_candidate_question,
        resolve_worker_count,
        seed_everything,
        write_jsonl,
    )
    from evaluation.subjective_rubrics import DEFAULT_SUBJECTIVE_DATASET_ORDER

from kg_prompting import build_kg_subjective_prompt
from kg_target_utils import (
    build_kg_cache_key,
    classify_kg_context_status,
    get_target_entity,
    load_kg_cache,
    save_kg_cache,
)
from neo4j_direct_retriever import close_all_drivers, retrieve_kg_context


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
        context_style: str = "relation_only",
        max_node_notes: int = 6,
        node_note_max_chars: int = 0,
    ) -> tuple[str, str]:
        cache_key = build_kg_cache_key(target_entity, question, context_style=context_style)
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
                context_style=context_style,
                max_node_notes=max_node_notes,
                node_note_max_chars=node_note_max_chars,
            )
        status = classify_kg_context_status(target_entity, kg_context)
        entry = {
            "target_entity": target_entity,
            "question": question,
            "kg_context": kg_context,
            "status": status,
            "context_style": context_style,
        }
        with self._lock:
            self._payload[cache_key] = entry
        return kg_context, status

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._payload)


@dataclass(frozen=True)
class KGSubjectiveQuestion:
    qid: str
    dataset: str
    type: str
    question: str
    gold_answer: str
    constraint_applied: str | None
    knowledge_domain: str | None
    target_entity: str


def detect_question_placeholder(question: str) -> str:
    for placeholder in ("[This Bird]", "[this bird]", "[the bird]", "[The Bird]"):
        if placeholder in question:
            return placeholder
    return "[This Bird]"


def sanitize_subjective_kg_context(kg_context: str, target_entity: str, question: str) -> str:
    text = str(kg_context or "")
    target = str(target_entity or "").strip()
    if not text or not target:
        return text

    placeholder = detect_question_placeholder(question)
    text = re.sub(re.escape(target), placeholder, text, flags=re.I)

    parts = target.split()
    if len(parts) >= 2 and parts[0][:1].isupper():
        genus = re.escape(parts[0])
        species = re.escape(parts[1])
        pattern = rf"\b{genus}\s+{species}(?:\s+[A-Za-z-]+)?\b"
        text = re.sub(pattern, placeholder, text, flags=re.I)
    return text


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run subjective answer generation with Neo4j KG-RAG.")
    parser.add_argument("--question-root", type=str, default="question")
    parser.add_argument("--out-dir", type=str, default="evaluation/results_subjective_kg_rag")
    parser.add_argument("--fewshot-root", type=str, default="evaluation/fewshot_examples")
    parser.add_argument("--models", nargs="*", default=None)
    parser.add_argument("--datasets", nargs="*", default=DEFAULT_SUBJECTIVE_DATASET_ORDER)
    parser.add_argument("--modes", nargs="*", default=list(SUPPORTED_PROMPT_MODES))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--answer-question-workers", type=int, default=None)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--print-every", type=int, default=20)
    parser.add_argument("--kg-uri", type=str, default="")
    parser.add_argument("--kg-user", type=str, default="")
    parser.add_argument("--kg-password", type=str, default="")
    parser.add_argument("--kg-limit", type=int, default=30)
    parser.add_argument("--kg-neighbor-limit", type=int, default=160)
    parser.add_argument("--kg-max-node-notes", type=int, default=6)
    parser.add_argument("--kg-node-note-max-chars", type=int, default=0)
    parser.add_argument("--kg-debug", action="store_true")
    parser.add_argument("--kg-cache-path", type=str, default=None)
    parser.add_argument("--include-types", nargs="*", default=None)
    parser.add_argument("--exclude-types", nargs="*", default=None)
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
    return parser.parse_args(argv)


def validate_modes(modes: list[str]) -> list[str]:
    normalized: list[str] = []
    for mode in modes:
        if mode not in SUPPORTED_PROMPT_MODES:
            raise SystemExit(f"Unsupported mode: {mode}. Supported: {', '.join(SUPPORTED_PROMPT_MODES)}")
        if mode not in normalized:
            normalized.append(mode)
    return normalized


def standardize_subjective_row_with_target(row: Dict[str, Any]) -> KGSubjectiveQuestion:
    return KGSubjectiveQuestion(
        qid=str(row.get("question_id", "")).strip(),
        dataset=str(row.get("dataset", "")).strip(),
        type=str(row.get("type", "")).strip(),
        question=str(row.get("question", "")).strip(),
        gold_answer=str(row.get("answer", "")).strip(),
        constraint_applied=(str(row.get("constraint_applied")).strip() if row.get("constraint_applied") is not None else None),
        knowledge_domain=(str(row.get("knowledge_domain")).strip() if row.get("knowledge_domain") is not None else None),
        target_entity=get_target_entity(row),
    )


def load_subjective_dataset_with_target(
    path: Path,
    limit: int = 0,
    include_types: set[str] | None = None,
    exclude_types: set[str] | None = None,
) -> list[KGSubjectiveQuestion]:
    rows = [standardize_subjective_row_with_target(row) for row in load_jsonl(path)]
    dataset_name = rows[0].dataset if rows else path.stem.replace("_questions", "")
    allowed_types = get_subjective_allowed_types(dataset_name)
    if allowed_types:
        rows = [row for row in rows if row.type in allowed_types]
    if include_types:
        rows = [row for row in rows if row.type in include_types]
    if exclude_types:
        rows = [row for row in rows if row.type not in exclude_types]
    rows.sort(key=lambda item: item.qid)
    if limit > 0:
        rows = rows[:limit]
    return rows


def build_kg_candidate_messages(
    item: KGSubjectiveQuestion,
    mode: str,
    prompt_body: str,
    fewshot_examples: list[Dict[str, Any]] | None = None,
) -> list[Dict[str, str]]:
    if mode not in SUPPORTED_PROMPT_MODES:
        raise KeyError(f"Unsupported prompting mode: {mode}")

    system_prompt = (
        "You are answering an ornithology benchmark question. "
        "Return strict JSON only with exactly one key: answer."
    )
    if mode == "cot":
        system_prompt += " Think silently if needed, but do not output reasoning."

    messages: list[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    if mode == "few_shot":
        if not fewshot_examples:
            raise ValueError(f"few_shot mode requires examples for dataset {item.dataset}")
        current_type = item.type.strip()
        same_type_examples = [example for example in fewshot_examples if str(example.get("type", "")).strip() == current_type]
        fallback_examples = [example for example in fewshot_examples if str(example.get("type", "")).strip() != current_type]
        selected_examples = same_type_examples[:2] or fallback_examples[:2]
        for example in selected_examples:
            example_question = str(example.get("question", "")).strip()
            example_answer = normalize_whitespace(str(example.get("answer", "")).strip())
            if not example_question or not example_answer:
                continue
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Dataset: {item.dataset}\n"
                        f"Question type: {example.get('type', current_type)}\n"
                        f"Question: {example_question}\n"
                        'Return only: {"answer": "..."}'
                    ),
                }
            )
            messages.append(
                {
                    "role": "assistant",
                    "content": json.dumps({"answer": example_answer}, ensure_ascii=False),
                }
            )

    user_parts = [
        "Task: answer the following bird-related subjective question.",
        f"Dataset: {item.dataset}",
        f"Question type: {item.type}",
    ]
    if item.knowledge_domain:
        user_parts.append(f"Knowledge domain: {item.knowledge_domain}")
    user_parts.extend(
        [
            prompt_body,
            "Do not reveal or guess any hidden target species name.",
            "Even if the graph context includes explicit names, refer to the target only with the placeholder already used in the question.",
            'Return only: {"answer": "..."}',
        ]
    )
    if mode == "cot":
        user_parts.append("You may reason privately, but the output must still contain only the final answer JSON.")
    messages.append({"role": "user", "content": "\n".join(user_parts)})
    return messages


def answer_one(
    client,
    spec,
    item: KGSubjectiveQuestion,
    mode: str,
    fewshot_examples: list[Dict[str, Any]] | None,
    temperature: float,
    max_tokens: int,
    retries: int,
    cache: KGContextCache,
    args: argparse.Namespace,
) -> Dict[str, Any]:
    print(f"[ANSWER-START] model={spec.alias} mode={mode} qid={item.qid}")
    prepared_question = prepare_candidate_question(item)
    kg_context, kg_context_status = cache.get_or_retrieve(
        target_entity=item.target_entity,
        question=prepared_question,
        limit=args.kg_limit,
        neighbor_limit=args.kg_neighbor_limit,
        debug=args.kg_debug,
        context_style="relation_plus_node_brief",
        max_node_notes=args.kg_max_node_notes,
        node_note_max_chars=args.kg_node_note_max_chars,
    )
    sanitized_kg_context = sanitize_subjective_kg_context(kg_context, item.target_entity, prepared_question)
    prompt_body = build_kg_subjective_prompt(prepared_question, sanitized_kg_context)
    result = {
        "question_id": item.qid,
        "answer": "",
        "target_entity": item.target_entity,
        "kg_context_status": kg_context_status,
        "kg_context": sanitized_kg_context,
        "error": "",
    }

    try:
        messages = build_kg_candidate_messages(
            item=item,
            mode=mode,
            prompt_body=prompt_body,
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
        answer = parse_candidate_response(raw_response)
        if not answer:
            raise ValueError(f"Empty answer after parsing for qid={item.qid}")
        result["answer"] = answer
        print(f"[ANSWER-DONE] model={spec.alias} mode={mode} qid={item.qid}")
    except Exception as exc:
        result["error"] = str(exc)
    return result


def run_mode_dataset(
    client,
    spec,
    dataset_name: str,
    items: list[KGSubjectiveQuestion],
    mode: str,
    out_path: Path,
    context_log_path: Path,
    fewshot_root: Path,
    resume: bool,
    answer_question_workers: int,
    temperature: float,
    max_tokens: int,
    retries: int,
    print_every: int,
    cache: KGContextCache,
    args: argparse.Namespace,
) -> None:
    ensure_dir(out_path.parent)
    ensure_dir(context_log_path.parent)
    existing_answers = load_existing_jsonl_map(out_path) if resume else {}
    existing_context_logs = load_existing_jsonl_map(context_log_path) if resume else {}

    completed_qids = {qid for qid, row in existing_answers.items() if has_nonempty_answer(row)}
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

    new_answers: Dict[str, Dict[str, Any]] = {}
    new_context_logs: Dict[str, Dict[str, Any]] = {}
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
                cache,
                args,
            ): item.qid
            for item in pending_items
        }
        for idx, future in enumerate(as_completed(futures), start=1):
            qid = futures[future]
            row = future.result()
            new_context_logs[qid] = {
                "question_id": row["question_id"],
                "target_entity": row["target_entity"],
                "kg_context_status": row["kg_context_status"],
                "kg_context": row["kg_context"],
            }
            if row.get("error"):
                print(f"[ANSWER-ERROR] model={spec.alias} mode={mode} qid={qid} err={row['error']}")
            elif row.get("answer"):
                new_answers[qid] = {"question_id": row["question_id"], "answer": row["answer"]}

            if idx % print_every == 0 or idx == len(futures):
                print(
                    f"[ANSWER-PROGRESS] model={spec.alias} dataset={dataset_name} "
                    f"mode={mode} completed={idx}/{len(futures)}"
                )

    merged_answers = existing_answers.copy()
    merged_answers.update(new_answers)
    ordered_answers = [
        {"question_id": item.qid, "answer": merged_answers[item.qid]["answer"]}
        for item in items
        if item.qid in merged_answers and has_nonempty_answer(merged_answers[item.qid])
    ]
    write_jsonl(out_path, ordered_answers)

    merged_context_logs = existing_context_logs.copy()
    merged_context_logs.update(new_context_logs)
    ordered_context_logs = [
        merged_context_logs[item.qid]
        for item in items
        if item.qid in merged_context_logs
    ]
    write_jsonl(context_log_path, ordered_context_logs)
    print(f"[ANSWER-WRITE] path={out_path} rows={len(ordered_answers)}")
    print(f"[CONTEXT-WRITE] path={context_log_path} rows={len(ordered_context_logs)}")


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    seed_everything()
    question_root = Path(args.question_root)
    out_dir = Path(args.out_dir)
    fewshot_root = Path(args.fewshot_root)
    modes = validate_modes(args.modes)
    answer_question_workers = resolve_worker_count(args.answer_question_workers, args.max_workers)

    if args.kg_uri:
        _sys.modules["neo4j_direct_retriever"].NEO4J_URI = args.kg_uri
    if args.kg_user:
        _sys.modules["neo4j_direct_retriever"].NEO4J_USERNAME = args.kg_user
    if args.kg_password:
        _sys.modules["neo4j_direct_retriever"].NEO4J_PASSWORD = args.kg_password

    specs = subjective_candidate_specs(args.models)
    if not specs:
        raise SystemExit("No enabled candidate models found. Check .env API keys or --models selection.")

    include_types = {value.strip() for value in (args.include_types or []) if str(value).strip()} or None
    exclude_types = {value.strip() for value in (args.exclude_types or []) if str(value).strip()} or None
    dataset_payloads: dict[str, list[KGSubjectiveQuestion]] = {}
    for dataset_name in args.datasets:
        path = discover_dataset_file(question_root, dataset_name)
        if not path:
            raise SystemExit(f"Dataset file not found for {dataset_name}")
        dataset_payloads[dataset_name] = load_subjective_dataset_with_target(
            path,
            limit=args.limit,
            include_types=include_types,
            exclude_types=exclude_types,
        )
        print(f"[LOAD] dataset={dataset_name} questions={len(dataset_payloads[dataset_name])} path={path}")

    cache = KGContextCache(load_kg_cache(args.kg_cache_path))
    try:
        for spec in specs:
            client = build_client(spec)
            for mode in modes:
                for dataset_name, items in dataset_payloads.items():
                    out_path = out_dir / "answers" / mode / spec.alias / f"{dataset_name}.jsonl"
                    context_log_path = out_dir / "context_logs" / mode / spec.alias / f"{dataset_name}.jsonl"
                    run_mode_dataset(
                        client=client,
                        spec=spec,
                        dataset_name=dataset_name,
                        items=items,
                        mode=mode,
                        out_path=out_path,
                        context_log_path=context_log_path,
                        fewshot_root=fewshot_root,
                        resume=args.resume,
                        answer_question_workers=answer_question_workers,
                        temperature=args.temperature,
                        max_tokens=args.max_tokens,
                        retries=args.retries,
                        print_every=args.print_every,
                        cache=cache,
                        args=args,
                    )
    finally:
        save_kg_cache(args.kg_cache_path, cache.snapshot())
        close_all_drivers()

    print(f"Done. KG-RAG subjective answers saved to {out_dir / 'answers'}")


if __name__ == "__main__":
    main()
