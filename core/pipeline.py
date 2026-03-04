from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List

from .config import Settings
from .extractor import extract_all
from .chunker import make_chunks
from .utils import read_json, append_jsonl
from .vectorstore import ChromaKB

def ingest(settings: Settings) -> Dict[str, Any]:
    kb_path = Path(settings.kb_path)
    sources_dir = kb_path / "sources"
    extracted_dir = kb_path / "extracted"
    index_dir = kb_path / "index"
    index_dir.mkdir(parents=True, exist_ok=True)
    chunks_index_path = index_dir / "chunks.jsonl"
    if chunks_index_path.exists():
        chunks_index_path.unlink()

    # 1) Extract
    extracted_count = extract_all(sources_dir=sources_dir, extracted_dir=extracted_dir)

    # 2) Chunk + persist index + upsert to Chroma (fresh rebuild)
    kb = ChromaKB(settings)
    kb.reset_collection()

    upsert_ids: List[str] = []
    upsert_docs: List[str] = []
    upsert_metas: List[Dict[str, Any]] = []

    for doc_path in sorted(extracted_dir.glob("*.json")):
        data = read_json(doc_path)
        doc_id = data["doc_id"]
        title = data.get("title") or doc_id
        text = data.get("text") or ""
        meta = data.get("metadata") or {}
        chunks = make_chunks(
            doc_id=doc_id,
            title=title,
            text=text,
            metadata=meta,
            chunk_size=settings.chunk_size,
            overlap=settings.chunk_overlap,
        )

        for c in chunks:
            append_jsonl(chunks_index_path, {
                "chunk_id": c.chunk_id,
                "doc_id": doc_id,
                "title": title,
                "metadata": c.metadata,
                "text_len": len(c.text),
            })
            upsert_ids.append(c.chunk_id)
            upsert_docs.append(c.text)
            upsert_metas.append(c.metadata)

    if upsert_ids:
        kb.upsert(ids=upsert_ids, documents=upsert_docs, metadatas=upsert_metas)

    return {
        "extracted_docs": extracted_count,
        "chunks_upserted": len(upsert_ids),
        "collection": settings.collection_name,
        "chroma_path": settings.chroma_path,
    }
