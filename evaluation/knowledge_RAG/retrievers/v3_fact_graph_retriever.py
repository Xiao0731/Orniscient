from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from evaluation.knowledge_RAG.config import KnowledgeRAGConfig
from evaluation.knowledge_RAG.formatting.context_formatter import result_from_items
from evaluation.knowledge_RAG.retrievers.base import RetrievalItem, RetrievalRequest, RetrievalResult
from evaluation.knowledge_RAG.routing.dataset_router import route_dataset


FACT_QUERY = """
MATCH (t:Taxon)-[:HAS_FACT]->(f:Fact)
WHERE
  toLower(coalesce(t.taxon_id, "")) CONTAINS toLower($target)
  OR toLower(coalesce(t.scientific_name, "")) CONTAINS toLower($target)
  OR toLower(coalesce(t.english_name_primary, "")) CONTAINS toLower($target)
  OR toLower(coalesce(f.subject_taxon_id, f.species, f.subject_name, "")) CONTAINS toLower($target)
OPTIONAL MATCH (f)-[:SUPPORTED_BY]->(e:Evidence)-[:DERIVED_FROM]->(c:Chunk)
RETURN properties(f) AS fact,
       collect({evidence: properties(e), chunk: properties(c)})[0..3] AS evidence,
       properties(t) AS taxon
LIMIT $limit
UNION
MATCH (f:Fact)
WHERE
  toLower(coalesce(f.species, f.subject_name, "")) CONTAINS toLower($target)
  OR toLower(coalesce(f.subject_name, "")) CONTAINS toLower($target)
OPTIONAL MATCH (f)-[:SUPPORTED_BY|EVIDENCED_BY|HAS_EVIDENCE]->(e:EvidenceChunk)
RETURN properties(f) AS fact,
       collect({evidence: properties(e), chunk: properties(e)})[0..3] AS evidence,
       {} AS taxon
LIMIT $limit
"""


def _clean(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z][a-z0-9\-]{2,}", str(text or "").lower()))


def _score_fact(question: str, fact: dict[str, Any], evidence_text: str) -> float:
    q = _tokens(question)
    text = " ".join(_clean(fact.get(k)) for k in ["predicate", "fact_type", "object_name", "value_text", "source_chapter"]) + " " + evidence_text
    return float(len(q & _tokens(text)) + float(fact.get("confidence", 0.0) or 0.0))


class V3FactGraphRetriever:
    def __init__(self, config: KnowledgeRAGConfig) -> None:
        self.config = config
        self.truth_dir = Path("kg_v2/outputs/intermediate/truth_artifacts")

    def _from_neo4j(self, request: RetrievalRequest, limit: int) -> list[RetrievalItem]:
        try:
            from neo4j import GraphDatabase
        except Exception:
            return []
        if not self.config.neo4j_password:
            return []
        try:
            driver = GraphDatabase.driver(
                self.config.neo4j_uri,
                auth=(self.config.neo4j_username, self.config.neo4j_password),
            )
            with driver.session(database=self.config.neo4j_database) as session:
                rows = [dict(record) for record in session.run(FACT_QUERY, target=request.target_entity, limit=limit)]
            driver.close()
        except Exception:
            return []
        return self._rows_to_items(rows, request)

    def _rows_to_items(self, rows: list[dict[str, Any]], request: RetrievalRequest) -> list[RetrievalItem]:
        items: list[RetrievalItem] = []
        for row in rows:
            fact = dict(row.get("fact") or row)
            evidence_rows = row.get("evidence") or []
            evidence_text = ""
            evidence_id = ""
            chunk_id = ""
            chunk_props: dict[str, Any] = {}
            if evidence_rows:
                first = dict(evidence_rows[0] or {})
                ev = dict(first.get("evidence") or first)
                chunk_props = dict(first.get("chunk") or {})
                evidence_text = _clean(ev.get("evidence_quote") or ev.get("cleaned_text") or ev.get("raw_text"))
                evidence_id = _clean(ev.get("evidence_id"))
                chunk_id = _clean(ev.get("source_chunk_id") or ev.get("chunk_id") or chunk_props.get("chunk_id"))
            value = _clean(fact.get("object_text") or fact.get("object_name") or fact.get("object_canonical_name") or fact.get("value_text"))
            text_parts = [
                f"{_clean(fact.get('predicate') or fact.get('fact_type'))}: {value}".strip(),
                f"Evidence: {evidence_text[:800]}" if evidence_text else "",
                f"Chunk: {_clean(chunk_props.get('cleaned_text') or chunk_props.get('raw_text'))[:500]}" if chunk_props else "",
            ]
            items.append(
                RetrievalItem(
                    item_type="fact",
                    text="\n".join(part for part in text_parts if part),
                    score=_score_fact(request.question, fact, evidence_text),
                    taxon_name=_clean((row.get("taxon") or {}).get("scientific_name") or fact.get("species") or fact.get("subject_name") or fact.get("subject_taxon_id")),
                    fact_id=_clean(fact.get("fact_id")),
                    evidence_id=evidence_id,
                    chunk_id=chunk_id,
                    source_chapter=_clean(fact.get("source_chapter") or (evidence_rows and (evidence_rows[0].get("evidence") or {}).get("source_chapter"))),
                    metadata={**fact, "evidence_id": evidence_id, "chunk_id": chunk_id, "used_v1_directed": False},
                )
            )
        items.sort(key=lambda item: item.score, reverse=True)
        return items

    def _from_local_artifacts(self, request: RetrievalRequest, limit: int) -> list[RetrievalItem]:
        path = self.truth_dir / "fact_nodes.jsonl"
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        target = request.target_entity.lower()
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                node = json.loads(line)
                props = dict(node.get("properties") or {})
                if target and target not in _clean(props.get("species") or props.get("subject_name")).lower():
                    continue
                rows.append({"fact": props, "evidence": []})
                if len(rows) >= max(limit * 4, limit):
                    break
        return self._rows_to_items(rows, request)[:limit]

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        route = route_dataset(request.dataset, request.type, "kg_v3")
        limit = max(1, min(self.config.kg_top_k, route.max_facts))
        if not request.target_entity:
            return result_from_items(
                status="target_not_found",
                knowledge_mode="kg_v3",
                route=route.route,
                items=[],
                context_style=route.context_style,
            )
        items = self._from_neo4j(request, limit) or self._from_local_artifacts(request, limit)
        return result_from_items(
            status="ok" if items else "empty",
            knowledge_mode="kg_v3",
            route=route.route,
            items=items[:limit],
            target=request.target_entity,
            context_style=route.context_style,
            max_chars=self.config.max_context_chars,
            debug={
                "initial_retrieval_count": len(items),
                "used_v1_directed": False,
                "node_labels": ["Taxon", "Fact", "Evidence", "Chunk"],
            },
        )
