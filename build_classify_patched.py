import os
import json
import re
import hashlib
import concurrent.futures
from pathlib import Path

import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv  # 🌟 1. 导入 dotenv

from prompt_complete import get_bird_classify_prompt

# 🌟 2. 强制加载 .env 文件，让代理和自定义 URL 生效！
load_dotenv(override=True)

DATA_DIR = os.getenv("BIRD_DATA_DIR", "./data")
OUT_DIR = os.getenv("BIRD_OUT_DIR", "./question")
MAX_WORKERS = int(os.getenv("BIRD_MAX_WORKERS", "5"))
TARGET_COUNT = int(os.getenv("BIRD_CLASSIFY_TARGET", "500"))
MODEL_NAME = os.getenv("BIRD_LLM_MODEL", "deepseek-chat")

# 🌟 3. 兼容获取 Key：优先找 DEEPSEEK_API_KEY，找不到再找 OPENAI_API_KEY
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
# 🌟 4. 如果你用的是硅基流动等镜像，确保这里能读到你 .env 里的地址
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

if not DEEPSEEK_API_KEY:
    raise RuntimeError("API Key 未设置，请检查 .env 文件中是否配置了 DEEPSEEK_API_KEY 或 OPENAI_API_KEY。")

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

CLASSIFY_TYPES = ["Feature-to-Family", "Taxon-to-Feature", "Taxonomic Hierarchy"]
TEXT_COLUMNS = [
    "Introduction",
    "GeneralHabitat",
    "DietandForaging",
    "Breeding",
    "ConservationStatus",
    "SystematicasHistory",
]

def clean_visuals_and_citations(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = re.sub(r'\(?[Ff]ig\.?\s*\d+\)?', '', text)
    text = re.sub(r'\(?[Pp]late\s*\d+\)?', '', text)
    text = re.sub(r'\(?[Pp]hoto.*?\)?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\([A-Z][a-z]+ (et al\.)?, \d{4}\)', '', text)
    text = re.sub(r'\[\d+(,\s*\d+)*\]', '', text)
    return re.sub(r'\s{2,}', ' ', text).strip()

def normalize_text(text: str) -> str:
    text = clean_visuals_and_citations(text)
    text = re.sub(r'\s+\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def mask_entities(text: str, entities) -> str:
    masked_text = text
    # longer strings first to avoid partial masking
    sorted_entities = sorted(
        {str(e).strip() for e in entities if pd.notna(e) and str(e).strip()},
        key=len,
        reverse=True,
    )
    for entity in sorted_entities:
        placeholder = "[the bird]"
        # order/family placeholders are only for question generation; keep context broadly anonymized
        masked_text = re.sub(re.escape(entity), placeholder, masked_text, flags=re.IGNORECASE)
    return masked_text

def find_order_file() -> str:
    candidates = [
        os.path.join(DATA_DIR, "BOW", "Order.xlsx"),
        os.path.join(DATA_DIR, "Order.xlsx"),
        "./Order.xlsx",
        "/mnt/data/Order.xlsx",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    raise FileNotFoundError(f"未找到 Order.xlsx，尝试过: {candidates}")

def save_jsonl_atomic(dataset_name: str, rows: list[dict]) -> str:
    dataset_dir = Path(OUT_DIR) / dataset_name
    dataset_dir.mkdir(parents=True, exist_ok=True)
    file_path = dataset_dir / f"{dataset_name}_questions.jsonl"
    with file_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return str(file_path)

def build_signature(question_type: str, order: str, family: str, context: str) -> str:
    key = f"{question_type}|{order}|{family}|{context[:1200]}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]

def call_deepseek_generator(system_prompt: str, user_content: str):
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.8,
            max_tokens=2200,
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"[API Error] {e}")
        return None

def process_order_file(file_path: str) -> list[dict]:
    df = pd.read_excel(file_path)
    for col in ["Order", "Family", "Common_name"]:
        df[col] = df[col].ffill().astype(str).str.strip()

    # group at Family-within-Order granularity; this better matches prompt semantics
    grouped = (
        df.groupby(["Order", "Family"], dropna=False)
        .agg({
            "Common_name": lambda x: sorted({str(v).strip() for v in x if pd.notna(v) and str(v).strip()}),
            **{col: lambda x, c=col: "\n".join([str(v) for v in x if pd.notna(v) and str(v).strip()]) for col in TEXT_COLUMNS}
        })
        .reset_index()
    )

    processed = []
    for _, row in grouped.iterrows():
        raw_parts = []
        for col in TEXT_COLUMNS:
            val = row.get(col, "")
            if isinstance(val, str) and val.strip():
                raw_parts.append(f"[{col}]\n{val}")
        raw_text = "\n\n".join(raw_parts)
        cleaned_text = normalize_text(raw_text)
        if len(cleaned_text) < 120:
            continue

        entities_to_mask = [row["Order"], row["Family"], *row["Common_name"]]
        masked_text = mask_entities(cleaned_text, entities_to_mask)
        processed.append({
            "order": row["Order"],
            "family": row["Family"],
            "context_masked": masked_text,
            "context_unmasked": cleaned_text,
            "common_names": row["Common_name"],
        })
    return processed

def build_tasks(items: list[dict], target_count: int) -> list[tuple]:
    raw_prompt = get_bird_classify_prompt()
    tasks = []
    seen = set()
    counters = {t: 0 for t in CLASSIFY_TYPES}
    base_quota = target_count // len(CLASSIFY_TYPES)
    quotas = {t: base_quota for t in CLASSIFY_TYPES}
    for t in CLASSIFY_TYPES[: target_count % len(CLASSIFY_TYPES)]:
        quotas[t] += 1

    q_index = 0
    for question_type in CLASSIFY_TYPES:
        for item in items:
            if counters[question_type] >= quotas[question_type]:
                break

            context = item["context_masked"] if question_type == "Feature-to-Family" else item["context_unmasked"]
            signature = build_signature(question_type, item["order"], item["family"], context)
            if signature in seen:
                continue
            seen.add(signature)

            q_index += 1
            counters[question_type] += 1
            q_id = f"bird_classify_{q_index:04d}"
            system_prompt = raw_prompt.replace("{type}", question_type)

            if question_type == "Feature-to-Family":
                task_note = (
                    f"Target taxon (hidden from the student): Order={item['order']}; Family={item['family']}.\n"
                    f"Generate a blind identification question from the anonymized context below.\n"
                    f"Do NOT reveal the real Order or Family in the question stem.\n"
                )
                user_content = task_note + "\nContext:\n" + context
                target_entity = f"{item['order']} | {item['family']}"
            else:
                task_note = (
                    f"Target Family: {item['family']}\n"
                    f"Belongs to Order: {item['order']}\n"
                    f"Generate the requested family-focused classification question based strictly on the text below.\n"
                )
                user_content = task_note + "\nContext:\n" + context
                target_entity = item["family"]

            tasks.append((q_id, question_type, target_entity, item["order"], item["family"], system_prompt, user_content, signature))

    return tasks

def process_single_task(task_payload):
    q_id, question_type, target_entity, order, family, system_prompt, user_content, signature = task_payload
    print(f"🚀 发送请求 -> ID: {q_id} | Type: {question_type} | Target: {target_entity}")
    llm_result_json = call_deepseek_generator(system_prompt, user_content)
    if not llm_result_json:
        return None
    return {
        "question_id": q_id,
        "dataset": "Bird-Classify",
        "type": question_type,
        "target_entity": target_entity,
        "order": order,
        "family": family,
        "sample_key": signature,
        **llm_result_json,
    }

def main():
    order_file = find_order_file()
    print(f"读取文件: {order_file}")
    items = process_order_file(order_file)
    print(f"成功加载 {len(items)} 个 family-level 分类单元。")

    tasks = build_tasks(items, TARGET_COUNT)
    print(f"任务数: {len(tasks)} / 目标 {TARGET_COUNT}")
    if not tasks:
        raise RuntimeError("没有成功构建任何 Bird-Classify 任务，请检查输入文件。")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for final_json in executor.map(process_single_task, tasks):
            if final_json:
                results.append(final_json)
                print(f"✅ 生成成功: {final_json['question_id']}")
            else:
                print("❌ 某题生成失败，被跳过")

    out_path = save_jsonl_atomic("Bird-Classify", results)
    print(f"\n🎉 Bird-Classify 完成，共写入 {len(results)} 题 -> {out_path}")

if __name__ == "__main__":
    main()
