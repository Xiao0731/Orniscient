from __future__ import annotations

import os
import threading
from typing import Any

try:
    from neo4j import Driver, GraphDatabase
except Exception:  # pragma: no cover
    Driver = object  # type: ignore
    GraphDatabase = None  # type: ignore

from table_kb_utils import clean_text, score_row_by_query, tokenize_query

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7688")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

REVERSE_BIRD_ID_CYPHER = """
MATCH (s)-[r:DIRECTED]-(o)
WHERE
    ("creature" IN labels(s) OR "Species" IN labels(s) OR coalesce(s.entity_type, "") = "creature")
    AND any(t IN $tokens WHERE
        toLower(coalesce(r.description, "")) CONTAINS t
        OR toLower(coalesce(r.keywords, "")) CONTAINS t
        OR toLower(coalesce(o.entity_id, o.name, o.description, "")) CONTAINS t
        OR toLower(coalesce(s.description, "")) CONTAINS t
    )
RETURN
    coalesce(s.entity_id, s.name, "") AS species,
    coalesce(s.description, "") AS species_description,
    collect(DISTINCT coalesce(r.description, ""))[0..$evidence_per_species] AS evidence,
    collect(DISTINCT coalesce(o.entity_id, o.name, ""))[0..$evidence_per_species] AS objects
LIMIT $raw_limit
"""

_DRIVER_LOCK = threading.Lock()
_DRIVER_CACHE: dict[tuple[str, str, str], Driver] = {}


def _get_driver(uri: str, username: str, password: str) -> Driver:
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


def _build_candidate_context(row: dict[str, Any], query_tokens: list[str]) -> str:
    evidence = [clean_text(entry) for entry in row.get("evidence", []) if clean_text(entry)]
    objects = [clean_text(entry) for entry in row.get("objects", []) if clean_text(entry)]
    parts = [clean_text(row.get("species", "")), clean_text(row.get("species_description", "")), *evidence, *objects]
    return " | ".join(part for part in parts if part)


def retrieve_bird_id_candidates(
    question: str,
    clue_text: str = "",
    top_k: int = 30,
    evidence_per_species: int = 5,
    kg_uri: str | None = None,
    kg_user: str | None = None,
    kg_password: str | None = None,
) -> str:
    """
    Retrieve candidate species for Bird-ID using only masked clues.

    Important: this function must never use target_entity or gold answers.
    It operates strictly on the visible question/clue text.
    """

    query_text = "\n".join(part for part in [clean_text(question), clean_text(clue_text)] if part)
    query_tokens = tokenize_query(query_text)[:24]
    if not query_tokens:
        return "[NO_REVERSE_KG_CONTEXT: no usable clue tokens]"

    uri = kg_uri or NEO4J_URI
    user = kg_user or NEO4J_USERNAME
    password = kg_password or NEO4J_PASSWORD
    driver = _get_driver(uri, user, password)

    raw_limit = max(40, int(top_k) * 4)
    with driver.session() as session:
        rows = [
            dict(record)
            for record in session.run(
                REVERSE_BIRD_ID_CYPHER,
                tokens=query_tokens,
                evidence_per_species=max(1, int(evidence_per_species)),
                raw_limit=raw_limit,
            )
        ]

    if not rows:
        return "[NO_REVERSE_KG_CONTEXT: no reverse candidates]"

    ranked: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        score = score_row_by_query(_build_candidate_context(row, query_tokens), query_tokens)
        score += 0.2 * len([entry for entry in row.get("evidence", []) if clean_text(entry)])
        ranked.append((score, row))

    ranked.sort(key=lambda pair: pair[0], reverse=True)
    top_rows = [row for score, row in ranked if score > 0][: max(1, int(top_k))]
    if not top_rows:
        return "[NO_REVERSE_KG_CONTEXT: no reverse candidates]"

    lines = [
        "[Reverse KG candidates]",
        "The following candidate species are retrieved from the graph using only the masked clues. The target name itself was not used.",
    ]
    for index, row in enumerate(top_rows, start=1):
        lines.append(f"{index}. Species: {clean_text(row.get('species', ''))}")
        species_note = clean_text(row.get("species_description", ""))
        if species_note:
            lines.append(f"   Species note: {species_note}")
        evidence = [clean_text(entry) for entry in row.get("evidence", []) if clean_text(entry)]
        if evidence:
            lines.append("   Evidence:")
            for evidence_line in evidence[: max(1, int(evidence_per_species))]:
                lines.append(f"   - {evidence_line}")
    return "\n".join(lines)
