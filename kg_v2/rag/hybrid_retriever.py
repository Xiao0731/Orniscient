"""Hybrid retrieval over the KG and EvidenceChunk vector index."""

from __future__ import annotations

from collections import OrderedDict

from kg_v2.rag.neo4j_retriever import Neo4jRetriever
from kg_v2.rag.vector_retriever import VectorRetriever


class HybridRetriever:
    def __init__(self, graph_retriever: Neo4jRetriever | None = None, vector_retriever: VectorRetriever | None = None):
        self.graph_retriever = graph_retriever or Neo4jRetriever()
        self.vector_retriever = vector_retriever or VectorRetriever()

    def search(self, query: str, top_k: int = 8) -> dict:
        graph_result = self.graph_retriever.retrieve(query, limit=top_k)
        vector_hits = self.vector_retriever.search(query, top_k=top_k * 2)

        merged: OrderedDict[str, dict] = OrderedDict()

        if graph_result["matched_entities"] or graph_result["paths"]:
            for evidence_node in graph_result["evidence_chunks"]:
                props = dict(evidence_node.get("properties", {}))
                chunk_id = props.get("chunk_id")
                if not chunk_id:
                    continue
                props["score"] = props.get("score", 0.0) + 1.0
                props["retrieval_source"] = "graph"
                merged[chunk_id] = props

        for hit in vector_hits:
            chunk_id = hit.get("chunk_id")
            if not chunk_id:
                continue
            payload = dict(hit)
            if chunk_id in merged:
                merged[chunk_id]["score"] = merged[chunk_id].get("score", 0.0) + payload.get("score", 0.0)
                merged[chunk_id]["retrieval_source"] = "graph+vector"
            else:
                payload["retrieval_source"] = "vector"
                merged[chunk_id] = payload

        ranked_chunks = sorted(merged.values(), key=lambda row: row.get("score", 0.0), reverse=True)[:top_k]
        return {
            "query": query,
            "graph_context": graph_result,
            "chunks": ranked_chunks,
        }
