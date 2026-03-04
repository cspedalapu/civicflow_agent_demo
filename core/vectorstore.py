from __future__ import annotations

import json

from typing import Any, Dict, List, Optional, Tuple
import chromadb
from chromadb.utils import embedding_functions

from .config import Settings

def _safe_collection_name(name: str) -> str:
    n = (name or "").strip()
    if len(n) < 3:
        n = f"{n}_main" if n else "kb_main"
    return n

def _build_embedding_fn(settings: Settings):
    provider = settings.embedding_provider.lower().strip()
    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for EMBEDDING_PROVIDER=openai")
        return embedding_functions.OpenAIEmbeddingFunction(
            api_key=settings.openai_api_key,
            model_name=settings.openai_embed_model,
        )
    # default: sentence-transformers
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=settings.st_model
    )

def sanitize_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
    """
    Chroma metadata values must be: str, int, float, bool, or None.
    This function flattens nested dicts using dot-keys, and JSON-stringifies lists/unknown types.
    """
    out: Dict[str, Any] = {}

    def _walk(obj: Any, prefix: str = ""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                key = f"{prefix}.{k}" if prefix else str(k)
                _walk(v, key)
        elif isinstance(obj, (str, int, float, bool)) or obj is None:
            out[prefix] = obj
        elif isinstance(obj, list):
            out[prefix] = json.dumps(obj, ensure_ascii=False)
        else:
            out[prefix] = str(obj)

    _walk(meta, "")
    # Remove empty key if present
    out.pop("", None)
    return out


class ChromaKB:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = chromadb.PersistentClient(path=settings.chroma_path)
        self.embed_fn = _build_embedding_fn(settings)
        cname = _safe_collection_name(settings.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=cname,
            embedding_function=self.embed_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(self, ids, documents, metadatas):
        clean = [sanitize_metadata(m or {}) for m in metadatas]
        self.collection.upsert(ids=ids, documents=documents, metadatas=clean)

    def query(self, query_text: str, top_k: int) -> Dict[str, Any]:
        return self.collection.query(
            query_texts=[query_text],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

def distance_to_similarity(d: float) -> float:
    """Best-effort normalization for Chroma distances.
    - For cosine distance (0..2): similarity ≈ 1 - d
    - Otherwise: similarity = 1/(1+d)
    """
    try:
        d = float(d)
    except Exception:
        return 0.0
    if 0.0 <= d <= 2.0:
        return max(0.0, 1.0 - d)
    return 1.0 / (1.0 + max(d, 0.0))
