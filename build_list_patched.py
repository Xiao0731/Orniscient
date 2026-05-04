
import os
import json
import random
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv  # 🌟 1. 导入 dotenv

# 🌟 2. 强制加载 .env 文件，让 API Key 生效！
load_dotenv(override=True)

# =========================
# Config
# =========================
DATA_CANDIDATES = [
    "./data/BIRDBASE.xlsx",
    "./BIRDBASE.xlsx",
]
OUTPUT_DIR = Path("./question/List-Global")
OUTPUT_FILE = OUTPUT_DIR / "List-Global_questions.jsonl"

TARGET_COUNT = int(os.getenv("LIST_GLOBAL_TARGET", "200"))
MAX_WORKERS = int(os.getenv("LIST_GLOBAL_MAX_WORKERS", "8"))
SAVE_EVERY = int(os.getenv("LIST_GLOBAL_SAVE_EVERY", "10"))
RANDOM_SEED = int(os.getenv("LIST_GLOBAL_RANDOM_SEED", "42"))

DEEPSEEK_API_KEY = (os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY", "")).strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip()

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Range controls: slightly relaxed compared with v3, but still quality-oriented.
MIN_ANSWER_SIZE = int(os.getenv("LIST_GLOBAL_MIN_ANSWER_SIZE", "3"))
MAX_ANSWER_SIZE = int(os.getenv("LIST_GLOBAL_MAX_ANSWER_SIZE", "120"))

# Keep domain diversity instead of letting one easy domain dominate everything.
DOMAIN_QUOTAS = {
    "Conservation": 35,
    "Biogeography": 45,
    "Ecology": 45,
    "Behavior": 40,
    "Taxonomy": 20,
    "Morphology": 15,
}


# =========================
# Prompt
# =========================
def get_list_global_prompt(condition_str: str, species_list: list[str]) -> str:
    species_json = json.dumps(species_list, ensure_ascii=False)

    return f"""
You are an ornithology benchmark question generator.

Your task is to convert a structured species-retrieval result from BIRDBASE into ONE high-quality benchmark question.

Requirements:
1. The dataset name must be exactly "List-Global".
2. The knowledge_domain should reflect the dominant biological dimension tested by the search conditions
   (examples: "Conservation", "Biogeography", "Ecology", "Behavior", "Taxonomy", "Morphology").
3. The type should be exactly "General".
4. The question must be a natural-language list/retrieval question asking for all bird species that satisfy the given conditions.
5. Do NOT add options.
6. The answer MUST be the exact full species list provided below, unchanged in content.
7. Prefer a natural phrasing, but preserve the biological meaning of the conditions exactly.
8. Return valid JSON only.

Search Conditions:
{condition_str}

Ground Truth Species List:
{species_json}

Return JSON with exactly these fields:
{{
  "dataset": "List-Global",
  "knowledge_domain": "...",
  "type": "General",
  "question": "...",
  "answer": [...]
}}
""".strip()


# =========================
# Helpers
# =========================
def find_birdbase_file() -> str:
    for path in DATA_CANDIDATES:
        if os.path.exists(path):
            return path
    raise FileNotFoundError(
        "Could not find BIRDBASE.xlsx. Tried: " + ", ".join(DATA_CANDIDATES)
    )


def normalize_text(x) -> str:
    if pd.isna(x):
        return ""
    return str(x).strip()


def _dedupe_columns(cols: list[str]) -> list[str]:
    seen = {}
    out = []
    for c in cols:
        base = c if c else "Unnamed"
        if base not in seen:
            seen[base] = 0
            out.append(base)
        else:
            seen[base] += 1
            out.append(f"{base}__{seen[base]}")
    return out


def load_birdbase() -> pd.DataFrame:
    file_path = find_birdbase_file()
    raw = pd.read_excel(file_path, header=0)
    raw.columns = [str(c).strip() for c in raw.columns]

    # First data row stores the true field names; top header row is category grouping.
    first_row = raw.iloc[0].tolist()
    new_cols = []
    for top, sub in zip(raw.columns, first_row):
        sub_txt = normalize_text(sub)
        top_txt = normalize_text(top)
        if sub_txt and not sub_txt.lower().startswith("unnamed"):
            new_cols.append(sub_txt)
        else:
            new_cols.append(top_txt)

    raw.columns = _dedupe_columns(new_cols)
    df = raw.iloc[1:].reset_index(drop=True).copy()

    print("Detected columns:")
    preview_cols = [
        c for c in [
            "English Name (BirdLife > IOC > Clements>AviList)",
            "Latin (BirdLife > IOC > Clements>AviList)",
            "Order",
            "Family IOC 15.1",
            "Genus",
            "Species",
            "2024 IUCN Red List category",
            "ISL",
            "RLM",
            "Primary Habitat",
            "Primary Diet",
            "Nest_Type",
            "Average Mass",
            "Mig",
            "Alt",
            "Irreg",
            "Disp",
            "Sed",
        ] if c in df.columns
    ]
    print(preview_cols)
    return df


def make_client() -> OpenAI:
    if not DEEPSEEK_API_KEY:
        raise ValueError("DEEPSEEK_API_KEY is not set.")
    return OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)


def append_jsonl(records: list[dict], path: Path) -> None:
    if not records:
        return
    with path.open("a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def parse_json_response(content: str) -> dict:
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()
    return json.loads(content)


def stable_question_id(idx: int) -> str:
    return f"list_global_{idx:04d}"


def get_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    normalized = {str(c).strip().lower(): c for c in df.columns}
    for cand in candidates:
        key = cand.strip().lower()
        if key in normalized:
            return normalized[key]
    return None


def top_values(df: pd.DataFrame, colname: str, top_n: int) -> list[str]:
    s = df[colname].astype(str).str.strip()
    vc = s.value_counts()
    return [v for v in vc.index.tolist() if v and v.lower() not in {"nan", "none"}][:top_n]


def cleaned_unique(df: pd.DataFrame, colname: str, min_count: int, max_count: int, top_n: int | None = None):
    s = df[colname].astype(str).str.strip()
    vc = s.value_counts()
    items = []
    for value, count in vc.items():
        vv = normalize_text(value)
        if not vv or vv.lower() in {"nan", "none"}:
            continue
        if min_count <= int(count) <= max_count:
            items.append((vv, s == vv))
    if top_n is not None:
        items = items[:top_n]
    return items


def yes_mask(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(["1", "1.0", "true", "yes", "y"])


def no_mask(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(["0", "0.0", "false", "no", "n"])


# =========================
# Condition builders
# =========================
def build_condition_specs(df: pd.DataFrame) -> tuple[list[dict], str]:
    specs = []

    species_col = get_col(df, [
        "Latin (BirdLife > IOC > Clements>AviList)",
        "IOC World Bird List (v15.1)",
        "eBird/Clements (V2024b)",
        "AviList v1 2025",
        "Species",
    ])
    common_name_col = get_col(df, ["English Name (BirdLife > IOC > Clements>AviList)"])
    iucn_col = get_col(df, ["2024 IUCN Red List category"])
    realm_col = get_col(df, ["RLM"])
    habitat_col = get_col(df, ["Primary Habitat"])
    diet_col = get_col(df, ["Primary Diet"])
    nest_col = get_col(df, ["Nest_Type"])
    island_col = get_col(df, ["ISL"])
    family_col = get_col(df, ["Family IOC 15.1", "Family Clements v2024b", "Family HBW/BirdLife v9.1 (2024)"])
    order_col = get_col(df, ["Order"])
    mass_col = get_col(df, ["Average Mass"])
    mig_col = get_col(df, ["Mig"])
    alt_col = get_col(df, ["Alt"])
    irreg_col = get_col(df, ["Irreg"])
    disp_col = get_col(df, ["Disp"])
    sed_col = get_col(df, ["Sed"])

    print("Column mapping:")
    print({
        "species_col": species_col,
        "common_name_col": common_name_col,
        "iucn_col": iucn_col,
        "realm_col": realm_col,
        "habitat_col": habitat_col,
        "diet_col": diet_col,
        "nest_col": nest_col,
        "island_col": island_col,
        "family_col": family_col,
        "order_col": order_col,
        "mass_col": mass_col,
        "mig_col": mig_col,
        "alt_col": alt_col,
        "irreg_col": irreg_col,
        "disp_col": disp_col,
        "sed_col": sed_col,
    })

    if species_col is None:
        raise ValueError("Could not find a scientific-name column in BIRDBASE after resolving the second header row.")

    # -------- Singles --------
    if iucn_col:
        for value, mask in cleaned_unique(df, iucn_col, min_count=3, max_count=300, top_n=12):
            specs.append({
                "knowledge_domain": "Conservation",
                "search_conditions": f"IUCN Status: {value}",
                "mask": mask,
            })

    if realm_col:
        for value, mask in cleaned_unique(df, realm_col, min_count=10, max_count=160, top_n=50):
            specs.append({
                "knowledge_domain": "Biogeography",
                "search_conditions": f"Zoogeographic Realm: {value}",
                "mask": mask,
            })

    if habitat_col:
        for value, mask in cleaned_unique(df, habitat_col, min_count=10, max_count=1600, top_n=20):
            specs.append({
                "knowledge_domain": "Ecology",
                "search_conditions": f"Primary Habitat: {value}",
                "mask": mask,
            })

    if diet_col:
        for value, mask in cleaned_unique(df, diet_col, min_count=10, max_count=1600, top_n=20):
            specs.append({
                "knowledge_domain": "Ecology",
                "search_conditions": f"Primary Diet: {value}",
                "mask": mask,
            })

    if nest_col:
        for value, mask in cleaned_unique(df, nest_col, min_count=5, max_count=150, top_n=70):
            specs.append({
                "knowledge_domain": "Behavior",
                "search_conditions": f"Nest Type: {value}",
                "mask": mask,
            })

    if family_col:
        for value, mask in cleaned_unique(df, family_col, min_count=5, max_count=80, top_n=100):
            specs.append({
                "knowledge_domain": "Taxonomy",
                "search_conditions": f"Family: {value}",
                "mask": mask,
            })

    if order_col:
        for value, mask in cleaned_unique(df, order_col, min_count=3, max_count=150, top_n=30):
            specs.append({
                "knowledge_domain": "Taxonomy",
                "search_conditions": f"Order: {value}",
                "mask": mask,
            })

    if island_col:
        isl_series = df[island_col]
        ymask = yes_mask(isl_series)
        nmask = no_mask(isl_series)
        if int(ymask.sum()) >= MIN_ANSWER_SIZE:
            specs.append({
                "knowledge_domain": "Biogeography",
                "search_conditions": "Island Endemism: Yes",
                "mask": ymask,
            })
        if int(nmask.sum()) >= MIN_ANSWER_SIZE:
            specs.append({
                "knowledge_domain": "Biogeography",
                "search_conditions": "Island Endemism: No",
                "mask": nmask,
            })

    movement_specs = []
    for col, label in [
        (mig_col, "Migratory Status: Migratory"),
        (alt_col, "Migratory Status: Altitudinal Migrant"),
        (irreg_col, "Movement Pattern: Irregular"),
        (disp_col, "Movement Pattern: Dispersive"),
        (sed_col, "Migratory Status: Sedentary"),
    ]:
        if col:
            mask = yes_mask(df[col])
            if int(mask.sum()) >= MIN_ANSWER_SIZE:
                movement_specs.append((label, mask))
                specs.append({
                    "knowledge_domain": "Behavior",
                    "search_conditions": label,
                    "mask": mask,
                })

    # -------- Pair conditions --------
    def add_pair_specs(col1, col2, domain, label1, label2, top1=20, top2=20, min_n=3, max_n=80):
        values1 = top_values(df, col1, top1)
        values2 = top_values(df, col2, top2)
        s1 = df[col1].astype(str).str.strip()
        s2 = df[col2].astype(str).str.strip()
        for v1 in values1:
            for v2 in values2:
                mask = (s1 == v1) & (s2 == v2)
                n = int(mask.sum())
                if min_n <= n <= max_n:
                    specs.append({
                        "knowledge_domain": domain,
                        "search_conditions": f"{label1}: {v1}; {label2}: {v2}",
                        "mask": mask,
                    })

    if iucn_col and realm_col:
        add_pair_specs(iucn_col, realm_col, "Conservation", "IUCN Status", "Zoogeographic Realm", top1=12, top2=30, min_n=3, max_n=70)

    if iucn_col and habitat_col:
        add_pair_specs(iucn_col, habitat_col, "Conservation", "IUCN Status", "Primary Habitat", top1=12, top2=14, min_n=3, max_n=70)

    if realm_col and habitat_col:
        add_pair_specs(realm_col, habitat_col, "Biogeography", "Zoogeographic Realm", "Primary Habitat", top1=35, top2=14, min_n=3, max_n=80)

    if realm_col and diet_col:
        add_pair_specs(realm_col, diet_col, "Ecology", "Zoogeographic Realm", "Primary Diet", top1=35, top2=14, min_n=3, max_n=80)

    if habitat_col and diet_col:
        add_pair_specs(habitat_col, diet_col, "Ecology", "Primary Habitat", "Primary Diet", top1=14, top2=14, min_n=3, max_n=90)

    if habitat_col and nest_col:
        add_pair_specs(habitat_col, nest_col, "Behavior", "Primary Habitat", "Nest Type", top1=14, top2=40, min_n=3, max_n=70)

    if island_col and realm_col:
        isl_yes = yes_mask(df[island_col])
        isl_no = no_mask(df[island_col])
        s_realm = df[realm_col].astype(str).str.strip()
        for realm in top_values(df, realm_col, 35):
            for label, base_mask in [("Island Endemism: Yes", isl_yes), ("Island Endemism: No", isl_no)]:
                mask = base_mask & (s_realm == realm)
                n = int(mask.sum())
                if 3 <= n <= 70:
                    specs.append({
                        "knowledge_domain": "Biogeography",
                        "search_conditions": f"{label}; Zoogeographic Realm: {realm}",
                        "mask": mask,
                    })

    if realm_col and movement_specs:
        s_realm = df[realm_col].astype(str).str.strip()
        for movement_label, base_mask in movement_specs:
            for realm in top_values(df, realm_col, 30):
                mask = base_mask & (s_realm == realm)
                n = int(mask.sum())
                if 3 <= n <= 70:
                    specs.append({
                        "knowledge_domain": "Behavior",
                        "search_conditions": f"{movement_label}; Zoogeographic Realm: {realm}",
                        "mask": mask,
                    })

    # -------- Mass / extreme value conditions --------
    if mass_col:
        mass = pd.to_numeric(df[mass_col], errors="coerce")
        if int(mass.notna().sum()) >= 100:
            quantiles = mass.quantile([0.05, 0.10, 0.20, 0.80, 0.90, 0.95]).to_dict()

            for q, phrase in [
                (0.05, "among the lightest 5% by average mass"),
                (0.10, "among the lightest 10% by average mass"),
                (0.20, "among the lightest 20% by average mass"),
                (0.80, "among the heaviest 20% by average mass"),
                (0.90, "among the heaviest 10% by average mass"),
                (0.95, "among the heaviest 5% by average mass"),
            ]:
                threshold = quantiles[q]
                mask = mass <= threshold if q < 0.5 else mass >= threshold
                n = int(mask.sum())
                if 5 <= n <= 2500:
                    specs.append({
                        "knowledge_domain": "Morphology",
                        "search_conditions": f"Average Mass: {phrase}",
                        "mask": mask,
                    })

            if realm_col:
                s_realm = df[realm_col].astype(str).str.strip()
                for q, phrase in [
                    (0.10, "among the lightest 10% by average mass"),
                    (0.90, "among the heaviest 10% by average mass"),
                ]:
                    threshold = quantiles[q]
                    base_mask = mass <= threshold if q < 0.5 else mass >= threshold
                    for realm in top_values(df, realm_col, 30):
                        mask = base_mask & (s_realm == realm)
                        n = int(mask.sum())
                        if 3 <= n <= 50:
                            specs.append({
                                "knowledge_domain": "Morphology",
                                "search_conditions": f"Average Mass: {phrase}; Zoogeographic Realm: {realm}",
                                "mask": mask,
                            })

            if habitat_col:
                s_hab = df[habitat_col].astype(str).str.strip()
                for q, phrase in [
                    (0.10, "among the lightest 10% by average mass"),
                    (0.90, "among the heaviest 10% by average mass"),
                ]:
                    threshold = quantiles[q]
                    base_mask = mass <= threshold if q < 0.5 else mass >= threshold
                    for habitat in top_values(df, habitat_col, 12):
                        mask = base_mask & (s_hab == habitat)
                        n = int(mask.sum())
                        if 3 <= n <= 50:
                            specs.append({
                                "knowledge_domain": "Morphology",
                                "search_conditions": f"Average Mass: {phrase}; Primary Habitat: {habitat}",
                                "mask": mask,
                            })

    return specs, species_col


def materialize_examples(df: pd.DataFrame, target_count: int) -> list[dict]:
    specs, species_col = build_condition_specs(df)
    if not specs:
        raise ValueError("No valid search-condition specs could be built from BIRDBASE.")

    rng = random.Random(RANDOM_SEED)
    rng.shuffle(specs)

    domain_buckets: dict[str, list[dict]] = {}
    seen = set()

    for spec in specs:
        matched = df.loc[spec["mask"]].copy()
        if matched.empty:
            continue

        species_list = sorted({
            normalize_text(x)
            for x in matched[species_col].tolist()
            if normalize_text(x) and normalize_text(x).lower() not in {"nan", "none"}
        })

        if not (MIN_ANSWER_SIZE <= len(species_list) <= MAX_ANSWER_SIZE):
            continue

        dedup_key = (
            spec["knowledge_domain"],
            spec["search_conditions"],
            tuple(species_list),
        )
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        domain_buckets.setdefault(spec["knowledge_domain"], []).append({
            "knowledge_domain": spec["knowledge_domain"],
            "search_conditions": spec["search_conditions"],
            "species_list": species_list,
        })

    counts = {k: len(v) for k, v in domain_buckets.items()}
    print(f"Available unique examples by domain: {counts}")

    selected = []
    used_keys = set()

    # First pass: satisfy quotas if possible
    for domain, quota in DOMAIN_QUOTAS.items():
        bucket = domain_buckets.get(domain, [])
        rng.shuffle(bucket)
        take = min(quota, len(bucket))
        for ex in bucket[:take]:
            key = (ex["knowledge_domain"], ex["search_conditions"], tuple(ex["species_list"]))
            if key not in used_keys:
                used_keys.add(key)
                selected.append(ex)

    # Second pass: fill remainder from all leftovers
    leftovers = []
    for domain, bucket in domain_buckets.items():
        for ex in bucket:
            key = (ex["knowledge_domain"], ex["search_conditions"], tuple(ex["species_list"]))
            if key not in used_keys:
                leftovers.append(ex)

    rng.shuffle(leftovers)
    for ex in leftovers:
        if len(selected) >= target_count:
            break
        key = (ex["knowledge_domain"], ex["search_conditions"], tuple(ex["species_list"]))
        if key not in used_keys:
            used_keys.add(key)
            selected.append(ex)

    if len(selected) < target_count:
        print(f"Warning: only materialized {len(selected)} unique examples (target={target_count}).")
    return selected[:target_count]


# =========================
# Generation
# =========================
def generate_one(example: dict, idx: int) -> dict:
    client = make_client()

    prompt = get_list_global_prompt(
        condition_str=example["search_conditions"],
        species_list=example["species_list"],
    )

    resp = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": "You are a precise benchmark question generator."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
    )

    content = resp.choices[0].message.content
    parsed = parse_json_response(content)

    item = {
        "question_id": stable_question_id(idx),
        "dataset": "List-Global",
        "knowledge_domain": parsed.get("knowledge_domain", example["knowledge_domain"]),
        "type": "General",
        "question": parsed["question"],
        "answer": example["species_list"],
        "provenance": {
            "source_db": "BIRDBASE",
            "search_conditions": example["search_conditions"],
        },
    }

    target_entity = parsed.get("target_entity")
    if isinstance(target_entity, str) and target_entity.strip():
        item["target_entity"] = target_entity.strip()

    return item


def write_header_info():
    print(f"Output file: {OUTPUT_FILE}")
    print(f"Target count: {TARGET_COUNT}")
    print(f"Workers: {MAX_WORKERS}")
    print(f"Save every: {SAVE_EVERY}")
    print(f"Random seed: {RANDOM_SEED}")
    print(f"Answer size range: [{MIN_ANSWER_SIZE}, {MAX_ANSWER_SIZE}]")


def main():
    random.seed(RANDOM_SEED)
    write_header_info()

    if OUTPUT_FILE.exists():
        OUTPUT_FILE.unlink()

    df = load_birdbase()
    print(f"Loaded BIRDBASE with {len(df)} data rows and {len(df.columns)} resolved columns")

    examples = materialize_examples(df, TARGET_COUNT)
    total = len(examples)
    print(f"Prepared {total} unique retrieval examples")

    written = 0
    buffer = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(generate_one, ex, i + 1): (i + 1, ex)
            for i, ex in enumerate(examples)
        }

        for future in as_completed(futures):
            idx, ex = futures[future]
            try:
                item = future.result()
                buffer.append(item)
                written += 1

                print(f"Generated {written}/{total}: {item['question_id']}")

                if len(buffer) >= SAVE_EVERY:
                    append_jsonl(buffer, OUTPUT_FILE)
                    print(f"Saved {len(buffer)} items -> {OUTPUT_FILE}")
                    buffer.clear()

            except Exception as e:
                print(f"Failed on example #{idx} ({ex['search_conditions']}): {e}")

    if buffer:
        append_jsonl(buffer, OUTPUT_FILE)
        print(f"Saved {len(buffer)} items -> {OUTPUT_FILE}")
        buffer.clear()

    print(f"Done. Total written: {written}")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
