from __future__ import annotations

import os
import re
import threading
from typing import Any, Dict, Iterable, List, Optional

try:
    from neo4j import Driver, GraphDatabase
except Exception:  # pragma: no cover
    Driver = object  # type: ignore
    GraphDatabase = None  # type: ignore

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7688")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

ANCHOR_EXACT_CYPHER = """
MATCH (s)
WHERE
    toLower(coalesce(s.entity_id, "")) = toLower($target)
    OR toLower(coalesce(s.name, "")) = toLower($target)
RETURN
    id(s) AS node_id,
    coalesce(s.entity_id, s.name, "") AS entity_id,
    labels(s) AS labels,
    coalesce(s.entity_type, "") AS entity_type,
    coalesce(s.description, "") AS description
LIMIT 5
"""

ANCHOR_FALLBACK_CYPHER = """
MATCH (s)
WHERE
    (
        toLower(coalesce(s.entity_id, "")) CONTAINS toLower($target)
        OR toLower(coalesce(s.name, "")) CONTAINS toLower($target)
    )
    AND (
        "Species" IN labels(s)
        OR "creature" IN labels(s)
        OR coalesce(s.entity_type, "") = "creature"
    )
RETURN
    id(s) AS node_id,
    coalesce(s.entity_id, s.name, "") AS entity_id,
    labels(s) AS labels,
    coalesce(s.entity_type, "") AS entity_type,
    coalesce(s.description, "") AS description
ORDER BY
    CASE
        WHEN toLower(coalesce(s.entity_id, "")) = toLower($target) THEN 0
        WHEN toLower(coalesce(s.name, "")) = toLower($target) THEN 1
        ELSE 2
    END
LIMIT 5
"""

EDGE_CYPHER = """
MATCH (s)-[r:DIRECTED]-(o)
WHERE id(s) IN $anchor_ids
RETURN
    coalesce(s.entity_id, s.name, "") AS subject,
    labels(s) AS subject_labels,
    coalesce(r.description, "") AS description,
    coalesce(r.keywords, "") AS keywords,
    coalesce(o.entity_id, o.name, o.description, "") AS object,
    labels(o) AS object_labels,
    coalesce(o.description, "") AS object_description,
    coalesce(o.source_id, "") AS object_source_id,
    coalesce(o.entity_type, "") AS object_entity_type,
    coalesce(r.source_id, "") AS source_id,
    coalesce(r.weight, 0.0) AS weight
LIMIT $neighbor_limit
"""

QUESTION_DOMAIN_HINTS = {
    "taxonomy": ["taxonomy", "order", "family", "genus", "classification"],
    "distribution": ["where", "range", "distribution", "native", "geographic"],
    "habitat": ["habitat", "live", "inhabit"],
    "diet": ["diet", "food", "feed", "prey"],
    "behavior": ["behavior", "migration", "migratory", "nest", "breeding"],
    "conservation": ["conservation", "threat", "endangered", "iucn", "status"],
}

DOMAIN_PRIORITY_KEYWORDS = {
    "taxonomy": ["classification", "taxonomy"],
    "distribution": ["geographic", "distribution", "range", "native range"],
    "habitat": ["habitat", "inhabits", "macro-habitat"],
    "diet": ["diet", "preys on", "foraging"],
    "behavior": ["behavior", "migratory", "nesting", "life history"],
    "conservation": ["conservation", "threat", "status", "iucn"],
}

_DRIVER_LOCK = threading.Lock()
_DRIVER_CACHE: dict[tuple[str, str, str], Driver] = {}


def clean_text(value: Optional[str]) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalize_text(value: Optional[str]) -> str:
    return clean_text(value).lower()


def split_sep_segments(text: str) -> list[str]:
    """
    Split a LightRAG aggregated property by <SEP> and normalize each segment.

    LightRAG often merges multiple descriptions/source_ids into one node
    property using <SEP>. Empty segments are discarded.
    """

    if not text:
        return []

    text = clean_text(text)
    segments: list[str] = []
    for part in str(text).split("<SEP>"):
        cleaned = clean_text(part)
        if cleaned:
            segments.append(cleaned)
    return segments


def truncate_text(text: str, max_chars: int) -> str:
    """
    Truncate text for prompt safety.
    """

    text = clean_text(text)
    if not text:
        return ""
    if max_chars > 0 and len(text) > max_chars:
        text = text[:max_chars].rstrip() + "..."
    return text


def select_aligned_node_description(
    object_description: str,
    object_source_id: str,
    edge_source_id: str,
    max_chars: int = 260,
) -> str:
    """
    Select an object-node description segment aligned with the current edge.

    In the recovered LightRAG-style Neo4j graph, object nodes may aggregate
    multiple source-specific descriptions:

        o.source_id    = chunk-a<SEP>chunk-b<SEP>chunk-c
        o.description  = desc-a<SEP>desc-b<SEP>desc-c

    The current relation edge also has:

        r.source_id = chunk-b

    When possible, align r.source_id with o.source_id and select the
    description segment at the same index. This recovers the local description
    related to the current relation source.

    If alignment fails, fall back to the first description segment. The fallback
    is only a conservative way to avoid injecting the entire aggregated node
    description into the prompt; it is not assumed to be the most relevant one.
    """

    desc_segments = split_sep_segments(object_description)
    if not desc_segments:
        return ""

    source_segments = split_sep_segments(object_source_id)
    edge_sources = set(split_sep_segments(edge_source_id))
    selected = ""

    # Prefer the description segment whose source_id matches the current edge.
    if source_segments and edge_sources:
        for idx, src in enumerate(source_segments):
            if src in edge_sources and idx < len(desc_segments):
                selected = desc_segments[idx]
                break

    # Fallback: keep the first segment only, never the full aggregated text.
    if not selected:
        selected = desc_segments[0]

    return truncate_text(selected, max_chars=max_chars)


def _tokenize_question(question: str) -> list[str]:
    return [token for token in re.findall(r"[A-Za-z][A-Za-z\-]{2,}", question.lower()) if len(token) >= 3]


def infer_domain_keywords(question: str) -> list[str]:
    question_lower = clean_text(question).lower()
    keywords: list[str] = []
    for domain, triggers in QUESTION_DOMAIN_HINTS.items():
        if any(trigger in question_lower for trigger in triggers):
            keywords.extend(DOMAIN_PRIORITY_KEYWORDS[domain])
    return list(dict.fromkeys(keywords))


def _get_driver(
    uri: str | None = None,
    username: str | None = None,
    password: str | None = None,
) -> Driver:
    uri = uri or NEO4J_URI
    username = username or NEO4J_USERNAME
    password = password or NEO4J_PASSWORD
    key = (uri, username, password)
    if GraphDatabase is None:
        raise RuntimeError("neo4j package is not installed; install neo4j to use KG graph retrieval.")
    with _DRIVER_LOCK:
        driver = _DRIVER_CACHE.get(key)
        if driver is None:
            driver = GraphDatabase.driver(uri, auth=(username, password))
            _DRIVER_CACHE[key] = driver
        return driver


def close_all_drivers() -> None:
    with _DRIVER_LOCK:
        drivers = list(_DRIVER_CACHE.values())
        _DRIVER_CACHE.clear()
    for driver in drivers:
        driver.close()


def _anchor_score(row: Dict[str, Any], target_entity: str) -> float:
    entity_id = normalize_text(row.get("entity_id"))
    target = normalize_text(target_entity)
    labels = {clean_text(label) for label in row.get("labels", [])}
    entity_type = normalize_text(row.get("entity_type"))

    score = 0.0
    if entity_id == target:
        score += 100.0
    elif entity_id.startswith(target):
        score += 20.0
    elif target and target in entity_id:
        score += 10.0

    if "creature" in labels:
        score += 5.0
    if "Species" in labels:
        score += 5.0
    if entity_type == "creature":
        score += 5.0
    if row.get("description"):
        score += 1.0
    return score


def _select_anchor_rows(rows: Iterable[Dict[str, Any]], target_entity: str) -> list[Dict[str, Any]]:
    candidates = list(rows)
    if not candidates:
        return []

    ranked = sorted(candidates, key=lambda row: _anchor_score(row, target_entity), reverse=True)
    target = normalize_text(target_entity)
    exact = [row for row in ranked if normalize_text(row.get("entity_id")) == target]
    if exact:
        return exact

    # For fuzzy fallback we keep only the best anchor to avoid contaminating context
    # with similarly named but different bird species.
    return ranked[:1]


def _score_edge(row: Dict[str, Any], question: str, domain_keywords: list[str], target_entity: str) -> float:
    text = " ".join(
        [
            clean_text(row.get("description")),
            clean_text(row.get("keywords")),
            clean_text(row.get("subject")),
            clean_text(row.get("object")),
        ]
    ).lower()
    score = float(row.get("weight") or 0.0)

    domain_matches = sum(1 for keyword in domain_keywords if keyword.lower() in text)
    score += 3.0 * domain_matches

    question_token_matches = sum(1 for token in _tokenize_question(question) if token in text)
    score += 0.5 * question_token_matches

    if clean_text(row.get("description")):
        score += 1.0
    if normalize_text(row.get("subject")) == normalize_text(target_entity):
        score += 1.0
    return score


def _is_nearly_same_text(left: str, right: str) -> bool:
    left_norm = normalize_text(left)
    right_norm = normalize_text(right)
    if not left_norm or not right_norm:
        return False
    if left_norm == right_norm:
        return True
    shorter, longer = sorted((left_norm, right_norm), key=len)
    if shorter and shorter in longer and len(shorter) / max(1, len(longer)) >= 0.8:
        return True
    return False


def _format_context_lines(
    rows: Iterable[Dict[str, Any]],
    context_style: str = "relation_only",
    include_keywords: bool = False,
    include_source: bool = False,
    max_node_notes: int = 6,
    node_note_max_chars: int = 0,
) -> list[str]:
    allowed_styles = {"relation_only", "relation_plus_node_brief"}
    if context_style not in allowed_styles:
        context_style = "relation_only"

    relation_lines: list[str] = []
    seen: set[tuple[str, str, str, str]] = set()
    node_note_lines: list[str] = []
    seen_node_objects: set[str] = set()

    for row in rows:
        subject = clean_text(row.get("subject"))
        description = clean_text(row.get("description"))
        keywords = clean_text(row.get("keywords"))
        object_name = clean_text(row.get("object"))
        source_id = clean_text(row.get("source_id"))
        object_description = clean_text(row.get("object_description"))
        object_source_id = clean_text(row.get("object_source_id"))

        if not description:
            continue

        dedupe_key = (subject, description, object_name, source_id)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        line = f"- {description}"
        if include_keywords and keywords:
            line += f" [keywords: {keywords}]"
        if include_source and source_id:
            line += f" [source: {source_id}]"
        relation_lines.append(line)

        if context_style != "relation_plus_node_brief":
            continue
        if len(node_note_lines) >= max_node_notes:
            continue
        if not object_name:
            continue

        object_key = normalize_text(object_name)
        if object_key in seen_node_objects:
            continue

        # Use the edge source_id to align into the aggregated object node fields.
        # This keeps node notes local to the current relation when possible.
        brief_description = select_aligned_node_description(
            object_description=object_description,
            object_source_id=object_source_id,
            edge_source_id=source_id,
            max_chars=node_note_max_chars,
        )
        if not brief_description:
            continue
        if _is_nearly_same_text(brief_description, description):
            continue

        seen_node_objects.add(object_key)
        node_note_lines.append(f"- {object_name}: {brief_description}")

    if not relation_lines:
        return []

    lines: list[str] = ["[Graph relation facts]", *relation_lines]
    if context_style == "relation_plus_node_brief" and node_note_lines:
        lines.extend(["", "[Brief related-node notes]", *node_note_lines])
    return lines


def retrieve_kg_context(
    target_entity: str,
    question: str = "",
    limit: int = 40,
    neighbor_limit: int = 160,
    debug: bool = False,
    context_style: str = "relation_only",
    include_keywords: bool = False,
    include_source: bool = False,
    max_node_notes: int = 6,
    node_note_max_chars: int = 0,
) -> str:
    """
    Retrieve one-hop graph evidence from a LightRAG-style Neo4j graph.

    The graph stores semantic meaning in DIRECTED edge properties instead of
    edge types, so we surface `description` and `keywords` as the actual KG
    evidence for prompting.
    """

    target_entity = clean_text(target_entity)
    question = clean_text(question)
    if context_style not in {"relation_only", "relation_plus_node_brief"}:
        context_style = "relation_only"
    if not target_entity:
        return "[NO_KG_CONTEXT: missing target_entity]"

    driver = _get_driver()
    domain_keywords = infer_domain_keywords(question)

    with driver.session() as session:
        anchor_rows = [dict(record) for record in session.run(ANCHOR_EXACT_CYPHER, target=target_entity)]
        anchor_strategy = "exact"
        if not anchor_rows:
            anchor_rows = [dict(record) for record in session.run(ANCHOR_FALLBACK_CYPHER, target=target_entity)]
            anchor_strategy = "contains"

        anchor_rows = _select_anchor_rows(anchor_rows, target_entity)
        if debug:
            print(f"[KG DEBUG] target_entity={target_entity!r}")
            print(f"[KG DEBUG] anchor_strategy={anchor_strategy}")
            print(f"[KG DEBUG] anchors={anchor_rows}")

        if not anchor_rows:
            return f"[NO_KG_CONTEXT: entity not found: {target_entity}]"

        anchor_ids = [row["node_id"] for row in anchor_rows]
        edge_rows = [
            dict(record)
            for record in session.run(
                EDGE_CYPHER,
                anchor_ids=anchor_ids,
                neighbor_limit=max(1, int(neighbor_limit)),
            )
        ]

    if debug:
        print(f"[KG DEBUG] retrieved_edges={len(edge_rows)}")
    if not edge_rows:
        return f"[NO_KG_CONTEXT: no edges for entity: {target_entity}]"

    ranked_rows = sorted(
        edge_rows,
        key=lambda row: _score_edge(row, question, domain_keywords, target_entity),
        reverse=True,
    )[: max(1, int(limit))]

    lines = _format_context_lines(
        ranked_rows,
        context_style=context_style,
        include_keywords=include_keywords,
        include_source=include_source,
        max_node_notes=max_node_notes,
        node_note_max_chars=node_note_max_chars,
    )
    if debug:
        preview = "\n".join(lines[:10])
        print("[KG DEBUG] context_preview=")
        print(preview)

    if not lines:
        return f"[NO_KG_CONTEXT: no usable relation descriptions for entity: {target_entity}]"
    return "\n".join(lines)


if __name__ == "__main__":
    try:
        output = retrieve_kg_context(
            target_entity="Whooping Crane",
            question="Explain the main conservation threats and habitat requirements of this species.",
            limit=20,
            neighbor_limit=160,
            debug=True,
            context_style="relation_plus_node_brief",
        )
        try:
            print(output)
        except UnicodeEncodeError:
            import sys

            sys.stdout.buffer.write(output.encode("utf-8", errors="replace"))
            sys.stdout.buffer.write(b"\n")
    finally:
        close_all_drivers()
