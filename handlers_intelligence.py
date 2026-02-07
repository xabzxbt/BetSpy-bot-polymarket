"""
Handlers for BetSpy Market Intelligence features.

Commands:
- /trending - Show trending markets with signals
- /analyze - Deep analysis of a specific market
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.enums import ParseMode
from loguru import logger
import html
import math

import time
from database import db
from repository import UserRepository
from translations import get_text
from market_intelligence import (
    market_intelligence, 
    MarketIntelligenceEngine,
    Category, 
    TimeFrame, 
    SignalStrength,
    MarketStats,
    BetRecommendation,
)
from keyboards_intelligence import (
    get_trending_keyboard,
    get_category_keyboard,
    get_market_detail_keyboard,
    get_cached_market,
)


router = Router(name="intelligence")


# ==================== HELPER FUNCTIONS ====================

def format_whale_analysis_block(wa: Any) -> str:
    """Format the structured whale analysis block.
    
    Args:
        wa: WhaleAnalysis object (typed Any to avoid circular imports if needed, but optimally imported)
    """
    if not wa or not wa.is_significant:
        return ""
        
    text = f"🐋 <b>АНАЛІЗ КИТІВ</b>\n"
    
    # 1. Headline
    if wa.dominance_side == "NEUTRAL":
        sentiment_text = f"⚖️ {wa.sentiment}"
    else:
        sentiment_text = f"💎 {wa.sentiment}" if "Strong" in wa.sentiment else f"{wa.sentiment}"
        
    text += f"💡 Smart Money: <b>{sentiment_text}</b> ({wa.dominance_pct:.0f}%)\n"
    
    # 2. Visual Bar
    bar_len = 10
    if wa.total_volume > 0:
        yes_share = wa.yes_volume / wa.total_volume
        filled = int(yes_share * bar_len)
    else:
        filled = 5
        
    bar = "▓" * filled + "░" * (bar_len - filled)
    text += f"YES {bar} NO\n\n"
    
    # 3. Key Stats
    if wa.top_trade_size > 0:
        text += f"🏆 Top Trade: <b>${format_volume(wa.top_trade_size)}</b> on {wa.top_trade_side}\n"
        
    if wa.last_trade_timestamp > 0:
        import time
        now = time.time()
        diff = now - wa.last_trade_timestamp
        if diff < 60: time_str = "just now"
        elif diff < 3600: time_str = f"{int(diff/60)}m ago"
        elif diff < 86400: time_str = f"{int(diff/3600)}h ago"
        else: time_str = "1d+ ago"
        text += f"⏱ Last Activity: {time_str} on {wa.last_trade_side}\n"

    text += "\n"
    
    # 4. Breakdown with Helper properties
    text += f"📈 <b>YES:</b> ${format_volume(wa.yes_volume)} ({wa.yes_count} trades)\n"
    text += f"📉 <b>NO:</b>  ${format_volume(wa.no_volume)} ({wa.no_count} trades)\n"
    
    duration_str = f" {wa.duration_text}" if wa.duration_text else ""
    text += f"Smart Money Vol: <b>${format_volume(wa.total_volume)}</b> ({wa.large_whale_share_pct:.0f}% whales){duration_str}\n" 
    
    return text



def format_signal_emoji(strength: SignalStrength) -> str:
    """Get emoji for signal strength."""
    return {
        SignalStrength.STRONG_BUY: "🟢🟢",
        SignalStrength.BUY: "🟢",
        SignalStrength.MODERATE: "🟡",
        SignalStrength.WEAK: "🟠",
        SignalStrength.AVOID: "🔴",
        SignalStrength.STRONG_SELL: "🔴🔴",
    }.get(strength, "⚪")


def format_price(price: float) -> str:
    """Format price as cents."""
    return f"{price*100:.0f}¢"


def format_volume(volume: float) -> str:
    """Format volume in K or M."""
    if volume >= 1_000_000:
        return f"${volume/1_000_000:.1f}M"
    elif volume >= 1_000:
        return f"${volume/1_000:.0f}K"
    else:
        return f"${volume:.0f}"


def format_market_card(market: MarketStats, index: int, lang: str) -> str:
    """Format a market as a compact card for the list view."""
    signal_emoji = format_signal_emoji(market.signal_strength)
    
    # Whale indicator
    if market.whale_consensus is not None:
        whale_dir = "YES" if market.whale_consensus >= 0.5 else "NO"
        whale_str = f"{whale_dir}"
    else:
        whale_str = "—"
    
    # Time
    if market.days_to_close == 0:
        time_str = "⏰ Сьогодні"
    elif market.days_to_close == 1:
        time_str = "⏰ Завтра"
    else:
        time_str = f"📅 {market.days_to_close} дн."
    
    safe_question = html.escape(market.question[:55])
    ellipsis = "..." if len(market.question) > 55 else ""
    
    text = (
        f"<b>{index}. {safe_question}{ellipsis}</b>\n"
        f"   💰 YES {format_price(market.yes_price)} · NO {format_price(market.no_price)}"
        f"  📊 {format_volume(market.volume_24h)}\n"
        f"   🐋 {whale_str}  {time_str}\n"
        f"   {signal_emoji} <b>{market.signal_score}/100 → {market.recommended_side}</b>\n"
    )
    
    return text


def format_market_detail(market: MarketStats, rec: BetRecommendation, lang: str) -> str:
    """Format detailed market analysis — clean, compact UI."""
    signal_emoji = format_signal_emoji(market.signal_strength)
    safe_question = html.escape(market.question)
    
    # Header
    text = f"<b>{safe_question}</b>\n"
    text += f"{'─'*28}\n\n"
    
    # === PRICES ===
    text += f"💰 YES: <b>{format_price(market.yes_price)}</b>  ·  NO: <b>{format_price(market.no_price)}</b>\n"
    text += f"📊 Vol 24h: {format_volume(market.volume_24h)}  ·  Total: {format_volume(market.volume_total)}\n"
    
    # Liquidity
    if market.liquidity > 0:
        text += f"💧 Ліквідність: {format_volume(market.liquidity)}\n"
    
    # Time
    if market.days_to_close == 0:
        text += f"⏰ Закривається <b>сьогодні</b>\n"
    elif market.days_to_close == 1:
        text += f"⏰ Закривається <b>завтра</b>\n"
    else:
        end_str = market.end_date.strftime("%d.%m.%Y")
        text += f"⏰ {end_str} ({market.days_to_close} дн.)\n"
    
    text += "\n"
    
    # === WHALE ANALYSIS ===
    wa_block = format_whale_analysis_block(market.whale_analysis)
    if wa_block:
         text += wa_block
    elif market.whale_consensus is not None:
         # Legacy fallback
         consensus_pct = int(market.whale_consensus * 100)
         bar_len = 10
         filled = int(market.whale_consensus * bar_len)
         bar = "▓" * filled + "░" * (bar_len - filled)
         
         text += f"🐋 <b>АНАЛІЗ КИТІВ</b>\n"
         text += f"YES {consensus_pct}% {bar} {100-consensus_pct}% NO\n"
         text += f"Об'єм: {format_volume(market.whale_total_volume)}"
         text += f" ({market.whale_yes_count}↑ / {market.whale_no_count}↓)\n"
    else:
         text += f"🐋 <b>АНАЛІЗ КИТІВ</b>\n"
         text += f"<i>Немає значної активності китів (<$1000)</i>\n"


    
    text += "\n"
    
    # === SIGNAL ===
    text += f"{'─'*28}\n"
    text += f"{signal_emoji} <b>Сигнал: {market.signal_score}/100</b>\n\n"
    
    # === RECOMMENDATION ===
    if rec.should_bet:
        text += f"✅ <b>Рекомендація: {rec.side} @ {format_price(rec.entry_price)}</b>\n"
        if rec.entry_price > 0:
            target_pct = ((rec.target_price / rec.entry_price) - 1) * 100
            stop_pct = (1 - (rec.stop_loss_price / rec.entry_price)) * 100
        else:
            target_pct = 0
            stop_pct = 0
        text += f"🎯 Ціль: {format_price(rec.target_price)} (+{target_pct:.0f}%)"
        text += f"  ·  🛑 Стоп: {format_price(rec.stop_loss_price)} (-{stop_pct:.0f}%)\n"
        text += f"⚖️ Ризик/Прибуток: 1:{rec.risk_reward_ratio:.1f}\n"
    else:
        text += f"❌ <b>НЕ СТАВИТИ</b>\n"
    
    text += "\n"
    
    # Pros/Cons compact
    if rec.reasons:
        for r in rec.reasons:
            text += f"✅ {r}\n"
    if rec.warnings:
        for w in rec.warnings:
            text += f"{w}\n"
    
    # Link
    text += f"\n🔗 <a href='{market.market_url}'>Відкрити на Polymarket</a>"
    
    return text


def format_market_links_footer(markets: list, start_index: int, lang: str) -> str:
    """Format footer with links to each market."""
    if not markets:
        return ""
        
    term_links = get_text("intel_footer_links", lang)
    term_go_to = get_text("intel_link_text", lang)
    
    text = f"\n{term_links}\n"
    for i, market in enumerate(markets):
        idx = start_index + i
        text += f"{idx}. <a href='{market.market_url}'>{term_go_to}</a>\n"
    return text



# ==================== COMMAND HANDLERS ====================

@router.message(Command("trending"))
async def cmd_trending(message: Message) -> None:
    """Show trending markets selection."""
    async with db.session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_or_create(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
        )
        
        try:
            title = get_text("intel_title", user.language)
            subtitle = get_text("intel_choose_category", user.language)
            
            await message.answer(
                f"{title}\n\n{subtitle}",
                reply_markup=get_category_keyboard(user.language),
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            logger.error(f"Error in /trending: {e}")
            await message.answer(
                get_text("error_generic", user.language),
                parse_mode=ParseMode.HTML,
            )





# ==================== CALLBACK HANDLERS ====================

@router.callback_query(F.data.startswith("intel:cat:"))
async def callback_category_select(callback: CallbackQuery) -> None:
    """Handle category selection and show markets directly."""
    logger.info(f"Received callback: {callback.data} from user {callback.from_user.id}")
    
    category_str = callback.data.split(":")[2]
    
    try:
        category = Category(category_str)
    except ValueError:
        category = Category.ALL
    
    # Trigger pagination for page 1
    await show_markets_page(callback, category, TimeFrame.MONTH, 1)


@router.callback_query(F.data.startswith("intel:p:"))
async def callback_pagination(callback: CallbackQuery) -> None:
    """Handle pagination."""
    # intel:p:category:timeframe:page
    parts = callback.data.split(":")
    category_str = parts[2]
    timeframe_str = parts[3]
    try:
        page = int(parts[4])
    except (IndexError, ValueError):
        page = 1
        
    try:
        category = Category(category_str)
    except ValueError:
        category = Category.ALL
        
    try:
        timeframe = TimeFrame(timeframe_str)
    except ValueError:
        timeframe = TimeFrame.MONTH
        
    await show_markets_page(callback, category, timeframe, page)


@router.callback_query(F.data.startswith("intel:time:"))
async def callback_refresh(callback: CallbackQuery) -> None:
    """Handle refresh (same as pagination but stay on page)."""
    # intel:time:category:timeframe:page
    parts = callback.data.split(":")
    category_str = parts[2]
    timeframe_str = parts[3]
    
    page = 1
    if len(parts) > 4:
        try:
            page = int(parts[4])
        except ValueError:
            page = 1
            
    try:
        category = Category(category_str)
        timeframe = TimeFrame(timeframe_str)
    except ValueError:
        category = Category.ALL
        timeframe = TimeFrame.MONTH
        
    await show_markets_page(callback, category, timeframe, page)


async def show_markets_page(
    callback: CallbackQuery, 
    category: Category, 
    timeframe: TimeFrame, 
    page: int
) -> None:
    """Common function to fetch and show markets."""
    async with db.session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )
        
        try:
            await callback.answer()
        except Exception:
            pass
        
        # Show loading
        loading_text = get_text("loading", user.language)
        try:
            await callback.message.edit_text(
                f"{loading_text}\n\n<i>This may take a few seconds...</i>", # TODO: Translate hint
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            await callback.message.answer(
                f"{loading_text}\n\n<i>This may take a few seconds...</i>",
                parse_mode=ParseMode.HTML,
            )
        
        try:
            await market_intelligence.init()
            # Fetch ALL relevant markets first (limit higher to allow pagination)
            markets = await market_intelligence.fetch_trending_markets(
                category=category,
                timeframe=timeframe,
                limit=50,  # Fetch up to 50 top markets
            )
            
            # If no markets found, try fallback method
            if not markets and timeframe != TimeFrame.MONTH:
                markets = await market_intelligence.fetch_trending_markets(
                    category=category,
                    timeframe=TimeFrame.MONTH,
                    limit=50,
                )
                timeframe = TimeFrame.MONTH
            
            # Category mappings
            cat_emoji_map = {
                Category.POLITICS: "🏛️",
                Category.SPORTS: "⚽",
                Category.POP_CULTURE: "🎬",
                Category.BUSINESS: "💼",
                Category.CRYPTO: "₿",
                Category.SCIENCE: "🔬",
                Category.GAMING: "🎮",
                Category.ENTERTAINMENT: "🎭",
                Category.WORLD: "🌍",
                Category.TECH: "💻",
                Category.ALL: "📊",
            }
            emoji = cat_emoji_map.get(category, "📊")
            
            cat_key_map = {
                Category.POLITICS: "cat_politics",
                Category.SPORTS: "cat_sports",
                Category.POP_CULTURE: "cat_pop_culture",
                Category.BUSINESS: "cat_business",
                Category.CRYPTO: "cat_crypto",
                Category.SCIENCE: "cat_science",
                Category.GAMING: "cat_gaming",
                Category.ENTERTAINMENT: "cat_entertainment",
                Category.WORLD: "cat_world",
                Category.TECH: "cat_tech",
                Category.ALL: "cat_all",
            }
            cat_key = cat_key_map.get(category, "cat_all")
            cat_name = get_text(cat_key, user.language)
            
            if not markets:
                await callback.message.edit_text(
                    get_text("no_signals", user.language),
                    reply_markup=get_category_keyboard(user.language),
                    parse_mode=ParseMode.HTML,
                )
                return

            # Pagination Logic
            ITEMS_PER_PAGE = 10
            total_items = len(markets)
            total_pages = math.ceil(total_items / ITEMS_PER_PAGE)
            
            if page < 1: page = 1
            if page > total_pages: page = total_pages
            
            start_idx = (page - 1) * ITEMS_PER_PAGE
            end_idx = start_idx + ITEMS_PER_PAGE
            
            markets_page = markets[start_idx:end_idx]
            
            # Header
            header = get_text("intel_header_category", user.language, emoji=emoji, category=cat_name.upper())
            page_info = get_text("intel_page_info", user.language, page=page, total_pages=total_pages, total_items=total_items)
            
            text = f"{header}\n{page_info}\n\n"
            
            # Cards
            for i, market in enumerate(markets_page):
                idx = start_idx + i + 1
                text += format_market_card(market, idx, user.language)
                text += "\n"
            
            # Footer links
            text += format_market_links_footer(markets_page, start_idx + 1, user.language)
            
            hint = get_text("intel_click_hint", user.language)
            text += f"\n{hint}"
            
            await callback.message.edit_text(
                text,
                reply_markup=get_trending_keyboard(
                    user.language, 
                    markets_page, 
                    category.value, 
                    timeframe.value,
                    page=page,
                    total_pages=total_pages
                ),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            
        except Exception as e:
            logger.error(f"Error fetching markets: {e}")
            try:
                await callback.message.edit_text(
                    get_text("error_generic", user.language),
                    reply_markup=get_category_keyboard(user.language),
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass





@router.callback_query(F.data.startswith("intel:m:"))
async def callback_market_detail(callback: CallbackQuery) -> None:
    """Show detailed market analysis."""
    logger.info(f"Received callback: {callback.data} from user {callback.from_user.id}")
    
    # Extract the cache key from callback data (intel:m:12345)
    cache_key = callback.data.split(":")[2]
    
    async with db.session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )
        
        try:
            await callback.answer()  # Always answer the callback first
        except Exception as e:
            logger.warning(f"Could not answer callback: {e}")
        
        # Get market from cache
        market = get_cached_market(cache_key)
        
        if not market:
            try:
                await callback.message.edit_text(
                    "❌ Ринок не знайдено. Спробуй оновити список.",
                    reply_markup=get_category_keyboard(user.language),
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                await callback.message.answer(
                    "❌ Ринок не знайдено. Спробуй оновити список.",
                    reply_markup=get_category_keyboard(user.language),
                    parse_mode=ParseMode.HTML,
                )
            return
        
        try:
            # Generate recommendation
            rec = market_intelligence.generate_recommendation(market)
            
            # Format detail view
            text = format_market_detail(market, rec, user.language)
            
            await callback.message.edit_text(
                text,
                reply_markup=get_market_detail_keyboard(user.language, market),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            
        except Exception as e:
            import traceback
            logger.error(f"Error in market detail: {e}\n{traceback.format_exc()}")
            try:
                await callback.message.edit_text(
                    "❌ Помилка при отриманні даних.",
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                await callback.message.answer(
                    "❌ Помилка при отриманні даних.",
                    parse_mode=ParseMode.HTML,
                )


@router.callback_query(F.data == "intel:back_categories")
async def callback_back_to_categories(callback: CallbackQuery) -> None:
    """Go back to category selection."""
    logger.info(f"Received callback: {callback.data} from user {callback.from_user.id}")
    
    async with db.session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )
        
        try:
            await callback.answer()  # Always answer the callback first
        except Exception as e:
            logger.warning(f"Could not answer callback: {e}")
        
        try:
            await callback.message.edit_text(
                "📊 <b>СИГНАЛИ РИНКІВ</b>\n\n"
                "Обери категорію:",
                reply_markup=get_category_keyboard(user.language),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            # If message edit fails, send new message
            await callback.message.answer(
                "📊 <b>СИГНАЛИ РИНКІВ</b>\n\n"
                "Обери категорію:",
                reply_markup=get_category_keyboard(user.language),
                parse_mode=ParseMode.HTML,
            )


# Catch-all callback handler for intel: callbacks that aren't handled
@router.callback_query(F.data.startswith("intel:"))
async def catch_intel_callbacks(callback: CallbackQuery):
    logger.warning(f"Unhandled intel callback: {callback.data} from user {callback.from_user.id}")
    await callback.answer("⚠️ Handler not found")


def setup_intelligence_handlers(dp) -> None:
    """Register intelligence handlers with dispatcher."""
    dp.include_router(router)
    logger.info("Intelligence handlers registered")
