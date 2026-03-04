"""Source -> ExtractedDoc

Extraction rules:
- .md/.txt: used as-is
- .json: prefer explicit text fields; otherwise render nested structures to readable text
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List
import re

from .utils import read_text, read_json, sha256_text, write_json


@dataclass
class ExtractedDoc:
    doc_id: str
    title: str
    text: str
    metadata: Dict[str, Any]

_PRIMARY_TEXT_KEYS = ("content", "text", "notes", "summary", "description", "body", "markdown", "md")
_JSON_META_SKIP_KEYS = {"content_hash"}


def _humanize_key(key: str) -> str:
    key = str(key or "").strip().replace("_", " ")
    return re.sub(r"\s+", " ", key).strip() or "field"


def _scalar_text(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _render_structured(value: Any, indent: int = 0) -> List[str]:
    prefix = "  " * indent
    lines: List[str] = []

    if isinstance(value, dict):
        for key, item in value.items():
            if key in _JSON_META_SKIP_KEYS:
                continue
            label = _humanize_key(key)
            if isinstance(item, (dict, list)):
                nested = _render_structured(item, indent + 1)
                if nested:
                    lines.append(f"{prefix}- {label}:")
                    lines.extend(nested)
            elif item not in (None, ""):
                lines.append(f"{prefix}- {label}: {_scalar_text(item)}")
        return lines

    if isinstance(value, list):
        for item in value:
            if isinstance(item, (dict, list)):
                nested = _render_structured(item, indent + 1)
                if nested:
                    lines.append(f"{prefix}-")
                    lines.extend(nested)
            elif item not in (None, ""):
                lines.append(f"{prefix}- {_scalar_text(item)}")
        return lines

    if value not in (None, ""):
        lines.append(f"{prefix}{_scalar_text(value)}")
    return lines


def _json_to_text(meta: Dict[str, Any], title: str) -> str:
    parts: List[str] = []
    consumed: set[str] = set()

    for key in _PRIMARY_TEXT_KEYS:
        item = meta.get(key)
        if isinstance(item, str) and item.strip():
            parts.append(item.strip())
            consumed.add(key)
        elif isinstance(item, (dict, list)):
            rendered = _render_structured(item)
            if rendered:
                parts.append(f"{_humanize_key(key)}:\n" + "\n".join(rendered))
                consumed.add(key)

    remaining = {
        k: v
        for k, v in meta.items()
        if k not in consumed and k not in _JSON_META_SKIP_KEYS and v not in (None, "")
    }
    rendered_remaining = _render_structured(remaining)
    if rendered_remaining:
        parts.append("Additional structured fields:\n" + "\n".join(rendered_remaining))

    if parts:
        return "\n\n".join(parts).strip()

    rendered_meta = _render_structured(meta)
    if rendered_meta:
        heading = f"# {title}\n" if title else ""
        return (heading + "\n".join(rendered_meta)).strip()
    return ""


def _safe_doc_id(path: Path, meta: Dict[str, Any], source_root: Path | None = None) -> str:
    explicit = str(meta.get("doc_id") or "").strip()
    if explicit:
        return explicit

    rel = path
    if source_root is not None:
        try:
            rel = path.relative_to(source_root)
        except ValueError:
            rel = path
    digest = sha256_text(rel.as_posix().lower())[:8]
    return f"{path.stem}__{digest}"


def _safe_doc_filename(doc_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(doc_id)).strip("._") or "doc"


def extract_one(path: Path, source_root: Path | None = None) -> ExtractedDoc:
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt"}:
        text = read_text(path).strip()
        meta = {"source_file": path.name, "source_type": suffix.lstrip(".")}
        title = path.stem
    elif suffix == ".json":
        raw = read_json(path)
        meta = raw if isinstance(raw, dict) else {"raw_json": raw}
        title = str(meta.get("title") or path.stem)
        text = _json_to_text(meta, title)
        if not text:
            text = f"Metadata-only document. Title: {title}. Source URL: {meta.get('source_url','')}."
            meta["metadata_only"] = True
    else:
        raise ValueError(f"Unsupported file type: {path.name}")

    doc_id = _safe_doc_id(path, meta, source_root=source_root)
    meta = dict(meta)
    meta.setdefault("title", title)
    meta.setdefault("doc_id", doc_id)
    meta.setdefault("source_file", path.name)
    meta.setdefault("source_type", suffix.lstrip("."))
    meta["text_hash"] = sha256_text(text)
    return ExtractedDoc(doc_id=doc_id, title=title, text=text, metadata=meta)


def extract_all(sources_dir: Path, extracted_dir: Path) -> int:
    extracted_dir.mkdir(parents=True, exist_ok=True)
    for old in extracted_dir.glob("*.json"):
        old.unlink()

    count = 0
    seen_doc_ids: set[str] = set()

    for p in sorted(sources_dir.rglob("*")):
        if p.is_dir():
            continue
        if p.suffix.lower() not in {".md", ".txt", ".json"}:
            continue
        doc = extract_one(p, source_root=sources_dir)

        resolved_id = doc.doc_id
        if resolved_id in seen_doc_ids:
            n = 2
            while f"{doc.doc_id}__dup{n}" in seen_doc_ids:
                n += 1
            resolved_id = f"{doc.doc_id}__dup{n}"
            doc.metadata["doc_id_original"] = doc.doc_id
            doc.metadata["doc_id_collision_resolved"] = True

        doc.doc_id = resolved_id
        doc.metadata["doc_id"] = resolved_id
        seen_doc_ids.add(resolved_id)

        out = extracted_dir / f"{_safe_doc_filename(doc.doc_id)}.json"
        write_json(out, {
            "doc_id": doc.doc_id,
            "title": doc.title,
            "text": doc.text,
            "metadata": doc.metadata,
        })
        count += 1
    return count
