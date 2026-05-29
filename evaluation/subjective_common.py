from __future__ import annotations

import json
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from dotenv import load_dotenv
from openai import OpenAI

try:
    from model_registry import ModelSpec, get_api_key
    from subjective_rubrics import format_rubric_block, get_rubric
except ModuleNotFoundError:
    from evaluation.model_registry import ModelSpec, get_api_key
    from evaluation.subjective_rubrics import format_rubric_block, get_rubric

load_dotenv(override=True)

RANDOM_SEED = 20260404
SUPPORTED_PROMPT_MODES = ("zero_shot", "few_shot", "cot")
DEFAULT_JUDGE_ALIASES = ("qwen3-max",)
KIMI_MODEL_NAME = "kimi-k2.5"
SUBJECTIVE_ALLOWED_TYPES: Dict[str, set[str]] = {
    "Bird-Classify": {"Taxonomic Hierarchy", "Taxon-to-Feature"},
}
TARGET_AWARE_SUBJECTIVE_DATASETS = {
    "Bird-Comp",
    "Bird-Life",
    "Bird-Eco",
    "Bird-Con",
    "Bird-Reason",
    "Bird-Plan",
}
LEAKAGE_SENSITIVE_DATASETS = {"Bird-ID"}
LEAKAGE_SENSITIVE_CLASSIFY_TYPES = {"Feature-to-Family", "Feature-to-Order", "Order-to-Family"}
FAIL_FAST_PATTERNS = (
    "insufficient_balance",
    "insufficient balance",
    "余额不足",
    "authentication failed",
    "invalid api key",
    "unauthorized",
    "forbidden",
)


@dataclass(frozen=True)
class SubjectiveQuestion:
    qid: str
    dataset: str
    type: str
    target_entity: str
    question: str
    gold_answer: str
    evidence_quotes: list[str]
    source_chapters: list[str]
    constraint_applied: Optional[str]
    knowledge_domain: Optional[str]


class FailFastError(RuntimeError):
    pass


def seed_everything() -> None:
    random.seed(RANDOM_SEED)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def resolve_worker_count(*values: Optional[int], minimum: int = 1) -> int:
    for value in values:
        if value is None:
            continue
        return max(minimum, int(value))
    return minimum


def discover_dataset_file(question_root: Path, dataset_name: str) -> Optional[Path]:
    candidates = [
        question_root / dataset_name / f"{dataset_name}_questions.jsonl",
        question_root / f"{dataset_name}_questions.jsonl",
    ]
    for path in candidates:
        if path.exists():
            return path
    matches = list(question_root.rglob(f"{dataset_name}_questions.jsonl"))
    return matches[0] if matches else None


def load_jsonl(path: Path) -> list[Dict[str, Any]]:
    rows: list[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _to_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    text = str(value).strip()
    return [text] if text else []


def standardize_subjective_row(row: Dict[str, Any]) -> SubjectiveQuestion:
    provenance = row.get("provenance", {}) or {}
    return SubjectiveQuestion(
        qid=str(row.get("question_id", "")).strip(),
        dataset=str(row.get("dataset", "")).strip(),
        type=str(row.get("type", "")).strip(),
        target_entity=str(row.get("target_entity", "")).strip(),
        question=str(row.get("question", "")).strip(),
        gold_answer=str(row.get("answer", "")).strip(),
        evidence_quotes=_to_str_list(provenance.get("exact_quote")),
        source_chapters=_to_str_list(provenance.get("source_chapter")),
        constraint_applied=(str(row.get("constraint_applied")).strip() if row.get("constraint_applied") is not None else None),
        knowledge_domain=(str(row.get("knowledge_domain")).strip() if row.get("knowledge_domain") is not None else None),
    )


def get_subjective_allowed_types(dataset: str) -> Optional[set[str]]:
    return SUBJECTIVE_ALLOWED_TYPES.get(dataset)


def _apply_subjective_type_filter(
    dataset: str,
    rows: list[SubjectiveQuestion],
) -> list[SubjectiveQuestion]:
    allowed_types = get_subjective_allowed_types(dataset)
    if not allowed_types:
        return rows
    return [row for row in rows if row.type in allowed_types]


def load_subjective_dataset(path: Path, limit: int = 0) -> list[SubjectiveQuestion]:
    rows = [standardize_subjective_row(row) for row in load_jsonl(path)]
    dataset_name = rows[0].dataset if rows else path.stem.replace("_questions", "")
    rows = _apply_subjective_type_filter(dataset_name, rows)
    rows.sort(key=lambda item: item.qid)
    if limit > 0:
        rows = rows[:limit]
    return rows


def load_fewshot_examples(root: Path, dataset: str) -> list[Dict[str, Any]]:
    path = root / f"{dataset}.json"
    if not path.exists():
        raise FileNotFoundError(f"Few-shot example file not found for {dataset}: {path}")
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list) or not payload:
        raise ValueError(f"Few-shot example file for {dataset} must be a non-empty JSON array: {path}")
    allowed_types = get_subjective_allowed_types(dataset)
    if allowed_types:
        payload = [example for example in payload if str(example.get("type", "")).strip() in allowed_types]
    if not payload:
        raise ValueError(f"No usable few-shot examples remain for subjective dataset {dataset}: {path}")
    return payload


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def should_inject_constraint(question: str, constraint: Optional[str]) -> bool:
    if not constraint:
        return False
    normalized_question = normalize_whitespace(question).lower()
    normalized_constraint = normalize_whitespace(constraint).lower()
    return bool(normalized_constraint) and normalized_constraint not in normalized_question


def is_leakage_sensitive_subjective_item(item: Any) -> bool:
    dataset = str(getattr(item, "dataset", "") or "").strip()
    item_type = str(getattr(item, "type", "") or "").strip()
    return dataset in LEAKAGE_SENSITIVE_DATASETS or (
        dataset == "Bird-Classify" and item_type in LEAKAGE_SENSITIVE_CLASSIFY_TYPES
    )


def should_inject_target_entity(item: Any) -> bool:
    dataset = str(getattr(item, "dataset", "") or "").strip()
    target = str(getattr(item, "target_entity", "") or "").strip()
    return bool(target) and dataset in TARGET_AWARE_SUBJECTIVE_DATASETS and not is_leakage_sensitive_subjective_item(item)


def prepare_candidate_question(item: SubjectiveQuestion) -> str:
    if item.dataset == "Bird-Plan" and should_inject_constraint(item.question, item.constraint_applied):
        return f"{item.question}\n\nAdditional planning constraint: {item.constraint_applied}"
    return item.question


def build_client(spec: ModelSpec) -> OpenAI:
    api_key = get_api_key(spec)
    if not api_key:
        raise ValueError(f"Missing API key for {spec.alias}: env {spec.api_key_env}")
    return OpenAI(
        api_key=api_key,
        base_url=spec.base_url,
        timeout=60.0,
        max_retries=0,
    )


def _is_fail_fast_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code in {401, 403}:
        return True
    code = str(getattr(exc, "code", "") or "").strip().lower()
    if code in {"1008", "401", "403", "insufficient_balance"}:
        return True
    lowered = f"{type(exc).__name__} {exc}".lower()
    if re.search(r"\b(?:1008|401|403)\b", lowered):
        return True
    return any(pattern in lowered for pattern in FAIL_FAST_PATTERNS)


def _build_completion_kwargs(
    spec: ModelSpec,
    messages: list[Dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> Dict[str, Any]:
    effective_temperature = 1.0 if spec.model == KIMI_MODEL_NAME else temperature
    kwargs: Dict[str, Any] = {
        "model": spec.model,
        "messages": messages,
        "timeout": 60.0,
    }
    if spec.supports_temperature:
        kwargs["temperature"] = effective_temperature
    if spec.supports_max_tokens:
        kwargs["max_tokens"] = max_tokens
    return kwargs


def call_with_retries(
    client: OpenAI,
    spec: ModelSpec,
    messages: list[Dict[str, str]],
    temperature: float,
    max_tokens: int,
    retries: int,
) -> str:
    last_error: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            kwargs = _build_completion_kwargs(spec, messages, temperature, max_tokens)
            if spec.model == KIMI_MODEL_NAME and temperature != 1:
                print(f"[TEMP-OVERRIDE] model={spec.alias} api_model={spec.model} temperature=1")
            print(f"[CALL] model={spec.alias} attempt={attempt + 1}/{retries + 1}")
            response = client.chat.completions.create(**kwargs)
            return response.choices[0].message.content or ""
        except Exception as exc:
            last_error = exc
            print(f"[CALL-ERROR] model={spec.alias} attempt={attempt + 1}/{retries + 1} err={exc}")
            if _is_fail_fast_error(exc):
                raise FailFastError(f"Fail-fast error for {spec.alias}: {exc}") from exc
            if attempt >= retries:
                break
            time.sleep(min(8, 1.5 * (attempt + 1)))
    raise RuntimeError(f"Model call failed for {spec.alias}: {last_error}") from last_error


def extract_json_object(text: str) -> Optional[str]:
    stripped = (text or "").strip()
    if not stripped:
        return None

    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.S | re.I)
    if fence_match:
        return fence_match.group(1)

    start = stripped.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False
    for idx in range(start, len(stripped)):
        ch = stripped[idx]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return stripped[start : idx + 1]
    return None


def _safe_json_load(text: str) -> Optional[Dict[str, Any]]:
    candidate = extract_json_object(text) or (text or "").strip()
    if not candidate:
        return None
    try:
        parsed = json.loads(candidate)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def parse_candidate_response(raw_response: str) -> str:
    raw_response = raw_response or ""
    parsed = _safe_json_load(raw_response)
    if parsed is not None:
        for key in ("answer", "final_answer"):
            value = parsed.get(key)
            if value is not None:
                text = normalize_whitespace(str(value))
                if text:
                    return text

    answer_match = re.search(r"(?:final answer|answer)\s*[:：]\s*(.+)$", raw_response, flags=re.I | re.M | re.S)
    if answer_match:
        return normalize_whitespace(answer_match.group(1))

    lines = [line.strip() for line in raw_response.splitlines() if line.strip()]
    if len(lines) >= 2 and re.search(r"reason|analysis|thinking|chain", lines[0], flags=re.I):
        return normalize_whitespace(lines[-1])
    return normalize_whitespace(raw_response)


def build_candidate_messages(
    item: SubjectiveQuestion,
    mode: str,
    question_for_model: str,
    fewshot_examples: Optional[list[Dict[str, Any]]] = None,
) -> list[Dict[str, str]]:
    if mode not in SUPPORTED_PROMPT_MODES:
        raise KeyError(f"Unsupported prompting mode: {mode}")

    system_prompt = (
        "You are answering an ornithology benchmark question. "
        "Return strict JSON only with exactly one key: answer."
    )
    if mode == "cot":
        system_prompt += " Think silently if needed, but do not output reasoning."

    instructions = [
        "Task: answer the following bird-related subjective question.",
        f"Dataset: {item.dataset}",
        f"Question type: {item.type}",
    ]
    if item.knowledge_domain:
        instructions.append(f"Knowledge domain: {item.knowledge_domain}")
    if should_inject_target_entity(item):
        instructions.append(f"Target entity: {str(getattr(item, 'target_entity', '')).strip()}")
    instructions.extend(
        [
            f"Question: {question_for_model}",
            'Return only: {"answer": "..."}',
        ]
    )
    if is_leakage_sensitive_subjective_item(item):
        instructions.insert(-1, "Do not reveal or guess any hidden target species name.")
    if mode == "cot":
        instructions.append("You may reason privately, but the output must still contain only the final answer JSON.")

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
    messages.append({"role": "user", "content": "\n".join(instructions)})
    return messages


def build_judge_messages(item: SubjectiveQuestion, candidate_answer: str) -> list[Dict[str, str]]:
    rubric = get_rubric(item.dataset)
    schema = {"question_id": item.qid}
    for dimension, max_score in rubric.items():
        schema[dimension] = max_score
    schema["score_total"] = 100

    evidence_block = "\n".join(f"- {quote}" for quote in item.evidence_quotes) if item.evidence_quotes else "- <none>"
    source_block = ", ".join(item.source_chapters) if item.source_chapters else "<unknown>"
    user_parts = [
        "You are a strict ornithology benchmark judge.",
        "Score only against the question, gold answer, and evidence.",
        "Do not mention model identity or write any explanation.",
        f"Dataset: {item.dataset}",
        f"Question type: {item.type}",
        format_rubric_block(item.dataset),
        "",
        f"Question: {item.question}",
        f"Gold answer: {item.gold_answer}",
        f"Candidate answer: {candidate_answer}",
        f"Source chapters: {source_block}",
        "Evidence quotes:",
        evidence_block,
    ]
    if item.dataset == "Bird-Plan" and item.constraint_applied:
        user_parts.append(f"Constraint applied: {item.constraint_applied}")
    user_parts.extend(
        [
            "",
            "Return strict JSON only.",
            "Do not use markdown.",
            "Do not add explanations or extra fields.",
            json.dumps(schema, ensure_ascii=False),
        ]
    )
    return [
        {
            "role": "system",
            "content": "Return strict JSON only with exactly the requested fields.",
        },
        {"role": "user", "content": "\n".join(user_parts)},
    ]


def parse_judge_response(raw_response: str, dataset: str, expected_qid: str) -> Dict[str, Any]:
    parsed = _safe_json_load(raw_response)
    if parsed is None:
        raise ValueError("Judge did not return a valid JSON object.")

    rubric = get_rubric(dataset)
    expected_keys = {"question_id", *rubric.keys(), "score_total"}
    actual_keys = set(parsed.keys())
    if actual_keys != expected_keys:
        raise ValueError(f"Judge JSON keys mismatch. expected={sorted(expected_keys)} actual={sorted(actual_keys)}")

    question_id = str(parsed.get("question_id", "")).strip()
    if question_id != expected_qid:
        raise ValueError(f"Judge question_id mismatch: expected {expected_qid}, got {question_id}")

    normalized: Dict[str, Any] = {"question_id": question_id}
    total = 0
    for dimension, max_score in rubric.items():
        value = int(round(float(parsed[dimension])))
        if value < 0 or value > max_score:
            raise ValueError(f"Dimension score out of range for {dimension}: {value}")
        normalized[dimension] = value
        total += value

    score_total = int(round(float(parsed["score_total"])))
    if score_total != total:
        raise ValueError(f"score_total mismatch: expected {total}, got {score_total}")
    normalized["score_total"] = score_total
    return normalized


def load_existing_jsonl_map(path: Path, key_field: str = "question_id") -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    rows = load_jsonl(path)
    mapping: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        key = str(row.get(key_field, "")).strip()
        if key:
            mapping[key] = row
    return mapping


def has_nonempty_answer(row: Dict[str, Any]) -> bool:
    return bool(str(row.get("answer", "")).strip())


def has_nonempty_score(row: Dict[str, Any]) -> bool:
    return row.get("score_total") is not None
