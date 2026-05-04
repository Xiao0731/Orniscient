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
from dataclasses import dataclass
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
        build_candidate_messages,
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

from text_rag_runtime import TextRAGCorpus, TextRAGResultBundle, build_text_rag_bundle
from text_rag_target_utils import get_family_order, get_target_entity


@dataclass(frozen=True)
class TextRAGSubjectiveQuestion:
    qid: str
    dataset: str
    type: str
    question: str
    gold_answer: str
    constraint_applied: str = ""
    knowledge_domain: str = ""
    target_entity: str = ""
    family: str = ""
    order: str = ""
    raw_row: dict[str, Any] | None = None


def standardize_subjective_row_with_target(row: dict[str, Any]) -> TextRAGSubjectiveQuestion:
    family, order = get_family_order(row)
    return TextRAGSubjectiveQuestion(
        qid=str(row.get("question_id", "")).strip(),
        dataset=str(row.get("dataset", "")).strip(),
        type=str(row.get("type", "")).strip(),
        question=str(row.get("question", "")).strip(),
        gold_answer=str(row.get("answer", "")).strip(),
        constraint_applied=(str(row.get("constraint_applied")).strip() if row.get("constraint_applied") is not None else ""),
        knowledge_domain=(str(row.get("knowledge_domain")).strip() if row.get("knowledge_domain") is not None else ""),
        target_entity=get_target_entity(row),
        family=family,
        order=order,
        raw_row=row,
    )


def load_subjective_dataset_with_target(
    path: Path,
    limit: int = 0,
    include_types: set[str] | None = None,
    exclude_types: set[str] | None = None,
) -> list[TextRAGSubjectiveQuestion]:
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


def build_subjective_text_rag_prompt(question_for_model: str, rag_block: str) -> str:
    if not rag_block:
        return question_for_model
    return (
        question_for_model
        + "\n\nExternal evidence from BOW text chunks is provided below.\n"
        + "These passages are retrieved using the target entity metadata and are intended as open-book reference material.\n"
        + "Use them only when they directly help answer the question.\n"
        + "If the passages are incomplete, irrelevant, or insufficient, rely on the question and answer cautiously.\n"
        + "Do not let the evidence distract you from the exact task.\n\n"
        + "[Text-RAG Evidence]\n"
        + rag_block
    )


def print_rag_debug(item: TextRAGSubjectiveQuestion, bundle: TextRAGResultBundle) -> None:
    print("[TEXT-RAG DEBUG]")
    print(f"qid={item.qid}")
    print(f"dataset={item.dataset}")
    print(f"target_entity={bundle.target_entity or item.target_entity}")
    print(f"retrieval_policy={bundle.retrieval_policy}")
    print(f"retrieved_context_status={bundle.status}")
    print(f"n_results={len(bundle.results)}")
    for row in bundle.debug_rows:
        matched_on = ";".join(str(x) for x in row.get("matched_on", [])) or "none"
        print(f"  #{row.get('rank')} chunk_id={row.get('chunk_id')}")
        print(f"     common_name={row.get('common_name', '')}")
        print(f"     species={row.get('species', '')}")
        print(f"     family={row.get('family', '')}")
        print(f"     order={row.get('order', '')}")
        print(f"     source_chapter={row.get('source_chapter', '')}")
        print(f"     source_chapter_raw={row.get('source_chapter_raw', '')}")
        print(f"     source_subchapter={row.get('source_subchapter', '')}")
        print(f"     matched_on={matched_on}")
        print(f"     score={row.get('score')}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run subjective answer generation with Text-RAG baseline.")
    parser.add_argument("--question-root", type=str, default="question")
    parser.add_argument("--out-dir", type=str, default="evaluation/results_subjective_text_rag")
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

    parser.add_argument("--bow-glob", type=str, default="")
    parser.add_argument("--order-xlsx", type=str, default="")
    parser.add_argument("--cache-jsonl", type=str, default="evaluation/cache/text_rag_chunks.jsonl")
    parser.add_argument("--species-chunks-jsonl", type=str, default="kg_v2/outputs/intermediate/species_chunks.jsonl")
    parser.add_argument("--family-chunks-jsonl", type=str, default="kg_v2/outputs/intermediate/family_chunks.jsonl")
    parser.add_argument("--chunk-chars", type=int, default=1200)
    parser.add_argument("--chunk-overlap", type=int, default=200)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--max-context-chars", type=int, default=9000)
    parser.add_argument("--no-restrict-to-target", action="store_true")
    parser.add_argument("--rag-debug", action="store_true")
    parser.add_argument("--include-types", nargs="*", default=None)
    parser.add_argument("--exclude-types", nargs="*", default=None)
    return parser.parse_args(argv)


def validate_modes(modes: list[str]) -> list[str]:
    normalized: list[str] = []
    for mode in modes:
        if mode not in SUPPORTED_PROMPT_MODES:
            raise SystemExit(f"Unsupported mode: {mode}. Supported: {', '.join(SUPPORTED_PROMPT_MODES)}")
        if mode not in normalized:
            normalized.append(mode)
    return normalized


def answer_one(client, spec, item: TextRAGSubjectiveQuestion, mode: str, fewshot_examples: list[Dict[str, Any]] | None, temperature: float, max_tokens: int, retries: int, corpus: TextRAGCorpus, args: argparse.Namespace) -> Dict[str, Any]:
    print(f"[ANSWER-START] model={spec.alias} mode={mode} qid={item.qid}")
    question_for_model = prepare_candidate_question(item)
    bundle = build_text_rag_bundle(
        corpus,
        item,
        top_k=args.top_k,
        max_total_chars=args.max_context_chars,
        restrict_to_target=not args.no_restrict_to_target,
    )
    if args.rag_debug:
        print_rag_debug(item, bundle)
    question_for_model = build_subjective_text_rag_prompt(question_for_model, bundle.context)
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
    answer = parse_candidate_response(raw_response)
    if not answer:
        raise ValueError(f"Empty answer after parsing for qid={item.qid}")
    print(f"[ANSWER-DONE] model={spec.alias} mode={mode} qid={item.qid}")
    return {
        "question_id": item.qid,
        "answer": answer,
        "target_entity": bundle.target_entity or item.target_entity,
        "retrieval_policy": bundle.retrieval_policy,
        "retrieved_context_status": bundle.status,
        "retrieved_chunk_ids": [r.chunk.chunk_id for r in bundle.results],
        "retrieved_context": bundle.context,
        "retrieved_debug": bundle.debug_rows,
    }


def run_mode_dataset(client, spec, dataset_name: str, items, mode: str, out_path: Path, fewshot_root: Path, resume: bool, answer_question_workers: int, temperature: float, max_tokens: int, retries: int, print_every: int, corpus: TextRAGCorpus, args: argparse.Namespace) -> None:
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

    new_rows: Dict[str, Dict[str, Any]] = {}
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
                corpus,
                args,
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
    ordered_rows = [merged[item.qid] for item in items if item.qid in merged and has_nonempty_answer(merged[item.qid])]
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

    dataset_payloads = {}
    for dataset_name in args.datasets:
        path = discover_dataset_file(question_root, dataset_name)
        if not path:
            raise SystemExit(f"Dataset file not found for {dataset_name}")
        include_types = set(args.include_types or [])
        exclude_types = set(args.exclude_types or [])
        dataset_payloads[dataset_name] = load_subjective_dataset_with_target(
            path,
            limit=args.limit,
            include_types=include_types or None,
            exclude_types=exclude_types or None,
        )
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
                    corpus=corpus,
                    args=args,
                )

    print(f"Done. Text-RAG subjective answers saved to {out_dir / 'answers'}")


if __name__ == "__main__":
    main()
