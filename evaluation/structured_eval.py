from __future__ import annotations

import argparse
import csv
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional, Sequence

try:
    from model_registry import enabled_specs, resolve_max_workers, resolve_objective_temperature
    from subjective_common import (
        KIMI_MODEL_NAME,
        build_client,
        discover_dataset_file,
        ensure_dir,
        extract_json_object,
        load_existing_jsonl_map,
        load_jsonl,
        write_jsonl,
    )
except ModuleNotFoundError:
    from evaluation.model_registry import enabled_specs, resolve_max_workers, resolve_objective_temperature
    from evaluation.subjective_common import (
        KIMI_MODEL_NAME,
        build_client,
        discover_dataset_file,
        ensure_dir,
        extract_json_object,
        load_existing_jsonl_map,
        load_jsonl,
        write_jsonl,
    )

STRUCTURED_DATASET_ORDER = [
    "List-Global",
    "Bird-ID",
    "Bird-Classify__Feature-to-Family",
]

RETRYABLE_ERROR_PATTERNS = (
    "429",
    "rate limit",
    "too many requests",
    "temporarily unavailable",
    "service unavailable",
    "timeout",
    "timed out",
    "connection reset",
)


@dataclass(frozen=True)
class StructuredDatasetConfig:
    dataset_key: str
    source_dataset: str
    type_filter: Optional[set[str]]
    prompt_builder: Callable[[Dict[str, Any]], str]
    answer_parser: Callable[[str], Dict[str, Any]]
    answer_is_nonempty: Callable[[Dict[str, Any]], bool]
    score_builder: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]
    score_is_nonempty: Callable[[Dict[str, Any]], bool]
    summary_builder: Callable[[list[Dict[str, Any]], str], Dict[str, Any]]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run minimal structured evaluation for the remaining four datasets.")
    parser.add_argument("--question-root", type=str, default="question")
    parser.add_argument("--out-dir", type=str, default="evaluation/results_structured")
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
    return parser.parse_args(argv)


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_name(text: str) -> str:
    text = normalize_space(text).lower()
    text = re.sub(r"^[\-\*\u2022]+", "", text).strip()
    text = re.sub(r"^[0-9]+[\.\)\-:]\s*", "", text)
    text = re.sub(r"[\"'`“”‘’]+", "", text)
    text = re.sub(r"[\(\)\[\]\{\}]+", " ", text)
    text = re.sub(r"[^a-z0-9\s\-]", " ", text)
    return normalize_space(text)


def normalize_taxon_label(text: str) -> str:
    return normalize_space(re.sub(r"[^A-Za-z0-9\- ]", " ", text or "")).lower()


def round_metric(value: float) -> float:
    return round(value, 4)


def format_percent(value: float | None) -> str:
    return "" if value is None else f"{value * 100:.2f}"


def write_csv(path: Path, rows: list[Dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def is_retryable_error(exc: Exception) -> bool:
    lowered = str(exc).lower()
    return any(pattern in lowered for pattern in RETRYABLE_ERROR_PATTERNS)


def build_request_kwargs(spec, temperature: float | None, max_tokens: int) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {
        "model": spec.model,
        "timeout": 60.0,
    }
    effective_temperature = temperature
    if spec.model == KIMI_MODEL_NAME and effective_temperature is None:
        effective_temperature = 1.0
    if spec.model == KIMI_MODEL_NAME and effective_temperature != 1.0:
        effective_temperature = 1.0
    if spec.supports_temperature and effective_temperature is not None:
        kwargs["temperature"] = effective_temperature
    if spec.supports_max_tokens:
        kwargs["max_tokens"] = max_tokens
    return kwargs


def call_model(
    client,
    spec,
    messages: list[Dict[str, str]],
    temperature: float | None,
    max_tokens: int,
    retries: int,
) -> str:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            kwargs = build_request_kwargs(spec, temperature, max_tokens)
            kwargs["messages"] = messages
            response = client.chat.completions.create(**kwargs)
            return response.choices[0].message.content or ""
        except Exception as exc:
            last_error = exc
            print(f"[STRUCTURED-CALL-ERROR] model={spec.alias} attempt={attempt + 1}/{retries + 1} err={exc}")
            if attempt >= retries or not is_retryable_error(exc):
                raise
            time.sleep(min(8.0, 1.5 * (attempt + 1)))
    raise RuntimeError(f"Model call failed for {spec.alias}: {last_error}") from last_error


def parse_json_payload(raw_response: str) -> Any:
    text = (raw_response or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass

    fenced = re.search(r"```(?:json)?\s*(\[.*?\]|\{.*?\})\s*```", text, flags=re.S | re.I)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except Exception:
            pass

    extracted = extract_json_object(text)
    if extracted:
        try:
            return json.loads(extracted)
        except Exception:
            pass

    array_match = re.search(r"(\[.*\])", text, flags=re.S)
    if array_match:
        try:
            return json.loads(array_match.group(1))
        except Exception:
            pass
    return None


def dedupe_preserve_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        normalized = normalize_space(item)
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(normalized)
    return output


def parse_list_items(raw_response: str, *, split_commas: bool) -> list[str]:
    payload = parse_json_payload(raw_response)
    if isinstance(payload, dict):
        answer = payload.get("answer")
        if isinstance(answer, list):
            return dedupe_preserve_order(str(item).strip() for item in answer)
        if isinstance(answer, str):
            raw_response = answer
    elif isinstance(payload, list):
        return dedupe_preserve_order(str(item).strip() for item in payload)

    text = normalize_space(raw_response)
    text = re.sub(r"^(?:answer|final answer)\s*[:：]\s*", "", text, flags=re.I)
    if not text:
        return []

    if re.search(r"\n", raw_response):
        candidates = [line.strip() for line in raw_response.splitlines() if line.strip()]
    elif re.search(r"\b[1-9][\.\)]\s*", text):
        candidates = [part.strip() for part in re.split(r"(?:^|\s)(?:[1-9][\.\)])\s*", text) if part.strip()]
    elif ";" in text or "|" in text or "/" in text:
        candidates = [part.strip() for part in re.split(r"[;|/]+", text) if part.strip()]
    elif split_commas and "," in text:
        candidates = [part.strip() for part in text.split(",") if part.strip()]
    else:
        candidates = [text]

    cleaned: list[str] = []
    for candidate in candidates:
        item = re.sub(r"^[\-\*\u2022]+", "", candidate).strip()
        item = re.sub(r"^[0-9]+[\.\)\-:]\s*", "", item)
        item = normalize_space(item)
        if item:
            cleaned.append(item)
    return dedupe_preserve_order(cleaned)


def extract_scientific_names(text: str) -> set[str]:
    matches = re.findall(r"\b([A-Z][a-z]+(?:-[a-z]+)?\s+[a-z][a-z\-]+)\b", text or "")
    return {normalize_name(match) for match in matches if normalize_name(match)}


def build_alias_variants(value: Any) -> set[str]:
    variants: set[str] = set()
    if value is None:
        return variants
    if isinstance(value, list):
        for item in value:
            variants.update(build_alias_variants(item))
        return variants

    raw = str(value).strip()
    if not raw:
        return variants

    normalized_full = normalize_name(raw)
    if normalized_full:
        variants.add(normalized_full)

    scientific_names = extract_scientific_names(raw)
    variants.update(scientific_names)

    segments = [segment.strip() for segment in re.split(r"[;/|]", raw) if segment.strip()]
    for segment in segments:
        segment_normalized = normalize_name(segment)
        if segment_normalized:
            variants.add(segment_normalized)

        scientific_in_segment = extract_scientific_names(segment)
        variants.update(scientific_in_segment)
        common_only = segment
        for scientific in scientific_in_segment:
            common_only = re.sub(r"\b[A-Z][a-z]+(?:-[a-z]+)?\s+[a-z][a-z\-]+\b", "", common_only)
        if "," in segment:
            for comma_part in segment.split(","):
                part_normalized = normalize_name(comma_part)
                if part_normalized:
                    variants.add(part_normalized)
        common_normalized = normalize_name(common_only)
        if common_normalized:
            variants.add(common_normalized)
    return {variant for variant in variants if variant}


def build_structured_messages(prompt: str) -> list[Dict[str, str]]:
    return [
        {
            "role": "system",
            "content": "You are a precise ornithology evaluation assistant. Return strict JSON only and no explanation.",
        },
        {"role": "user", "content": prompt},
    ]


def build_list_global_prompt(item: Dict[str, Any]) -> str:
    return "\n".join(
        [
            "Answer the following bird retrieval query.",
            "Return strict JSON only.",
            'Use this schema: {"answer": ["species_a", "species_b"]}',
            "Return only species names, preferably canonical scientific species names.",
            "Do not include explanations or extra keys.",
            "",
            f"Question: {item.get('question', '')}",
        ]
    )


def build_bird_id_prompt(item: Dict[str, Any]) -> str:
    clue_text = str(item.get("clue_text", "")).strip()
    prompt_lines = [
        "Identify the most likely bird species.",
        "Return strict JSON only.",
        'Use this schema: {"answer": ["guess1", "guess2", "guess3", "guess4", "guess5"]}',
        "Provide at most 5 guesses, ordered from highest confidence to lowest.",
        "Do not include explanations or extra keys.",
        "",
        f"Question: {item.get('question', '')}",
    ]
    if clue_text:
        prompt_lines.extend(["", f"Clue text: {clue_text}"])
    return "\n".join(prompt_lines)


def build_feature_to_family_prompt(item: Dict[str, Any]) -> str:
    return "\n".join(
        [
            "Identify the avian order and family described below.",
            "Return strict JSON only.",
            'Use this schema: {"order": "...", "family": "..."}',
            "Do not include explanations or extra keys.",
            "",
            f"Question: {item.get('question', '')}",
        ]
    )


def parse_list_global_answer(raw_response: str) -> Dict[str, Any]:
    return {"answer": parse_list_items(raw_response, split_commas=True)}


def parse_bird_id_answer(raw_response: str) -> Dict[str, Any]:
    payload = parse_json_payload(raw_response)
    if isinstance(payload, dict) and isinstance(payload.get("answer"), list):
        guesses = [normalize_space(str(item)) for item in payload["answer"]]
    else:
        guesses = parse_list_items(raw_response, split_commas=False)
        if len(guesses) == 1 and guesses[0].count(",") >= 2:
            guesses = [part.strip() for part in guesses[0].split(",") if part.strip()]
    guesses = dedupe_preserve_order(guesses)[:5]
    return {"answer": guesses}


def parse_feature_to_family_answer(raw_response: str) -> Dict[str, Any]:
    payload = parse_json_payload(raw_response)
    order = ""
    family = ""
    if isinstance(payload, dict):
        if "order" in payload:
            order = normalize_space(str(payload.get("order", "")))
        if "family" in payload:
            family = normalize_space(str(payload.get("family", "")))
        if (not order or not family) and "answer" in payload:
            raw_response = str(payload["answer"])

    if not order:
        match = re.search(r"order\s*[:：]\s*([A-Za-z][A-Za-z\-\s]+?)(?:\||,|\n|family|$)", raw_response, flags=re.I)
        if match:
            order = normalize_space(match.group(1))
    if not family:
        match = re.search(r"family\s*[:：]\s*([A-Za-z][A-Za-z\-\s]+?)(?:\||,|\n|$)", raw_response, flags=re.I)
        if match:
            family = normalize_space(match.group(1))

    if (not order or not family) and "|" in raw_response:
        parts = [normalize_space(part) for part in raw_response.split("|") if normalize_space(part)]
        for part in parts:
            if not order and not re.search(r"family\s*[:：]", part, flags=re.I):
                maybe = re.sub(r"^order\s*[:：]\s*", "", part, flags=re.I)
                if maybe:
                    order = order or normalize_space(maybe)
            if not family and not re.search(r"order\s*[:：]", part, flags=re.I):
                maybe = re.sub(r"^family\s*[:：]\s*", "", part, flags=re.I)
                if maybe:
                    family = family or normalize_space(maybe)

    return {"order": order, "family": family}


def has_nonempty_list_answer(row: Dict[str, Any]) -> bool:
    answer = row.get("answer")
    return isinstance(answer, list) and len(answer) > 0


def has_nonempty_feature_answer(row: Dict[str, Any]) -> bool:
    return bool(str(row.get("order", "")).strip()) and bool(str(row.get("family", "")).strip())


def score_list_global(item: Dict[str, Any], answer_row: Dict[str, Any]) -> Dict[str, Any]:
    predicted = [normalize_name(entry) for entry in answer_row.get("answer", []) if normalize_name(entry)]
    gold_raw = item.get("answer", []) or []
    gold = [normalize_name(entry) for entry in (gold_raw if isinstance(gold_raw, list) else [gold_raw]) if normalize_name(str(entry))]

    pred_set = set(predicted)
    gold_set = set(gold)
    hits = len(pred_set & gold_set)
    precision = hits / len(pred_set) if pred_set else 0.0
    recall = hits / len(gold_set) if gold_set else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall > 0 else 0.0
    exact_set_match = int(pred_set == gold_set)
    return {
        "question_id": str(item["question_id"]),
        "precision": round_metric(precision),
        "recall": round_metric(recall),
        "f1": round_metric(f1),
        "exact_set_match": exact_set_match,
    }


def score_bird_id(item: Dict[str, Any], answer_row: Dict[str, Any]) -> Dict[str, Any]:
    guesses = [str(guess).strip() for guess in answer_row.get("answer", []) if str(guess).strip()]
    gold_aliases = set()
    gold_aliases.update(build_alias_variants(item.get("answer")))
    gold_aliases.update(build_alias_variants(item.get("target_entity")))

    weights = [1.0, 0.8, 0.6, 0.4, 0.2]
    weighted_top5_score = 0.0
    top1_hit = 0
    top5_hit = 0

    for idx, guess in enumerate(guesses[:5]):
        guess_aliases = build_alias_variants(guess)
        matched = bool(guess_aliases & gold_aliases)
        if matched:
            if idx == 0:
                top1_hit = 1
            top5_hit = 1
            weighted_top5_score = weights[idx]
            break

    return {
        "question_id": str(item["question_id"]),
        "top1_hit": top1_hit,
        "top5_hit": top5_hit,
        "weighted_top5_score": round_metric(weighted_top5_score),
    }


def score_feature_to_family(item: Dict[str, Any], answer_row: Dict[str, Any]) -> Dict[str, Any]:
    pred_order = normalize_taxon_label(str(answer_row.get("order", "")))
    pred_family = normalize_taxon_label(str(answer_row.get("family", "")))
    gold_order = normalize_taxon_label(str(item.get("order", "")))
    gold_family = normalize_taxon_label(str(item.get("family", "")))
    order_correct = int(pred_order == gold_order and gold_order != "")
    family_correct = int(pred_family == gold_family and gold_family != "")
    hierarchical_score = 1.0 if order_correct and family_correct else (0.5 if order_correct else 0.0)
    return {
        "question_id": str(item["question_id"]),
        "order_correct": order_correct,
        "family_correct": family_correct,
        "hierarchical_score": round_metric(hierarchical_score),
    }


def has_list_global_score(row: Dict[str, Any]) -> bool:
    return row.get("f1") is not None


def has_bird_id_score(row: Dict[str, Any]) -> bool:
    return row.get("weighted_top5_score") is not None


def has_feature_score(row: Dict[str, Any]) -> bool:
    return row.get("hierarchical_score") is not None


def summarize_list_global(rows: list[Dict[str, Any]], dataset_key: str) -> Dict[str, Any]:
    n_total = len(rows)
    avg_precision = sum(float(row["precision"]) for row in rows) / n_total if n_total else 0.0
    avg_recall = sum(float(row["recall"]) for row in rows) / n_total if n_total else 0.0
    avg_f1 = sum(float(row["f1"]) for row in rows) / n_total if n_total else 0.0
    set_em = sum(int(row["exact_set_match"]) for row in rows) / n_total if n_total else 0.0
    return {
        "dataset": dataset_key,
        "n_total": n_total,
        "avg_precision": format_percent(avg_precision),
        "avg_recall": format_percent(avg_recall),
        "avg_f1": format_percent(avg_f1),
        "set_em": format_percent(set_em),
        "top1_accuracy": "",
        "top5_hit_rate": "",
        "weighted_top5_accuracy": "",
        "order_accuracy": "",
        "family_accuracy": "",
        "hierarchical_accuracy": "",
    }


def summarize_bird_id(rows: list[Dict[str, Any]], dataset_key: str) -> Dict[str, Any]:
    n_total = len(rows)
    top1 = sum(int(row["top1_hit"]) for row in rows) / n_total if n_total else 0.0
    top5 = sum(int(row["top5_hit"]) for row in rows) / n_total if n_total else 0.0
    weighted = sum(float(row["weighted_top5_score"]) for row in rows) / n_total if n_total else 0.0
    return {
        "dataset": dataset_key,
        "n_total": n_total,
        "avg_precision": "",
        "avg_recall": "",
        "avg_f1": "",
        "set_em": "",
        "top1_accuracy": format_percent(top1),
        "top5_hit_rate": format_percent(top5),
        "weighted_top5_accuracy": format_percent(weighted),
        "order_accuracy": "",
        "family_accuracy": "",
        "hierarchical_accuracy": "",
    }


def summarize_feature_to_family(rows: list[Dict[str, Any]], dataset_key: str) -> Dict[str, Any]:
    n_total = len(rows)
    order_accuracy = sum(int(row["order_correct"]) for row in rows) / n_total if n_total else 0.0
    family_accuracy = sum(int(row["family_correct"]) for row in rows) / n_total if n_total else 0.0
    hierarchical_accuracy = sum(float(row["hierarchical_score"]) for row in rows) / n_total if n_total else 0.0
    return {
        "dataset": dataset_key,
        "n_total": n_total,
        "avg_precision": "",
        "avg_recall": "",
        "avg_f1": "",
        "set_em": "",
        "top1_accuracy": "",
        "top5_hit_rate": "",
        "weighted_top5_accuracy": "",
        "order_accuracy": format_percent(order_accuracy),
        "family_accuracy": format_percent(family_accuracy),
        "hierarchical_accuracy": format_percent(hierarchical_accuracy),
    }


DATASET_CONFIGS: Dict[str, StructuredDatasetConfig] = {
    "List-Global": StructuredDatasetConfig(
        dataset_key="List-Global",
        source_dataset="List-Global",
        type_filter=None,
        prompt_builder=build_list_global_prompt,
        answer_parser=parse_list_global_answer,
        answer_is_nonempty=has_nonempty_list_answer,
        score_builder=score_list_global,
        score_is_nonempty=has_list_global_score,
        summary_builder=summarize_list_global,
    ),
    "Bird-ID": StructuredDatasetConfig(
        dataset_key="Bird-ID",
        source_dataset="Bird-ID",
        type_filter=None,
        prompt_builder=build_bird_id_prompt,
        answer_parser=parse_bird_id_answer,
        answer_is_nonempty=has_nonempty_list_answer,
        score_builder=score_bird_id,
        score_is_nonempty=has_bird_id_score,
        summary_builder=summarize_bird_id,
    ),
    "Bird-Classify__Feature-to-Family": StructuredDatasetConfig(
        dataset_key="Bird-Classify__Feature-to-Family",
        source_dataset="Bird-Classify",
        type_filter={"Feature-to-Family"},
        prompt_builder=build_feature_to_family_prompt,
        answer_parser=parse_feature_to_family_answer,
        answer_is_nonempty=has_nonempty_feature_answer,
        score_builder=score_feature_to_family,
        score_is_nonempty=has_feature_score,
        summary_builder=summarize_feature_to_family,
    ),
}


def load_structured_items(question_root: Path, config: StructuredDatasetConfig, limit: int) -> list[Dict[str, Any]]:
    path = discover_dataset_file(question_root, config.source_dataset)
    if not path:
        raise FileNotFoundError(f"Dataset file not found for {config.source_dataset}")
    rows = load_jsonl(path)
    if config.type_filter:
        rows = [row for row in rows if str(row.get("type", "")).strip() in config.type_filter]
    rows.sort(key=lambda row: str(row.get("question_id", "")).strip())
    if limit > 0:
        rows = rows[:limit]
    print(f"[LOAD] dataset={config.dataset_key} questions={len(rows)} path={path}")
    return rows


def answer_one_item(
    client,
    spec,
    item: Dict[str, Any],
    config: StructuredDatasetConfig,
    temperature: float | None,
    max_tokens: int,
    retries: int,
) -> Dict[str, Any]:
    qid = str(item["question_id"])
    print(f"[STRUCTURED-ANSWER-START] model={spec.alias} dataset={config.dataset_key} qid={qid}")
    raw_response = call_model(
        client=client,
        spec=spec,
        messages=build_structured_messages(config.prompt_builder(item)),
        temperature=temperature,
        max_tokens=max_tokens,
        retries=retries,
    )
    parsed_answer = config.answer_parser(raw_response)
    if not config.answer_is_nonempty(parsed_answer):
        raise ValueError(f"Parsed empty answer for {config.dataset_key} qid={qid}")
    answer_row = {"question_id": qid, **parsed_answer}
    print(f"[STRUCTURED-ANSWER-DONE] model={spec.alias} dataset={config.dataset_key} qid={qid}")
    return answer_row


def run_answer_stage(
    client,
    spec,
    items: list[Dict[str, Any]],
    config: StructuredDatasetConfig,
    answers_path: Path,
    answer_question_workers: int,
    temperature: float | None,
    max_tokens: int,
    retries: int,
    resume: bool,
    print_every: int,
) -> list[Dict[str, Any]]:
    ensure_dir(answers_path.parent)
    existing = load_existing_jsonl_map(answers_path) if resume else {}
    completed_qids = {qid for qid, row in existing.items() if config.answer_is_nonempty(row)}
    pending_items = [item for item in items if str(item["question_id"]) not in completed_qids]

    print(
        f"[STRUCTURED-ANSWER] model={spec.alias} dataset={config.dataset_key} "
        f"total={len(items)} pending={len(pending_items)} workers={answer_question_workers}"
    )
    if pending_items:
        new_rows: Dict[str, Dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=answer_question_workers) as executor:
            futures = {
                executor.submit(
                    answer_one_item,
                    client,
                    spec,
                    item,
                    config,
                    temperature,
                    max_tokens,
                    retries,
                ): str(item["question_id"])
                for item in pending_items
            }
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
        existing.update(new_rows)

    ordered_rows = [existing[str(item["question_id"])] for item in items if str(item["question_id"]) in existing and config.answer_is_nonempty(existing[str(item["question_id"])])]
    write_jsonl(answers_path, ordered_rows)
    print(f"[STRUCTURED-ANSWER-WRITE] path={answers_path} rows={len(ordered_rows)}")
    return ordered_rows


def run_score_stage(
    items: list[Dict[str, Any]],
    answers_rows: list[Dict[str, Any]],
    config: StructuredDatasetConfig,
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

    ordered_rows = [existing[str(item["question_id"])] for item in items if str(item["question_id"]) in existing and config.score_is_nonempty(existing[str(item["question_id"])])]
    write_jsonl(scores_path, ordered_rows)
    print(f"[STRUCTURED-SCORE-WRITE] path={scores_path} rows={len(ordered_rows)}")
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
    ensure_dir(answer_root)
    ensure_dir(scored_root)
    ensure_dir(summary_root)

    dataset_keys = []
    for dataset_key in args.datasets:
        if dataset_key not in DATASET_CONFIGS:
            raise SystemExit(f"Unsupported structured dataset: {dataset_key}")
        if dataset_key not in dataset_keys:
            dataset_keys.append(dataset_key)

    dataset_payloads = {dataset_key: load_structured_items(question_root, DATASET_CONFIGS[dataset_key], args.limit) for dataset_key in dataset_keys}
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
            f"temperature={'<provider-default>' if effective_temperature is None else effective_temperature}"
        )
        for dataset_key in dataset_keys:
            config = DATASET_CONFIGS[dataset_key]
            items = dataset_payloads[dataset_key]
            answers_path = model_answer_dir / f"{dataset_key}.jsonl"
            scores_path = model_scored_dir / f"{dataset_key}.jsonl"
            answer_rows = run_answer_stage(
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
            )
            run_score_stage(
                items=items,
                answers_rows=answer_rows,
                config=config,
                scores_path=scores_path,
                resume=args.resume,
            )

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
    print(f"Done. Structured evaluation results saved to {out_dir}")


if __name__ == "__main__":
    main()
