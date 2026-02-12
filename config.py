"""
Application configuration using pydantic-settings.

All configuration is loaded from environment variables.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram Bot
    bot_token: str = Field(..., description="Telegram Bot API token")

    # Database
    database_url: str = Field(..., description="PostgreSQL connection URL")

    @field_validator("database_url", mode="before")
    @classmethod
    def fix_database_url(cls, v: str) -> str:
        if v and v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v and v.startswith("postgresql://") and "+asyncpg" not in v:
             return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    # Polymarket API URLs
    polymarket_data_api_url: str = Field(
        default="https://data-api.polymarket.com",
        description="Polymarket Data API base URL",
    )

    # Referral Code for Polymarket links
    polymarket_referral_code: str = Field(
        default="",
        description="Polymarket referral code (e.g., xabzxbt)",
    )

    # Polling Configuration
    polling_interval_seconds: int = Field(
        default=60,
        ge=10,
        le=300,
        description="Interval between trade checks in seconds",
    )

    # User Limits
    max_wallets_per_user: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Maximum wallets a user can track",
    )

    # Minimum trade amount filter
    min_trade_amount_usdc: float = Field(
        default=0.0,
        ge=0.0,
        description="Minimum trade amount in USDC to trigger notification",
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )

    # Rate Limiting
    api_rate_limit_requests: int = Field(
        default=100,
        ge=1,
        description="Maximum API requests per period",
    )

    api_rate_limit_period_seconds: int = Field(
        default=10,
        ge=1,
        description="Rate limit period in seconds",
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def get_referral_link(event_slug: str, market_slug: str = "") -> str:
    """
    Generate Polymarket link with referral code.
    
    Args:
        event_slug: Event slug from API
        market_slug: Market slug (kept for backwards compatibility, not used)
        
    Returns:
        Full URL with referral code if configured
    """
    settings = get_settings()
    
    # Polymarket only supports /event/{event_slug} format
    base_url = f"https://polymarket.com/event/{event_slug}"
    
    # Add referral code if configured
    if settings.polymarket_referral_code:
        ref_code = settings.polymarket_referral_code.strip().rstrip('-')
        return f"{base_url}?via={ref_code}"
    
    return base_url


def get_profile_link(address: str) -> str:
    """Generate Polymarket profile link with referral code."""
    settings = get_settings()
    base_url = f"https://polymarket.com/profile/{address}"

    if settings.polymarket_referral_code:
        ref_code = settings.polymarket_referral_code.strip().rstrip('-')
        return f"{base_url}?via={ref_code}"
    
    return base_url
