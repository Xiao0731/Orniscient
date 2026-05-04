"""Vector retrieval over EvidenceChunk index."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

from kg_v2.rag.build_vector_index import _dense_embed_texts, hashing_embed
from kg_v2.schema.ontology_v2 import VECTOR_INDEX_DIR, load_jsonl


class VectorRetriever:
    def __init__(self, index_dir: str | Path = VECTOR_INDEX_DIR):
        index_path = Path(index_dir)
        manifest_path = index_path / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Vector index manifest not found: {manifest_path}")
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.vectors = np.load(index_path / "vectors.npy")
        self.metadata = load_jsonl(index_path / "metadata.jsonl")

    def _embed_query(self, query: str) -> np.ndarray:
        backend = self.manifest["backend"]
        if backend == "hashing":
            return hashing_embed(query, dim=self.manifest["dim"])
        if backend == "openai":
            model = self.manifest.get("model") or os.environ.get("KG_V2_EMBED_MODEL", "BAAI/bge-m3")
            return _dense_embed_texts([query], model=model)[0]
        raise ValueError(f"Unsupported backend: {backend}")

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        if len(self.metadata) == 0:
            return []
        query_vector = self._embed_query(query)
        scores = self.vectors @ query_vector
        top_indices = np.argsort(scores)[::-1][:top_k]
        results: list[dict] = []
        for index in top_indices:
            row = dict(self.metadata[int(index)])
            row["score"] = float(scores[int(index)])
            results.append(row)
        return results
