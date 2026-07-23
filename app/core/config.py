from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    openai_api_key: SecretStr = Field(default=SecretStr(""))

    openai_model_low: str = "gpt-4.1-mini"
    openai_model_medium: str = "gpt-4.1-mini"
    openai_model_high: str = "gpt-4.1-mini"
    openai_model_safety: str = "gpt-4.1-mini"

    openai_timeout_seconds: int = Field(
        default=120,
        ge=10,
        le=600,
    )

    openai_max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
    )

    max_upload_mb: int = Field(
        default=15,
        ge=1,
        le=100,
    )

    max_pdf_pages: int = Field(
        default=10,
        ge=1,
        le=100,
    )

    tesseract_cmd: str | None = None
    tesseract_language: str = "eng"
    poppler_path: str | None = None

    database_url: str = (
        "sqlite:///./data/runtime/invoice_intelligence.db"
    )

    db_echo: bool = False

    chroma_path: str = "./data/chroma"
    chroma_vendor_collection: str = "vendor_master"
    chroma_template_collection: str = "vendor_templates"
    chroma_history_collection: str = "validated_invoice_summaries"
    chroma_embedding_model: str = "all-MiniLM-L6-v2"

    rag_top_k: int = Field(
        default=5,
        ge=1,
        le=50,
    )

    rag_max_distance: float = Field(
        default=0.55,
        ge=0.0,
    )

    rag_ambiguity_margin: float = Field(
        default=0.03,
        ge=0.0,
    )

    rag_knowledge_base_version: str = "v1"
    rag_embedding_dimensions: int = 384
    rag_min_template_score: float = Field(
        default=0.45,
        ge=0.0,
        le=1.0,
    )

    rag_min_history_score: float = Field(
        default=0.45,
        ge=0.0,
        le=1.0,
    )

    max_correction_attempts: int = Field(
        default=1,
        ge=0,
        le=5,
    )

    safety_block_threshold: float = Field(
        default=0.80,
        ge=0.0,
        le=1.0,
    )

    openai_input_usd_per_million: float = Field(
        default=0.40,
        ge=0.0,
    )

    openai_output_usd_per_million: float = Field(
        default=1.60,
        ge=0.0,
    )

    def model_for_complexity(self, tier: str) -> str:
        """Return the configured model for a complexity tier."""

        models = {
            "low": self.openai_model_low,
            "medium": self.openai_model_medium,
            "high": self.openai_model_high,
        }

        normalized_tier = tier.lower().strip()

        return models.get(
            normalized_tier,
            self.openai_model_medium,
        )

    def has_openai_key(self) -> bool:
        """Return True when a usable OpenAI API key is configured."""

        value = self.openai_api_key.get_secret_value().strip()

        return bool(
            value
            and value != "replace_me"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Create and cache the application settings."""

    return Settings()