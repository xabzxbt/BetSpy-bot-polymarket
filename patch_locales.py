"""
Patch script: Add deep analysis i18n keys to existing locale files.

Run once: python patch_locales.py
"""

import json
import os

LOCALES_DIR = os.path.join(os.path.dirname(__file__), "locales")

DEEP_KEYS = {
    "en": {
        "deep": {
            "loading": "🔬 Running deep analysis... (5-10 sec)",
            "error": "❌ Deep analysis failed. Try again later.",
            "days_left": "⏳ {days} days remaining",
            "section_probability": "PROBABILITY MODELS",
            "section_edge": "EDGE & SIZING",
            "section_greeks": "TIME & VOLATILITY",
            "section_whale_intel": "WHALE INTELLIGENCE",
            "section_distribution": "SIMULATION DISTRIBUTION",
            "model_vs_market": "model {model}% vs market {market}%",
            "edge_too_small": "Edge too small to bet",
            "no_edge_data": "Insufficient data for edge calculation",
            "theta_anomaly": "Price stuck — time decay opportunity!",
            "time_value": "Market overpays {value}¢ for uncertainty",
            "vega_sleeping": "Low volatility — possible breakout ahead",
            "vega_spiking": "High volatility — news event detected!",
            "overreaction": "Market overreaction detected!",
            "no_clear_edge": "No clear edge — HOLD / skip",
            "btn_deep": "🔬 Deep Analysis"
        }
    },
    "uk": {
        "deep": {
            "loading": "🔬 Запуск глибокого аналізу... (5-10 сек)",
            "error": "❌ Помилка аналізу. Спробуйте пізніше.",
            "days_left": "⏳ {days} днів залишилось",
            "section_probability": "МОДЕЛІ ЙМОВІРНОСТІ",
            "section_edge": "EDGE & РОЗМІР СТАВКИ",
            "section_greeks": "ЧАС & ВОЛАТИЛЬНІСТЬ",
            "section_whale_intel": "WHALE INTELLIGENCE",
            "section_distribution": "РОЗПОДІЛ СИМУЛЯЦІЙ",
            "model_vs_market": "модель {model}% vs ринок {market}%",
            "edge_too_small": "Edge занадто малий для ставки",
            "no_edge_data": "Недостатньо даних для розрахунку edge",
            "theta_anomaly": "Ціна застрягла — можливість на часовому розпаді!",
            "time_value": "Ринок переплачує {value}¢ за невизначеність",
            "vega_sleeping": "Низька волатильність — можливий різкий рух",
            "vega_spiking": "Висока волатильність — новинна подія!",
            "overreaction": "Виявлено надмірну реакцію ринку!",
            "no_clear_edge": "Немає чіткого edge — HOLD / пропустити",
            "btn_deep": "🔬 Глибокий аналіз"
        }
    },
    "ru": {
        "deep": {
            "loading": "🔬 Запуск глубокого анализа... (5-10 сек)",
            "error": "❌ Ошибка анализа. Попробуйте позже.",
            "days_left": "⏳ {days} дней осталось",
            "section_probability": "МОДЕЛИ ВЕРОЯТНОСТИ",
            "section_edge": "EDGE & РАЗМЕР СТАВКИ",
            "section_greeks": "ВРЕМЯ & ВОЛАТИЛЬНОСТЬ",
            "section_whale_intel": "WHALE INTELLIGENCE",
            "section_distribution": "РАСПРЕДЕЛЕНИЕ СИМУЛЯЦИЙ",
            "model_vs_market": "модель {model}% vs рынок {market}%",
            "edge_too_small": "Edge слишком мал для ставки",
            "no_edge_data": "Недостаточно данных для расчёта edge",
            "theta_anomaly": "Цена застряла — возможность на временном распаде!",
            "time_value": "Рынок переплачивает {value}¢ за неопределённость",
            "vega_sleeping": "Низкая волатильность — возможен резкий рывок",
            "vega_spiking": "Высокая волатильность — новостное событие!",
            "overreaction": "Обнаружена чрезмерная реакция рынка!",
            "no_clear_edge": "Нет чёткого edge — HOLD / пропустить",
            "btn_deep": "🔬 Глубокий анализ"
        }
    }
}


def patch():
    for lang, keys in DEEP_KEYS.items():
        filepath = os.path.join(LOCALES_DIR, f"{lang}.json")
        if not os.path.exists(filepath):
            print(f"SKIP: {filepath} not found")
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Merge deep keys
        for section, values in keys.items():
            if section not in data:
                data[section] = {}
            if isinstance(values, dict):
                data[section].update(values)
            else:
                data[section] = values

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"PATCHED: {filepath} (+{sum(len(v) if isinstance(v, dict) else 1 for v in keys.values())} keys)")


if __name__ == "__main__":
    patch()
