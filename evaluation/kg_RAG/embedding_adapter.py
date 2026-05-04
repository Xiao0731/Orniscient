from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None  # type: ignore


DEFAULT_EMBEDDING_PROVIDER = "bge_m3"
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-m3"
DEFAULT_EMBEDDING_DIM = 1024
MANIFEST_FILENAME = "embedding_manifest.json"


class EmbeddingConfigError(RuntimeError):
    pass


class EmbeddingManifestError(RuntimeError):
    pass


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_repo_env(required: tuple[str, ...] = ()) -> None:
    env_path = _repo_root() / ".env"
    if load_dotenv and env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)
    elif required:
        raise EmbeddingConfigError(
            "Missing .env or missing required key: " + " / ".join(required)
        )


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _key_suffix(key: str) -> str:
    return f"...{key[-4:]}" if key else "<empty>"


def _manifest_path(index_dir: str | Path) -> Path:
    return Path(index_dir) / MANIFEST_FILENAME


def build_embedding_manifest(
    *,
    embedding_provider: str,
    embedding_model: str,
    embedding_dim: int,
    index_name: str,
) -> dict[str, Any]:
    return {
        "embedding_provider": embedding_provider,
        "embedding_model": embedding_model,
        "embedding_dim": int(embedding_dim),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "index_name": index_name,
    }


def write_embedding_manifest(index_dir: str | Path, manifest: dict[str, Any]) -> Path:
    path = _manifest_path(index_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_embedding_manifest(index_dir: str | Path) -> dict[str, Any] | None:
    path = _manifest_path(index_dir)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def validate_embedding_manifest(
    index_dir: str | Path,
    *,
    embedding_provider: str,
    embedding_model: str,
    embedding_dim: int,
    index_name: str = "",
    rebuild: bool = False,
) -> dict[str, Any]:
    existing = load_embedding_manifest(index_dir)
    if existing is None:
        manifest = build_embedding_manifest(
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            embedding_dim=embedding_dim,
            index_name=index_name or f"bird_kg_v3_{embedding_model.split('/')[-1].lower().replace('-', '_')}",
        )
        write_embedding_manifest(index_dir, manifest)
        return manifest

    mismatches: list[str] = []
    if str(existing.get("embedding_provider", "")) != str(embedding_provider):
        mismatches.append("embedding_provider")
    if str(existing.get("embedding_model", "")) != str(embedding_model):
        mismatches.append("embedding_model")
    if int(existing.get("embedding_dim", 0) or 0) != int(embedding_dim):
        mismatches.append("embedding_dim")

    if mismatches and not rebuild:
        raise EmbeddingManifestError(
            "Embedding manifest mismatch for vector index "
            f"{Path(index_dir)} ({', '.join(mismatches)}). "
            "Delete the old vector index or pass --rebuild-vector-index / --rebuild."
        )

    if mismatches and rebuild:
        manifest = build_embedding_manifest(
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            embedding_dim=embedding_dim,
            index_name=index_name or str(existing.get("index_name", "")),
        )
        write_embedding_manifest(index_dir, manifest)
        return manifest
    return existing


@dataclass(frozen=True)
class EmbeddingAdapterConfig:
    provider: str = DEFAULT_EMBEDDING_PROVIDER
    model: str = DEFAULT_EMBEDDING_MODEL
    dim: int = DEFAULT_EMBEDDING_DIM
    device: str = "auto"
    api_base: str = ""
    api_key: str = ""
    batch_size: int = 16
    max_length: int = 8192

    @classmethod
    def from_env(cls, *, provider: str | None = None, model: str | None = None, dim: int | None = None) -> "EmbeddingAdapterConfig":
        load_repo_env()
        return cls(
            provider=provider or _env("EMBEDDING_PROVIDER", DEFAULT_EMBEDDING_PROVIDER),
            model=model or _env("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
            dim=int(dim or _env("EMBEDDING_DIM", str(DEFAULT_EMBEDDING_DIM))),
            device=_env("EMBEDDING_DEVICE", "auto"),
            api_base=_env("EMBEDDING_API_BASE") or _env("EMBEDDING_BASE_URL"),
            api_key=_env("EMBEDDING_API_KEY"),
            batch_size=int(_env("EMBEDDING_BATCH_SIZE", "16")),
            max_length=int(_env("EMBEDDING_MAX_LENGTH", "8192")),
        )


class EmbeddingAdapter:
    def __init__(self, config: EmbeddingAdapterConfig | None = None, **overrides: Any) -> None:
        if config is None:
            config = EmbeddingAdapterConfig.from_env(
                provider=overrides.pop("provider", None),
                model=overrides.pop("model", None),
                dim=overrides.pop("dim", None),
            )
        self.config = config
        self.provider = self._normalize_provider(config.provider)
        self.model_name = config.model
        self._model: Any = None
        if self.provider == "api_compatible" and "deepseek" in self.model_name.lower():
            raise EmbeddingConfigError(
                "DeepSeek chat/reasoning models must not be used as embedding models. "
                "Set EMBEDDING_MODEL=BAAI/bge-m3 or another embedding-capable model."
            )
        if self.provider == "api_compatible" and (not config.api_base or not config.api_key):
            raise EmbeddingConfigError(
                "Missing .env or missing required key: EMBEDDING_API_BASE / EMBEDDING_API_KEY"
            )

    @staticmethod
    def _normalize_provider(provider: str) -> str:
        provider = (provider or DEFAULT_EMBEDDING_PROVIDER).strip()
        if provider in {"bge_m3", "local_bge_m3"}:
            return "local_bge_m3"
        if provider in {"api", "api_compatible", "openai_compatible"}:
            return "api_compatible"
        if provider == "disabled":
            return "disabled"
        raise EmbeddingConfigError(f"Unsupported embedding provider: {provider}")

    @property
    def dim(self) -> int:
        return int(self.config.dim)

    @property
    def enabled(self) -> bool:
        return self.provider != "disabled"

    def _load_local_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer

            kwargs = {}
            if self.config.device and self.config.device != "auto":
                kwargs["device"] = self.config.device
            self._model = SentenceTransformer(self.model_name, **kwargs)
            return self._model
        except Exception as first_error:
            try:
                from FlagEmbedding import BGEM3FlagModel

                kwargs = {"use_fp16": False}
                if self.config.device and self.config.device != "auto":
                    kwargs["device"] = self.config.device
                self._model = BGEM3FlagModel(self.model_name, **kwargs)
                return self._model
            except Exception as second_error:
                raise EmbeddingConfigError(
                    "Local BGE-M3 embedding backend is unavailable. Install sentence-transformers "
                    "or FlagEmbedding, or set EMBEDDING_PROVIDER=api_compatible with "
                    "EMBEDDING_API_BASE/EMBEDDING_API_KEY."
                ) from second_error or first_error

    def _embed_local(self, texts: list[str]) -> list[list[float]]:
        model = self._load_local_model()
        if hasattr(model, "encode"):
            vectors = model.encode(texts, batch_size=self.config.batch_size, normalize_embeddings=True)
            return [list(map(float, row)) for row in vectors]
        output = model.encode(texts, batch_size=self.config.batch_size, max_length=self.config.max_length)
        dense = output.get("dense_vecs", output) if isinstance(output, dict) else output
        return [list(map(float, row)) for row in dense]

    def _embed_api(self, texts: list[str]) -> list[list[float]]:
        base = self.config.api_base.rstrip("/")
        url = base if base.endswith("/embeddings") else f"{base}/embeddings"
        payload = json.dumps({"model": self.model_name, "input": texts}, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8"))
        items = data.get("data", [])
        vectors = [item.get("embedding", []) for item in items]
        if any(len(vector) != self.dim for vector in vectors):
            actual_dims = [len(vector) for vector in vectors]
            raise EmbeddingConfigError(
                f"Embedding dim mismatch for {self.model_name}: expected dim {self.dim}, "
                f"actual dim(s) {actual_dims[:3]} from {url}"
            )
        return [list(map(float, vector)) for vector in vectors]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if self.provider == "disabled":
            raise EmbeddingConfigError("Embedding is disabled; vector retrieval is unavailable.")
        clean_texts = [str(text or "")[: self.config.max_length * 4] for text in texts]
        vectors = self._embed_api(clean_texts) if self.provider == "api_compatible" else self._embed_local(clean_texts)
        if vectors and len(vectors[0]) != self.dim:
            raise EmbeddingConfigError(
                f"Embedding dim mismatch for {self.model_name}: expected {self.dim}, got {len(vectors[0])}"
            )
        return vectors

    def embed_query(self, query: str) -> list[float]:
        vectors = self.embed_texts([query])
        return vectors[0] if vectors else []

    def manifest(self, index_name: str = "bird_kg_v3_bge_m3") -> dict[str, Any]:
        return build_embedding_manifest(
            embedding_provider=self.config.provider,
            embedding_model=self.model_name,
            embedding_dim=self.dim,
            index_name=index_name,
        )

    def log_safe_summary(self) -> str:
        if self.provider == "api_compatible":
            return (
                f"embedding_provider=api_compatible model={self.model_name} dim={self.dim} "
                f"api_key={_key_suffix(self.config.api_key)}"
            )
        return f"embedding_provider={self.config.provider} model={self.model_name} dim={self.dim}"
