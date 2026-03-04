import os
from dataclasses import dataclass

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
    # Providers
    llm_provider: str = _env("LLM_PROVIDER", "openai")
    llm_model: str = _env("LLM_MODEL", "gpt-4o-mini")
    openai_api_key: str = _env("OPENAI_API_KEY", "")

    llm_max_tokens: int = _env_int("LLM_MAX_TOKENS", 220)
    llm_temperature: float = _env_float("LLM_TEMPERATURE", 0.2)

    embedding_provider: str = _env("EMBEDDING_PROVIDER", "sentence_transformers")
    st_model: str = _env("ST_MODEL", "BAAI/bge-m3")
    openai_embed_model: str = _env("OPENAI_EMBED_MODEL", "text-embedding-3-small")

    # Paths
    kb_path: str = _env("KB_PATH", "knowledge_base")
    chroma_path: str = _env("CHROMA_PATH", "knowledge_base/vector_store_chroma")
    collection_name: str = _env("COLLECTION_NAME", "kb")

    # Retrieval / guardrails
    top_k: int = _env_int("TOP_K", 6)
    min_similarity: float = _env_float("MIN_SIMILARITY", 0.35)
    max_context_chars: int = _env_int("MAX_CONTEXT_CHARS", 8000)

    chunk_size: int = _env_int("CHUNK_SIZE", 900)
    chunk_overlap: int = _env_int("CHUNK_OVERLAP", 120)

    # Additional guardrails
    min_keyword_overlap: float = _env_float("MIN_KEYWORD_OVERLAP", 0.15)
    high_similarity_override: float = _env_float("HIGH_SIMILARITY_OVERRIDE", 0.65)

    clarify_min_similarity: float = _env_float("CLARIFY_MIN_SIMILARITY", 0.25)

    # GitHub Models (OpenAI-compatible)
    openai_base_url: str = _env("OPENAI_BASE_URL", "")

    github_token: str = _env("GITHUB_TOKEN", "")
    github_api_version: str = _env("GITHUB_API_VERSION", "2022-11-28")
    github_models_endpoint: str = _env("GITHUB_MODELS_ENDPOINT", "https://models.github.ai/inference")

    retrieve_top_n: int = _env_int("RETRIEVE_TOP_N", 10)

    use_reranker: bool = _env_bool("USE_RERANKER", False)
    rerank_keep_k: int = _env_int("RERANK_KEEP_K", 3)
    rerank_model: str = _env("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    rerank_max_doc_chars: int = _env_int("RERANK_MAX_DOC_CHARS", 900)
    rerank_device: str = _env("RERANK_DEVICE", "cuda")

    # Agentic orchestration
    use_langgraph: bool = _env_bool("USE_LANGGRAPH", True)

    # Appointment store
    appointments_path: str = _env("APPOINTMENTS_PATH", "data/appointments.json")

    # Server

    host: str = _env("HOST", "0.0.0.0")
    port: int = _env_int("PORT", 8000)

def get_settings() -> Settings:
    return Settings()
