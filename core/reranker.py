from __future__ import annotations
from typing import Dict, Any, List
from sentence_transformers import CrossEncoder

_RERANKER = None
_RERANK_MODEL = None
_RERANK_DEVICE = None

def get_reranker(model_name: str, device: str = "cuda") -> CrossEncoder:
    global _RERANKER, _RERANK_MODEL, _RERANK_DEVICE
    if _RERANKER is None or _RERANK_MODEL != model_name or _RERANK_DEVICE != device:
        _RERANKER = CrossEncoder(model_name, device=device)
        _RERANK_MODEL = model_name
        _RERANK_DEVICE = device
    return _RERANKER

def rerank_hits(
    query: str,
    hits: List[Dict[str, Any]],
    model_name: str,
    keep_k: int,
    max_doc_chars: int,
    device: str = "cuda",
) -> List[Dict[str, Any]]:
    if not hits:
        return hits

    ce = get_reranker(model_name, device=device)

    pairs = []
    for h in hits:
        txt = (h.get("text") or "").strip()
        txt = txt[:max_doc_chars]
        pairs.append((query, txt))

    scores = ce.predict(pairs)  # higher is better

    out = []
    for h, s in zip(hits, scores):
        hh = dict(h)
        hh["rerank_score"] = float(s)
        out.append(hh)

    out.sort(key=lambda x: x.get("rerank_score", -1e9), reverse=True)
    return out[:keep_k]
