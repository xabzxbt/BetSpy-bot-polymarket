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
        },
        "quant": {
            "setup_bull": "BULL",
            "setup_bear": "BEAR",
            "setup_neut": "NEUTRAL",
            "intro_Rec": " → RECOMMENDED",
            "intro_NoRec": " → SKIP",
            "header_mc": "🎲 MONTE CARLO",
            "mc_runs": "Runs: {runs}x",
            "mc_prob": "P(YES): {prob}%",
            "mc_pnl": "Exp. PnL: {pnl}",
            "header_bayes": "🧠 BAYESIAN",
            "bayes_prior": "Prior: {pct}%",
            "bayes_post": "Posterior: {pct}%",
            "bayes_comment_label": "Comment: {text}",
            "bayes_c_neutral": "Neutral",
            "bayes_c_strong_yes": "Strong YES signal",
            "bayes_c_weak_yes": "Weak NO signal",
            "bayes_c_confirm": "Confirms market",
            "header_edge": "📐 EDGE",
            "edge_val": "Edge: {sign}{pct} p.p.",
            "edge_good": "Good edge! Bettable.",
            "edge_bad": "No edge. Skip.",
            "header_kelly": "💰 KELLY CRITERION",
            "kelly_opt": "Optimal: {pct}%",
            "kelly_safe": "Safe: {pct}%",
            "kelly_zero": "Don't bet.",
            "header_theta": "⏳ THETA (TIME)",
            "theta_val": "Decay: {val}",
            "theta_short": "Comment: {text}",
            "theta_market": "Market decay",
            "theta_yours": "Your decay",
            "internals_tilt": "Tilt: {val}",
            "internals_mom": "Momentum: {val}",
            "internals_ratio": "Smart/Total: {val}",
            "internals_liq": "Liq: {val}",
            "internals_rec": "Recency: {val}",
            "header_concl": "🏁 CONCLUSION",
            "concl_good": "Good setup: edge {edge}%, bet {kelly}% of bankroll",
            "concl_bad": "Skip this market",
            "mom_stable": "Stable",
            "mom_grow": "Growing",
            "mom_drop": "Declining",
            "rec_old": "Stale",
            "rec_active": "Active ({time}m)",
            "rec_mod": "Moderate ({time}h)"
        },
        "unified": {
            "analysis_title": "DEEP ANALYSIS",
            "briefly": "Briefly",
            "liq_high": "HIGH",
            "liq_med": "MEDIUM",
            "liq_low": "LOW",
            "risk_low_liq": "Low liquidity",
            "risk_whale_opp": "Whales oppose",
            "risk_long_term": "Long term",
            "risks": "Risks"
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
        },
        "quant": {
            "setup_bull": "БИК",
            "setup_bear": "ВЕДМІДЬ",
            "setup_neut": "НЕЙТРАЛЬНИЙ",
            "intro_Rec": " → РЕКОМЕНДОВАНО",
            "intro_NoRec": " → ПРОПУСТИТИ",
            "header_mc": "🎲 МОНТЕ КАРЛО",
            "mc_runs": "Прогонів: {runs}x",
            "mc_prob": "P(ТАК): {prob}%",
            "mc_pnl": "Очікуваний PnL: {pnl}",
            "header_bayes": "🧠 БАЄСОВСЬКИЙ",
            "bayes_prior": "Апріорі: {pct}%",
            "bayes_post": "Апостеріорі: {pct}%",
            "bayes_comment_label": "Коментар: {text}",
            "bayes_c_neutral": "Нейтральний",
            "bayes_c_strong_yes": "Сильний сигнал ТАК",
            "bayes_c_weak_yes": "Слабкий сигнал НІ",
            "bayes_c_confirm": "Підтверджує ринок",
            "header_edge": "📐 EDGE",
            "edge_val": "Edge: {sign}{pct} п.п.",
            "edge_good": "Хороший edge! Можна ставити.",
            "edge_bad": "Немає edge. Пропустити.",
            "header_kelly": "💰 КРИТЕРІЙ КЕЛЛІ",
            "kelly_opt": "Оптимально: {pct}%",
            "kelly_safe": "Безпечно: {pct}%",
            "kelly_zero": "Не ставити.",
            "header_theta": "⏳ ТЕТА (ЧАС)",
            "theta_val": "Розпад: {val}",
            "theta_short": "Коментар: {text}",
            "theta_market": "Ринковий розпад",
            "theta_yours": "Ваш розпад",
            "internals_tilt": "Нахил: {val}",
            "internals_mom": "Імпульс: {val}",
            "internals_ratio": "Розумні/Всього: {val}",
            "internals_liq": "Ліквідність: {val}",
            "internals_rec": "Актуальність: {val}",
            "header_concl": "🏁 ВИСНОВОК",
            "concl_good": "Хороша ставка: edge {edge}%, ставте {kelly}% від банку",
            "concl_bad": "Пропустіть цей ринок",
            "mom_stable": "Стабільний",
            "mom_grow": "Ростучий",
            "mom_drop": "Падаючий",
            "rec_old": "Застарілий",
            "rec_active": "Активний ({time}хв)",
            "rec_mod": "Помірний ({time}г)"
        },
        "unified": {
            "analysis_title": "ГЛИБОКИЙ АНАЛІЗ",
            "briefly": "Стисло",
            "liq_high": "ВИСОКА",
            "liq_med": "СЕРЕДНЯ",
            "liq_low": "НИЗЬКА",
            "risk_low_liq": "Низька ліквідність",
            "risk_whale_opp": "Кити проти",
            "risk_long_term": "Довгостроковий",
            "risks": "Ризики"
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
        },
        "quant": {
            "setup_bull": "БЫК",
            "setup_bear": "МЕДВЕДЬ",
            "setup_neut": "НЕЙТРАЛЬНЫЙ",
            "intro_Rec": " → РЕКОМЕНДУЕТСЯ",
            "intro_NoRec": " → ПРОПУСТИТЬ",
            "header_mc": "🎲 МОНТЕ КАРЛО",
            "mc_runs": "Прогонов: {runs}x",
            "mc_prob": "P(ДА): {prob}%",
            "mc_pnl": "Ожидаемый PnL: {pnl}",
            "header_bayes": "🧠 БАЙЕСОВСКИЙ",
            "bayes_prior": "Априори: {pct}%",
            "bayes_post": "Апостериори: {pct}%",
            "bayes_comment_label": "Комментарий: {text}",
            "bayes_c_neutral": "Нейтральный",
            "bayes_c_strong_yes": "Сильный сигнал ДА",
            "bayes_c_weak_yes": "Слабый сигнал НЕТ",
            "bayes_c_confirm": "Подтверждает рынок",
            "header_edge": "📐 EDGE",
            "edge_val": "Edge: {sign}{pct} п.п.",
            "edge_good": "Хороший edge! Можно ставить.",
            "edge_bad": "Нет edge. Пропустить.",
            "header_kelly": "💰 КРИТЕРИЙ КЕЛЛИ",
            "kelly_opt": "Оптимально: {pct}%",
            "kelly_safe": "Безопасно: {pct}%",
            "kelly_zero": "Не ставить.",
            "header_theta": "⏳ ТЕТА (ВРЕМЯ)",
            "theta_val": "Распад: {val}",
            "theta_short": "Комментарий: {text}",
            "theta_market": "Рыночный распад",
            "theta_yours": "Ваш распад",
            "internals_tilt": "Наклон: {val}",
            "internals_mom": "Импульс: {val}",
            "internals_ratio": "Умные/Всего: {val}",
            "internals_liq": "Ликвидность: {val}",
            "internals_rec": "Актуальность: {val}",
            "header_concl": "🏁 ВЫВОД",
            "concl_good": "Хорошая ставка: edge {edge}%, ставьте {kelly}% от банка",
            "concl_bad": "Пропустите этот рынок",
            "mom_stable": "Стабильный",
            "mom_grow": "Растущий",
            "mom_drop": "Падающий",
            "rec_old": "Устаревший",
            "rec_active": "Активный ({time}м)",
            "rec_mod": "Умеренный ({time}ч)"
        },
        "unified": {
            "analysis_title": "ГЛУБОКИЙ АНАЛИЗ",
            "briefly": "Кратко",
            "liq_high": "ВЫСОКАЯ",
            "liq_med": "СРЕДНЯЯ",
            "liq_low": "НИЗКАЯ",
            "risk_low_liq": "Низкая ликвидность",
            "risk_whale_opp": "Киты против",
            "risk_long_term": "Долгосрочный",
            "risks": "Риски"
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

    print("Deep keys added successfully!")

if __name__ == "__main__":
    patch()
    print("Script completed")
