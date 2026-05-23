from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # App
    app_name: str
    debug: bool

    # Ollama
    ollama_base_url: str
    ollama_model: str
    ollama_embedding_model: str

    # PGVector
    pgvector_connection_string: str
    pgvector_collection: str

    # Document ingestion
    upload_dir: str
    chunk_size: int
    chunk_overlap: int
    min_similarity_score: float

    # Keycloak
    keycloak_url: str
    keycloak_realm: str
    keycloak_client_id: str


@lru_cache
def get_settings() -> Settings:
    return Settings()