from __future__ import annotations

from collections import defaultdict
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    from birdbase_table_utils import apply_birdbase_constraints, normalize_species_name, parse_birdbase_constraints_from_text
    from text_rag_runtime import RetrievalResult, TextRAGCorpus, tokenize
except ModuleNotFoundError:
    from evaluation.text_RAG.birdbase_table_utils import apply_birdbase_constraints, normalize_species_name, parse_birdbase_constraints_from_text
    from evaluation.text_RAG.text_rag_runtime import RetrievalResult, TextRAGCorpus, tokenize


TYPE_CHAPTER_HINTS = {
    "Morphological Diagnosis": ["identification", "field identification", "plumages", "measurements", "similar species"],
    "Behavioral Fingerprint": ["behavior", "habitat", "diet", "foraging", "breeding", "movement"],
    "Acoustic & Phenological ID": ["sounds", "vocal", "breeding", "season", "movement"],
    "Sex & Age Diagnosis": ["plumages", "bare parts", "measurements", "molt"],
}

HIGH_FREQUENCY_GENERIC_TOKENS = {
    "juvenile", "plumage", "adult", "male", "female", "wing", "molt", "basic", "formative", "definitive",
    "similar", "feathers",
}

DISCRIMINATIVE_TOKENS = {
    "flightless", "island", "coastal", "nocturnal", "bill", "feet", "legs", "stripe", "striped", "crest",
    "mask", "tail", "crown", "speculum", "supercilium", "chevron", "wetland", "forest", "marsh", "desert",
    "river", "lake", "mountain", "swamp", "resident", "endemic", "voice", "call",
}

IDENTIFICATION_HINT_TERMS = {
    "male", "female", "adult", "juvenile", "immature", "plumage", "bill", "wing", "tail", "head", "crown",
    "breast", "flank", "eye", "supercilium", "speculum", "crest", "size", "weight", "length", "voice", "call",
    "song", "vocal", "habitat", "forest", "marsh", "wetland", "coastal", "island", "range", "migration",
    "breeding", "resident", "endemic", "behavior", "foraging",
}

CITATION_HEAVY_PATTERNS = [
    r"review of the evidence",
    r"following plumage descriptions",
    r"\b[A-Z][a-z]+ et al\.",
    r"\(\d+\s+[A-Z][a-z]+,\s*[A-Z]\.",
    r"\b[A-Z][a-z]+,\s*[A-Z]\.",
    r"\b(Master'?s|Ph\.?D\.?|thesis|unpubl\.|unpublished|journal|university|report)\b",
    r"\b(handbook|phylogenetic analysis|references|copyright|winter wing molt)\b",
    r"\b\d{4}\b",
    r"https?://",
]


def _species_key(result: RetrievalResult) -> str:
    scientific = str(result.chunk.species or "").strip()
    return scientific or str(result.chunk.common_name or "").strip()


def _chapter_type_bonus(result: RetrievalResult, item_type: str) -> float:
    labels = " ".join([result.chunk.chapter, result.chunk.source_chapter_raw, result.chunk.source_subchapter]).lower()
    bonus = 0.0
    for hint in TYPE_CHAPTER_HINTS.get(item_type, []):
        if hint in labels:
            bonus += 6.0
    return bonus


def _token_weight(token: str, idf: dict[str, float]) -> float:
    weight = float(idf.get(token, 1.0))
    if token in HIGH_FREQUENCY_GENERIC_TOKENS:
        weight *= 0.35
    if token in DISCRIMINATIVE_TOKENS:
        weight *= 1.8
    if len(token) >= 8:
        weight *= 1.15
    return weight


def _weighted_overlap_bonus(corpus: TextRAGCorpus, chunk_text: str, query_tokens: list[str]) -> float:
    chunk_tokens = set(tokenize(chunk_text))
    return sum(_token_weight(token, corpus._idf) for token in set(query_tokens) if token in chunk_tokens)  # type: ignore[attr-defined]


def _retrieve_type_prefiltered_results(
    corpus: TextRAGCorpus,
    query_text: str,
    item_type: str,
    top_k: int,
) -> list[RetrievalResult]:
    hints = [hint.lower() for hint in TYPE_CHAPTER_HINTS.get(item_type, [])]
    all_species_chunks = [chunk for chunk in corpus.chunks if chunk.source_type == "species"]
    preferred_chunks = []
    if hints:
        for chunk in all_species_chunks:
            labels = " ".join([chunk.chapter, chunk.source_chapter_raw, chunk.source_subchapter]).lower()
            if any(hint in labels for hint in hints):
                preferred_chunks.append(chunk)
    candidate_chunks = preferred_chunks if len(preferred_chunks) >= 500 else all_species_chunks

    q_tokens = tokenize(query_text)
    q_set = set(q_tokens)
    scored: list[RetrievalResult] = []
    for chunk in candidate_chunks:
        score, matched = corpus._score_by_text(chunk, q_tokens, q_set, target_norm="")  # type: ignore[attr-defined]
        score += _weighted_overlap_bonus(corpus, " ".join([chunk.chapter, chunk.source_chapter_raw, chunk.source_subchapter, chunk.text]), q_tokens)
        labels = " ".join([chunk.chapter, chunk.source_chapter_raw, chunk.source_subchapter]).lower()
        chapter_bonus = 0.0
        for hint in hints:
            if hint in labels:
                chapter_bonus += 6.0
        score += chapter_bonus
        if chapter_bonus:
            matched.append(f"chapter_prefilter:{chapter_bonus:.1f}")
        if score > 0:
            scored.append(RetrievalResult(chunk=chunk, score=score, matched_on=matched))
    scored.sort(key=lambda row: (-row.score, row.chunk.chunk_id))
    return scored[:top_k]


@lru_cache(maxsize=1)
def _canonical_species_common_name_map() -> dict[str, str]:
    path = Path("kg_v2") / "outputs" / "intermediate" / "taxonomy" / "canonical_taxon_nodes.jsonl"
    mapping: dict[str, str] = {}
    if not path.exists():
        return mapping
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(obj.get("rank", "")).strip().lower() != "species":
                continue
            scientific = normalize_species_name(obj.get("scientific_name", ""))
            english = str(obj.get("english_name_primary", "")).strip()
            if scientific and english and scientific not in mapping:
                mapping[scientific] = english
    return mapping


def _best_common_name(scientific_name: str, fallback_common_name: str) -> str:
    canonical_map = _canonical_species_common_name_map()
    canonical = canonical_map.get(normalize_species_name(scientific_name), "")
    return canonical or fallback_common_name


def _split_sentences(text: str) -> list[str]:
    clean = str(text or "").replace("\n", " ").strip()
    if not clean:
        return []
    pieces = re.split(r"(?<=[.!?;])\s+", clean)
    return [piece.strip(" -") for piece in pieces if piece.strip()]


def _score_evidence_sentence(sentence: str, chapter: str, item_type: str, query_tokens: list[str] | None = None) -> float:
    lower = sentence.lower()
    score = 0.0
    if 35 <= len(sentence) <= 280:
        score += 2.0
    if any(term in lower for term in IDENTIFICATION_HINT_TERMS):
        score += 5.0
    if any(hint in chapter.lower() for hint in TYPE_CHAPTER_HINTS.get(item_type, [])):
        score += 2.0
    if re.search(r"\b(male|female|adult|juvenile|immature)\b", lower):
        score += 2.5
    if re.search(r"\b(bill|wing|tail|head|crown|breast|flank|speculum|supercilium|crest)\b", lower):
        score += 2.5
    if re.search(r"\b(call|song|voice|vocal)\b", lower):
        score += 2.0
    if re.search(r"\b(habitat|forest|wetland|marsh|coastal|island|endemic|range)\b", lower):
        score += 2.0
    if query_tokens:
        distinctive_overlap = [
            token for token in set(query_tokens)
            if token not in HIGH_FREQUENCY_GENERIC_TOKENS and len(token) >= 4 and token in lower
        ]
        score += min(len(distinctive_overlap), 6) * 1.4
    for pattern in CITATION_HEAVY_PATTERNS:
        if re.search(pattern, sentence, flags=re.IGNORECASE):
            score -= 12.0
    if len(re.findall(r"\(", sentence)) >= 2:
        score -= 3.0
    if lower.startswith(("introduction", "acknowledgements", "about the author")):
        score -= 4.0
    return score


def _select_evidence_snippet(result: RetrievalResult, item_type: str, query_text: str = "") -> str:
    chapter = result.chunk.chapter or result.chunk.source_chapter_raw or ""
    query_tokens = tokenize(query_text) if query_text else []
    sentences = _split_sentences(result.chunk.text)
    preferred_sentences = [
        sentence for sentence in sentences
        if not any(re.search(pattern, sentence, flags=re.IGNORECASE) for pattern in CITATION_HEAVY_PATTERNS)
    ]
    sentence_pool = preferred_sentences or sentences
    best_sentence = ""
    best_score = float("-inf")
    for sentence in sentence_pool:
        score = _score_evidence_sentence(sentence, chapter, item_type, query_tokens=query_tokens)
        if score > best_score:
            best_score = score
            best_sentence = sentence
    snippet = best_sentence or result.chunk.text.replace("\n", " ").strip()
    return snippet[:260]


def _candidate_name_key(scientific_name: str, common_name: str) -> str:
    return normalize_species_name(scientific_name) or normalize_species_name(common_name)


def _results_for_exact_names(corpus: TextRAGCorpus, *, scientific_name: str, common_name: str, query_text: str, item_type: str, max_results: int) -> list[RetrievalResult]:
    chunks = corpus.exact_species_chunks(scientific_name) or corpus.exact_species_chunks(common_name)
    if not chunks:
        return []
    q_tokens = tokenize(query_text)
    q_set = set(q_tokens)
    scored: list[RetrievalResult] = []
    seen_chunk_ids: set[str] = set()
    for chunk in chunks:
        if chunk.chunk_id in seen_chunk_ids:
            continue
        seen_chunk_ids.add(chunk.chunk_id)
        score, matched = corpus._score_by_text(chunk, q_tokens, q_set, target_norm="")  # type: ignore[attr-defined]
        score += _weighted_overlap_bonus(corpus, " ".join([chunk.chapter, chunk.source_chapter_raw, chunk.source_subchapter, chunk.text]), q_tokens)
        score += _chapter_type_bonus(RetrievalResult(chunk=chunk, score=score, matched_on=matched), item_type)
        if score > 0:
            scored.append(RetrievalResult(chunk=chunk, score=score, matched_on=matched))
    scored.sort(key=lambda r: (-r.score, r.chunk.chunk_id))
    return scored[:max_results]


def build_bird_id_candidate_context(
    item: dict,
    corpus: TextRAGCorpus,
    birdbase_df=None,
    column_map: dict | None = None,
    candidate_k: int = 30,
    evidence_per_candidate: int = 3,
) -> dict[str, Any]:
    question = str(item.get("question", "")).strip()
    clue_text = str(item.get("clue_text", "")).strip()
    item_type = str(item.get("type", "")).strip()
    knowledge_domain = str(item.get("knowledge_domain", "")).strip()
    query_text = "\n".join([question, clue_text, item_type, knowledge_domain])

    raw_results = _retrieve_type_prefiltered_results(
        corpus=corpus,
        query_text=query_text,
        item_type=item_type,
        top_k=max(candidate_k * evidence_per_candidate * 6, 60),
    )
    species_groups: dict[str, list[RetrievalResult]] = defaultdict(list)
    for result in raw_results:
        key = _species_key(result)
        if key:
            species_groups[key].append(result)

    birdbase_bonus: dict[str, float] = {}
    birdbase_candidate_rows: list[dict[str, Any]] = []
    parsed_constraints = {}
    unresolved_constraints: list[str] = []
    if birdbase_df is not None and column_map:
        parsed_constraints = parse_birdbase_constraints_from_text(query_text, column_map, mode="bird_id", text_source="question")
        unresolved_constraints = list(parsed_constraints.get("unresolved_constraints", []))
        matched_df, _ = apply_birdbase_constraints(birdbase_df, column_map, parsed_constraints)
        latin_col = column_map.get("latin_name")
        english_col = column_map.get("english_name")
        for _, row in matched_df.iterrows():
            latin = normalize_species_name(row.get(latin_col, "")) if latin_col else ""
            english = normalize_species_name(row.get(english_col, "")) if english_col else ""
            if latin:
                birdbase_bonus[latin] = birdbase_bonus.get(latin, 0.0) + 10.0
            if english:
                birdbase_bonus[english] = birdbase_bonus.get(english, 0.0) + 6.0
            scientific_name = str(row.get(latin_col, "")).strip() if latin_col else ""
            common_name = str(row.get(english_col, "")).strip() if english_col else ""
            evidence_results = _results_for_exact_names(
                corpus,
                scientific_name=scientific_name,
                common_name=common_name,
                query_text=query_text,
                item_type=item_type,
                max_results=evidence_per_candidate,
            )
            birdbase_candidate_rows.append(
                {
                    "scientific_name": scientific_name,
                    "common_name": _best_common_name(scientific_name, common_name),
                    "score": round(max((result.score for result in evidence_results), default=0.0) + 14.0, 4),
                    "birdbase_bonus": 14.0,
                    "evidence_results": evidence_results,
                }
            )

    candidates: list[dict[str, Any]] = []
    for species_key, results in species_groups.items():
        enriched: list[RetrievalResult] = []
        total_score = 0.0
        for result in results:
            extra = _chapter_type_bonus(result, item_type)
            total = result.score + extra
            enriched.append(RetrievalResult(chunk=result.chunk, score=total, matched_on=list(result.matched_on) + ([f"type_bonus:{item_type}"] if extra else [])))
            total_score += total
        enriched.sort(key=lambda r: (-r.score, r.chunk.chunk_id))
        scientific_name = str(enriched[0].chunk.species or "").strip()
        common_name = _best_common_name(
            scientific_name,
            str(enriched[0].chunk.common_name or "").strip(),
        )
        key_norms = {normalize_species_name(scientific_name), normalize_species_name(common_name)}
        bonus = max((birdbase_bonus.get(key, 0.0) for key in key_norms if key), default=0.0)
        candidates.append(
            {
                "scientific_name": scientific_name,
                "common_name": common_name,
                "score": round(total_score + bonus, 4),
                "birdbase_bonus": bonus,
                "evidence_results": enriched[:evidence_per_candidate],
            }
        )

    candidate_by_name: dict[str, dict[str, Any]] = {}
    for candidate in candidates + birdbase_candidate_rows:
        key = _candidate_name_key(candidate.get("scientific_name", ""), candidate.get("common_name", ""))
        if not key:
            continue
        existing = candidate_by_name.get(key)
        if existing is None or float(candidate["score"]) > float(existing["score"]):
            deduped_results: list[RetrievalResult] = []
            seen_chunk_ids: set[str] = set()
            for result in candidate.get("evidence_results", []):
                if result.chunk.chunk_id in seen_chunk_ids:
                    continue
                seen_chunk_ids.add(result.chunk.chunk_id)
                deduped_results.append(result)
            candidate["evidence_results"] = deduped_results[:evidence_per_candidate]
            candidate_by_name[key] = candidate

    candidates = list(candidate_by_name.values())
    candidates.sort(key=lambda row: (-row["score"], row["scientific_name"], row["common_name"]))
    candidates = candidates[:candidate_k]

    lines = [
        "You are solving a masked bird identification task.",
        "The gold target species name was NOT used for retrieval.",
        "The candidates below were retrieved only from visible clues in the question.",
        "",
        "[Candidate species]",
    ]
    for idx, candidate in enumerate(candidates, start=1):
        lines.append(f"{idx}. Common name: {candidate['common_name'] or 'NA'}")
        lines.append(f"   Scientific name: {candidate['scientific_name'] or 'NA'}")
        lines.append("   Evidence:")
        for evidence in candidate["evidence_results"]:
            snippet = _select_evidence_snippet(evidence, item_type, query_text=query_text)
            lines.append(f"   - {snippet}")
    context = "\n".join(lines) if candidates else ""

    candidate_species = []
    candidate_debug = []
    for rank, candidate in enumerate(candidates, start=1):
        candidate_species.append(
            {
                "rank": rank,
                "common_name": candidate["common_name"],
                "scientific_name": candidate["scientific_name"],
                "score": candidate["score"],
            }
        )
        candidate_debug.append(
            {
                "rank": rank,
                "common_name": candidate["common_name"],
                "scientific_name": candidate["scientific_name"],
                "score": candidate["score"],
                "birdbase_bonus": candidate["birdbase_bonus"],
                "evidence": [
                    {
                        "chunk_id": result.chunk.chunk_id,
                        "source_chapter": result.chunk.chapter,
                        "source_chapter_raw": result.chunk.source_chapter_raw,
                        "matched_on": list(result.matched_on),
                        "score": round(float(result.score), 4),
                        "snippet": _select_evidence_snippet(result, item_type, query_text=query_text),
                    }
                    for result in candidate["evidence_results"]
                ],
            }
        )

    return {
        "retrieval_policy": "bird_id_bow_birdbase_candidate_retrieval",
        "retrieved_context_status": "ok" if candidates else "no_context",
        "retrieved_context": context,
        "candidate_species": candidate_species,
        "candidate_debug": candidate_debug,
        "parsed_constraints": parsed_constraints,
        "unresolved_constraints": unresolved_constraints,
    }
