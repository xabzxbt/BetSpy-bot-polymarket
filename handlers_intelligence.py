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

from database import db
from repository import UserRepository
from translations import get_text
from market_intelligence import (
    market_intelligence, 
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
    """Format a market as a card for the list view."""
    signal_emoji = format_signal_emoji(market.signal_strength)
    
    # Whale indicator
    whale_pct = market.whale_consensus if market.recommended_side == "YES" else (1 - market.whale_consensus)
    whale_str = f"{whale_pct*100:.0f}%"
    
    # Time indicator
    if market.days_to_close == 0:
        time_str = "🕐 Сьогодні"
    elif market.days_to_close == 1:
        time_str = "🕐 Завтра"
    elif market.days_to_close <= 7:
        time_str = f"🕐 {market.days_to_close} днів"
    else:
        time_str = f"🕐 {market.days_to_close} днів"
    
    # Category emoji - all Polymarket categories
    cat_emoji = {
        "politics": "🏛️",
        "sports": "⚽",
        "pop-culture": "🎬",
        "business": "💼",
        "crypto": "₿",
        "science": "🔬",
        "gaming": "🎮",
        "entertainment": "🎭",
        "world": "🌍",
        "tech": "💻",
    }.get(market.category, "📊")
    
    # Escape HTML special characters in question to prevent parsing errors
    safe_question = html.escape(market.question[:50])
    ellipsis = "..." if len(market.question) > 50 else ""
    
    text = (
        f"<b>{index}. {cat_emoji} {safe_question}{ellipsis}</b>\n"
        f"├ 💰 Vol: {format_volume(market.volume_24h)} (24h)\n"
        f"├ 🟢 YES {format_price(market.yes_price)} | 🔴 NO {format_price(market.no_price)}\n"
        f"├ 🐋 Кити: {whale_str} {market.recommended_side}\n"
        f"├ {time_str}\n"
        f"└ {signal_emoji} <b>Signal: {market.signal_score}/100 → {market.recommended_side}</b>\n"
    )
    
    return text


def format_market_detail(market: MarketStats, rec: BetRecommendation, lang: str) -> str:
    """Format detailed market analysis."""
    signal_emoji = format_signal_emoji(market.signal_strength)
    
    # Category emoji - all Polymarket categories
    cat_emoji = {
        "politics": "🏛️",
        "sports": "⚽",
        "pop-culture": "🎬",
        "business": "💼",
        "crypto": "₿",
        "science": "🔬",
        "gaming": "🎮",
        "entertainment": "🎭",
        "world": "🌍",
        "tech": "💻",
    }.get(market.category, "📊")
    
    # Escape HTML special characters in question
    safe_question = html.escape(market.question)
    
    # Build the detailed view
    text = f"{cat_emoji} <b>{safe_question}</b>\n\n"
    
    # Signal summary
    text += f"{'═'*30}\n"
    text += f"{signal_emoji} <b>SIGNAL: {market.signal_score}/100</b>\n"
    text += f"💡 Рекомендація: <b>{rec.side}</b> @ {format_price(rec.entry_price)}\n"
    text += f"{'═'*30}\n\n"
    
    # Price info
    text += "💰 <b>ЦІНИ:</b>\n"
    text += f"├ 🟢 YES: {format_price(market.yes_price)}\n"
    text += f"└ 🔴 NO: {format_price(market.no_price)}\n\n"
    
    # Volume stats
    text += "📊 <b>VOLUME:</b>\n"
    text += f"├ 24h: {format_volume(market.volume_24h)}\n"
    text += f"└ Total: {format_volume(market.volume_total)}\n\n"
    
    # Whale analysis
    text += "🐋 <b>WHALE ANALYSIS:</b>\n"
    if market.whale_total_volume > 0:
        yes_pct = market.whale_consensus * 100
        no_pct = 100 - yes_pct
        text += f"├ 🟢 YES: {yes_pct:.0f}% ({format_volume(market.whale_yes_volume)})\n"
        text += f"├ 🔴 NO: {no_pct:.0f}% ({format_volume(market.whale_no_volume)})\n"
        text += f"├ Кити YES: {market.whale_yes_count}\n"
        text += f"└ Кити NO: {market.whale_no_count}\n\n"
    else:
        text += "└ Недостатньо даних\n\n"
    
    # Retail analysis
    if market.retail_total_volume > 0:
        retail_yes_pct = (market.retail_yes_volume / market.retail_total_volume) * 100
        text += "👥 <b>RETAIL:</b>\n"
        text += f"├ 🟢 YES: {retail_yes_pct:.0f}%\n"
        text += f"└ 🔴 NO: {100-retail_yes_pct:.0f}%\n\n"
    
    # Price history
    if market.price_24h_ago > 0:
        change_24h = market.price_change_24h * 100
        sign = "+" if change_24h > 0 else ""
        text += "📈 <b>ТРЕНД:</b>\n"
        text += f"├ 24h: {sign}{change_24h:.1f}%\n"
        if market.price_7d_ago > 0:
            change_7d = market.price_change_7d * 100
            sign = "+" if change_7d > 0 else ""
            text += f"└ 7d: {sign}{change_7d:.1f}%\n\n"
        else:
            text += "\n"
    
    # Time to close
    text += "⏰ <b>ЗАКРИТТЯ:</b>\n"
    if market.days_to_close == 0:
        text += "└ Сьогодні!\n\n"
    elif market.days_to_close == 1:
        text += "└ Завтра\n\n"
    else:
        end_str = market.end_date.strftime("%d.%m.%Y")
        text += f"└ {end_str} ({market.days_to_close} днів)\n\n"
    
    # Score breakdown
    text += "📊 <b>SCORE BREAKDOWN:</b>\n"
    text += f"├ Whale Consensus: {market.signal_score * 0.4:.0f}/40\n"
    text += f"├ Volume: ~{market.signal_score * 0.2:.0f}/20\n"
    text += f"├ Trend: ~{market.signal_score * 0.2:.0f}/20\n"
    text += f"├ Liquidity: ~{market.signal_score * 0.1:.0f}/10\n"
    text += f"└ Time Value: ~{market.signal_score * 0.1:.0f}/10\n\n"
    
    # Recommendation box
    text += f"{'═'*30}\n"
    text += "💡 <b>РЕКОМЕНДАЦІЯ:</b>\n\n"
    
    if rec.should_bet:
        text += f"✅ <b>СТАВИТИ: {rec.side}</b>\n\n"
        text += f"├ Entry: {format_price(rec.entry_price)}\n"
        text += f"├ Target: {format_price(rec.target_price)} (+{((rec.target_price/rec.entry_price)-1)*100:.0f}%)\n"
        text += f"├ Stop-loss: {format_price(rec.stop_loss_price)} (-{(1-(rec.stop_loss_price/rec.entry_price))*100:.0f}%)\n"
        text += f"└ Risk/Reward: 1:{rec.risk_reward_ratio:.1f}\n\n"
    else:
        text += "❌ <b>НЕ СТАВИТИ</b>\n\n"
    
    # Reasons
    if rec.reasons:
        text += "✅ <b>Плюси:</b>\n"
        for reason in rec.reasons:
            text += f"  {reason}\n"
        text += "\n"
    
    # Warnings
    if rec.warnings:
        text += "⚠️ <b>Ризики:</b>\n"
        for warning in rec.warnings:
            text += f"  {warning}\n"
            
    # Link
    text += f"\n🔗 <a href='{market.market_url}'>Відкрити на Polymarket ↗️</a>"
    
    return text


def format_market_links_footer(markets: list, start_index: int) -> str:
    """Format footer with links to each market."""
    if not markets:
        return ""
        
    text = "\n🔗 <b>Посилання на ринки:</b>\n"
    for i, market in enumerate(markets):
        idx = start_index + i
        # Use HTML link
        text += f"{idx}. <a href='{market.market_url}'>Перейти до ринку ↗️</a>\n"
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
            await message.answer(
                "� <b>СИГНАЛИ РИНКІВ</b>\n\n"
                "Обери категорію та часовий проміжок:",
                reply_markup=get_category_keyboard(user.language),
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            logger.error(f"Error in /trending: {e}")
            await message.answer(
                "❌ Помилка при завантаженні даних. Спробуй пізніше.",
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
        try:
            await callback.message.edit_text(
                "🔄 Аналізую ринки...\n\n<i>Це може зайняти декілька секунд...</i>",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            await callback.message.answer(
                "🔄 Аналізую ринки...\n\n<i>Це може зайняти декілька секунд...</i>",
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
            
            if not markets:
                cat_emoji = {
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
                }.get(category, "📊")
                
                await callback.message.edit_text(
                    f"{cat_emoji} <b>Не знайдено активних сигналів.</b>\n\n"
                    "Спробуйте пізніше або іншу категорію.",
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
            
            # Format display
            cat_emoji = {
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
            }.get(category, "📊")
            
            cat_name = {
                Category.POLITICS: "Політика",
                Category.SPORTS: "Спорт",
                Category.POP_CULTURE: "Pop Culture",
                Category.BUSINESS: "Бізнес",
                Category.CRYPTO: "Крипто",
                Category.SCIENCE: "Наука",
                Category.GAMING: "Ігри",
                Category.ENTERTAINMENT: "Розваги",
                Category.WORLD: "Світ",
                Category.TECH: "Технології",
                Category.ALL: "Всі",
            }.get(category, "Всі")
            
            text = f"{cat_emoji} <b>СИГНАЛИ: {cat_name.upper()}</b>\n"
            text += f"<i>Сторінка {page}/{total_pages} | Всього: {total_items}</i>\n\n"
            
            # Cards
            for i, market in enumerate(markets_page):
                idx = start_idx + i + 1
                text += format_market_card(market, idx, user.language)
                text += "\n"
            
            # Footer links
            text += format_market_links_footer(markets_page, start_idx + 1)
            
            text += "\n💡 <i>Натисни на номер для детального аналізу</i>"
            
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
                    "❌ Помилка при завантаженні даних.\nСпробуйте оновити або змінити категорію.",
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
            logger.error(f"Error in market detail: {e}")
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
