from dataclasses import dataclass
from typing import List, Dict, Any
import re

from .kb_quality import clean_user_facing_text, infer_content_audience

@dataclass
class Chunk:
    chunk_id: str
    text: str
    metadata: Dict[str, Any]


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 120) -> List[str]:
    """Simple character chunker with overlap."""
    if not text:
        return []
    text = text.replace("\r\n", "\n")
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(n, start + chunk_size)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = max(0, end - overlap)
    return chunks


_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+.+$", re.MULTILINE)


def split_markdown_sections(md: str) -> List[str]:
    """Split markdown into sections by headings, keeping each heading with its content."""
    md = (md or "").replace("\r\n", "\n")
    matches = list(_MD_HEADING_RE.finditer(md))
    if not matches:
        return [md.strip()] if md.strip() else []

    sections: List[str] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md)
        sec = md[start:end].strip()
        if sec:
            sections.append(sec)
    return sections


def make_chunks(
    doc_id: str,
    title: str,
    text: str,
    metadata: Dict[str, Any],
    chunk_size: int = 900,
    overlap: int = 120,
) -> List[Chunk]:
    out: List[Chunk] = []

    is_markdown = (metadata.get("source_type") == "md") or bool(_MD_HEADING_RE.search(text or ""))

    parts: List[str] = []
    if is_markdown:
        for sec in split_markdown_sections(text):
            if len(sec) <= chunk_size:
                parts.append(sec)
            else:
                # Keep the first heading line as prefix for sub-chunks
                lines = sec.splitlines()
                prefix = lines[0].strip() if lines else ""
                body = "\n".join(lines[1:]).strip()

                # Reserve space for prefix + newline
                reserve = len(prefix) + 1 if prefix else 0
                sub_chunk_size = max(200, chunk_size - reserve)

                for sub in chunk_text(body, chunk_size=sub_chunk_size, overlap=overlap):
                    parts.append(f"{prefix}\n{sub}".strip() if prefix else sub.strip())
    else:
        parts = chunk_text(text, chunk_size=chunk_size, overlap=overlap)

    for i, part in enumerate(parts):
        cleaned_part = clean_user_facing_text(part)
        if not cleaned_part:
            continue
        cid = f"{doc_id}::chunk{i:04d}"
        md = dict(metadata)
        md.update(
            {
                "doc_id": doc_id,
                "title": title,
                "chunk_index": i,
                "content_audience": infer_content_audience(title=title, text=cleaned_part),
            }
        )
        out.append(Chunk(chunk_id=cid, text=cleaned_part, metadata=md))

    return out
