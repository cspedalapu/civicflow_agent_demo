import os
from dataclasses import dataclass, field
from typing import Any


def _env(key: str, default: str = "") -> str:
    v = os.getenv(key)
    return v if v is not None and v != "" else default

def _env_int(key: str, default: int) -> int:
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default

def _env_float(key: str, default: float) -> float:
    try:
        return float(_env(key, str(default)))
    except ValueError:
        return default

def _env_bool(key: str, default: bool) -> bool:
    v = _env(key, str(default)).strip().lower()
    return v in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    """Application settings — env vars are read when get_settings() is called,
    NOT at import time, so load_dotenv() has a chance to run first."""

    # Providers
    llm_provider: str = ""
    llm_model: str = ""
    openai_api_key: str = ""

    llm_max_tokens: int = 220
    llm_temperature: float = 0.2

    embedding_provider: str = ""
    st_model: str = ""
    openai_embed_model: str = ""

    # Paths
    kb_path: str = ""
    chroma_path: str = ""
    collection_name: str = ""

    # Retrieval / guardrails
    top_k: int = 6
    min_similarity: float = 0.35
    max_context_chars: int = 8000

    chunk_size: int = 900
    chunk_overlap: int = 120

    # Additional guardrails
    min_keyword_overlap: float = 0.15
    high_similarity_override: float = 0.65

    clarify_min_similarity: float = 0.25

    # GitHub Models (OpenAI-compatible)
    openai_base_url: str = ""

    github_token: str = ""
    github_api_version: str = ""
    github_models_endpoint: str = ""

    retrieve_top_n: int = 10

    use_reranker: bool = False
    rerank_keep_k: int = 3
    rerank_model: str = ""
    rerank_max_doc_chars: int = 900
    rerank_device: str = ""

    # Agentic orchestration
    use_langgraph: bool = True

    # Appointment store
    appointments_path: str = ""

    # Server
    host: str = ""
    port: int = 8000


def get_settings() -> Settings:
    """Build Settings from current os.environ (call AFTER load_dotenv)."""
    return Settings(
        llm_provider=_env("LLM_PROVIDER", "openai"),
        llm_model=_env("LLM_MODEL", "gpt-4o-mini"),
        openai_api_key=_env("OPENAI_API_KEY", ""),
        llm_max_tokens=_env_int("LLM_MAX_TOKENS", 220),
        llm_temperature=_env_float("LLM_TEMPERATURE", 0.2),
        embedding_provider=_env("EMBEDDING_PROVIDER", "sentence_transformers"),
        st_model=_env("ST_MODEL", "BAAI/bge-m3"),
        openai_embed_model=_env("OPENAI_EMBED_MODEL", "text-embedding-3-small"),
        kb_path=_env("KB_PATH", "knowledge_base"),
        chroma_path=_env("CHROMA_PATH", "knowledge_base/vector_store_chroma"),
        collection_name=_env("COLLECTION_NAME", "kb"),
        top_k=_env_int("TOP_K", 6),
        min_similarity=_env_float("MIN_SIMILARITY", 0.35),
        max_context_chars=_env_int("MAX_CONTEXT_CHARS", 8000),
        chunk_size=_env_int("CHUNK_SIZE", 900),
        chunk_overlap=_env_int("CHUNK_OVERLAP", 120),
        min_keyword_overlap=_env_float("MIN_KEYWORD_OVERLAP", 0.15),
        high_similarity_override=_env_float("HIGH_SIMILARITY_OVERRIDE", 0.65),
        clarify_min_similarity=_env_float("CLARIFY_MIN_SIMILARITY", 0.25),
        openai_base_url=_env("OPENAI_BASE_URL", ""),
        github_token=_env("GITHUB_TOKEN", ""),
        github_api_version=_env("GITHUB_API_VERSION", "2022-11-28"),
        github_models_endpoint=_env("GITHUB_MODELS_ENDPOINT", "https://models.github.ai/inference"),
        retrieve_top_n=_env_int("RETRIEVE_TOP_N", 10),
        use_reranker=_env_bool("USE_RERANKER", False),
        rerank_keep_k=_env_int("RERANK_KEEP_K", 3),
        rerank_model=_env("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"),
        rerank_max_doc_chars=_env_int("RERANK_MAX_DOC_CHARS", 900),
        rerank_device=_env("RERANK_DEVICE", "cpu"),
        use_langgraph=_env_bool("USE_LANGGRAPH", True),
        appointments_path=_env("APPOINTMENTS_PATH", "data/appointments.json"),
        host=_env("HOST", "0.0.0.0"),
        port=_env_int("PORT", 8000),
    )
