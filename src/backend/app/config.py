"""Application configuration using Pydantic Settings.

Configuration is loaded from environment variables and validated at startup.
Missing required variables will cause the application to fail fast with clear errors.
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = Field(description="PostgreSQL connection URL (asyncpg)")
    supabase_url: str = Field(description="Supabase project URL")
    supabase_secret_key: str = Field(description="Supabase secret API key (server-side only)")
    supabase_jwt_secret: str = Field(description="Supabase JWT secret for token verification")

    # AWS
    aws_access_key_id: str = Field(description="AWS access key ID")
    aws_secret_access_key: str = Field(description="AWS secret access key")
    aws_region: str = Field(default="us-east-1", description="AWS region")
    aws_endpoint_url: str | None = Field(
        default=None, description="AWS endpoint URL (for LocalStack)"
    )

    # Third-party APIs
    apify_api_token: str = Field(description="Apify API token for TikTok scraping")
    openai_api_key: str = Field(description="OpenAI API key for embeddings")

    # Agent LLM APIs
    anthropic_api_key: str = Field(description="Anthropic API key for Claude orchestrator")
    gemini_api_key: str = Field(description="Google Gemini API key for classification/vision")

    # Entity resolution APIs (optional — agent tools degrade gracefully without them)
    google_maps_api_key: str | None = Field(
        default=None, description="Google Maps API key for place resolution"
    )
    google_books_api_key: str | None = Field(
        default=None, description="Google Books API key (optional, uses public endpoint)"
    )
    tmdb_api_key: str | None = Field(
        default=None, description="TMDB API key for movie/show resolution"
    )
    spotify_client_id: str | None = Field(
        default=None, description="Spotify client ID for music resolution"
    )
    spotify_client_secret: str | None = Field(
        default=None, description="Spotify client secret for music resolution"
    )

    # Payments (optional for MVP)
    stripe_secret_key: str | None = Field(default=None, description="Stripe secret key")
    stripe_webhook_secret: str | None = Field(
        default=None, description="Stripe webhook signing secret"
    )

    # Notifications (optional for MVP)
    resend_api_key: str | None = Field(default=None, description="Resend API key for email")

    # Observability (optional)
    sentry_dsn: str | None = Field(default=None, description="Sentry DSN for error tracking")
    posthog_api_key: str | None = Field(default=None, description="PostHog API key for analytics")

    # Application
    environment: str = Field(default="development", description="Environment name")
    log_level: str = Field(default="INFO", description="Logging level")
    cors_origins: list[str] = Field(
        default=["http://localhost:3000"], description="Allowed CORS origins"
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment is one of allowed values."""
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"environment must be one of {allowed}")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is one of allowed values."""
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return v_upper

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Settings are loaded once and cached for the lifetime of the application.
    This ensures environment variables are read only once at startup.

    Returns:
        Settings instance with validated configuration.

    Raises:
        ValidationError: If required environment variables are missing or invalid.
    """
    return Settings()


# Convenience access to settings
settings = get_settings()
