"""Build a vector index for EvidenceChunk records."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

import numpy as np

from kg_v2.schema.ontology_v2 import INTERMEDIATE_DIR, VECTOR_INDEX_DIR, load_jsonl, write_jsonl

from evaluation.kg_RAG.embedding_adapter import EmbeddingAdapter, EmbeddingConfigError, validate_embedding_manifest


def hashing_embed(text: str, dim: int = 384) -> np.ndarray:
    vector = np.zeros(dim, dtype=np.float32)
    tokens = re.findall(r"\b\w+\b", (text or "").lower())
    for token in tokens:
        digest = hashlib.sha1(token.encode("utf-8")).hexdigest()
        bucket = int(digest[:8], 16) % dim
        sign = 1.0 if int(digest[8:10], 16) % 2 == 0 else -1.0
        vector[bucket] += sign
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector /= norm
    return vector


def _dense_embed_texts(texts: list[str], model: str) -> np.ndarray:
    adapter = EmbeddingAdapter(model=model, dim=int(os.environ.get("EMBEDDING_DIM", "1024")))
    matrix = np.array(adapter.embed_texts(texts), dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def build_vector_index(
    evidence_chunks_path=INTERMEDIATE_DIR / "evidence_chunks.jsonl",
    index_dir: str | Path = VECTOR_INDEX_DIR,
    backend: str = "hashing",
    dim: int = 384,
) -> dict:
    index_path = Path(index_dir)
    index_path.mkdir(parents=True, exist_ok=True)
    evidence_rows = load_jsonl(evidence_chunks_path)
    texts = [row.get("cleaned_text") or row.get("raw_text", "") for row in evidence_rows]

    actual_backend = backend
    if backend in {"dense", "bge_m3", "api_compatible", "openai"}:
        provider = os.environ.get("EMBEDDING_PROVIDER", "bge_m3")
        model = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-m3")
        expected_dim = int(os.environ.get("EMBEDDING_DIM", "1024"))
        validate_embedding_manifest(
            index_path,
            embedding_provider=provider,
            embedding_model=model,
            embedding_dim=expected_dim,
            index_name=os.environ.get("PGVECTOR_COLLECTION", "bird_kg_v3_bge_m3"),
            rebuild=os.environ.get("REBUILD_VECTOR_INDEX", "").lower() in {"1", "true", "yes"},
        )
        try:
            vectors = _dense_embed_texts(texts, model=model)
            metadata = {"backend": provider, "model": model, "dim": int(vectors.shape[1])}
        except EmbeddingConfigError:
            raise
        except Exception:
            actual_backend = "hashing"
        else:
            np.save(index_path / "vectors.npy", vectors)
            write_jsonl(index_path / "metadata.jsonl", evidence_rows)
            manifest = {
                "backend": provider,
                "model": model,
                "dim": int(vectors.shape[1]),
                "count": len(evidence_rows),
                "metadata_path": str(index_path / "metadata.jsonl"),
                "vectors_path": str(index_path / "vectors.npy"),
            }
            with (index_path / "manifest.json").open("w", encoding="utf-8") as handle:
                json.dump(manifest, handle, ensure_ascii=False, indent=2)
            return manifest

    if actual_backend == "hashing":
        vectors = np.vstack([hashing_embed(text, dim=dim) for text in texts]) if texts else np.zeros((0, dim), dtype=np.float32)
        np.save(index_path / "vectors.npy", vectors)
        write_jsonl(index_path / "metadata.jsonl", evidence_rows)
        manifest = {
            "backend": "hashing",
            "dim": dim,
            "count": len(evidence_rows),
            "metadata_path": str(index_path / "metadata.jsonl"),
            "vectors_path": str(index_path / "vectors.npy"),
        }
        with (index_path / "manifest.json").open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2)
        return manifest

    raise ValueError(f"Unsupported vector backend: {backend}")


if __name__ == "__main__":
    build_vector_index()
