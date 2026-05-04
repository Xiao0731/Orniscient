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

import glob
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

try:
    import pandas as pd
except Exception:  # pandas is only needed for the legacy XLSX fallback.
    pd = None  # type: ignore


STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "by", "from", "at", "as",
    "is", "are", "was", "were", "be", "been", "being", "this", "that", "these", "those", "it", "its",
    "into", "than", "then", "their", "them", "they", "he", "she", "his", "her", "you", "your", "we",
    "our", "but", "if", "not", "do", "does", "did", "which", "what", "when", "where", "who", "whom",
    "how", "why", "can", "could", "should", "would", "may", "might", "about", "under", "over", "between",
    "during", "also", "only", "using", "use", "used", "within", "most", "more", "less", "very", "than",
    "bird", "birds", "species", "target", "provided", "text", "based", "describe", "identify",
}

UI_JUNK = {"close", "share", "print", "photo", "video"}


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def clean_visuals_and_citations(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = re.sub(r"\b(photo|video)\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r'\(?[Ff]ig\.?\s*\d+\)?', '', text)
    text = re.sub(r'\(?[Pp]late\s*\d+\)?', '', text)
    text = re.sub(r'\([A-Z][a-z]+(?: et al\.)?,\s*\d{4}\)', '', text)
    text = re.sub(r'\[\d+(?:,\s*\d+)*\]', '', text)
    return re.sub(r'\s{2,}', ' ', text).strip()


def normalize_name(text: str) -> str:
    text = normalize_space(str(text or "")).lower()
    text = text.replace("’", "'")
    text = re.sub(r"[^a-z0-9'\-\s|]", " ", text)
    return normalize_space(text)


def normalize_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_name(text))


def tokenize(text: str) -> list[str]:
    text = normalize_name(text)
    toks = [tok for tok in re.split(r"\s+", text) if tok and tok not in STOPWORDS and tok not in UI_JUNK and len(tok) > 1]
    return toks


def safe_text(val: object) -> str:
    if val is None:
        return ""
    if pd is not None:
        try:
            if isinstance(val, float) and pd.isna(val):
                return ""
        except Exception:
            pass
    return str(val).strip()


def _flatten_value(value: Any) -> str:
    """Convert common benchmark field shapes into a stable query string."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value).strip()
    if isinstance(value, dict):
        preferred = [
            "common_name", "Common_name", "common", "name", "scientific_name", "scientific",
            "species", "Species", "species_name", "target_entity", "family", "family_name",
            "order", "order_name", "answer", "text", "source_chapter", "source_chapter_raw",
        ]
        parts = []
        for k in preferred:
            if k in value:
                v = _flatten_value(value.get(k))
                if v:
                    parts.append(v)
        if not parts:
            for v in value.values():
                sv = _flatten_value(v)
                if sv:
                    parts.append(sv)
        seen = set()
        out = []
        for x in parts:
            nx = normalize_name(x)
            if nx and nx not in seen:
                seen.add(nx)
                out.append(x)
        return " | ".join(out)
    if isinstance(value, (list, tuple, set)):
        return " | ".join([_flatten_value(v) for v in value if _flatten_value(v)])
    return str(value).strip()


def _as_mapping(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        base = dict(item)
    else:
        base = {}
        for name in dir(item):
            if name.startswith("_"):
                continue
            try:
                value = getattr(item, name)
            except Exception:
                continue
            if callable(value):
                continue
            if isinstance(value, (str, int, float, bool, dict, list, tuple, set)) or value is None:
                base[name] = value
    for container_key in ("raw", "row", "data", "payload", "meta", "metadata", "provenance"):
        nested = base.get(container_key)
        if isinstance(nested, dict):
            for k, v in nested.items():
                base.setdefault(k, v)
                base.setdefault(f"{container_key}.{k}", v)
    # If provenance exists after flattening, expose provenance.source_chapter for diagnostics only.
    prov = base.get("provenance")
    if isinstance(prov, dict):
        for k, v in prov.items():
            base.setdefault(f"provenance.{k}", v)
    return base


def _first_nonempty(mapping: dict[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        if key in mapping:
            v = _flatten_value(mapping.get(key))
            if v:
                return v
    return ""


def _collect_nonempty(mapping: dict[str, Any], keys: Sequence[str]) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for key in keys:
        if key in mapping:
            v = _flatten_value(mapping.get(key))
            nv = normalize_name(v)
            if v and nv not in seen:
                seen.add(nv)
                parts.append(v)
    return "\n".join(parts)


@dataclass
class RetrievalChunk:
    chunk_id: str
    source_type: str  # species | family
    common_name: str
    species: str
    family: str
    order: str
    source_file: str
    chapter: str
    chunk_index: int
    text: str
    token_count: int
    source_chapter_raw: str = ""
    source_subchapter: str = ""
    iucn_status: str = ""

    @property
    def combined_entity_names(self) -> set[str]:
        names = {
            normalize_name(self.common_name), normalize_name(self.species),
            normalize_name(self.family), normalize_name(self.order),
        }
        names.discard("")
        return names


@dataclass
class RetrievalResult:
    chunk: RetrievalChunk
    score: float
    matched_on: list[str]


@dataclass
class TextRAGResultBundle:
    context: str
    results: list[RetrievalResult]
    retrieval_policy: str
    target_entity: str
    status: str
    debug_rows: list[dict[str, Any]]


# Dataset-level routing. This is not answer-provenance routing: it only uses the public
# dataset/task type to choose plausible BOW chapters.
DATASET_CHAPTER_HINTS: dict[str, list[str]] = {
    "QA-SC": ["introduction", "distribution", "habitat", "conservation", "systematics", "diet", "breeding"],
    "QA-MC": ["introduction", "distribution", "habitat", "conservation", "systematics", "diet", "breeding"],
    "QA-SA": ["distribution", "systematics", "subspecies", "measurements", "conservation", "breeding"],
    "Bird-Geo": ["distribution", "habitat", "movement", "migration", "elevation", "range"],
    "Bird-Taxonomy": ["systematics", "subspecies", "variation", "hybridization", "taxonomy"],
    "Bird-Comp": ["identification", "fieldidentification", "similarspecies", "plumages", "measurements", "variation", "subspecies", "systematics"],
    "Bird-Life": ["breeding", "breedingphenology", "phenology", "nest", "eggs", "incubation", "parentalcare", "youngbirds", "fledgling", "vocal", "behavior", "demography", "lifespan"],
    "Bird-Con": ["conservation", "management", "conservationstatus", "population", "threat", "humanactivity", "mortality", "demography", "habitat"],
    "Bird-Eco": ["diet", "dietandforaging", "foraging", "habitat", "behavior", "predation", "interspecific", "distribution"],
    "Bird-Reason": ["introduction", "distribution", "habitat", "movement", "migration", "diet", "foraging", "breeding", "demography", "conservation", "behavior", "vocal"],
    "Bird-Plan": ["conservation", "management", "habitat", "diet", "foraging", "breeding", "demography", "distribution", "threat"],
    "Bird-ID": ["identification", "fieldidentification", "similarspecies", "plumages", "measurements", "vocal", "habitat", "diet", "foraging", "movement", "migration"],
    "Bird-Classify": ["introduction", "systematics", "habitat", "diet", "foraging", "breeding", "conservation"],
}

KNOWLEDGE_DOMAIN_HINTS: dict[str, list[str]] = {
    "geography": ["distribution", "habitat", "movement", "migration"],
    "distribution": ["distribution", "habitat", "movement", "migration"],
    "taxonomy": ["systematics", "subspecies", "variation", "hybridization"],
    "phylogeny": ["systematics", "subspecies", "variation", "hybridization"],
    "morphology": ["identification", "fieldidentification", "plumages", "measurements", "similarspecies"],
    "identification": ["identification", "fieldidentification", "plumages", "measurements", "similarspecies"],
    "conservation": ["conservation", "management", "conservationstatus", "population", "threat"],
    "diet": ["diet", "dietandforaging", "foraging", "habitat"],
    "ecological": ["diet", "dietandforaging", "foraging", "habitat", "behavior", "predation"],
    "life history": ["breeding", "breedingphenology", "nest", "eggs", "incubation", "parentalcare", "demography"],
}

LEAKAGE_SENSITIVE_DATASETS = {"Bird-ID", "Bird-Classify"}
NO_TEXT_RAG_DATASETS = {"List-Global"}


class TextRAGCorpus:
    def __init__(
        self,
        chunks: list[RetrievalChunk],
        *,
        top_k: int = 5,
        max_chars_per_chunk: int = 1200,
        default_restrict_to_target: bool = True,
    ) -> None:
        self.chunks = chunks
        self.top_k = top_k
        self.max_chars_per_chunk = max_chars_per_chunk
        self.default_restrict_to_target = default_restrict_to_target
        self._idf = self._build_idf(chunks)
        self._species_name_index: dict[str, list[RetrievalChunk]] = defaultdict(list)
        self._family_name_index: dict[str, list[RetrievalChunk]] = defaultdict(list)
        for c in chunks:
            if c.source_type == "species":
                for name in [c.common_name, c.species]:
                    n = normalize_name(name)
                    if n:
                        self._species_name_index[n].append(c)
            elif c.source_type == "family":
                for name in [c.family, c.order]:
                    n = normalize_name(name)
                    if n:
                        self._family_name_index[n].append(c)

    @staticmethod
    def _build_idf(chunks: Sequence[RetrievalChunk]) -> dict[str, float]:
        df: dict[str, int] = defaultdict(int)
        for chunk in chunks:
            seen = set(tokenize(" ".join([chunk.chapter, chunk.source_chapter_raw, chunk.text])))
            for tok in seen:
                df[tok] += 1
        total = max(1, len(chunks))
        return {tok: math.log((1 + total) / (1 + freq)) + 1.0 for tok, freq in df.items()}

    @classmethod
    def from_paths(
        cls,
        *,
        bow_glob: str = "",
        order_xlsx: str | None = None,
        cache_jsonl: str | None = None,
        chunk_chars: int = 1200,
        chunk_overlap: int = 200,
        top_k: int = 5,
        max_chars_per_chunk: int = 1200,
        default_restrict_to_target: bool = True,
        species_chunks_jsonl: str | None = None,
        family_chunks_jsonl: str | None = None,
    ) -> "TextRAGCorpus":
        """Load the retrieval corpus.

        Preferred path for the current KG-v2 pipeline:
          - kg_v2/outputs/intermediate/species_chunks.jsonl
          - kg_v2/outputs/intermediate/family_chunks.jsonl

        Legacy XLSX/cache loading is kept only as a fallback so older commands still run.
        """
        chunks: list[RetrievalChunk] = []
        used_kgv2 = False
        for path, source_type in [
            (species_chunks_jsonl, "species"),
            (family_chunks_jsonl, "family"),
        ]:
            if path:
                p = Path(path)
                if p.exists():
                    chunks.extend(cls._load_kg_v2_chunks_jsonl(p, expected_source_type=source_type))
                    used_kgv2 = True
                else:
                    print(f"[TEXT-RAG-WARN] chunk jsonl not found: {p}")
        if used_kgv2:
            return cls(chunks, top_k=top_k, max_chars_per_chunk=max_chars_per_chunk, default_restrict_to_target=default_restrict_to_target)

        cache_path = Path(cache_jsonl) if cache_jsonl else None
        if cache_path and cache_path.exists():
            chunks = cls._load_chunks_jsonl(cache_path)
            return cls(chunks, top_k=top_k, max_chars_per_chunk=max_chars_per_chunk, default_restrict_to_target=default_restrict_to_target)

        # Legacy fallback: rebuild from BOW XLSX + Order.xlsx. Prefer not to use this for KG-v2 experiments.
        if not bow_glob:
            raise ValueError("No retrieval corpus found. Provide --species-chunks-jsonl/--family-chunks-jsonl or legacy --bow-glob.")
        chunks = []
        for path in sorted(glob.glob(bow_glob)):
            chunks.extend(build_species_chunks_from_xlsx(path, chunk_chars=chunk_chars, chunk_overlap=chunk_overlap))
        if order_xlsx:
            chunks.extend(build_family_chunks_from_order_xlsx(order_xlsx, chunk_chars=chunk_chars, chunk_overlap=chunk_overlap))
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with cache_path.open("w", encoding="utf-8") as f:
                for chunk in chunks:
                    f.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")
        return cls(chunks, top_k=top_k, max_chars_per_chunk=max_chars_per_chunk, default_restrict_to_target=default_restrict_to_target)

    @staticmethod
    def _load_chunks_jsonl(path: Path) -> list[RetrievalChunk]:
        rows: list[RetrievalChunk] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                allowed = {field.name for field in RetrievalChunk.__dataclass_fields__.values()}  # type: ignore
                filtered = {k: v for k, v in obj.items() if k in allowed}
                for k in allowed:
                    filtered.setdefault(k, "" if k not in {"chunk_index", "token_count"} else 0)
                rows.append(RetrievalChunk(**filtered))
        return rows

    @staticmethod
    def _load_kg_v2_chunks_jsonl(path: Path, *, expected_source_type: str) -> list[RetrievalChunk]:
        rows: list[RetrievalChunk] = []
        with path.open("r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                raw_text = clean_visuals_and_citations(safe_text(obj.get("raw_text", obj.get("text", ""))))
                if not raw_text:
                    continue
                source_db = safe_text(obj.get("source_db", ""))
                source_type = expected_source_type
                if source_db.upper() == "BOW_FAMILY":
                    source_type = "family"
                elif obj.get("species_name") or obj.get("common_name"):
                    source_type = "species"
                chapter = safe_text(obj.get("source_chapter", ""))
                chapter_raw = safe_text(obj.get("source_chapter_raw", ""))
                if not chapter or normalize_key(chapter) == "unknown":
                    chapter = chapter_raw or "Unknown"
                chunk_id = safe_text(obj.get("chunk_id", f"{source_type}_chunk_{i}"))
                rows.append(
                    RetrievalChunk(
                        chunk_id=chunk_id,
                        source_type=source_type,
                        common_name=safe_text(obj.get("common_name", "")),
                        species=safe_text(obj.get("species_name", obj.get("species", ""))),
                        family=safe_text(obj.get("family_name", obj.get("family", ""))),
                        order=safe_text(obj.get("order_name", obj.get("order", ""))),
                        source_file=safe_text(obj.get("source_file", str(path))),
                        chapter=chapter,
                        source_chapter_raw=chapter_raw,
                        source_subchapter=safe_text(obj.get("source_subchapter", "")),
                        iucn_status=safe_text(obj.get("iucn_status", "")),
                        chunk_index=i,
                        text=raw_text,
                        token_count=len(tokenize(raw_text)),
                    )
                )
        return rows

    def exact_species_chunks(self, target_entity: str) -> list[RetrievalChunk]:
        targets = _target_name_candidates(target_entity)
        out: list[RetrievalChunk] = []
        seen: set[str] = set()
        for target in targets:
            for chunk in self._species_name_index.get(target, []):
                if chunk.chunk_id not in seen:
                    seen.add(chunk.chunk_id)
                    out.append(chunk)
        return out

    def exact_family_chunks(self, target_entity: str, *, family: str = "", order: str = "") -> list[RetrievalChunk]:
        targets = _target_name_candidates(target_entity)
        for x in [family, order]:
            nx = normalize_name(x)
            if nx and nx not in targets:
                targets.append(nx)
        out: list[RetrievalChunk] = []
        seen: set[str] = set()
        for target in targets:
            for chunk in self._family_name_index.get(target, []):
                if chunk.chunk_id not in seen:
                    seen.add(chunk.chunk_id)
                    out.append(chunk)
        return out

    def retrieve_blind(
        self,
        *,
        query_text: str,
        dataset: str,
        source_type: str,
        top_k: int | None = None,
    ) -> list[RetrievalResult]:
        candidates = [c for c in self.chunks if c.source_type == source_type]
        q_tokens = tokenize(query_text)
        q_set = set(q_tokens)
        scored: list[RetrievalResult] = []
        for c in candidates:
            score, matched = self._score_by_text(c, q_tokens, q_set, target_norm="")
            hint = _chapter_hint_score(c, dataset, query_text, "")
            score += hint
            if hint > 0:
                matched.append(f"chapter_hint:{hint:.1f}")
            if score > 0:
                scored.append(RetrievalResult(c, score, matched))
        scored.sort(key=lambda r: (-r.score, r.chunk.chunk_id))
        return scored[: (top_k or self.top_k)]

    def score_target_chunks(
        self,
        *,
        chunks: list[RetrievalChunk],
        query_text: str,
        target_entity: str,
        dataset: str,
        top_k: int | None = None,
    ) -> list[RetrievalResult]:
        q_tokens = tokenize(query_text)
        q_set = set(q_tokens)
        target_norms = _target_name_candidates(target_entity)
        scored: list[RetrievalResult] = []
        for c in chunks:
            score, matched = self._score_by_text(c, q_tokens, q_set, target_norm="")
            # Entity match is exact metadata match only, never raw_text match.
            c_names = c.combined_entity_names
            if any(t in c_names for t in target_norms):
                score += 80.0
                matched.append("target_metadata_exact")
            hint = _chapter_hint_score(c, dataset, query_text, "")
            score += hint
            if hint > 0:
                matched.append(f"chapter_hint:{hint:.1f}")
            # Keep target chunks even when lexical overlap is low; chapter routing is the signal.
            if score > 0:
                scored.append(RetrievalResult(c, score, matched))
        scored.sort(key=lambda r: (-r.score, r.chunk.chunk_id))
        return scored[: (top_k or self.top_k)]

    def _score_by_text(
        self,
        chunk: RetrievalChunk,
        query_tokens: list[str],
        query_token_set: set[str],
        target_norm: str = "",
    ) -> tuple[float, list[str]]:
        chunk_text_for_score = " ".join([chunk.chapter, chunk.source_chapter_raw, chunk.source_subchapter, chunk.text])
        chunk_tokens = set(tokenize(chunk_text_for_score))
        score = 0.0
        overlap_terms: list[str] = []
        for tok in query_token_set:
            if tok in chunk_tokens:
                tok_score = self._idf.get(tok, 1.0)
                score += tok_score
                overlap_terms.append(tok)
        matched = []
        if overlap_terms:
            matched.append(f"kw:{','.join(overlap_terms[:8])}")
        if chunk.token_count < 12:
            score -= 3.0
        return score, matched

    def format_context(
        self,
        results: Sequence[RetrievalResult],
        *,
        max_total_chars: int = 3500,
        redact_identity: bool = False,
    ) -> str:
        parts: list[str] = []
        total = 0
        for idx, result in enumerate(results, start=1):
            chunk = result.chunk
            snippet = normalize_space(chunk.text)
            if redact_identity:
                snippet = _redact_chunk_identity(snippet, chunk)
            if len(snippet) > self.max_chars_per_chunk:
                snippet = snippet[: self.max_chars_per_chunk].rstrip() + " ..."
            if redact_identity:
                header = (
                    f"[{idx}] source_type={chunk.source_type}; chapter={chunk.chapter or 'NA'}; "
                    f"subchapter={chunk.source_subchapter or 'NA'}; matched_on={';'.join(result.matched_on) or 'none'}"
                )
            else:
                header = (
                    f"[{idx}] source_type={chunk.source_type}; common_name={chunk.common_name or 'NA'}; "
                    f"species={chunk.species or 'NA'}; family={chunk.family or 'NA'}; order={chunk.order or 'NA'}; "
                    f"chapter={chunk.chapter or 'NA'}; subchapter={chunk.source_subchapter or 'NA'}; "
                    f"matched_on={';'.join(result.matched_on) or 'none'}"
                )
            block = header + "\n" + snippet
            if total + len(block) + 2 > max_total_chars:
                break
            parts.append(block)
            total += len(block) + 2
        return "\n\n".join(parts)


def _target_name_candidates(target_entity: str) -> list[str]:
    raw = str(target_entity or "")
    pieces = re.split(r"\s*\|\s*|\s*/\s*|\s*;\s*", raw)
    candidates: list[str] = []
    for piece in [raw] + pieces:
        n = normalize_name(piece)
        if n and n not in candidates:
            candidates.append(n)
    return candidates


def _chapter_hint_score(chunk: RetrievalChunk, dataset: str, question: str, extra_query: str) -> float:
    keys = {
        normalize_key(chunk.chapter),
        normalize_key(chunk.source_chapter_raw),
        normalize_key(chunk.source_subchapter),
    }
    joined_keys = " ".join(keys)
    hints = list(DATASET_CHAPTER_HINTS.get(dataset, []))

    domain_text = normalize_name(extra_query)
    for domain_kw, domain_hints in KNOWLEDGE_DOMAIN_HINTS.items():
        if domain_kw in domain_text:
            hints.extend(domain_hints)

    score = 0.0
    seen_hints: set[str] = set()
    for hint in hints:
        h = normalize_key(hint)
        if not h or h in seen_hints:
            continue
        seen_hints.add(h)
        if any(h in key or key in h for key in keys if key):
            score += 18.0
        elif h in joined_keys:
            score += 12.0
    # Weak keyword nudge inside chapter labels only, not a full-body entity search.
    chapter_words = set(tokenize(" ".join([chunk.chapter, chunk.source_chapter_raw, chunk.source_subchapter])))
    for tok in set(tokenize(" ".join([question, extra_query]))):
        if tok in chapter_words:
            score += 1.5
    return score


def _redact_chunk_identity(text: str, chunk: RetrievalChunk) -> str:
    # Do not reveal the entity whose identity is the answer in Bird-ID/Bird-Classify.
    replacements = [chunk.common_name, chunk.species, chunk.family, chunk.order]
    out = text
    for name in sorted([x for x in replacements if x], key=len, reverse=True):
        pattern = re.compile(re.escape(name), flags=re.IGNORECASE)
        out = pattern.sub("[REDACTED_ENTITY]", out)
    return out


def _result_to_debug_row(result: RetrievalResult, rank: int) -> dict[str, Any]:
    chunk = result.chunk
    return {
        "rank": rank,
        "chunk_id": chunk.chunk_id,
        "source_type": chunk.source_type,
        "common_name": chunk.common_name,
        "species": chunk.species,
        "family": chunk.family,
        "order": chunk.order,
        "source_chapter": chunk.chapter,
        "source_chapter_raw": chunk.source_chapter_raw,
        "source_subchapter": chunk.source_subchapter,
        "matched_on": list(result.matched_on),
        "score": round(float(result.score), 4),
    }


def extract_query_fields_from_item(item: Any) -> dict[str, str]:
    m = _as_mapping(item)
    question = _first_nonempty(m, ["question", "prompt", "query", "task", "question_text"])
    dataset = _first_nonempty(m, ["dataset", "dataset_name", "task_dataset", "dataset_key"])
    # Some structured configs use dataset_key such as Bird-Classify__Feature-to-Family.
    if dataset.startswith("Bird-Classify"):
        dataset = "Bird-Classify"
    elif dataset.startswith("Bird-ID"):
        dataset = "Bird-ID"
    elif dataset.startswith("List-Global"):
        dataset = "List-Global"

    target_entity = _first_nonempty(
        m,
        [
            "target_entity", "species_name", "target_species", "species", "Species", "scientific_name",
            "common_name", "Common_name", "bird", "entity", "answer_entity",
            "meta.target_entity", "meta.species_name", "meta.scientific_name", "meta.common_name",
            "metadata.target_entity", "metadata.species_name", "metadata.scientific_name", "metadata.common_name",
        ],
    )
    family = _first_nonempty(m, ["family", "family_name", "metadata.family", "meta.family"])
    order = _first_nonempty(m, ["order", "order_name", "metadata.order", "meta.order"])
    clue_text = _first_nonempty(m, ["clue_text", "metadata.clue_text", "meta.clue_text"])
    extra_query = _collect_nonempty(
        m,
        [
            "clue_text", "type", "knowledge_domain", "constraint_applied", "family", "order",
            "comparison_target", "candidate_family", "candidate_order",
            "meta.type", "meta.knowledge_domain", "metadata.type", "metadata.knowledge_domain",
        ],
    )
    return {
        "question": question,
        "target_entity": target_entity,
        "extra_query": extra_query,
        "dataset": dataset,
        "family": family,
        "order": order,
        "clue_text": clue_text,
    }


def select_target_aware_results(
    corpus: TextRAGCorpus,
    query: dict[str, str],
    *,
    top_k: int,
    restrict_to_target: bool | None,
) -> tuple[list[RetrievalResult], bool, str, str]:
    """Return (results, redact_identity, retrieval_policy_label, status)."""
    dataset = query.get("dataset", "")
    q_text = "\n".join([
        query.get("question", ""),
        query.get("clue_text", ""),
        query.get("extra_query", ""),
    ])

    if dataset in NO_TEXT_RAG_DATASETS:
        return [], False, "no_text_rag_for_dataset", "no_context"

    # Leakage-sensitive tasks: the hidden entity is literally the answer.
    # Do not use target_entity to retrieve, and redact metadata from retrieved chunks.
    if dataset == "Bird-ID":
        results = corpus.retrieve_blind(query_text=q_text, dataset=dataset, source_type="species", top_k=top_k)
        status = "ok" if results else "no_context"
        return results, True, "blind_species_text_retrieval_no_target_entity", status

    if dataset == "Bird-Classify":
        results = corpus.retrieve_blind(query_text=q_text, dataset=dataset, source_type="family", top_k=top_k)
        status = "ok" if results else "no_context"
        return results, True, "blind_family_text_retrieval_no_target_entity", status

    # Normal entity-aware/oracle condition: test whether giving the target bird's BOW text helps.
    # Important: exact match only on metadata common_name/species_name; never search target inside raw_text.
    restrict = corpus.default_restrict_to_target if restrict_to_target is None else restrict_to_target
    target = query.get("target_entity", "")
    if restrict:
        if not target:
            return [], False, "missing_target_entity_no_text_rag", "missing_target_entity"

        target_chunks = corpus.exact_species_chunks(target)
        if not target_chunks:
            # Family-level fallback for rare family tasks outside Bird-Classify.
            target_chunks = corpus.exact_family_chunks(target, family=query.get("family", ""), order=query.get("order", ""))
        if target_chunks:
            results = corpus.score_target_chunks(
                chunks=target_chunks,
                query_text=q_text,
                target_entity=target,
                dataset=dataset,
                top_k=top_k,
            )
            status = "ok" if results else "no_context"
            return results, False, "entity_exact_metadata_then_dataset_chapter_routing", status
        return [], False, "no_exact_metadata_match_for_target_entity", "no_target_match"

    # Non-restricted fallback: lexical retrieval over all chunks. Use only for diagnostics.
    results = corpus.retrieve_blind(query_text=q_text, dataset=dataset, source_type="species", top_k=top_k)
    status = "ok" if results else "no_context"
    return results, False, "global_species_text_retrieval_diagnostic", status


def build_text_rag_bundle(
    corpus: TextRAGCorpus,
    item: Any,
    *,
    top_k: int,
    max_total_chars: int,
    restrict_to_target: bool | None = None,
) -> TextRAGResultBundle:
    query = extract_query_fields_from_item(item)
    results, redact, policy, status = select_target_aware_results(
        corpus,
        query,
        top_k=top_k,
        restrict_to_target=restrict_to_target,
    )
    context = ""
    if results:
        formatted_context = corpus.format_context(results, max_total_chars=max_total_chars, redact_identity=redact)
        if formatted_context:
            if redact:
                warning = (
                    "Retrieved evidence from the external BOW text corpus (Text-RAG baseline).\n"
                    "This is a leakage-sensitive identification/classification task, so entity names in metadata and text have been redacted. "
                    "Use the evidence only as anonymous supporting descriptions; answer the ORIGINAL question.\n"
                )
            elif policy == "entity_exact_metadata_then_dataset_chapter_routing":
                warning = (
                    "Retrieved evidence from the external BOW text corpus (Text-RAG baseline).\n"
                    "The evidence is selected by exact target-entity metadata match and dataset-level chapter routing. "
                    "It may be incomplete. Answer the ORIGINAL question; use the evidence only when relevant, and do not invent unsupported facts.\n"
                )
            else:
                warning = (
                    "Retrieved evidence from the external BOW text corpus (Text-RAG baseline).\n"
                    "The evidence is selected by diagnostic blind retrieval over the BOW corpus. "
                    "It may be incomplete or noisy. Answer the ORIGINAL question; use the evidence only when relevant, and do not invent unsupported facts.\n"
                )
            context = warning + f"Retrieval policy: {policy}.\n\n" + formatted_context
        else:
            status = "no_context"

    debug_rows = [_result_to_debug_row(result, idx) for idx, result in enumerate(results, start=1)]
    return TextRAGResultBundle(
        context=context,
        results=list(results),
        retrieval_policy=policy,
        target_entity=query.get("target_entity", ""),
        status=status,
        debug_rows=debug_rows,
    )


def build_text_rag_block(
    corpus: TextRAGCorpus,
    item: Any,
    *,
    top_k: int,
    max_total_chars: int,
    restrict_to_target: bool | None = None,
) -> tuple[str, list[RetrievalResult]]:
    bundle = build_text_rag_bundle(
        corpus,
        item,
        top_k=top_k,
        max_total_chars=max_total_chars,
        restrict_to_target=restrict_to_target,
    )
    return bundle.context, bundle.results


# -----------------------------------------------------------------------------
# Legacy XLSX fallback. These are intentionally simple and are not recommended
# for the current KG-v2 experiment; use species_chunks.jsonl/family_chunks.jsonl.
# -----------------------------------------------------------------------------

def _rolling_char_chunks(text: str, chunk_chars: int, chunk_overlap: int) -> list[str]:
    text = normalize_space(text)
    if not text:
        return []
    if len(text) <= chunk_chars:
        return [text]
    chunks: list[str] = []
    start = 0
    step = max(1, chunk_chars - chunk_overlap)
    while start < len(text):
        piece = text[start: start + chunk_chars].strip()
        if piece:
            chunks.append(piece)
        if start + chunk_chars >= len(text):
            break
        start += step
    return chunks


def build_species_chunks_from_xlsx(path: str, *, chunk_chars: int, chunk_overlap: int) -> list[RetrievalChunk]:
    if pd is None:
        raise ImportError("pandas is required for legacy XLSX loading")
    file_path = Path(path)
    df = pd.read_excel(file_path)
    for col in ["Common_name", "Species", "Genus", "Family", "Order"]:
        if col not in df.columns:
            df[col] = ""
    if "text" not in df.columns:
        raise ValueError(f"File has no 'text' column: {path}")
    df["Common_name"] = df["Common_name"].ffill().astype(str).str.strip()
    df["Species"] = df["Species"].ffill().astype(str).apply(lambda x: x.split("\n")[0].strip())
    df["Family"] = df["Family"].ffill().astype(str).str.strip()
    df["Order"] = df["Order"].ffill().astype(str).str.strip()
    grouped = df.groupby(["Common_name", "Species", "Family", "Order"], dropna=False)["text"].apply(lambda x: "\n".join(x.dropna().astype(str))).reset_index()
    chunks: list[RetrievalChunk] = []
    for row_idx, row in grouped.iterrows():
        full_text = clean_visuals_and_citations(safe_text(row["text"]))
        for j, piece in enumerate(_rolling_char_chunks(full_text, chunk_chars, chunk_overlap)):
            chunks.append(RetrievalChunk(
                chunk_id=f"species::{file_path.stem}::{row_idx}::{j}",
                source_type="species",
                common_name=safe_text(row["Common_name"]),
                species=safe_text(row["Species"]),
                family=safe_text(row["Family"]),
                order=safe_text(row["Order"]),
                source_file=str(file_path),
                chapter="LegacyXLSX",
                source_chapter_raw="LegacyXLSX",
                chunk_index=j,
                text=piece,
                token_count=len(tokenize(piece)),
            ))
    return chunks


def build_family_chunks_from_order_xlsx(path: str, *, chunk_chars: int, chunk_overlap: int) -> list[RetrievalChunk]:
    if pd is None:
        raise ImportError("pandas is required for legacy XLSX loading")
    file_path = Path(path)
    df = pd.read_excel(file_path)
    if "Family" not in df.columns:
        return []
    chunks: list[RetrievalChunk] = []
    text_columns = [c for c in df.columns if c not in {"Order", "Family", "Genus", "Species", "Common_name", "Level"}]
    for row_idx, row in df.iterrows():
        family = safe_text(row.get("Family", ""))
        order = safe_text(row.get("Order", ""))
        if not family:
            continue
        for col in text_columns:
            text = clean_visuals_and_citations(safe_text(row.get(col, "")))
            if not text:
                continue
            for j, piece in enumerate(_rolling_char_chunks(text, chunk_chars, chunk_overlap)):
                chunks.append(RetrievalChunk(
                    chunk_id=f"family::{file_path.stem}::{row_idx}::{col}::{j}",
                    source_type="family",
                    common_name="",
                    species="",
                    family=family,
                    order=order,
                    source_file=str(file_path),
                    chapter=col,
                    source_chapter_raw=col,
                    chunk_index=j,
                    text=piece,
                    token_count=len(tokenize(piece)),
                ))
    return chunks
