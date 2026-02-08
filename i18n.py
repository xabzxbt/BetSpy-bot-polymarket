"""
BetSpy i18n Service — JSON-based, middleware-compatible.

Architecture:
  1. Locale files: locales/en.json, locales/uk.json, locales/ru.json
  2. I18nService singleton loads all locales at startup
  3. Aiogram middleware resolves user language per request
  4. Handlers call `t(key, **kwargs)` via middleware-injected function

Adding a new language:
  1. Create locales/<code>.json (copy en.json and translate)
  2. Add code to SUPPORTED_LANGUAGES
  3. Done — no code changes needed
"""

import json
import os
from typing import Dict, Any, Optional, Callable
from pathlib import Path
from loguru import logger


SUPPORTED_LANGUAGES = ["en", "uk", "ru"]
DEFAULT_LANGUAGE = "en"


class I18nService:
    """Loads and serves translations from JSON locale files."""

    def __init__(self, locales_dir: str = None):
        if locales_dir is None:
            locales_dir = os.path.join(os.path.dirname(__file__), "locales")
        self._locales_dir = Path(locales_dir)
        self._translations: Dict[str, Dict[str, str]] = {}  # lang → {key: text}
        self._loaded = False

    def load(self) -> None:
        """Load all locale files."""
        for lang in SUPPORTED_LANGUAGES:
            filepath = self._locales_dir / f"{lang}.json"
            if not filepath.exists():
                logger.warning(f"Locale file not found: {filepath}")
                continue
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Flatten nested dicts: {"btn": {"add": "Add"}} → {"btn.add": "Add"}
            flat = {}
            self._flatten(data, "", flat)
            self._translations[lang] = flat
            logger.info(f"Loaded {len(flat)} keys for locale '{lang}'")

        self._loaded = True
        logger.info(f"I18n loaded: {list(self._translations.keys())}")

    def _flatten(self, obj: Any, prefix: str, out: Dict[str, str]) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                new_key = f"{prefix}.{k}" if prefix else k
                self._flatten(v, new_key, out)
        else:
            out[prefix] = str(obj)

    def get(self, key: str, lang: str = DEFAULT_LANGUAGE, **kwargs) -> str:
        """Get translated string. Falls back to EN, then returns key."""
        if not self._loaded:
            self.load()

        # Try requested language
        text = self._translations.get(lang, {}).get(key)
        # Fallback to EN
        if text is None and lang != DEFAULT_LANGUAGE:
            text = self._translations.get(DEFAULT_LANGUAGE, {}).get(key)
        # Fallback to raw key
        if text is None:
            logger.warning(f"Missing translation: [{lang}] {key}")
            return f"[{key}]"

        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError) as e:
                logger.warning(f"Format error for [{lang}] {key}: {e}")
                return text

        return text

    def get_translator(self, lang: str) -> Callable:
        """Return a bound translator function for a specific language.
        
        Usage in handlers:
            t = i18n.get_translator("uk")
            t("btn.add_wallet")  # → "➕ Додати гаманець"
        """
        def t(key: str, **kwargs) -> str:
            return self.get(key, lang, **kwargs)
        return t


# Global singleton
i18n = I18nService()


def get_text(key: str, lang: str = "en", **kwargs) -> str:
    """Drop-in replacement for the old translations.get_text().
    
    Keeps backward compatibility while using the new i18n system.
    """
    return i18n.get(key, lang, **kwargs)


def get_side_text(side: str, lang: str = "en") -> str:
    if side.upper() == "BUY":
        return get_text("trade.side_buy", lang)
    return get_text("trade.side_sell", lang)


def get_pnl_emoji(value: float) -> str:
    if value > 0:
        return "🟢"
    elif value < 0:
        return "🔴"
    return "⚪"
