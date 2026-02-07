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
    if market.whale_consensus is not None:
        whale_pct = market.whale_consensus if market.recommended_side == "YES" else (1 - market.whale_consensus)
        whale_str = f"{whale_pct*100:.0f}%"
    else:
        whale_str = "—"
    
    # Time indicator
    if market.days_to_close == 0:
        time_str = get_text("lbl_today", lang)
    elif market.days_to_close == 1:
        time_str = get_text("lbl_tomorrow", lang)
    else:
        time_str = get_text("lbl_days_left", lang, days=market.days_to_close)
    
    # Category emoji & name
    cat_emoji_map = {
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
    }
    cat_emoji = cat_emoji_map.get(market.category, "📊")
    
    # Escape HTML special characters in question to prevent parsing errors
    safe_question = html.escape(market.question[:50])
    ellipsis = "..." if len(market.question) > 50 else ""
    
    lbl_vol = get_text("lbl_vol", lang)
    lbl_whales = get_text("lbl_whales", lang)
    lbl_signal = get_text("lbl_signal", lang)
    
    text = (
        f"<b>{index}. {cat_emoji} {safe_question}{ellipsis}</b>\n"
        f"├ {lbl_vol} {format_volume(market.volume_24h)} (24h)\n"
        f"├ 🟢 YES {format_price(market.yes_price)} | 🔴 NO {format_price(market.no_price)}\n"
        f"├ {lbl_whales} {whale_str} {market.recommended_side}\n"
        f"├ {time_str}\n"
        f"└ {signal_emoji} <b>{lbl_signal} {market.signal_score}/100 → {market.recommended_side}</b>\n"
    )
    
    return text


def format_market_detail(market: MarketStats, rec: BetRecommendation, lang: str) -> str:
    """Format detailed market analysis."""
    signal_emoji = format_signal_emoji(market.signal_strength)
    
    # Category emoji
    cat_emoji_map = {
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
    }
    cat_emoji = cat_emoji_map.get(market.category, "📊")
    
    # Escape HTML special characters
    safe_question = html.escape(market.question)
    
    # Build the detailed view
    text = f"{cat_emoji} <b>{safe_question}</b>\n\n"
    
    # Signal summary
    lbl_signal = get_text("lbl_signal", lang)
    lbl_rec = get_text("lbl_rec", lang)
    
    text += f"{'═'*30}\n"
    text += f"{signal_emoji} <b>{lbl_signal} {market.signal_score}/100</b>\n"
    text += f"{lbl_rec} <b>{rec.side}</b> @ {format_price(rec.entry_price)}\n"
    text += f"{'═'*30}\n\n"
    
    # Price info
    lbl_prices = get_text("lbl_prices", lang)
    text += f"{lbl_prices}\n"
    text += f"├ 🟢 YES: {format_price(market.yes_price)}\n"
    text += f"└ 🔴 NO: {format_price(market.no_price)}\n\n"
    
    # Volume stats
    lbl_volume = get_text("lbl_volume_title", lang)
    text += f"{lbl_volume}\n"
    text += f"├ 24h: {format_volume(market.volume_24h)}\n"
    text += f"└ Total: {format_volume(market.volume_total)}\n\n"
    
    # Whale Analysis
    text += f"🐋 <b>{get_text('intel_whale_analysis', lang)}</b>\n"
    
    if market.whale_consensus is not None:
        consensus_pct = int(market.whale_consensus * 100)
        # Visual bar
        bar_len = 10
        filled = int(market.whale_consensus * bar_len)
        bar = "▓" * filled + "░" * (bar_len - filled)
        
        text += f"YES {consensus_pct}% {bar} {100-consensus_pct}% NO\n"
        
        if market.whale_yes_volume > 0 or market.whale_no_volume > 0:
            text += f"Vol: {format_volume(market.whale_total_volume)} (Yes: {market.whale_yes_count} / No: {market.whale_no_count})\n"
        else:
            text += get_text("lbl_not_enough_data", lang) + "\n"
    else:
        text += "<i>Дані про активність китів тимчасово недоступні (Data unavailable).</i>\n"
    text += "\n" # Add a newline for spacing after whale analysis
    
    # Retail analysis
    lbl_retail = get_text("lbl_retail", lang)
    if market.retail_total_volume > 0:
        retail_yes_pct = (market.retail_yes_volume / market.retail_total_volume) * 100
        retail_no_pct = 100 - retail_yes_pct
        text += f"{lbl_retail}\n"
        text += f"├ 🟢 YES: {retail_yes_pct:.0f}%\n"
        text += f"└ 🔴 NO: {retail_no_pct:.0f}%\n\n"
    
    # Price history
    if market.price_24h_ago > 0:
        change_24h = market.price_change_24h * 100
        sign = "+" if change_24h > 0 else ""
        lbl_trend = get_text("lbl_trend", lang)
        text += f"{lbl_trend}\n"
        text += f"├ 24h: {sign}{change_24h:.1f}%\n"
        if market.price_7d_ago > 0:
            change_7d = market.price_change_7d * 100
            sign = "+" if change_7d > 0 else ""
            text += f"└ 7d: {sign}{change_7d:.1f}%\n\n"
        else:
            text += "\n"
    
    # Time to close
    lbl_closing = get_text("lbl_closing", lang)
    text += f"{lbl_closing}\n"
    if market.days_to_close == 0:
        text += f"└ {get_text('lbl_today', lang)}\n\n"
    elif market.days_to_close == 1:
        text += f"└ {get_text('lbl_tomorrow', lang)}\n\n"
    else:
        end_str = market.end_date.strftime("%d.%m.%Y")
        text += f"└ {end_str} ({get_text('lbl_days_left', lang, days=market.days_to_close)})\n\n"
    
    # Score breakdown
    lbl_score = get_text("lbl_score_breakdown", lang)
    text += f"{lbl_score}\n"
    
    # Show meaningful breakdown based on available data
    whale_status = "✅" if market.whale_consensus is not None else "❌ N/A"
    vol_tier = "High" if market.volume_24h >= 100000 else ("Med" if market.volume_24h >= 25000 else "Low")
    liq_tier = "Good" if market.liquidity >= 25000 else ("OK" if market.liquidity >= 10000 else "Low")
    
    text += f"├ 🐋 Whale data: {whale_status}\n"
    text += f"├ 📊 Volume: {vol_tier} ({format_volume(market.volume_24h)})\n"
    text += f"├ 💧 Liquidity: {liq_tier} ({format_volume(market.liquidity)})\n"
    text += f"└ 🎯 Total: {market.signal_score}/100\n\n"
    
    # Recommendation box
    lbl_rec_title = get_text("lbl_recommendation", lang)
    text += f"{'═'*30}\n"
    text += f"{lbl_rec_title}\n\n"
    
    if rec.should_bet:
        bet_text = get_text("lbl_bet_yes" if rec.side == "YES" else "lbl_bet_no", lang)
        text += f"{bet_text}\n\n"
        text += f"├ Entry: {format_price(rec.entry_price)}\n"
        # Defensive: avoid division by zero
        if rec.entry_price > 0:
            target_pct = ((rec.target_price / rec.entry_price) - 1) * 100
            stop_pct = (1 - (rec.stop_loss_price / rec.entry_price)) * 100
        else:
            target_pct = 0
            stop_pct = 0
        text += f"├ Target: {format_price(rec.target_price)} (+{target_pct:.0f}%)\n"
        text += f"├ Stop-loss: {format_price(rec.stop_loss_price)} (-{stop_pct:.0f}%)\n"
        text += f"└ Risk/Reward: 1:{rec.risk_reward_ratio:.1f}\n\n"
    else:
        text += f"{get_text('lbl_dont_bet', lang)}\n\n"
    
    # Reasons
    if rec.reasons:
        text += f"{get_text('lbl_pros', lang)}\n"
        for reason in rec.reasons:
            text += f"  {reason}\n"
        text += "\n"
    
    # Warnings
    if rec.warnings:
        text += f"{get_text('lbl_cons', lang)}\n"
        for warning in rec.warnings:
            text += f"  {warning}\n"
            
    # Link
    link_text = get_text("lbl_open_polymarket", lang, url=market.market_url)
    text += f"\n{link_text}"
    
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
