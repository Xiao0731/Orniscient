from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None  # type: ignore


PROJECT_ROOT = Path(__file__).resolve().parents[2]

INTENT_ROUTES = [
    {
        "name": "conservation_threats",
        "keywords": {"threat", "threats", "conservation", "endangered", "vulnerable", "human", "humans", "predator", "parasite", "disease", "mortality", "decline", "risk"},
        "domains": {"ConservationAndResearch"},
        "predicates": {
            "THREATENED_BY",
            "HAS_CONSERVATION_ACTION",
            "HAS_IUCN_STATUS",
            "HAS_POPULATION_TREND",
            "INTERACTS_WITH_HUMANS",
            "HAS_PREDATOR",
            "HAS_PARASITE",
            "HAS_DISEASE",
            "HAS_MORTALITY_CAUSE",
            "REQUIRES_RESEARCH_ON",
        },
        "predicate_priority": {
            "THREATENED_BY": 8.0,
            "INTERACTS_WITH_HUMANS": 7.0,
            "HAS_MORTALITY_CAUSE": 6.5,
            "HAS_PREDATOR": 6.0,
            "HAS_PARASITE": 5.5,
            "HAS_DISEASE": 5.5,
            "REQUIRES_RESEARCH_ON": 5.0,
            "HAS_POPULATION_TREND": 4.0,
            "HAS_IUCN_STATUS": 2.0,
            "HAS_CONSERVATION_ACTION": 0.5,
        },
    },
    {
        "name": "diet_foraging",
        "keywords": {"diet", "eat", "eats", "food", "forage", "forages", "foraging", "feed", "feeds", "feeding", "prey"},
        "domains": {"EcologyAndDiet"},
        "predicates": {"EATS_ITEM", "EATS_CATEGORY", "FORAGES_BY", "FORAGES_IN_STRATUM", "HAS_ECOLOGICAL_ROLE"},
    },
    {
        "name": "habitat",
        "keywords": {"habitat", "biome", "forest", "wetland", "grassland", "microhabitat", "woodland", "mangrove"},
        "domains": {"Habitat"},
        "predicates": {"INHABITS_BIOME", "USES_MICROHABITAT"},
    },
    {
        "name": "breeding_life_history",
        "keywords": {"breed", "breeds", "breeding", "nest", "nests", "egg", "eggs", "clutch", "parent", "parental", "incubation", "fledging"},
        "domains": {"LifeHistoryAndBreeding"},
        "predicates": {"BREEDS_DURING", "NESTS_AT", "HAS_NEST_STRUCTURE", "HAS_EGG_TRAIT", "HAS_CLUTCH_SIZE", "HAS_PARENTAL_ROLE", "HAS_INCUBATION_PERIOD", "HAS_FLEDGING_PERIOD", "HAS_DEVELOPMENT_NOTE", "HAS_DEMOGRAPHIC_NOTE"},
    },
    {
        "name": "morphology_identification",
        "keywords": {"plumage", "identify", "identification", "morphology", "body", "bill", "wing", "tail", "tarsus", "mass", "length", "diagnostic"},
        "domains": {"MorphologyAndIdentification"},
        "predicates": {"HAS_BODY_LENGTH", "HAS_BODY_MASS", "HAS_WING_LENGTH", "HAS_TAIL_LENGTH", "HAS_BILL_LENGTH", "HAS_TARSUS_LENGTH", "HAS_WINGSPAN", "HAS_PLUMAGE_TRAIT", "HAS_MOLT_PATTERN", "HAS_SEXUAL_DIMORPHISM", "HAS_AGE_DIMORPHISM", "HAS_DIAGNOSTIC_TRAIT", "HAS_STRUCTURE_TRAIT"},
    },
    {
        "name": "vocal_behavior",
        "keywords": {"call", "calls", "song", "songs", "vocal", "sound", "behavior", "courtship", "mating", "pair", "territorial", "locomotion"},
        "domains": {"VocalAndBehavior"},
        "predicates": {"HAS_VOCALIZATION_TYPE", "CALLS_DURING", "HAS_NONVOCAL_SOUND", "HAS_SOUND_DIAGNOSTIC", "HAS_SOCIAL_BEHAVIOR", "HAS_TERRITORIAL_BEHAVIOR", "HAS_LOCOMOTION_STYLE", "HAS_FLIGHT_ABILITY", "HAS_DAILY_ACTIVITY_PATTERN", "HAS_COURTSHIP_BEHAVIOR", "HAS_MATING_SYSTEM", "HAS_PAIR_BOND", "HAS_COPULATION_BEHAVIOR", "HAS_AGONISTIC_BEHAVIOR"},
    },
    {
        "name": "distribution_movement",
        "keywords": {"range", "occur", "occurs", "distribution", "migrate", "migrates", "migration", "winter", "winters", "endemic", "elevation"},
        "domains": {"DistributionAndMovement"},
        "predicates": {"OCCURS_IN", "ENDEMIC_TO", "BREEDS_IN", "WINTERS_IN", "MIGRATES_VIA", "HAS_MIGRATION_PATTERN", "HAS_ELEVATION_RANGE", "HAS_DISTRIBUTION_NOTE"},
    },
    {
        "name": "taxonomy",
        "keywords": {"taxonomy", "taxonomic", "subspecies", "related", "hybrid", "hybridizes", "classification", "phylogeny"},
        "domains": {"TaxonomyAndPhylogeny"},
        "predicates": {"HAS_SUBSPECIES", "HAS_GEOGRAPHIC_VARIATION", "HAS_SUBSPECIES_TRAIT", "HAS_SUBSPECIES_DISTRIBUTION", "HYBRIDIZES_WITH", "RELATED_TO", "HAS_CLASSIFICATION_HISTORY", "HAS_TAXONOMIC_NOTE"},
    },
]


@dataclass
class RetrievedItem:
    fact_id: str
    predicate: str
    fact_domain: str
    object_text: str
    source_chunk_id: str
    source_chapter: str
    evidence_id: str
    evidence_quote: str
    chunk_text: str = ""
    score: float = 0.0


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z][a-z0-9\-]{2,}", value.lower()))


def norm_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Invalid JSONL in {path}: line={line_no} error={exc.msg}") from exc
            if isinstance(row, dict):
                yield row


def load_env(env_file: str) -> None:
    if load_dotenv:
        if env_file:
            load_dotenv(dotenv_path=env_file, override=False)
        else:
            default_env = PROJECT_ROOT / ".env"
            if default_env.exists():
                load_dotenv(dotenv_path=default_env, override=False)


def sample_items(target: str) -> list[RetrievedItem]:
    chunk_prefix = target or "Casuarius casuarius"
    return [
        RetrievedItem(
            fact_id="sample_fact_1",
            predicate="THREATENED_BY",
            fact_domain="ConservationAndResearch",
            object_text="habitat loss and hunting pressure",
            source_chunk_id=f"{chunk_prefix}::sample-threats",
            source_chapter="Conservation",
            evidence_id="sample_evidence_1",
            evidence_quote="Sample evidence placeholder for interface demonstration.",
            chunk_text="Sample chunk excerpt: conservation accounts often summarize direct threats, human pressures, and habitat change.",
            score=10.0,
        ),
        RetrievedItem(
            fact_id="sample_fact_2",
            predicate="INTERACTS_WITH_HUMANS",
            fact_domain="ConservationAndResearch",
            object_text="affected by roads, hunting, or land-use change",
            source_chunk_id=f"{chunk_prefix}::sample-human-interactions",
            source_chapter="Conservation",
            evidence_id="sample_evidence_2",
            evidence_quote="Sample evidence placeholder for interface demonstration.",
            chunk_text="Sample chunk excerpt: local interactions with humans can be important for conservation planning.",
            score=9.0,
        ),
    ]


def infer_intent(question: str) -> dict[str, Any]:
    q_tokens = tokens(question)
    best_route: dict[str, Any] | None = None
    best_overlap = 0
    for route in INTENT_ROUTES:
        overlap = len(q_tokens & route["keywords"])
        if overlap > best_overlap:
            best_overlap = overlap
            best_route = route
    if not best_route:
        return {"name": "general", "domains": set(), "predicates": set(), "keywords": set()}
    return best_route


def resolve_target_from_processed_chunks(claims_dir: Path, *, target: str, question: str) -> tuple[str, set[str], str]:
    processed_path = claims_dir / "processed_unique_chunks.jsonl"
    if not processed_path.exists():
        if target:
            return target, set(), f"processed_unique_chunks.jsonl missing; using literal target={target!r}"
        return "", set(), "processed_unique_chunks.jsonl missing and --target was not provided"

    query_text = target or question
    query_norm = norm_name(query_text)
    query_tokens = set(query_norm.split())
    matches: dict[str, Counter] = defaultdict(Counter)
    name_by_taxon: dict[str, str] = {}
    for row in iter_jsonl(processed_path):
        taxon_id = clean(row.get("subject_taxon_id"))
        if not taxon_id:
            continue
        chunk_id = clean(row.get("chunk_id") or row.get("source_chunk_id"))
        source_doc_id = clean(row.get("source_doc_id"))
        chunk_name = chunk_id.split("::", 1)[0]
        doc_name = re.sub(r"^bow_(species|family)_", "", source_doc_id).replace("_", " ")
        candidates = [chunk_name, doc_name, source_doc_id]
        for candidate in candidates:
            candidate_norm = norm_name(candidate)
            candidate_tokens = set(candidate_norm.split())
            exact = bool(target) and candidate_norm == norm_name(target)
            contains = bool(target) and norm_name(target) in candidate_norm
            question_hit = not target and candidate_tokens and candidate_tokens.issubset(query_tokens)
            if exact or contains or question_hit:
                matches[taxon_id][candidate_norm] += 1
                name_by_taxon.setdefault(taxon_id, chunk_name or doc_name)
    if not matches:
        if target:
            return target, set(), f"no taxon_id match for target={target!r}; falling back to evidence/chunk text matching"
        return "", set(), "could not infer a unique target from the question; please pass --target"
    if not target and len(matches) > 1:
        ranked = sorted(matches.items(), key=lambda item: -sum(item[1].values()))
        if len(ranked) > 1 and sum(ranked[0][1].values()) == sum(ranked[1][1].values()):
            names = [name_by_taxon.get(taxon_id, taxon_id) for taxon_id, _ in ranked[:5]]
            return "", set(), "ambiguous target candidates: " + ", ".join(names) + "; please pass --target"
    best_taxon = max(matches.items(), key=lambda item: sum(item[1].values()))[0]
    return name_by_taxon.get(best_taxon, target or best_taxon), {best_taxon}, f"matched target_taxon_id={best_taxon}"


def object_label(fact: dict[str, Any]) -> str:
    label = clean(fact.get("object_canonical_name") or fact.get("object_canonical_id"))
    if label:
        return label
    value_min = fact.get("value_min")
    value_max = fact.get("value_max")
    unit = clean(fact.get("unit"))
    if value_min is not None or value_max is not None:
        if value_min is not None and value_max is not None and value_min != value_max:
            return clean(f"{value_min}-{value_max} {unit}")
        return clean(f"{value_min if value_min is not None else value_max} {unit}")
    return ""


def load_chunks(paths: list[str], wanted_chunk_ids: set[str]) -> dict[str, str]:
    if not paths or not wanted_chunk_ids:
        return {}
    chunks: dict[str, str] = {}
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            continue
        for row in iter_jsonl(path):
            chunk_id = clean(row.get("chunk_id") or row.get("source_chunk_id"))
            if chunk_id in wanted_chunk_ids:
                chunks[chunk_id] = clean(row.get("text") or row.get("cleaned_text") or row.get("raw_text"))
    return chunks


def retrieve_kg_items(
    *,
    claims_dir: Path,
    facts_dir: Path,
    chunks_paths: list[str],
    question: str,
    target: str,
    top_k: int,
) -> tuple[str, str, list[RetrievedItem]]:
    resolved_target, target_taxon_ids, target_note = resolve_target_from_processed_chunks(claims_dir, target=target, question=question)
    if not resolved_target and not target_taxon_ids:
        raise RuntimeError(target_note)

    intent = infer_intent(question)
    question_tokens = tokens(question)
    target_norm = norm_name(resolved_target or target)
    target_doc_token = target_norm.replace(" ", "_")

    candidate_facts: dict[str, dict[str, Any]] = {}
    for fact_path in (facts_dir / "species_facts.jsonl", facts_dir / "family_facts.jsonl"):
        for fact in iter_jsonl(fact_path):
            taxon_id = clean(fact.get("subject_taxon_id"))
            if target_taxon_ids and taxon_id not in target_taxon_ids:
                continue
            if intent["domains"] and clean(fact.get("fact_domain")) not in intent["domains"]:
                continue
            if intent["predicates"] and clean(fact.get("predicate")) not in intent["predicates"]:
                continue
            fact_id = clean(fact.get("fact_id"))
            if fact_id:
                candidate_facts[fact_id] = fact

    if not candidate_facts and target_taxon_ids and intent["name"] != "general":
        for fact_path in (facts_dir / "species_facts.jsonl", facts_dir / "family_facts.jsonl"):
            for fact in iter_jsonl(fact_path):
                taxon_id = clean(fact.get("subject_taxon_id"))
                if taxon_id in target_taxon_ids:
                    fact_id = clean(fact.get("fact_id"))
                    if fact_id:
                        candidate_facts[fact_id] = fact

    if not candidate_facts:
        raise RuntimeError(f"No local facts matched target={resolved_target!r}. Use --sample-mode to preview the interface.")

    evidence_ids_by_fact: dict[str, list[str]] = defaultdict(list)
    wanted_fact_ids = set(candidate_facts)
    for link in iter_jsonl(facts_dir / "fact_evidence_links.jsonl"):
        fact_id = clean(link.get("fact_id"))
        if fact_id in wanted_fact_ids:
            evidence_ids_by_fact[fact_id].append(clean(link.get("evidence_id")))
    wanted_evidence_ids = {evidence_id for values in evidence_ids_by_fact.values() for evidence_id in values if evidence_id}

    evidence_by_id: dict[str, dict[str, Any]] = {}
    for evidence in iter_jsonl(facts_dir / "evidences.jsonl"):
        evidence_id = clean(evidence.get("evidence_id"))
        if evidence_id not in wanted_evidence_ids:
            continue
        if not target_taxon_ids:
            chunk_id_norm = norm_name(clean(evidence.get("source_chunk_id")))
            doc_norm = norm_name(clean(evidence.get("source_doc_id")).replace("_", " "))
            if target_norm and target_norm not in chunk_id_norm and target_doc_token not in doc_norm:
                continue
        evidence_by_id[evidence_id] = evidence

    rows: list[RetrievedItem] = []
    for fact_id, fact in candidate_facts.items():
        fact_text = " ".join([clean(fact.get("predicate")), clean(fact.get("fact_domain")), object_label(fact)])
        for evidence_id in evidence_ids_by_fact.get(fact_id, []):
            evidence = evidence_by_id.get(evidence_id)
            if not evidence:
                continue
            evidence_text = clean(evidence.get("evidence_quote"))
            score_text = " ".join([fact_text, evidence_text, clean(evidence.get("source_chapter"))])
            score = len(question_tokens & tokens(score_text)) + float(fact.get("confidence") or 0.0)
            if intent["predicates"] and clean(fact.get("predicate")) in intent["predicates"]:
                score += 3.0
            if intent["domains"] and clean(fact.get("fact_domain")) in intent["domains"]:
                score += 2.0
            score += float(intent.get("predicate_priority", {}).get(clean(fact.get("predicate")), 0.0))
            rows.append(
                RetrievedItem(
                    fact_id=fact_id,
                    predicate=clean(fact.get("predicate")),
                    fact_domain=clean(fact.get("fact_domain")),
                    object_text=object_label(fact),
                    source_chunk_id=clean(evidence.get("source_chunk_id")),
                    source_chapter=clean(evidence.get("source_chapter")),
                    evidence_id=evidence_id,
                    evidence_quote=evidence_text,
                    score=score,
                )
            )

    dedup: dict[tuple[str, str], RetrievedItem] = {}
    for row in rows:
        key = (row.fact_id, row.evidence_id)
        if key not in dedup or row.score > dedup[key].score:
            dedup[key] = row
    rows = sorted(dedup.values(), key=lambda item: (-item.score, item.predicate, item.source_chunk_id))[:top_k]
    chunk_texts = load_chunks(chunks_paths, {row.source_chunk_id for row in rows})
    rows = [
        RetrievedItem(**{**row.__dict__, "chunk_text": chunk_texts.get(row.source_chunk_id, "")})
        for row in rows
    ]
    return resolved_target or target, f"{target_note}; intent={intent['name']}", rows


def build_prompts(question: str, target: str, items: list[RetrievedItem]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    vanilla_messages = [
        {"role": "system", "content": "You are an expert assistant for bird ecology. Answer the question directly and concisely."},
        {"role": "user", "content": question},
    ]
    evidence_blocks = []
    for index, item in enumerate(items, start=1):
        block = [
            f"[{index}] predicate={item.predicate}, fact_domain={item.fact_domain}, source_chunk_id={item.source_chunk_id}",
            f"Fact object: {item.object_text}" if item.object_text else "",
            f"Evidence: {item.evidence_quote}" if item.evidence_quote else "",
            f"Chunk excerpt: {item.chunk_text[:1200]}" if item.chunk_text else "",
        ]
        evidence_blocks.append("\n".join(part for part in block if part))
    kg_user = "\n\n".join(
        [
            "Question:",
            question,
            "Target:",
            target or "unknown",
            "Retrieved evidence:",
            "\n\n".join(evidence_blocks) if evidence_blocks else "(no evidence retrieved)",
            "Please answer with evidence-grounded reasoning.",
        ]
    )
    kg_messages = [
        {"role": "system", "content": "You are an expert assistant for bird ecology. Answer the question using the provided evidence. If evidence is insufficient, state the limitation. Do not invent facts beyond the evidence."},
        {"role": "user", "content": kg_user},
    ]
    return vanilla_messages, kg_messages


def print_messages(title: str, messages: list[dict[str, str]]) -> None:
    print(f"[{title}]")
    for message in messages:
        print(f"{message['role'].title()}:")
        print(message["content"])
        print()


def chat_completion(messages: list[dict[str, str]], *, model: str, api_key: str, api_base: str) -> str:
    url = api_base.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 900,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        detail = re.sub(r"(api key\s*:\s*)[^\"\s,}]+", r"\1<redacted>", detail, flags=re.IGNORECASE)
        detail = re.sub(r"(Authorization\s*:\s*Bearer\s+)[^\"\s,}]+", r"\1<redacted>", detail, flags=re.IGNORECASE)
        raise RuntimeError(f"LLM request failed: HTTP {exc.code}: {detail[:500]}") from exc
    except Exception as exc:
        raise RuntimeError(f"LLM request failed: {exc}") from exc
    return clean(response_payload["choices"][0]["message"]["content"])


def api_config(args: argparse.Namespace) -> tuple[str, str]:
    api_key = clean(args.api_key) or clean(os.environ.get("DEEPSEEK_API_KEY")) or clean(os.environ.get("OPENAI_API_KEY"))
    api_base = clean(args.api_base) or clean(os.environ.get("DEEPSEEK_BASE_URL")) or clean(os.environ.get("OPENAI_BASE_URL")) or "https://api.deepseek.com"
    return api_key, api_base


def print_retrieved(items: list[RetrievedItem]) -> None:
    print("[Retrieved Evidence / Chunks]")
    for index, item in enumerate(items, start=1):
        print(f"{index}. fact_id={item.fact_id}")
        print(f"   predicate={item.predicate}")
        print(f"   fact_domain={item.fact_domain}")
        print(f"   source_chunk_id={item.source_chunk_id}")
        if item.object_text:
            print(f"   object={item.object_text}")
        if item.evidence_quote:
            print(f"   evidence={item.evidence_quote[:300]}")
        if item.chunk_text:
            print(f"   chunk_excerpt={item.chunk_text[:300]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a one-question vanilla vs. KG-augmented comparison.")
    parser.add_argument("--question", required=True)
    parser.add_argument("--target", default="")
    parser.add_argument("--model", default="deepseek-chat")
    parser.add_argument("--knowledge-mode", default="kg_v3", choices=["kg_v3", "hybrid", "text_rag"])
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--claims-dir", default="KG/intermediate/claims_final_global_v2")
    parser.add_argument("--facts-dir", default="KG/intermediate/facts_final_global_v2")
    parser.add_argument("--chunks-path", action="append", default=[], help="Optional JSONL chunk store path. Can be passed multiple times.")
    parser.add_argument("--api-base", default="")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--env-file", default="")
    parser.add_argument("--sample-mode", action="store_true")
    parser.add_argument("--no-api", action="store_true")
    args = parser.parse_args()

    load_env(args.env_file)
    if args.knowledge_mode != "kg_v3":
        print(f"[Note] knowledge-mode={args.knowledge_mode} currently uses the deterministic kg_v3 local artifact retriever.")

    if args.sample_mode:
        target = args.target or "Casuarius casuarius"
        items = sample_items(target)[: args.top_k]
        note = "sample-mode"
    else:
        target, note, items = retrieve_kg_items(
            claims_dir=Path(args.claims_dir),
            facts_dir=Path(args.facts_dir),
            chunks_paths=args.chunks_path,
            question=args.question,
            target=args.target,
            top_k=args.top_k,
        )

    vanilla_messages, kg_messages = build_prompts(args.question, target, items)
    print("[Question]")
    print(args.question)
    print()
    print("[Target]")
    print(target or args.target or "(not resolved)")
    print()
    print("[Retrieval Note]")
    print(note)
    print()

    if args.no_api:
        print_messages("Vanilla Prompt", vanilla_messages)
        print_messages("Knowledge-Augmented Prompt", kg_messages)
        print_retrieved(items)
        return 0

    api_key, api_base = api_config(args)
    if not api_key:
        raise SystemExit("Missing API key. Set DEEPSEEK_API_KEY/OPENAI_API_KEY, pass --api-key, or use --no-api / --sample-mode.")

    vanilla_answer = chat_completion(vanilla_messages, model=args.model, api_key=api_key, api_base=api_base)
    kg_answer = chat_completion(kg_messages, model=args.model, api_key=api_key, api_base=api_base)

    print("[Vanilla Answer]")
    print(vanilla_answer)
    print()
    print("[Knowledge-Augmented Answer]")
    print(kg_answer)
    print()
    print_retrieved(items)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
