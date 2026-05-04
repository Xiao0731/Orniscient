import os
import re
import glob
import asyncio
from pathlib import Path
from typing import Iterable

import pandas as pd
import numpy as np
from dotenv import load_dotenv
from lightrag import LightRAG
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from lightrag.utils import setup_logger, wrap_embedding_func_with_attrs

# ============================================================
# Fast Skeleton Builder for Ornithology KG
# ------------------------------------------------------------
# 核心思路：
# 1) 不再对每只鸟做一次重型 LLM 脱水
# 2) 结构化字段直接灌入骨架文档
# 3) Habitat / Geography / Diet / Behavior / Threat 用规则抽取
# 4) 仍然交给 LightRAG 做轻量图谱抽取与入库
# ============================================================

# ------------------------------
# Tunables
# ------------------------------
WORKING_DIR = "./bird_graph_storage"
PROCESSED_LOG = Path("./processed_birds.log")
INSERT_FLUSH_SIZE = 64
CHUNK_TOKEN_SIZE = 800
LLM_MODEL_MAX_ASYNC = 4
EMBEDDING_FUNC_MAX_ASYNC = 8
EMBEDDING_BATCH_NUM = 32
MAX_PARALLEL_INSERT = 8

# 如果你想只跑某几个文件，改这里；默认跑 ./data/BOW/*.xlsx
BOW_GLOB = "./data/BOW/*.xlsx"

# 是否在骨架文档里保留一个很短的 source summary，帮助 LightRAG 更稳定抽取
INCLUDE_SOURCE_EVIDENCE = True
SOURCE_EVIDENCE_MAX_CHARS = 1200

load_dotenv(override=True)
setup_logger("lightrag", level="INFO")
os.makedirs(WORKING_DIR, exist_ok=True)

# ------------------------------
# 与原 test_LightRAG.py 对齐的数据库默认值
# 若 .env 里已有配置，会优先使用 .env
# ------------------------------
os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
os.environ.setdefault("NEO4J_USERNAME", "neo4j")
os.environ.setdefault("NEO4J_PASSWORD", "deng9q768")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_USER", "postgres")
os.environ.setdefault("POSTGRES_PASSWORD", "lightrag_password")
os.environ.setdefault("POSTGRES_DATABASE", "lightrag")

# 保留你的 sparse KG 约束，让 LightRAG 抽图时继续收敛
ONTOLOGY_GUIDANCE = """
[CRITICAL INSTRUCTION: ORNITHOLOGY BENCHMARK SCHEMA V5 - EXTREME SUMMARIZATION]
Objective: Extract a MINIMALIST, high-level biological skeletal outline.
Context: You are processing one small chunk of a massive monograph. You MUST act with extreme restraint.

**1. The "Global Significance & Anti-Explosion" Rule (STRICT):**
- DO NOT extract every fact. Only extract DEFINING, PRIMARY characteristics of the species.
- If a chunk discusses secondary details, IGNORE THEM COMPLETELY.
- [CRITICAL] Your goal is to keep the final graph under 20 edges per bird. Do NOT invent new nodes if a broad category already fits.

**2. Entity Extraction Rules (STRICT LIMITS):**
- "Species": The central biological entity.
- "Taxon": ONLY Order, Family, and Genus. (Max 3 nodes per species).
- "Habitat": Broad biomes only (e.g., "Freshwater Wetlands", "Tropical Forests", "Savanna").
- "Geography": Continental or Regional scale ONLY (e.g., "Sub-Saharan Africa", "Neotropics").
- "Food": Primary diet categories ONLY (e.g., "Insects", "Seeds", "Small Fish", "Aquatic Vegetation").
- "Behavior": Broad life-history traits (e.g., "Migratory", "Ground-nesting", "Monogamous").
- "Threat": Top major anthropogenic or environmental threats (e.g., "Habitat Loss", "Hybridization").
- "ConservationStatus": Official IUCN category only.

**3. Allowed Relationship Types:**
- [Species] -BELONGS_TO-> [Taxon]
- [Species] -INHABITS-> [Habitat]
- [Species] -FOUND_IN-> [Geography]
- [Species] -PREYS_ON-> [Food]
- [Species] -EXHIBITS-> [Behavior]
- [Species] -THREATENED_BY-> [Threat]
- [Species] -HAS_STATUS-> [ConservationStatus]
- [Species] -RELATED_TO-> [Species]

**4. Aggregation, Noise Filtering & Orphan Prevention (CRITICAL):**
- CONNECTIVITY MANDATE: Every extracted non-species entity MUST have a direct relationship with a "Species" node in this chunk.
- SYNONYM MERGING: Group specific items into one. "Freshwater marsh", "River", and "Pond" must ALL be extracted simply as "Freshwater Wetlands".
- NO ADJECTIVE NODES: Do not create nodes for "Large", "Red", "Small".
- NO CITATIONS/DATA NOISE: Remove citations, sample sizes, or any reference numbers.
- QUANTITY CAP PER CHUNK: A single chunk should rarely produce more than 3-5 new relationships. Be ruthlessly concise.
""".strip()

# ------------------------------
# Rule dictionaries
# ------------------------------
HABITAT_RULES = {
    "Freshwater Wetlands": [
        r"\bfreshwater wetlands?\b", r"\bmarsh(?:es)?\b", r"\bswamp(?:s)?\b",
        r"\bpond(?:s)?\b", r"\briver(?:s)?\b", r"\blake(?:s)?\b",
        r"\bwetland(?:s)?\b", r"\bfen(?:s)?\b", r"\bbog(?:s)?\b"
    ],
    "Mangroves": [r"\bmangrove(?:s)?\b"],
    "Tropical Forests": [
        r"\btropical forest(?:s)?\b", r"\brainforest(?:s)?\b", r"\bprimary forest(?:s)?\b",
        r"\blowland forest(?:s)?\b", r"\bevergreen forest(?:s)?\b"
    ],
    "Montane Forests": [r"\bmontane forest(?:s)?\b", r"\bcloud forest(?:s)?\b", r"\bsubmontane forest(?:s)?\b"],
    "Temperate Forests": [r"\btemperate forest(?:s)?\b", r"\bdeciduous forest(?:s)?\b", r"\bmixed forest(?:s)?\b"],
    "Savanna": [r"\bsavann?a\b", r"\bgrassland(?:s)?\b", r"\bopen country\b"],
    "Marine Coastal": [r"\bcoast(?:al)?\b", r"\bestuar(?:y|ies)\b", r"\bshore\b", r"\bmarine\b", r"\btidal\b"],
    "Arid Shrubland": [r"\barid\b", r"\bdesert\b", r"\bshrubland\b", r"\bsemi-arid\b"],
    "Alpine": [r"\balpine\b", r"\bhigh mountain\b", r"\bsubalpine\b"],
    "Agricultural Landscapes": [r"\bcropland\b", r"\bfarmland\b", r"\bagricultural\b", r"\bpasture\b", r"\brice field(?:s)?\b"],
    "Urban Areas": [r"\burban\b", r"\bcity\b", r"\bsuburban\b", r"\bgarden(?:s)?\b", r"\bparkland\b"],
}

DIET_RULES = {
    "Insects": [r"\binsectivor", r"\binsects?\b", r"\bart[h]?ropods?\b", r"\binvertebrates?\b", r"\blarvae\b"],
    "Seeds": [r"\bgranivor", r"\bseeds?\b", r"\bgrains?\b"],
    "Fruit": [r"\bfrugivor", r"\bfruit\b", r"\bberries\b", r"\bfigs?\b"],
    "Nectar": [r"\bnectar\b", r"\bnectarivor"],
    "Small Fish": [r"\bfish\b", r"\bpiscivor"],
    "Aquatic Vegetation": [r"\baquatic vegetation\b", r"\bwater plants?\b", r"\bmacrophytes?\b"],
    "Small Vertebrates": [r"\bsmall vertebrates?\b", r"\blizards?\b", r"\bfrogs?\b", r"\brodents?\b"],
    "Carrion": [r"\bcarrion\b", r"\bscaveng"],
    "Crustaceans": [r"\bcrustaceans?\b", r"\bcrabs?\b", r"\bshrimp\b"],
    "Mollusks": [r"\bmollusks?\b", r"\bsnails?\b", r"\bbivalves?\b"],
}

BEHAVIOR_RULES = {
    "Migratory": [r"\bmigrat", r"\blong-distance migrant", r"\bpartial migrant", r"\bseasonal migrant"],
    "Resident": [r"\bresident\b", r"\bsedentary\b"],
    "Nomadic": [r"\bnomadic\b"],
    "Ground-nesting": [r"\bground[- ]nest", r"\bnests? on the ground\b"],
    "Cavity-nesting": [r"\bcavity[- ]nest", r"\bnests? in cavities\b", r"\bhole[- ]nest\b"],
    "Tree-nesting": [r"\bnests? in trees\b", r"\btree[- ]nest\b"],
    "Colonial": [r"\bcolonial\b", r"\bnests? in colonies\b"],
    "Monogamous": [r"\bmonogam"],
    "Polygynous": [r"\bpolygyn"],
    "Arboreal": [r"\barboreal\b", r"\bforages? in trees\b"],
    "Aquatic Foraging": [r"\bdives?\b", r"\bwades?\b", r"\bforages? in shallow water\b", r"\bswims?\b"],
    "Nocturnal": [r"\bnocturnal\b", r"\bactive at night\b"],
}

THREAT_RULES = {
    "Habitat Loss": [r"\bhabitat loss\b", r"\bhabitat destruction\b", r"\bdeforestation\b", r"\bdrainage\b", r"\bland conversion\b"],
    "Habitat Fragmentation": [r"\bfragmentation\b"],
    "Invasive Species": [r"\binvasive\b", r"\bintroduced predators?\b", r"\bexotic predators?\b", r"\bferal (?:cats?|dogs?)\b", r"\brats?\b"],
    "Hunting": [r"\bhunting\b", r"\btrapping\b", r"\bpersecution\b", r"\bpoaching\b"],
    "Climate Change": [r"\bclimate change\b", r"\bsea-level rise\b", r"\bwarming\b"],
    "Pollution": [r"\bpollution\b", r"\bpesticides?\b", r"\bcontamination\b", r"\boil spill\b"],
    "Hybridization": [r"\bhybridization\b"],
    "Human Disturbance": [r"\bdisturbance\b", r"\btourism\b", r"\bhuman activity\b"],
    "Overgrazing": [r"\bovergrazing\b"],
    "Water Management": [r"\bwater extraction\b", r"\bdam(?:ming)?\b", r"\bwetland drainage\b"],
}

GEOGRAPHY_RULES = {
    "Neotropics": [r"\bneotropic", r"\bamazon\b", r"\bsouth america\b", r"\bcentral america\b", r"\bcaribbean\b"],
    "Nearctic": [r"\bnorth america\b", r"\bnearctic\b"],
    "Palearctic": [r"\bpalearctic\b", r"\beurope\b", r"\bcentral asia\b", r"\bnorth africa\b", r"\bwestern palearctic\b"],
    "Afrotropics": [r"\bsub-saharan africa\b", r"\bafrotropic\b", r"\bafrica south of the sahara\b"],
    "Indomalaya": [r"\bindia\b", r"\bsouth asia\b", r"\bsoutheast asia\b", r"\bindomalaya\b"],
    "Australasia": [r"\baustralia\b", r"\bnew guinea\b", r"\baustralasia\b"],
    "Oceania": [r"\bpolynesia\b", r"\bmicronesia\b", r"\bmelanesia\b", r"\boceania\b"],
    "Antarctic/Subantarctic": [r"\bantarctic\b", r"\bsubantarctic\b"],
    "Indian Ocean Islands": [r"\bindian ocean\b", r"\bmascarene\b", r"\bseychelles\b", r"\bmadagascar\b"],
}

# 常见生境归一化预处理
NORMALIZATION_REPLACEMENTS = {
    r"\bfreshwater marsh(?:es)?\b": "Freshwater Wetlands",
    r"\briver(?:s)?\b": "Freshwater Wetlands",
    r"\bpond(?:s)?\b": "Freshwater Wetlands",
    r"\bswamp(?:s)?\b": "Freshwater Wetlands",
    r"\blake(?:s)?\b": "Freshwater Wetlands",
    r"\bmangrove(?:s)?\b": "Mangroves",
    r"\bprimary forest(?:s)?\b": "Tropical Forests",
    r"\bmontane forest(?:s)?\b": "Montane Forests",
    r"\bcloud forest(?:s)?\b": "Montane Forests",
}

STATUS_CANONICAL = {
    "LC": "Least Concern",
    "NT": "Near Threatened",
    "VU": "Vulnerable",
    "EN": "Endangered",
    "CR": "Critically Endangered",
    "EW": "Extinct in the Wild",
    "EX": "Extinct",
    "DD": "Data Deficient",
    "NE": "Not Evaluated",
}


def clean_visuals_and_citations(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = re.sub(r'\(?[Ff]ig\.?\s*\d+\)?', '', text)
    text = re.sub(r'\(?[Pp]late\s*\d+\)?', '', text)
    text = re.sub(r'\(?[Pp]hoto.*?\)?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\([A-Z][a-z]+ (et al\.)?, \d{4}\)', '', text)
    text = re.sub(r'\[\d+(,\s*\d+)*\]', '', text)
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()


def normalize_before_rules(text: str) -> str:
    out = text
    for pat, repl in NORMALIZATION_REPLACEMENTS.items():
        out = re.sub(pat, repl, out, flags=re.IGNORECASE)
    return out


def load_inserted() -> set[str]:
    if not PROCESSED_LOG.exists():
        return set()
    return {line.strip() for line in PROCESSED_LOG.read_text(encoding="utf-8").splitlines() if line.strip()}


def mark_inserted(name: str) -> None:
    with PROCESSED_LOG.open("a", encoding="utf-8") as f:
        f.write(name + "\n")


def canonical_status(raw: str) -> str:
    raw = (raw or "NE").strip().upper()
    return STATUS_CANONICAL.get(raw, raw)


def extract_labels(text: str, rule_map: dict[str, list[str]], max_n: int) -> list[str]:
    hits: list[str] = []
    lowered = text.lower()
    for label, patterns in rule_map.items():
        for pat in patterns:
            if re.search(pat, lowered, flags=re.IGNORECASE):
                hits.append(label)
                break
    return hits[:max_n]


def extract_source_evidence(text: str, max_chars: int = SOURCE_EVIDENCE_MAX_CHARS) -> str:
    text = text.strip()
    if not text:
        return ""
    # 优先截取带关键词的句子，增强 LightRAG 对骨架关系的抽取稳定性
    sentences = re.split(r'(?<=[.!?])\s+', text)
    keywords = [
        "habitat", "distribution", "range", "diet", "feeds", "forages",
        "nest", "breeding", "migrat", "threat", "decline", "conservation", "status"
    ]
    chosen: list[str] = []
    total = 0
    for sent in sentences:
        s = sent.strip()
        if not s:
            continue
        s_lower = s.lower()
        if any(k in s_lower for k in keywords):
            if total + len(s) + 1 > max_chars:
                break
            chosen.append(s)
            total += len(s) + 1
    if not chosen:
        return text[:max_chars]
    return " ".join(chosen)


def safe_text(val: object) -> str:
    if pd.isna(val):
        return ""
    return str(val).strip()


def process_bow_file_structured(file_path: str) -> list[dict]:
    if file_path.lower().endswith(".csv"):
        df = pd.read_csv(file_path)
    else:
        df = pd.read_excel(file_path)

    # 最大程度兼容你现有数据格式
    for col in ["Common_name", "Species", "Genus", "Family", "Order", "Level"]:
        if col not in df.columns:
            df[col] = ""
    if "text" not in df.columns:
        raise ValueError(f"File has no 'text' column: {file_path}")

    df["Common_name"] = df["Common_name"].ffill().astype(str).str.strip()
    df["Species"] = df["Species"].ffill().astype(str).apply(lambda x: x.split("\n")[0].strip())
    df["Genus"] = df["Genus"].ffill().astype(str).str.strip()
    df["Family"] = df["Family"].ffill().astype(str).str.strip()
    df["Order"] = df["Order"].ffill().astype(str).str.strip()
    df["Level"] = df["Level"].ffill().fillna("NE").astype(str).str.strip().replace("", "NE")

    grouped = (
        df.groupby(["Common_name", "Species", "Genus", "Family", "Order", "Level"], dropna=False)["text"]
        .apply(lambda x: "\n".join(x.dropna().astype(str)))
        .reset_index()
    )

    birds: list[dict] = []
    for _, row in grouped.iterrows():
        common_name = safe_text(row["Common_name"])
        if not common_name:
            continue
        cleaned_text = clean_visuals_and_citations(safe_text(row["text"]))
        cleaned_text = normalize_before_rules(cleaned_text)
        birds.append(
            {
                "common_name": common_name,
                "species": safe_text(row["Species"]),
                "genus": safe_text(row["Genus"]),
                "family": safe_text(row["Family"]),
                "order": safe_text(row["Order"]),
                "level": canonical_status(safe_text(row["Level"])),
                "text": cleaned_text,
            }
        )
    return birds


def build_skeleton_doc(bird: dict) -> str:
    text = bird["text"]

    habitats = extract_labels(text, HABITAT_RULES, max_n=3)
    diets = extract_labels(text, DIET_RULES, max_n=2)
    behaviors = extract_labels(text, BEHAVIOR_RULES, max_n=3)
    threats = extract_labels(text, THREAT_RULES, max_n=2)
    geos = extract_labels(text, GEOGRAPHY_RULES, max_n=2)

    habitats_str = ", ".join(habitats) if habitats else "Unknown"
    diets_str = ", ".join(diets) if diets else "Unknown"
    behaviors_str = ", ".join(behaviors) if behaviors else "Unknown"
    threats_str = ", ".join(threats) if threats else "Unknown"
    geos_str = ", ".join(geos) if geos else "Unknown"

    evidence_section = ""
    if INCLUDE_SOURCE_EVIDENCE:
        evidence = extract_source_evidence(text, SOURCE_EVIDENCE_MAX_CHARS)
        evidence_section = f"\n\n## Source Evidence Snippet\n{evidence}" if evidence else ""

    return f"""
# Species: {bird['common_name']} ({bird['species'] or 'Unknown scientific name'})

## Taxonomy
Order: {bird['order'] or 'Unknown'}
Family: {bird['family'] or 'Unknown'}
Genus: {bird['genus'] or 'Unknown'}

## Geographic Distribution
Primary region: {geos_str}

## Macro-Habitat
Primary habitats: {habitats_str}

## Dietary Niche
Primary diet: {diets_str}

## Life History and Behavior
Primary behavior traits: {behaviors_str}

## Conservation Status and Threats
IUCN status: {bird['level'] or 'Not Evaluated'}
Primary threats: {threats_str}
{evidence_section}
""".strip()


async def llm_model_func(prompt, system_prompt=None, history_messages=None, keyword_extraction=False, **kwargs):
    history_messages = history_messages or []
    if system_prompt and "extract" in system_prompt.lower():
        system_prompt = ONTOLOGY_GUIDANCE + "\n" + system_prompt
    model_name = os.environ.get("KG_LLM_MODEL", "deepseek-chat").strip() or "deepseek-chat"
    return await openai_complete_if_cache(
        model_name,
        prompt,
        system_prompt=system_prompt,
        history_messages=history_messages,
        api_key=os.environ.get("OPENAI_API_KEY", "").strip(),
        base_url=os.environ.get("OPENAI_BASE_URL", "").strip(),
        **kwargs,
    )


@wrap_embedding_func_with_attrs(embedding_dim=1024, max_token_size=8192, model_name="BAAI/bge-m3")
async def my_embedding_func(texts: list[str]) -> np.ndarray:
    return await openai_embed.func(
        texts,
        model="BAAI/bge-m3",
        api_key=os.environ.get("EMBEDDING_API_KEY", "").strip(),
        base_url=os.environ.get("EMBEDDING_BASE_URL", "").strip(),
    )


async def flush_insert(rag: LightRAG, pending: list[tuple[str, str]], inserted: set[str]) -> tuple[int, int]:
    if not pending:
        return 0, 0

    docs = [doc for _, doc in pending]
    names = [name for name, _ in pending]
    ok = 0
    fail = 0

    try:
        await rag.ainsert(docs)
        for name in names:
            mark_inserted(name)
            inserted.add(name)
            ok += 1
    except Exception as batch_error:
        print(f"⚠️ 批量插入失败，回退到单条插入: {batch_error}")
        for name, doc in pending:
            if name in inserted:
                continue
            try:
                await rag.ainsert(doc)
                mark_inserted(name)
                inserted.add(name)
                ok += 1
            except Exception as single_error:
                print(f"❌ 单条插入失败: {name} -> {single_error}")
                fail += 1
    finally:
        pending.clear()

    return ok, fail


def build_lightrag_runtime(
    *,
    working_dir: str = WORKING_DIR,
    chunk_token_size: int = CHUNK_TOKEN_SIZE,
    llm_model_max_async: int = LLM_MODEL_MAX_ASYNC,
    embedding_func_max_async: int = EMBEDDING_FUNC_MAX_ASYNC,
    embedding_batch_num: int = EMBEDDING_BATCH_NUM,
    max_parallel_insert: int = MAX_PARALLEL_INSERT,
) -> LightRAG:
    """Create a LightRAG runtime using the existing V1 storage/runtime defaults."""

    return LightRAG(
        working_dir=working_dir,
        llm_model_func=llm_model_func,
        embedding_func=my_embedding_func,
        chunk_token_size=chunk_token_size,
        llm_model_max_async=llm_model_max_async,
        embedding_func_max_async=embedding_func_max_async,
        embedding_batch_num=embedding_batch_num,
        max_parallel_insert=max_parallel_insert,
        enable_llm_cache=True,
        enable_llm_cache_for_entity_extract=True,
        kv_storage="PGKVStorage",
        vector_storage="PGVectorStorage",
        graph_storage="Neo4JStorage",
        doc_status_storage="PGDocStatusStorage",
    )


async def ingest_named_docs(
    rag: LightRAG,
    named_docs: Iterable[tuple[str, str]],
    *,
    processed_log: Path | None = None,
    flush_size: int = INSERT_FLUSH_SIZE,
) -> dict[str, int]:
    """Reusable async batch ingest with the same fallback behavior as V1."""

    log_path = processed_log or PROCESSED_LOG
    inserted = (
        {line.strip() for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()}
        if log_path.exists()
        else set()
    )
    pending: list[tuple[str, str]] = []
    total_seen = 0
    total_ok = 0
    total_fail = 0

    def _mark(name: str) -> None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(name + "\n")

    async def _flush() -> None:
        nonlocal total_ok, total_fail
        if not pending:
            return
        docs = [doc for _, doc in pending]
        names = [name for name, _ in pending]
        try:
            await rag.ainsert(docs)
            for name in names:
                if name not in inserted:
                    inserted.add(name)
                    _mark(name)
                    total_ok += 1
        except Exception:
            for name, doc in pending:
                if name in inserted:
                    continue
                try:
                    await rag.ainsert(doc)
                    inserted.add(name)
                    _mark(name)
                    total_ok += 1
                except Exception:
                    total_fail += 1
        finally:
            pending.clear()

    for name, doc in named_docs:
        total_seen += 1
        if name in inserted:
            continue
        pending.append((name, doc))
        if len(pending) >= flush_size:
            await _flush()
    await _flush()
    return {"seen": total_seen, "inserted": total_ok, "failed": total_fail, "processed_log_size": len(inserted)}


def iter_bow_files() -> list[str]:
    all_files = glob.glob(BOW_GLOB)
    all_files = [f for f in all_files if os.path.basename(f).split("-")[0].isdigit()]
    all_files.sort(key=lambda x: int(os.path.basename(x).split("-")[0]))
    return all_files


async def main() -> None:
    rag = build_lightrag_runtime()

    await rag.initialize_storages()

    try:
        inserted = load_inserted()
        all_files = iter_bow_files()

        print(f"Found {len(all_files)} files; {len(inserted)} birds already inserted.")

        pending_insert: list[tuple[str, str]] = []
        total_seen = 0
        total_ok = 0
        total_fail = 0

        for file_path in all_files:
            print(f"\n{'=' * 70}\n📂 Reading: {file_path}")
            birds = process_bow_file_structured(file_path)
            print(f"   Parsed {len(birds)} birds from file")

            for bird in birds:
                total_seen += 1
                name = bird["common_name"]
                if name in inserted:
                    continue

                doc = build_skeleton_doc(bird)
                pending_insert.append((name, doc))

                if len(pending_insert) >= INSERT_FLUSH_SIZE:
                    ok, fail = await flush_insert(rag, pending_insert, inserted)
                    total_ok += ok
                    total_fail += fail
                    print(f"   ✅ Flushed batch | success={ok} fail={fail} total_inserted={len(inserted)}")

        if pending_insert:
            ok, fail = await flush_insert(rag, pending_insert, inserted)
            total_ok += ok
            total_fail += fail
            print(f"   ✅ Final flush | success={ok} fail={fail} total_inserted={len(inserted)}")

        print("\n🎉 Skeleton KG build finished.")
        print(f"   Total seen: {total_seen}")
        print(f"   Newly inserted: {total_ok}")
        print(f"   Failed inserts: {total_fail}")
        print(f"   Processed log size: {len(inserted)}")

    finally:
        try:
            await rag.finalize_storages()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
