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
        has_nonempty_answer,
        load_existing_jsonl_map,
        load_fewshot_examples,
        load_jsonl,
        parse_candidate_response,
        prepare_candidate_question,
        resolve_worker_count,
        seed_everything,
        write_jsonl,
    )
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
        load_jsonl,
        parse_candidate_response,
        prepare_candidate_question,
        resolve_worker_count,
        seed_everything,
        write_jsonl,
    )

from remaining_bird_classify import build_taxon_to_feature_context, build_taxonomic_hierarchy_context
from remaining_bird_con import build_bird_con_context
from text_rag_runtime import TextRAGCorpus, TextRAGResultBundle, build_text_rag_bundle
from text_rag_target_utils import get_family_order, get_target_entity


SUPPORTED_DATASETS = ["Bird-Con", "Bird-Classify"]


@dataclass(frozen=True)
class RemainingSubjectiveQuestion:
    qid: str
    dataset: str
    type: str
    question: str
    gold_answer: str
    knowledge_domain: str = ""
    constraint_applied: str = ""
    target_entity: str = ""
    family: str = ""
    order: str = ""
    raw_row: dict[str, Any] | None = None


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run remaining-four task-adapted subjective KB/Text-RAG answer generation.")
    parser.add_argument("--question-root", type=str, default="question")
    parser.add_argument("--out-dir", type=str, default="evaluation/output/results_subjective_remaining_kb")
    parser.add_argument("--fewshot-root", type=str, default="evaluation/fewshot_examples")
    parser.add_argument("--models", nargs="*", default=None)
    parser.add_argument("--datasets", nargs="*", default=SUPPORTED_DATASETS)
    parser.add_argument("--modes", nargs="*", default=list(SUPPORTED_PROMPT_MODES))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--answer-question-workers", type=int, default=None)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--print-every", type=int, default=20)
    parser.add_argument("--species-chunks-jsonl", type=str, default="kg_v2/outputs/intermediate/species_chunks.jsonl")
    parser.add_argument("--family-chunks-jsonl", type=str, default="kg_v2/outputs/intermediate/family_chunks.jsonl")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--max-context-chars", type=int, default=9000)
    parser.add_argument("--include-types", nargs="*", default=None)
    parser.add_argument("--exclude-types", nargs="*", default=None)
    parser.add_argument("--only-question-ids", type=str, default="")
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args(argv)


def standardize_row(row: dict[str, Any]) -> RemainingSubjectiveQuestion:
    family, order = get_family_order(row)
    return RemainingSubjectiveQuestion(
        qid=str(row.get("question_id", "")).strip(),
        dataset=str(row.get("dataset", "")).strip(),
        type=str(row.get("type", "")).strip(),
        question=str(row.get("question", "")).strip(),
        gold_answer=str(row.get("answer", "")).strip(),
        knowledge_domain=str(row.get("knowledge_domain", "")).strip(),
        constraint_applied=str(row.get("constraint_applied", "")).strip(),
        target_entity=get_target_entity(row),
        family=family,
        order=order,
        raw_row=row,
    )


def load_dataset(
    path: Path,
    limit: int,
    include_types: set[str] | None,
    exclude_types: set[str] | None,
    only_question_ids: set[str] | None,
) -> list[RemainingSubjectiveQuestion]:
    rows = [standardize_row(row) for row in load_jsonl(path)]
    if include_types:
        rows = [row for row in rows if row.type in include_types]
    if exclude_types:
        rows = [row for row in rows if row.type not in exclude_types]
    if only_question_ids:
        rows = [row for row in rows if row.qid in only_question_ids]
    rows.sort(key=lambda row: row.qid)
    if limit > 0:
        rows = rows[:limit]
    return rows


def build_remaining_prompt(item: RemainingSubjectiveQuestion, question_for_model: str, bundle: TextRAGResultBundle) -> str:
    if not bundle.context:
        return question_for_model
    if item.dataset == "Bird-Con":
        instruction = (
            "[Conservation-focused BOW Evidence]\n"
            + bundle.context
            + "\n\nFor this Bird-Con question, answer the exact subtype:\n"
            + "- Status & Trend: status, trend, and uncertainty.\n"
            + "- Threat Analysis: main threats and mechanisms.\n"
            + "- Historical & Extinction: historical causes, dates or last records if available.\n"
            + "Do not invent unsupported conservation facts."
        )
        return question_for_model + "\n\n" + instruction
    if item.type == "Taxonomic Hierarchy":
        extra = (
            "[Bird-Classify Answer Requirements]\n"
            "- First state taxonomic placement.\n"
            "- Then use family-level systematic evidence.\n"
            "- Then mention family-level diagnostic or ecological traits only when grounded.\n"
            "- Do not answer with generic order-level traits only.\n\n"
            + bundle.context
            + "\n\nThis is a taxonomic hierarchy question.\n"
            "1. Taxonomic hierarchy: state the Order -> Family relationship clearly.\n"
            "2. Supporting systematic evidence: use SystematicasHistory when available.\n"
            "3. Family-level diagnostic or ecological traits: mention only evidence-grounded traits.\n"
            "Use the retrieved family-level evidence.\n"
            "The answer should not be a one-sentence placement only.\n"
            "Avoid generic order-level statements unless they are explicitly tied to the target family."
        )
        return question_for_model + "\n\n" + extra
    if item.type == "Taxon-to-Feature":
        extra = (
            "[Bird-Classify Answer Requirements]\n"
            "- First state taxonomic placement.\n"
            "- Then summarize family-specific defining traits.\n"
            "- Use Introduction, Systematics, Habitat, Diet, and Breeding evidence.\n"
            "- Do not answer with generic order-level traits only.\n\n"
            + bundle.context
            + "\n\nThe order-family relationship should be stated first, but the defining traits must be specific to the given family when family-level evidence is available. "
            "Do not replace family-specific traits with generic order-level traits.\n"
            "1. Taxonomic placement: state that family X belongs to order Y.\n"
            "2. Family-specific diagnostic traits: prioritize Introduction and Systematics for diagnostic features.\n"
            "3. Ecology and life-history traits: use GeneralHabitat, DietAndForaging, and Breeding if available.\n"
            "4. Grounding: do not invent unsupported traits; if evidence is limited, say so.\n"
            "Use the retrieved family-level evidence.\n"
            "The answer should not be a one-sentence placement only.\n"
            "Include at least 4 family-specific traits if evidence is available.\n"
            "Avoid generic statements like 'members of this order are diverse birds' unless tied to the target family."
        )
        return question_for_model + "\n\n" + extra
    return question_for_model + "\n\n" + bundle.context


def dispatch_context(corpus: TextRAGCorpus, item: RemainingSubjectiveQuestion, args: argparse.Namespace) -> tuple[TextRAGResultBundle, dict[str, Any]]:
    extras: dict[str, Any] = {}
    if item.dataset == "Bird-Con":
        bundle = build_bird_con_context(corpus, item, top_k=args.top_k, max_context_chars=args.max_context_chars)
        iucn_values = [row.get("iucn_status") for row in bundle.debug_rows if row.get("iucn_status")]
        extras["iucn_status_seen"] = sorted({value for value in iucn_values if value})
        return bundle, extras
    if item.dataset == "Bird-Classify":
        if item.type == "Taxon-to-Feature":
            return build_taxon_to_feature_context(corpus, item, top_k=args.top_k, max_context_chars=args.max_context_chars), extras
        if item.type == "Taxonomic Hierarchy":
            return build_taxonomic_hierarchy_context(corpus, item, top_k=args.top_k, max_context_chars=args.max_context_chars), extras
        if item.type == "Feature-to-Family":
            return TextRAGResultBundle("", [], "feature_to_family_structured_only", item.target_entity, "no_context", []), extras
        return build_text_rag_bundle(corpus, item, top_k=args.top_k, max_total_chars=args.max_context_chars, restrict_to_target=False), extras
    return build_text_rag_bundle(corpus, item, top_k=args.top_k, max_total_chars=args.max_context_chars, restrict_to_target=True), extras


def print_debug(item: RemainingSubjectiveQuestion, bundle: TextRAGResultBundle) -> None:
    print("[REMAINING-TEXT-RAG DEBUG]")
    print(f"qid={item.qid}")
    print(f"dataset={item.dataset}")
    print(f"type={item.type}")
    print(f"target_entity={item.target_entity}")
    print(f"retrieval_policy={bundle.retrieval_policy}")
    print(f"retrieved_context_status={bundle.status}")
    print(f"n_results={len(bundle.results)}")
    for row in bundle.debug_rows:
        print(f"  #{row.get('rank')} chunk_id={row.get('chunk_id')} score={row.get('score')}")
        print(f"     family={row.get('family', '')} order={row.get('order', '')}")
        print(f"     source_chapter={row.get('source_chapter', '')}")
        print(f"     source_chapter_raw={row.get('source_chapter_raw', '')}")
        print(f"     matched_on={';'.join(row.get('matched_on', []))}")


def answer_one(client, spec, item: RemainingSubjectiveQuestion, mode: str, fewshot_examples, temperature: float, max_tokens: int, retries: int, corpus: TextRAGCorpus, args: argparse.Namespace) -> Dict[str, Any]:
    print(f"[ANSWER-START] model={spec.alias} mode={mode} qid={item.qid}")
    question_for_model = prepare_candidate_question(item)
    bundle, extras = dispatch_context(corpus, item, args)
    if args.debug:
        print_debug(item, bundle)
    prompt = build_remaining_prompt(item, question_for_model, bundle)
    messages = build_candidate_messages(item=item, mode=mode, question_for_model=prompt, fewshot_examples=fewshot_examples)
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
    row = {
        "question_id": item.qid,
        "answer": answer,
        "type": item.type,
        "target_entity": item.target_entity,
        "retrieval_policy": bundle.retrieval_policy,
        "retrieved_context_status": bundle.status,
        "retrieved_context": bundle.context,
        "retrieved_chunk_ids": [result.chunk.chunk_id for result in bundle.results],
        "retrieved_debug": bundle.debug_rows,
    }
    row.update(extras)
    print(f"[ANSWER-DONE] model={spec.alias} mode={mode} qid={item.qid}")
    return row


def run_mode_dataset(client, spec, dataset_name: str, items: list[RemainingSubjectiveQuestion], mode: str, out_path: Path, fewshot_root: Path, resume: bool, answer_question_workers: int, temperature: float, max_tokens: int, retries: int, print_every: int, corpus: TextRAGCorpus, args: argparse.Namespace) -> None:
    ensure_dir(out_path.parent)
    existing = load_existing_jsonl_map(out_path) if resume else {}
    completed_qids = {qid for qid, row in existing.items() if has_nonempty_answer(row)}
    pending_items = [item for item in items if item.qid not in completed_qids]
    fewshot_examples = load_fewshot_examples(fewshot_root, dataset_name) if mode == "few_shot" else None

    print(
        f"[ANSWER] model={spec.alias} dataset={dataset_name} mode={mode} "
        f"total={len(items)} pending={len(pending_items)} workers={answer_question_workers}"
    )
    if not pending_items and resume:
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
                print(f"[ANSWER-ERROR] model={spec.alias} dataset={dataset_name} mode={mode} qid={qid} err={exc}")
            else:
                new_rows[qid] = row
            if idx % print_every == 0 or idx == len(futures):
                print(f"[ANSWER-PROGRESS] model={spec.alias} dataset={dataset_name} mode={mode} completed={idx}/{len(futures)}")

    merged = existing.copy()
    merged.update(new_rows)
    ordered = [merged[item.qid] for item in items if item.qid in merged and has_nonempty_answer(merged[item.qid])]
    write_jsonl(out_path, ordered)
    print(f"[ANSWER-WRITE] path={out_path} rows={len(ordered)}")


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    seed_everything()
    question_root = Path(args.question_root)
    out_dir = Path(args.out_dir)
    fewshot_root = Path(args.fewshot_root)
    modes = []
    for mode in args.modes:
        if mode not in SUPPORTED_PROMPT_MODES:
            raise SystemExit(f"Unsupported mode: {mode}")
        if mode not in modes:
            modes.append(mode)
    answer_question_workers = resolve_worker_count(args.answer_question_workers, args.max_workers)

    dataset_payloads: dict[str, list[RemainingSubjectiveQuestion]] = {}
    include_types = set(args.include_types or [])
    exclude_types = set(args.exclude_types or [])
    only_question_ids = {qid.strip() for qid in args.only_question_ids.split(",") if qid.strip()}
    for dataset_name in args.datasets:
        if dataset_name not in SUPPORTED_DATASETS:
            raise SystemExit(f"Unsupported dataset: {dataset_name}")
        path = discover_dataset_file(question_root, dataset_name)
        if not path:
            raise SystemExit(f"Dataset file not found for {dataset_name}")
        dataset_payloads[dataset_name] = load_dataset(path, args.limit, include_types or None, exclude_types or None, only_question_ids or None)
        print(f"[LOAD] dataset={dataset_name} questions={len(dataset_payloads[dataset_name])} path={path}")

    corpus = TextRAGCorpus.from_paths(
        species_chunks_jsonl=args.species_chunks_jsonl,
        family_chunks_jsonl=args.family_chunks_jsonl,
        top_k=args.top_k,
        max_chars_per_chunk=1400,
        default_restrict_to_target=True,
    )
    print(f"[TEXT-RAG-REMAINING] loaded chunks={len(corpus.chunks)}")

    specs = subjective_candidate_specs(args.models)
    if not specs:
        raise SystemExit("No enabled candidate models found. Check .env API keys or --models selection.")

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


if __name__ == "__main__":
    main()
