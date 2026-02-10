"""
BetSpy Analytics Integration — CHANGES TO EXISTING FILES

This file documents the EXACT changes needed in existing files.
All new files go into the project as-is. These are the PATCHES.

=================================================================
FILE 1: main.py — Register new handler
=================================================================

ADD import at top (after other handler imports):
>>> from handlers_analytics import setup_analytics_handlers

ADD handler registration (BEFORE setup_intelligence_handlers):
>>> setup_analytics_handlers(dp)  # Deep Analysis — BEFORE intelligence (has intel: catch-all)

ADD cleanup in finally block:
>>> from analytics.data_fetcher import data_fetcher as analytics_fetcher
>>> await analytics_fetcher.close()

=================================================================
FILE 2: keyboards_intelligence.py — Add "Deep Analysis" button
=================================================================

In function get_market_detail_keyboard(), ADD the Deep Analysis button
BEFORE the watchlist button:

    # Deep Analysis button
    if cache_key:
        builder.row(
            InlineKeyboardButton(
                text=get_text("deep.btn_deep", lang),
                callback_data=f"deep:{cache_key}",
            )
        )

=================================================================
FILE 3: requirements.txt — No changes needed!
=================================================================

All analytics use only: math, random, asyncio, dataclasses, re
These are Python stdlib. No new pip packages required.

CoinGecko API is called via aiohttp (already in requirements).

=================================================================
SUMMARY OF NEW FILES:
=================================================================

analytics/__init__.py              — Package init
analytics/data_fetcher.py          — CLOB price history + CoinGecko
analytics/probability.py           — signal_score → probability
analytics/kelly.py                 — Kelly Criterion
analytics/greeks.py                — Theta + Vega
analytics/monte_carlo.py           — Monte Carlo simulations
analytics/bayesian.py              — Bayesian inference
analytics/orchestrator.py          — Runs everything

handlers_analytics.py              — Telegram handlers for deep:* callbacks
services/format_service_analytics.py — Formats DeepAnalysis for Telegram
patch_locales.py                   — Run once to add i18n keys
"""
