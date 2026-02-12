from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from market_intelligence import market_intelligence as engine, Category, TimeFrame
from services.format_service import format_signals_list, format_deep_analysis_result, format_brief_signal
from analytics.orchestrator import Orchestrator
from services.user_service import resolve_user
from i18n import get_text

router = Router(name="signals")
orch = Orchestrator()


@router.callback_query(F.data == "signals_quick")
async def signals_quick_handler(callback: CallbackQuery):
    """
    Quick signals — fast opportunities without deep analysis.
    Uses fetch_signal_markets with strict filters.
    """
    _, lang = await resolve_user(callback.from_user)
    try:
        await callback.answer(get_text("loading", lang))
    except Exception:
        pass
    
    # Fetch pre-filtered signal markets
    markets = await engine.fetch_signal_markets(limit=5)
    
    # Format for display
    text = format_signals_list(markets, lang)
    
    # Add refresh button
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Refresh", callback_data="signals_quick")],
        [InlineKeyboardButton(text="📊 Deep Analysis", callback_data="signals_all")],
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("signal_analyze_"))
async def signal_deep_handler(callback: CallbackQuery):
    """
    Deep analysis for a specific market from signals list.
    """
    _, lang = await resolve_user(callback.from_user)
    slug = callback.data.replace("signal_analyze_", "")
    
    try:
        await callback.answer(get_text("loading", lang))
    except Exception:
        pass
    
    # Fetch market data
    markets = await engine.fetch_signal_markets(limit=10)
    target = next((m for m in markets if m.slug == slug), None)
    
    if not target:
        await callback.message.reply("❌ Market not found or expired.")
        return
    
    # Run deep analysis
    result = await orch.analyze_market(target)
    
    # Format with full conflict handling
    text = format_deep_analysis_result(result, lang)
    
    keyboard_list = []
    if result.is_positive_setup:
         keyboard_list.append([
            InlineKeyboardButton(
                text=f"✅ Take {result.rec_side}", 
                callback_data=f"trade_{slug}_{result.rec_side.lower()}"
            )
        ])
    
    keyboard_list.append([InlineKeyboardButton(text="◀️ Back to Signals", callback_data="signals_quick")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_list)
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "signals_all")
async def signals_all_handler(callback: CallbackQuery):
    """
    Alternative: Show all signals with deep analysis per market.
    Slower but more detailed than signals_quick.
    """
    _, lang = await resolve_user(callback.from_user)
    try:
        await callback.answer(get_text("loading", lang))
    except Exception:
        pass
    
    # Get trending markets
    markets = await engine.fetch_trending_markets(limit=20)
    
    # Run deep analysis on each
    results = []
    for m in markets:
        result = await orch.analyze_market(m)
        if result.is_positive_setup and result.confidence >= 50:
            results.append(result)
    
    # Sort by confidence
    results.sort(key=lambda r: r.confidence, reverse=True)
    
    # Format top 5
    if not results:
        text = "🔍 No actionable signals found.\n\nMarkets are fairly priced or Smart Money conflicts are too strong."
    else:
        text = "⚡ <b>Top Signals (Deep Analysis)</b>\n\n"
        for idx, res in enumerate(results[:5], start=1):
            text += f"{idx}. {format_brief_signal(res)}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Refresh", callback_data="signals_all")],
        [InlineKeyboardButton(text="🔥 Hot Markets", callback_data="hot_all")],
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


def setup_signals_handlers(dp) -> None:
    dp.include_router(router)
    from loguru import logger
    logger.info("Signals handlers registered")
