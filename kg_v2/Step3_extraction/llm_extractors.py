"""Structured JSON claim extraction for Step 3 (patched coercion version)."""

from __future__ import annotations

import json
import re
import sys
from typing import Any

from kg_v2.Step3_extraction.normalizers import QUALIFIER_KEYS
from kg_v2.utils.llm_utils import LLMResponseError, OpenAICompatibleConfig, chat_json_raw, load_openai_compatible_config

EXTRACTION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "source_db": {"type": "string", "enum": ["BOW"]},
        "source_release": {"type": "string"},
        "source_doc_id": {"type": "string"},
        "source_chunk_id": {"type": "string"},
        "source_chapter": {"type": "string"},
        "subject_taxon_id": {"type": "string"},
        "subject_rank": {"type": "string", "enum": ["species", "family"]},
        "claims": {"type": "array", "maxItems": 4, "items": {"$ref": "#/$defs/claim"}},
    },
    "required": [
        "source_db",
        "source_release",
        "source_doc_id",
        "source_chunk_id",
        "source_chapter",
        "subject_taxon_id",
        "subject_rank",
        "claims",
    ],
    "$defs": {
        "claim": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "fact_domain": {
                    "type": "string",
                    "enum": [
                        "TaxonomyAndPhylogeny",
                        "MorphologyAndIdentification",
                        "DistributionAndMovement",
                        "Habitat",
                        "EcologyAndDiet",
                        "VocalAndBehavior",
                        "LifeHistoryAndBreeding",
                        "ConservationAndResearch",
                    ],
                },
                "predicate": {"type": "string"},
                "object_type": {"type": "string", "enum": ["concept", "numeric", "text", "relation"]},
                "object_text": {"type": "string"},
                "object_canonical_id": {"type": "string"},
                "object_canonical_name": {"type": "string"},
                "value_min": {"type": ["number", "null"]},
                "value_max": {"type": ["number", "null"]},
                "unit": {"type": "string"},
                "qualifiers_raw": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {key: {"type": "string"} for key in QUALIFIER_KEYS},
                    "required": QUALIFIER_KEYS,
                },
                "evidence_quote": {"type": "string"},
                "confidence": {"type": "number"},
            },
            "required": [
                "fact_domain",
                "predicate",
                "object_type",
                "object_text",
                "object_canonical_id",
                "object_canonical_name",
                "value_min",
                "value_max",
                "unit",
                "qualifiers_raw",
                "evidence_quote",
                "confidence",
            ],
        }
    },
}

SYSTEM_PROMPT = """You are a structured information extraction engine for a bird ecology knowledge base.

Extract at most 4 high-value claims from one chunk.
Return valid JSON only.
Use only allowed fact domains and allowed predicates.
If no valid claim exists, return an empty claims array.
Each claim MUST include:
- fact_domain
- predicate
- object_type
- object_text
- object_canonical_id
- object_canonical_name
- value_min
- value_max
- unit
- qualifiers_raw
- evidence_quote
- confidence
Current project stage uses chunk-level evidence only. Do not attempt character offsets.
"""

USER_PROMPT_TEMPLATE = """You are given one bird-knowledge chunk that has already been attached to a canonical taxonomy node.

## Subject metadata
- subject_taxon_id: {subject_taxon_id}
- subject_rank: {subject_rank}

## Source metadata
- source_db: {source_db}
- source_release: {source_release}
- source_doc_id: {source_doc_id}
- source_chunk_id: {source_chunk_id}
- source_chapter: {source_chapter}

Allowed fact domains:
{allowed_fact_domains}

Allowed predicates:
{allowed_predicates}

Return exactly one JSON object with fields:
- source_db
- source_release
- source_doc_id
- source_chunk_id
- source_chapter
- subject_taxon_id
- subject_rank
- claims

Input chunk:
{chunk_text}
"""


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_configure_stdio()


def _debug_print(text: str) -> None:
    text = str(text)
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        safe_text = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
        try:
            print(safe_text, flush=True)
        except Exception:
            pass
    except Exception:
        pass


def build_prompt(metadata: dict, allowed_domains: list[str], allowed_predicates: list[str], candidates: list[dict], chunk_text: str) -> str:
    return USER_PROMPT_TEMPLATE.format(
        subject_taxon_id=metadata["subject_taxon_id"],
        subject_rank=metadata["subject_rank"],
        source_db=metadata["source_db"],
        source_release=metadata["source_release"],
        source_doc_id=metadata["source_doc_id"],
        source_chunk_id=metadata["source_chunk_id"],
        source_chapter=metadata["source_chapter"],
        allowed_fact_domains=json.dumps(allowed_domains, ensure_ascii=False),
        allowed_predicates=json.dumps(allowed_predicates, ensure_ascii=False),
        chunk_text=chunk_text,
    )


VALID_OBJECT_TYPES = {"concept", "numeric", "text", "relation"}
NUMERIC_OBJECT_TYPES = {"number", "measurement", "range", "value", "count", "length", "mass", "size"}
RELATION_OBJECT_TYPES = {"species", "taxon", "genus", "family", "order", "subspecies", "organism", "entity"}
CONCEPT_OBJECT_TYPES = {
    "habitat",
    "location",
    "region",
    "country",
    "place",
    "biome",
    "behavior",
    "food",
    "diet",
    "threat",
    "status",
    "trait",
    "morphology",
    "vocalization",
    "breeding",
    "nest",
}
TEXT_OBJECT_TYPES = {"sentence", "description", "note", "unknown", ""}


def _is_number(value: Any) -> bool:
    if value in ("", None):
        return False
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


def _looks_like_taxon_id(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return bool(re.match(r"^(taxon[_:-]|avibase[_:-]|clements[_:-])", text))


def _normalize_object_type(claim: dict) -> str:
    raw = str(claim.get("object_type", "") or "").strip().lower()
    raw = raw.replace("-", "_").replace(" ", "_")
    if raw in VALID_OBJECT_TYPES:
        return raw
    if _is_number(claim.get("value_min")) or _is_number(claim.get("value_max")):
        return "numeric"
    if _looks_like_taxon_id(claim.get("object_canonical_id")):
        return "relation"
    if raw in NUMERIC_OBJECT_TYPES:
        return "numeric"
    if raw in RELATION_OBJECT_TYPES:
        return "relation"
    if raw in CONCEPT_OBJECT_TYPES:
        return "concept"
    if raw in TEXT_OBJECT_TYPES:
        return "text"
    return "text"


def _coerce_wrapper(wrapper: dict, metadata: dict, *, debug: bool = False) -> dict:
    if not isinstance(wrapper, dict):
        raise ValueError("LLM response root must be an object")

    out = {
        "source_db": wrapper.get("source_db") or metadata["source_db"],
        "source_release": wrapper.get("source_release") or metadata["source_release"],
        "source_doc_id": wrapper.get("source_doc_id") or metadata["source_doc_id"],
        "source_chunk_id": wrapper.get("source_chunk_id") or metadata["source_chunk_id"],
        "source_chapter": wrapper.get("source_chapter") or metadata["source_chapter"],
        "subject_taxon_id": wrapper.get("subject_taxon_id") or metadata["subject_taxon_id"],
        "subject_rank": wrapper.get("subject_rank") or metadata["subject_rank"],
        "claims": [],
    }

    claims = wrapper.get("claims", [])
    if not isinstance(claims, list):
        raise ValueError("LLM response claims must be an array")

    for claim in claims[:4]:
        if not isinstance(claim, dict):
            continue
        evidence_quote = claim.get("evidence_quote", "") or ""
        if isinstance(evidence_quote, (list, tuple)):
            evidence_quote = " ".join(str(item) for item in evidence_quote)
        qualifiers = claim.get("qualifiers_raw") if isinstance(claim.get("qualifiers_raw"), dict) else {}
        qualifiers = {k: str(qualifiers.get(k, "") or "") for k in QUALIFIER_KEYS}
        try:
            confidence = float(claim.get("confidence", 0.8))
        except Exception:
            confidence = 0.8
        original_object_type = claim.get("object_type", "text")
        object_type = _normalize_object_type(claim)
        if debug and str(original_object_type or "").strip().lower() != object_type:
            _debug_print(
                "[DEBUG_OBJECT_TYPE_NORMALIZED] "
                f"chunk_id={metadata.get('source_chunk_id', '')} "
                f"raw={original_object_type!r} normalized={object_type!r}"
            )
        out["claims"].append({
            "fact_domain": claim.get("fact_domain") or claim.get("domain", ""),
            "predicate": claim.get("predicate", ""),
            "object_type": object_type,
            "object_text": claim.get("object_text", ""),
            "object_canonical_id": claim.get("object_canonical_id", "") or "",
            "object_canonical_name": claim.get("object_canonical_name", "") or "",
            "value_min": claim.get("value_min", None),
            "value_max": claim.get("value_max", None),
            "unit": claim.get("unit", "") or "",
            "qualifiers_raw": qualifiers,
            "evidence_quote": evidence_quote,
            "confidence": confidence,
        })
    return out


def validate_extraction_wrapper(wrapper: dict, routing: dict) -> None:
    required = ["source_db","source_release","source_doc_id","source_chunk_id","source_chapter","subject_taxon_id","subject_rank","claims"]
    for key in required:
        if key not in wrapper:
            raise ValueError(f"LLM response missing required field: {key}")
    if wrapper.get("source_db") != "BOW":
        raise ValueError("LLM response source_db must be BOW")
    if wrapper.get("subject_rank") not in {"species", "family"}:
        raise ValueError("LLM response subject_rank must be species or family")
    if not isinstance(wrapper.get("claims"), list):
        raise ValueError("LLM response claims must be an array")
    if len(wrapper["claims"]) > 4:
        raise ValueError("LLM response exceeded 4 claims")

    allowed_domains = set(routing["allowed_fact_domains"])
    allowed_predicates = set(routing["allowed_predicates"])
    for claim in wrapper["claims"]:
        if claim.get("fact_domain") not in allowed_domains:
            raise ValueError(f"LLM response used disallowed domain: {claim.get('fact_domain')}")
        if claim.get("predicate") not in allowed_predicates:
            raise ValueError(f"LLM response used disallowed predicate: {claim.get('predicate')}")
        if claim.get("object_type") not in {"concept", "numeric", "text", "relation"}:
            raise ValueError("LLM response used invalid object_type")
        if not claim.get("evidence_quote"):
            raise ValueError("LLM response claim missing evidence_quote")
        if not isinstance(claim.get("confidence"), (int, float)):
            raise ValueError("LLM response confidence must be numeric")


class StructuredLLMExtractor:
    def __init__(self, config: OpenAICompatibleConfig | None = None, *, debug: bool = False) -> None:
        self.config = config or load_openai_compatible_config()
        if self.config is None:
            raise RuntimeError("Missing DeepSeek/OpenAI-compatible config for LLM extraction")
        self.debug = debug

    def runtime_debug_info(self) -> dict:
        return {
            "provider": self.config.provider,
            "model": self.config.model,
            "base_url": self.config.base_url,
            "api_key_present": bool(self.config.api_key),
            "api_key_source": self.config.api_key_source,
            "base_url_source": self.config.base_url_source,
            "model_source": self.config.model_source,
            "temperature": self.config.temperature,
            "max_retries": self.config.max_retries,
        }

    def extract(self, *, metadata: dict, routing: dict, chunk_text: str, canonical_candidates: list[dict]) -> dict:
        user_prompt = build_prompt(
            metadata,
            routing["allowed_fact_domains"],
            routing["allowed_predicates"],
            canonical_candidates,
            chunk_text,
        )
        last_error = None
        last_raw_preview = ""
        for _ in range(self.config.max_retries + 1):
            try:
                wrapper, raw_response = chat_json_raw(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    json_schema=EXTRACTION_JSON_SCHEMA,
                    config=self.config,
                )
                last_raw_preview = raw_response[:500]
                if self.debug:
                    _debug_print("[DEBUG_LLM_RAW_RESPONSE]")
                    _debug_print(raw_response)
                wrapper = _coerce_wrapper(wrapper, metadata, debug=self.debug)
                validate_extraction_wrapper(wrapper, routing)
                return wrapper
            except LLMResponseError as exc:
                last_error = exc
                last_raw_preview = exc.raw_response_preview
                if self.debug and exc.raw_response_preview:
                    _debug_print("[DEBUG_LLM_RAW_RESPONSE]")
                    _debug_print(exc.raw_response_preview)
                if str(exc).startswith("LLM request failed: HTTP"):
                    raise exc
                continue
            except ValueError as exc:
                last_error = exc
                if self.debug and last_raw_preview:
                    _debug_print("[DEBUG_LLM_RAW_RESPONSE]")
                    _debug_print(last_raw_preview)
                continue
        raise LLMResponseError(
            f"LLM extraction failed schema validation after retries: {last_error}",
            raw_response_preview=last_raw_preview,
        ) from last_error


class MockStructuredExtractor:
    def extract(self, *, metadata: dict, routing: dict, chunk_text: str, canonical_candidates: list[dict]) -> dict:
        return {
            "source_db": metadata["source_db"],
            "source_release": metadata["source_release"],
            "source_doc_id": metadata["source_doc_id"],
            "source_chunk_id": metadata["source_chunk_id"],
            "source_chapter": metadata["source_chapter"],
            "subject_taxon_id": metadata["subject_taxon_id"],
            "subject_rank": metadata["subject_rank"],
            "claims": [],
        }
