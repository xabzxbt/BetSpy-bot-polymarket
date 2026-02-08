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

    polymarket_gamma_api_url: str = Field(
        default="https://gamma-api.polymarket.com",
        description="Polymarket Gamma API base URL",
    )

    # USER_PNL_URL из фронта (используется для /user-pnl)
    polymarket_user_pnl_url: str = Field(
        default="https://user-pnl-api.polymarket.com",
        description="Polymarket User PnL base URL (USER_PNL_URL from frontend)",
    )

    # Referral Code for Polymarket links
    polymarket_referral_code: str = Field(
        default="",
        description="Polymarket referral code (e.g., xabzxbt-t1f3)",
    )

    # NOTE: CLOB auth keys removed — whale analysis uses PUBLIC endpoints only.
    # No private key needed.

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
        default=30,
        ge=1,
        description="Maximum API requests per period",
    )

    api_rate_limit_period_seconds: int = Field(
        default=60,
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
        market_slug: Market slug from API (optional, can be empty or same as event_slug)
        
    Returns:
        Full URL with referral code if configured
        
    URL Format:
        - If market_slug is empty or same as event_slug: /event/{event_slug}
        - If market_slug is different: /event/{event_slug}/{market_slug}
    """
    settings = get_settings()
    
    # Build base URL - don't duplicate slug if they're the same
    if not market_slug or market_slug == event_slug:
        base_url = f"https://polymarket.com/event/{event_slug}"
    else:
        base_url = f"https://polymarket.com/event/{event_slug}/{market_slug}"
    
    # Add referral code if configured
    if settings.polymarket_referral_code:
        # Clean the referral code (remove any trailing dashes or spaces)
        ref_code = settings.polymarket_referral_code.strip().rstrip('-')
        return f"{base_url}?via={ref_code}"
    
    return base_url
