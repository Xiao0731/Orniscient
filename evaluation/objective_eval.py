from __future__ import annotations

import argparse
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

from model_registry import (
    ModelSpec,
    enabled_specs,
    get_api_key,
    resolve_max_workers,
    resolve_objective_temperature,
)

load_dotenv(override=True)

SUPPORTED_OBJECTIVE_DATASETS = {
    "QA-SC": "single_choice",
    "QA-MC": "multi_choice",
    "QA-SA": "short_answer",
    "Bird-Geo": "single_choice",
    "Bird-Taxonomy": "short_answer",
}
DEFAULT_DATASET_ORDER = ["QA-SC", "QA-MC", "QA-SA", "Bird-Geo", "Bird-Taxonomy"]


@dataclass
class EvalResult:
    question_id: str
    dataset: str
    model_alias: str
    target_entity: str
    prediction_raw: str
    prediction_answer: str
    gold_answer: str
    score_em: float
    score_f1: float
    is_correct: int
    error: str = ""


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


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_objective_prompt(item: Dict[str, Any], task_type: str) -> str:
    q = item.get("question", "")
    target = item.get("target_entity", "")
    options = item.get("options", {}) or {}
    parts = [
        "You are answering an ornithology benchmark question.",
        "Answer using ONLY a compact JSON object.",
        "Do not include markdown, explanation, or extra keys.",
        "For species-identification style questions, if needed, answer with a specific species-level name rather than a genus/family or vague category.",
        "",
        f"Dataset: {item.get('dataset', '')}",
        f"Target entity: {target}",
        f"Question: {q}",
    ]
    if options:
        parts.append("Options:")
        for key, val in options.items():
            parts.append(f"{key}. {val}")
    if task_type == "single_choice":
        letters = ", ".join(options.keys()) if options else "A, B, C, D"
        parts += ["", '{"answer": "<ONE LETTER>"}', f"The answer must be one of: {letters}."]
    elif task_type == "multi_choice":
        option_keys = ", ".join(options.keys()) if options else "A, B, C, D, E"
        parts += ["", '{"answer": "<LETTERS SEPARATED BY COMMAS>"}', f"Use only option letters from: {option_keys}", 'Example: {"answer": "A, C, E"}']
    else:
        parts += ["", '{"answer": "<SHORT ANSWER>"}', "Keep the answer concise and faithful to the question."]
    return "\n".join(parts)


def parse_json_answer(text: str) -> Optional[str]:
    text = text.strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and "answer" in obj:
            return str(obj["answer"]).strip()
    except Exception:
        pass
    m = re.search(r'"answer"\s*:\s*"(.*?)"', text, flags=re.S)
    if m:
        return m.group(1).strip()
    m = re.search(r"answer\s*[:=]\s*(.+)$", text, flags=re.I | re.M)
    if m:
        return m.group(1).strip().strip('"')
    return text.strip() if text else None


def normalize_text(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r'[\[\]\(\)\{\}\.,;:!?"“”\'`]+', "", s)
    return s


def normalize_single_choice(s: str) -> str:
    s = s.strip().upper()
    m = re.search(r"\b([A-E])\b", s)
    return m.group(1) if m else s[:1]


def normalize_multi_choice(s: str) -> List[str]:
    letters = re.findall(r"[A-E]", s.upper())
    seen = set(letters)
    return [x for x in ["A", "B", "C", "D", "E"] if x in seen]


def token_f1(pred: str, gold: str) -> float:
    p = normalize_text(pred).split()
    g = normalize_text(gold).split()
    if not p and not g:
        return 1.0
    if not p or not g:
        return 0.0

    common = 0
    g_counts: Dict[str, int] = {}
    for tok in g:
        g_counts[tok] = g_counts.get(tok, 0) + 1

    for tok in p:
        if g_counts.get(tok, 0) > 0:
            common += 1
            g_counts[tok] -= 1

    if common == 0:
        return 0.0

    precision = common / len(p)
    recall = common / len(g)
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def set_f1_from_lists(pred_items: List[str], gold_items: List[str]) -> float:
    p = {normalize_text(x) for x in pred_items if normalize_text(x)}
    g = {normalize_text(x) for x in gold_items if normalize_text(x)}
    if not p and not g:
        return 1.0
    if not p or not g:
        return 0.0
    inter = len(p & g)
    prec = inter / len(p)
    rec = inter / len(g)
    return 0.0 if prec + rec == 0 else 2 * prec * rec / (prec + rec)


def normalize_short_answer_text(s: str) -> str:
    s = normalize_text(s)
    s = re.sub(r"^(the answer is|answer is|it is|it's|its|this is|they are|it was|they were)\s+", "", s)
    s = s.replace(" to ", "-")
    s = s.replace(" – ", "-").replace(" — ", "-")
    s = re.sub(r"\b(days?|day)\b", "", s)
    s = re.sub(r"\b(months?|month)\b", "", s)
    s = re.sub(r"\b(years?|year)\b", "", s)
    s = re.sub(r"\bmeters?\b", "m", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_numbers(s: str) -> List[str]:
    s = s.lower().replace(" to ", "-").replace(" – ", "-").replace(" — ", "-")
    nums = re.findall(r"\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)?", s)
    return nums


def canonical_boolean(s: str) -> Optional[bool]:
    s = normalize_short_answer_text(s)
    negative_signals = [
        "false", "no", "not", "no longer", "not currently",
        "distinct species", "separate species"
    ]
    positive_signals = [
        "true", "yes", "currently", "conspecific", "same species"
    ]
    if any(x in s for x in negative_signals):
        return False
    if any(x in s for x in positive_signals):
        return True
    return None


def canonical_monotypic(s: str) -> Optional[str]:
    s = normalize_short_answer_text(s)
    if any(x in s for x in ["monotypic", "no recognized subspecies", "no subspecies", "no valid subspecies"]):
        return "monotypic"
    return None


def split_taxa_items(s: str) -> List[str]:
    s = s.strip()
    if not s:
        return []
    s = re.sub(r"\band\b", ",", s, flags=re.I)
    parts = re.split(r"[;,/|\n]+", s)
    cleaned = []
    for p in parts:
        p = normalize_short_answer_text(p)
        if p:
            cleaned.append(p)
    return cleaned


def score_qa_mc(pred: str, gold: str) -> tuple[float, float, int]:
    pred_set = normalize_multi_choice(pred)
    gold_set = normalize_multi_choice(gold)
    em = 1.0 if pred_set == gold_set else 0.0
    f1 = set_f1_from_lists(pred_set, gold_set)
    correct = int(em == 1.0)
    return em, f1, correct


def score_qa_sa(pred: str, gold: str) -> tuple[float, float, int]:
    pred_n = normalize_short_answer_text(pred)
    gold_n = normalize_short_answer_text(gold)

    em = 1.0 if pred_n == gold_n else 0.0
    if em == 1.0:
        return em, 1.0, 1

    pred_mono = canonical_monotypic(pred)
    gold_mono = canonical_monotypic(gold)
    if pred_mono and gold_mono and pred_mono == gold_mono:
        return 0.0, 1.0, 1

    pred_nums = extract_numbers(pred)
    gold_nums = extract_numbers(gold)
    if pred_nums and gold_nums and pred_nums == gold_nums:
        return 0.0, 1.0, 1

    if pred_n and gold_n and (pred_n in gold_n or gold_n in pred_n):
        f1 = max(token_f1(pred_n, gold_n), 0.85)
        return 0.0, f1, int(f1 >= 0.8)

    f1 = token_f1(pred_n, gold_n)
    return 0.0, f1, int(f1 >= 0.8)


def score_bird_taxonomy(pred: str, gold: str, item_type: str) -> tuple[float, float, int]:
    pred_n = normalize_short_answer_text(pred)
    gold_n = normalize_short_answer_text(gold)

    em = 1.0 if pred_n == gold_n else 0.0
    if em == 1.0:
        return em, 1.0, 1

    item_type = (item_type or "").strip().lower()

    if item_type == "taxonomic trap":
        pb = canonical_boolean(pred)
        gb = canonical_boolean(gold)
        if pb is not None and gb is not None and pb == gb:
            return 0.0, 1.0, 1

    if item_type == "monotypic verification":
        pred_mono = canonical_monotypic(pred)
        gold_mono = canonical_monotypic(gold)
        if pred_mono and gold_mono and pred_mono == gold_mono:
            return 0.0, 1.0, 1

    if item_type == "subspecies check":
        pred_items = split_taxa_items(pred)
        gold_items = split_taxa_items(gold)
        if pred_items or gold_items:
            f1 = set_f1_from_lists(pred_items, gold_items)
            return 0.0, f1, int(f1 >= 0.8)

    if item_type == "nomenclature & etymology":
        pred_nums = extract_numbers(pred)
        gold_nums = extract_numbers(gold)
        if pred_nums and gold_nums and pred_nums == gold_nums:
            return 0.0, 1.0, 1

    if item_type == "sister/similar taxa":
        pb = canonical_boolean(pred)
        gb = canonical_boolean(gold)
        if pb is not None and gb is not None and pb == gb:
            return 0.0, 1.0, 1

    pred_nums = extract_numbers(pred)
    gold_nums = extract_numbers(gold)
    if pred_nums and gold_nums and pred_nums == gold_nums:
        return 0.0, 1.0, 1

    f1 = token_f1(pred_n, gold_n)
    return 0.0, f1, int(f1 >= 0.8)


def score_answer(dataset: str, item_type: str, pred: str, gold: str) -> tuple[float, float, int]:
    if dataset in {"QA-SC", "Bird-Geo"}:
        correct = int(normalize_single_choice(pred) == normalize_single_choice(gold))
        return float(correct), float(correct), correct
    if dataset == "QA-MC":
        return score_qa_mc(pred, gold)
    if dataset == "QA-SA":
        return score_qa_sa(pred, gold)
    if dataset == "Bird-Taxonomy":
        return score_bird_taxonomy(pred, gold, item_type)

    correct = int(normalize_text(pred) == normalize_text(gold))
    return float(correct), float(correct), correct


def build_client(spec: ModelSpec) -> OpenAI:
    api_key = get_api_key(spec)
    if not api_key:
        raise ValueError(f"Missing API key for {spec.alias}: env {spec.api_key_env}")
    print(f"{spec.alias} key suffix: {api_key[-4:] if api_key else '<empty>'}")
    return OpenAI(api_key=api_key, base_url=spec.base_url)


def build_completion_kwargs(spec: ModelSpec, max_tokens: int) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {}
    temperature = resolve_objective_temperature(spec)
    if spec.supports_temperature and temperature is not None:
        kwargs["temperature"] = temperature
    if spec.supports_max_tokens:
        kwargs["max_tokens"] = max_tokens
    return kwargs


def is_retryable_error(exc: Exception) -> bool:
    text = str(exc).lower()
    retry_signals = [
        "429", "rate limit", "too many requests", "temporarily unavailable",
        "service unavailable", "timeout", "timed out", "connection reset",
        "并发", "限流", "超频", "1302", "1305",
    ]
    return any(signal in text for signal in retry_signals)


def run_one(
    client: OpenAI,
    spec: ModelSpec,
    prompt: str,
    max_tokens: int = 256,
    max_retries: int = 3,
) -> str:
    messages = []
    if spec.supports_system_prompt:
        messages.append({"role": "system", "content": "You are a precise evaluation assistant."})
        messages.append({"role": "user", "content": prompt})
    else:
        messages.append({"role": "user", "content": "System instruction: You are a precise evaluation assistant.\n\n" + prompt})

    request_kwargs = build_completion_kwargs(spec, max_tokens)
    last_exc: Optional[Exception] = None

    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=spec.model,
                messages=messages,
                **request_kwargs,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            last_exc = exc
            if attempt >= max_retries or not is_retryable_error(exc):
                raise
            time.sleep(min(8.0, 1.5 * (2 ** (attempt - 1))))

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("run_one exited unexpectedly without response or exception")


def evaluate_item(client: OpenAI, spec: ModelSpec, item: Dict[str, Any]) -> EvalResult:
    dataset = item.get("dataset", "")
    task_type = SUPPORTED_OBJECTIVE_DATASETS[dataset]
    prompt = build_objective_prompt(item, task_type)
    gold = str(item.get("answer", "")).strip()
    item_type = str(item.get("type", "")).strip()

    try:
        raw = run_one(client, spec, prompt)
        pred = parse_json_answer(raw) or ""
        score_em, score_f1, correct = score_answer(dataset, item_type, pred, gold)
        return EvalResult(
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
    except Exception as e:
        print(f"[EVAL ERROR] dataset={dataset} qid={item.get('question_id','')} err={e}")
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


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def run_dataset_for_model(
    client: OpenAI,
    spec: ModelSpec,
    ds_name: str,
    rows: List[Dict[str, Any]],
    out_dir: Path,
    max_workers: int,
    print_every: int,
    save_predictions: bool,
) -> Dict[str, Any]:
    results: List[EvalResult] = []
    completed = 0
    errors = 0
    metric_sum = 0.0

    temperature = resolve_objective_temperature(spec)
    effective_workers = resolve_max_workers(spec, max_workers)

    with ThreadPoolExecutor(max_workers=effective_workers) as executor:
        futures = [executor.submit(evaluate_item, client, spec, item) for item in rows]
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
                    f"  [{spec.alias} | {ds_name}] {completed}/{total} | "
                    f"valid={completed - errors} | errors={errors} | "
                    f"workers={effective_workers} | "
                    f"temperature={'<provider-default>' if temperature is None else temperature} | "
                    f"score={live_score:.2f}"
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
    }

    if save_predictions:
        write_jsonl(out_dir / f"{ds_name}_predictions.jsonl", [asdict(r) for r in results])
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Streaming objective evaluation for bird benchmark datasets.")
    parser.add_argument("--question-root", type=str, default="question")
    parser.add_argument("--out-dir", type=str, default="evaluation/results_objective_stream")
    parser.add_argument("--models", nargs="*", default=["deepseek", "qwen", "kimi", "glm", "doubao", "hunyuan", "wenxin", "minimax"])
    parser.add_argument("--datasets", nargs="*", default=DEFAULT_DATASET_ORDER)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-workers", type=int, default=8)
    parser.add_argument("--print-every", type=int, default=20)
    parser.add_argument("--save-predictions", action="store_true")
    args = parser.parse_args()

    question_root = Path(args.question_root)
    out_dir = Path(args.out_dir)
    ensure_dir(out_dir)

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
            "datasets": {},
        }
        print(f"\n=== MODEL: {spec.alias} | {spec.model} ===")
        print(
            f"[POLICY] temperature={'<provider-default>' if model_temperature is None else model_temperature} | "
            f"workers={model_workers} | "
            f"public_concurrency={spec.max_concurrency if spec.max_concurrency is not None else '<dynamic/undocumented>'} | "
            f"public_rpm={spec.rpm_limit if spec.rpm_limit is not None else '<dynamic/undocumented>'} | "
            f"public_tpm={spec.tpm_limit if spec.tpm_limit is not None else '<dynamic/undocumented>'}"
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
            )
            model_summary["datasets"][ds_name] = ds_summary
            print(f"[DONE] {spec.alias} | {ds_name} | score={ds_summary['score']:.2f}")

        (model_dir / "summary.json").write_text(json.dumps(model_summary, ensure_ascii=False, indent=2), encoding="utf-8")
        all_summary[spec.alias] = model_summary

    (out_dir / "summary_all.json").write_text(json.dumps(all_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDone. Results saved to {out_dir}")


if __name__ == "__main__":
    main()
