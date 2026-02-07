"""
Multi-language translations for the Polymarket Whale Tracker Bot.
Supports: English (EN), Ukrainian (UK), Russian (RU)
"""

from enum import Enum
from typing import Dict, Any


class Language(str, Enum):
    """Supported languages."""
    EN = "en"
    UK = "uk"
    RU = "ru"


TRANSLATIONS: Dict[str, Dict[str, str]] = {
    # ==================== ONBOARDING ====================
    "welcome_choose_language": {
        "en": "🎯 <b>Welcome to BetSpy!</b>\n\nPlease choose your language:",
        "uk": "🎯 <b>Ласкаво просимо до BetSpy!</b>\n\nОберіть мову:",
        "ru": "🎯 <b>Добро пожаловать в BetSpy!</b>\n\nВыберите язык:",
    },
    "welcome_main": {
        "en": (
            "🎯 <b>BetSpy</b> — Your Edge on Polymarket\n\n"
            "Track the smartest traders. Copy their moves. Win more.\n\n"
            "🔥 <b>What you get:</b>\n"
            "├ ⚡ <b>Instant alerts</b> — know when whales trade\n"
            "├ 📊 <b>Full analytics</b> — positions, PnL, win rate\n"
            "├ ⏸️ <b>Smart filters</b> — set min amount, pause alerts\n"
            "└ 🐋 <b>Track {limit} wallets</b> — build your watchlist\n\n"
            "💡 <i>Pro tip: Start by adding top traders from the leaderboard!</i>\n\n"
            "Ready to spy? 👇"
        ),
        "uk": (
            "🎯 <b>BetSpy</b> — Твоя перевага на Polymarket\n\n"
            "Відстежуй найкращих трейдерів. Копіюй їхні рухи. Вигравай більше.\n\n"
            "🔥 <b>Що ти отримуєш:</b>\n"
            "├ ⚡ <b>Миттєві сповіщення</b> — знай коли кити торгують\n"
            "├ 📊 <b>Повна аналітика</b> — позиції, PnL, win rate\n"
            "├ ⏸️ <b>Розумні фільтри</b> — мін. сума, пауза сповіщень\n"
            "└ 🐋 <b>Відстежуй {limit} гаманців</b> — створи свій watchlist\n\n"
            "💡 <i>Порада: Почни з топ-трейдерів з лідерборду!</i>\n\n"
            "Готовий шпигувати? 👇"
        ),
        "ru": (
            "🎯 <b>BetSpy</b> — Твоё преимущество на Polymarket\n\n"
            "Отслеживай лучших трейдеров. Копируй их сделки. Выигрывай больше.\n\n"
            "🔥 <b>Что ты получаешь:</b>\n"
            "├ ⚡ <b>Мгновенные уведомления</b> — знай когда киты торгуют\n"
            "├ 📊 <b>Полная аналитика</b> — позиции, PnL, win rate\n"
            "├ ⏸️ <b>Умные фильтры</b> — мин. сумма, пауза уведомлений\n"
            "└ 🐋 <b>Отслеживай {limit} кошельков</b> — создай свой watchlist\n\n"
            "💡 <i>Совет: Начни с топ-трейдеров из лидерборда!</i>\n\n"
            "Готов шпионить? 👇"
        ),
    },
    
    # ==================== MAIN MENU BUTTONS ====================
    "btn_add_wallet": {
        "en": "➕ Add Wallet",
        "uk": "➕ Додати гаманець",
        "ru": "➕ Добавить кошелёк",
    },
    "btn_my_wallets": {
        "en": "📋 My Wallets",
        "uk": "📋 Мої гаманці",
        "ru": "📋 Мои кошельки",
    },
    "btn_trending": {
        "en": "📊 Categories",
        "uk": "📊 Категорії",
        "ru": "📊 Категории",
    },

    "btn_settings": {
        "en": "⚙️ Settings",
        "uk": "⚙️ Налаштування",
        "ru": "⚙️ Настройки",
    },
    "btn_help": {
        "en": "❓ Help",
        "uk": "❓ Допомога",
        "ru": "❓ Помощь",
    },
    "btn_back": {
        "en": "⬅️ Back",
        "uk": "⬅️ Назад",
        "ru": "⬅️ Назад",
    },
    "btn_back_to_menu": {
        "en": "🏠 Main Menu",
        "uk": "🏠 Головне меню",
        "ru": "🏠 Главное меню",
    },
    "btn_cancel": {
        "en": "❌ Cancel",
        "uk": "❌ Скасувати",
        "ru": "❌ Отмена",
    },
    
    # ==================== WALLET BUTTONS ====================
    "btn_view_positions": {
        "en": "📊 Positions",
        "uk": "📊 Позиції",
        "ru": "📊 Позиции",
    },
    "btn_view_pnl": {
        "en": "💰 PnL",
        "uk": "💰 PnL",
        "ru": "💰 PnL",
    },
    "btn_view_pnl_range": {
        "en": "📅 PnL Report",
        "uk": "📅 Звіт PnL",
        "ru": "📅 Отчёт PnL",
    },
    "btn_view_detailed_stats": {
        "en": "📊 Detailed Stats",
        "uk": "📊 Детальна статистика",
        "ru": "📊 Детальная статистика",
    },
    "btn_recent_trades": {
        "en": "📈 Recent Trades",
        "uk": "📈 Останні угоди",
        "ru": "📈 Последние сделки",
    },
    "btn_pnl_7_days": {
        "en": "7 Days PnL",
        "uk": "7 днів PnL",
        "ru": "7 дней PnL",
    },
    "btn_pnl_14_days": {
        "en": "14 Days PnL",
        "uk": "14 днів PnL",
        "ru": "14 дней PnL",
    },
    "btn_pnl_30_days": {
        "en": "30 Days PnL",
        "uk": "30 днів PnL",
        "ru": "30 дней PnL",
    },
    "btn_stats_1_day": {
        "en": "1 Day Stats",
        "uk": "Статистика за 1 день",
        "ru": "Статистика за 1 день",
    },
    "btn_stats_1_week": {
        "en": "1 Week Stats",
        "uk": "Статистика за 1 тиждень",
        "ru": "Статистика за 1 неделю",
    },
    "btn_stats_1_month": {
        "en": "1 Month Stats",
        "uk": "Статистика за 1 місяць",
        "ru": "Статистика за 1 месяц",
    },
    "btn_stats_all_time": {
        "en": "All Time Stats",
        "uk": "Статистика за весь час",
        "ru": "Статистика за всё время",
    },
    "btn_debug_wallet": {
        "en": "🔧 Debug",
        "uk": "🔧 Дебаг",
        "ru": "🔧 Отладка",
    },
    "btn_remove_wallet": {
        "en": "🗑 Remove",
        "uk": "🗑 Видалити",
        "ru": "🗑 Удалить",
    },
    "btn_confirm_remove": {
        "en": "✅ Yes, Remove",
        "uk": "✅ Так, видалити",
        "ru": "✅ Да, удалить",
    },
    
    # ==================== WALLET SETTINGS BUTTONS ====================
    "btn_wallet_settings": {
        "en": "⚙️ Settings",
        "uk": "⚙️ Налаштування",
        "ru": "⚙️ Настройки",
    },
    "btn_view_profile": {
        "en": "👤 View Profile",
        "uk": "👤 Профіль",
        "ru": "👤 Профиль",
    },
    "btn_pause_wallet": {
        "en": "⏸️ Pause Alerts",
        "uk": "⏸️ Пауза сповіщень",
        "ru": "⏸️ Пауза уведомлений",
    },
    "btn_resume_wallet": {
        "en": "▶️ Resume Alerts",
        "uk": "▶️ Відновити сповіщення",
        "ru": "▶️ Возобновить уведомления",
    },
    "btn_set_min_amount": {
        "en": "💰 Min Amount",
        "uk": "💰 Мін. сума",
        "ru": "💰 Мин. сумма",
    },
    "btn_min_amount_0": {
        "en": "All trades",
        "uk": "Всі угоди",
        "ru": "Все сделки",
    },
    "btn_min_amount_100": {
        "en": "$100+",
        "uk": "$100+",
        "ru": "$100+",
    },
    "btn_min_amount_500": {
        "en": "$500+",
        "uk": "$500+",
        "ru": "$500+",
    },
    "btn_min_amount_1000": {
        "en": "$1,000+",
        "uk": "$1,000+",
        "ru": "$1,000+",
    },
    "btn_min_amount_5000": {
        "en": "$5,000+",
        "uk": "$5,000+",
        "ru": "$5,000+",
    },
    "btn_min_amount_10000": {
        "en": "$10,000+",
        "uk": "$10,000+",
        "ru": "$10,000+",
    },
    
    # ==================== WALLET SETTINGS MESSAGES ====================
    "wallet_settings_menu": {
        "en": (
            "⚙️ <b>Wallet Settings</b>\n\n"
            "👤 <b>{name}</b>\n"
            "📍 <code>{address}</code>\n\n"
            "🔔 Notifications: {status}\n"
            "💰 Min trade amount: {min_amount}"
        ),
        "uk": (
            "⚙️ <b>Налаштування гаманця</b>\n\n"
            "👤 <b>{name}</b>\n"
            "📍 <code>{address}</code>\n\n"
            "🔔 Сповіщення: {status}\n"
            "💰 Мін. сума угоди: {min_amount}"
        ),
        "ru": (
            "⚙️ <b>Настройки кошелька</b>\n\n"
            "👤 <b>{name}</b>\n"
            "📍 <code>{address}</code>\n\n"
            "🔔 Уведомления: {status}\n"
            "💰 Мин. сумма сделки: {min_amount}"
        ),
    },
    "wallet_paused": {
        "en": "⏸️ Paused",
        "uk": "⏸️ На паузі",
        "ru": "⏸️ На паузе",
    },
    "wallet_active": {
        "en": "✅ Active",
        "uk": "✅ Активно",
        "ru": "✅ Активно",
    },
    "wallet_pause_success": {
        "en": "⏸️ Notifications paused for <b>{name}</b>",
        "uk": "⏸️ Сповіщення призупинено для <b>{name}</b>",
        "ru": "⏸️ Уведомления приостановлены для <b>{name}</b>",
    },
    "wallet_resume_success": {
        "en": "▶️ Notifications resumed for <b>{name}</b>",
        "uk": "▶️ Сповіщення відновлено для <b>{name}</b>",
        "ru": "▶️ Уведомления возобновлены для <b>{name}</b>",
    },
    "select_min_amount": {
        "en": "💰 <b>Select minimum trade amount</b>\n\nOnly trades above this amount will trigger notifications:",
        "uk": "💰 <b>Оберіть мінімальну суму угоди</b>\n\nТільки угоди вище цієї суми будуть надсилати сповіщення:",
        "ru": "💰 <b>Выберите минимальную сумму сделки</b>\n\nТолько сделки выше этой суммы будут отправлять уведомления:",
    },
    "min_amount_updated": {
        "en": "✅ Minimum amount set to <b>{amount}</b> for {name}",
        "uk": "✅ Мінімальна сума встановлена <b>{amount}</b> для {name}",
        "ru": "✅ Минимальная сумма установлена <b>{amount}</b> для {name}",
    },
    "min_amount_all": {
        "en": "All trades",
        "uk": "Всі угоди",
        "ru": "Все сделки",
    },
    
    # ==================== SETTINGS BUTTONS ====================
    "btn_change_language": {
        "en": "🌐 Language",
        "uk": "🌐 Мова",
        "ru": "🌐 Язык",
    },
    "btn_notifications": {
        "en": "🔔 Notifications",
        "uk": "🔔 Сповіщення",
        "ru": "🔔 Уведомления",
    },
    
    # ==================== ADD WALLET FLOW ====================
    "add_wallet_prompt": {
        "en": "📝 <b>Add New Wallet</b>\n\nSend me the wallet address (0x...):\n\n<i>Example: 0x1234567890abcdef...</i>",
        "uk": "📝 <b>Додати новий гаманець</b>\n\nНадішли мені адресу гаманця (0x...):\n\n<i>Приклад: 0x1234567890abcdef...</i>",
        "ru": "📝 <b>Добавить новый кошелёк</b>\n\nОтправь мне адрес кошелька (0x...):\n\n<i>Пример: 0x1234567890abcdef...</i>",
    },
    "add_wallet_nickname_prompt": {
        "en": "👤 <b>Set Nickname</b>\n\nWallet: <code>{address}</code>\n\nSend a nickname for this wallet or press the button to use the detected name:",
        "uk": "👤 <b>Встановити нікнейм</b>\n\nГаманець: <code>{address}</code>\n\nНадішли нікнейм для цього гаманця або натисни кнопку, щоб використати знайдене ім'я:",
        "ru": "👤 <b>Установить никнейм</b>\n\nКошелёк: <code>{address}</code>\n\nОтправь никнейм для этого кошелька или нажми кнопку, чтобы использовать найденное имя:",
    },
    "btn_use_detected_name": {
        "en": "✅ Use: {name}",
        "uk": "✅ Використати: {name}",
        "ru": "✅ Использовать: {name}",
    },
    "btn_use_address": {
        "en": "📋 Use Address",
        "uk": "📋 Використати адресу",
        "ru": "📋 Использовать адрес",
    },
    "wallet_added": {
        "en": "✅ <b>Wallet Added!</b>\n\n👤 Name: <b>{name}</b>\n📋 Address: <code>{address}</code>\n\nYou'll receive notifications when this wallet makes trades!",
        "uk": "✅ <b>Гаманець додано!</b>\n\n👤 Ім'я: <b>{name}</b>\n📋 Адреса: <code>{address}</code>\n\nТи отримуватимеш сповіщення про угоди цього гаманця!",
        "ru": "✅ <b>Кошелёк добавлен!</b>\n\n👤 Имя: <b>{name}</b>\n📋 Адрес: <code>{address}</code>\n\nТы будешь получать уведомления о сделках этого кошелька!",
    },
    "wallet_removed": {
        "en": "🗑 Wallet <b>{name}</b> has been removed.",
        "uk": "🗑 Гаманець <b>{name}</b> видалено.",
        "ru": "🗑 Кошелёк <b>{name}</b> удалён.",
    },
    "wallet_already_exists": {
        "en": "⚠️ This wallet is already being tracked!",
        "uk": "⚠️ Цей гаманець вже відстежується!",
        "ru": "⚠️ Этот кошелёк уже отслеживается!",
    },
    "wallet_limit_reached": {
        "en": "⚠️ You've reached the limit of {limit} wallets.\n\nRemove some wallets to add new ones.",
        "uk": "⚠️ Ти досягнув ліміту в {limit} гаманців.\n\nВидали деякі, щоб додати нові.",
        "ru": "⚠️ Ты достиг лимита в {limit} кошельков.\n\nУдали некоторые, чтобы добавить новые.",
    },
    "invalid_address": {
        "en": "❌ Invalid wallet address.\n\nPlease send a valid Ethereum address starting with 0x",
        "uk": "❌ Невірна адреса гаманця.\n\nНадішли коректну Ethereum адресу, що починається з 0x",
        "ru": "❌ Неверный адрес кошелька.\n\nОтправь корректный Ethereum адрес, начинающийся с 0x",
    },
    
    # ==================== WALLET LIST ====================
    "no_wallets": {
        "en": "📭 <b>No Wallets</b>\n\nYou don't have any tracked wallets yet.\n\nPress «➕ Add Wallet» to start tracking!",
        "uk": "📭 <b>Немає гаманців</b>\n\nУ тебе ще немає відстежуваних гаманців.\n\nНатисни «➕ Додати гаманець» щоб почати!",
        "ru": "📭 <b>Нет кошельков</b>\n\nУ тебя пока нет отслеживаемых кошельков.\n\nНажми «➕ Добавить кошелёк» чтобы начать!",
    },
    "wallet_list_header": {
        "en": "📋 <b>Your Wallets</b> ({count}/{limit})\n\nSelect a wallet to view details:",
        "uk": "📋 <b>Твої гаманці</b> ({count}/{limit})\n\nОбери гаманець для перегляду:",
        "ru": "📋 <b>Твои кошельки</b> ({count}/{limit})\n\nВыбери кошелёк для просмотра:",
    },
    "wallet_details": {
        "en": (
            "👤 <b>{name}</b>\n\n"
            "📋 Address: <code>{address}</code>\n"
            "📅 Tracking since: {date}\n\n"
            "Select an action:"
        ),
        "uk": (
            "👤 <b>{name}</b>\n\n"
            "📋 Адреса: <code>{address}</code>\n"
            "📅 Відстежується з: {date}\n\n"
            "Обери дію:"
        ),
        "ru": (
            "👤 <b>{name}</b>\n\n"
            "📋 Адрес: <code>{address}</code>\n"
            "📅 Отслеживается с: {date}\n\n"
            "Выбери действие:"
        ),
    },
    "confirm_remove_wallet": {
        "en": "⚠️ <b>Remove Wallet?</b>\n\nAre you sure you want to stop tracking <b>{name}</b>?",
        "uk": "⚠️ <b>Видалити гаманець?</b>\n\nТи впевнений, що хочеш припинити відстеження <b>{name}</b>?",
        "ru": "⚠️ <b>Удалить кошелёк?</b>\n\nТы уверен, что хочешь прекратить отслеживание <b>{name}</b>?",
    },
    
    # ==================== POSITIONS ====================
    "positions_header": {
        "en": "📊 <b>Positions for {name}</b>\n\n",
        "uk": "📊 <b>Позиції {name}</b>\n\n",
        "ru": "📊 <b>Позиции {name}</b>\n\n",
    },
    "position_item": {
        "en": (
            "📈 <b>{title}</b>\n"
            "• Outcome: {outcome}\n"
            "• Size: {size:.2f} shares\n"
            "• Avg Price: ${avg_price:.2f}\n"
            "• Current: ${current_value:.2f}\n"
            "• PnL: {pnl_emoji} ${pnl:.2f} ({pnl_percent:.1f}%)\n\n"
        ),
        "uk": (
            "📈 <b>{title}</b>\n"
            "• Результат: {outcome}\n"
            "• Кількість: {size:.2f} акцій\n"
            "• Сер. ціна: ${avg_price:.2f}\n"
            "• Поточна вартість: ${current_value:.2f}\n"
            "• PnL: {pnl_emoji} ${pnl:.2f} ({pnl_percent:.1f}%)\n\n"
        ),
        "ru": (
            "📈 <b>{title}</b>\n"
            "• Исход: {outcome}\n"
            "• Количество: {size:.2f} акций\n"
            "• Сред. цена: ${avg_price:.2f}\n"
            "• Текущая стоимость: ${current_value:.2f}\n"
            "• PnL: {pnl_emoji} ${pnl:.2f} ({pnl_percent:.1f}%)\n\n"
        ),
    },
    "no_positions": {
        "en": "📭 This wallet has no open positions.",
        "uk": "📭 Цей гаманець не має відкритих позицій.",
        "ru": "📭 У этого кошелька нет открытых позиций.",
    },
    "positions_summary": {
        "en": "━━━━━━━━━━━━━━━━━━\n💼 <b>Total Value:</b> ${total_value:.2f}",
        "uk": "━━━━━━━━━━━━━━━━━━\n💼 <b>Загальна вартість:</b> ${total_value:.2f}",
        "ru": "━━━━━━━━━━━━━━━━━━\n💼 <b>Общая стоимость:</b> ${total_value:.2f}",
    },
    
    # ==================== PNL ====================
    "pnl_header": {
        "en": "💰 <b>PnL Summary for {name}</b>\n\n",
        "uk": "💰 <b>PnL звіт для {name}</b>\n\n",
        "ru": "💰 <b>PnL отчёт для {name}</b>\n\n",
    },
    "pnl_summary": {
        "en": (
            "💼 <b>Portfolio Value:</b> ${total_value:.2f}\n\n"
            "📈 <b>Unrealized PnL:</b> {pnl_emoji} ${unrealized_pnl:.2f}\n"
            "📊 <b>Realized PnL:</b> {realized_emoji} ${realized_pnl:.2f}\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🏆 <b>Total PnL:</b> {total_emoji} ${total_pnl:.2f}"
        ),
        "uk": (
            "💼 <b>Вартість портфеля:</b> ${total_value:.2f}\n\n"
            "📈 <b>Нереалізований PnL:</b> {pnl_emoji} ${unrealized_pnl:.2f}\n"
            "📊 <b>Реалізований PnL:</b> {realized_emoji} ${realized_pnl:.2f}\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🏆 <b>Загальний PnL:</b> {total_emoji} ${total_pnl:.2f}"
        ),
        "ru": (
            "💼 <b>Стоимость портфеля:</b> ${total_value:.2f}\n\n"
            "📈 <b>Нереализованный PnL:</b> {pnl_emoji} ${unrealized_pnl:.2f}\n"
            "📊 <b>Реализованный PnL:</b> {realized_emoji} ${realized_pnl:.2f}\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🏆 <b>Общий PnL:</b> {total_emoji} ${total_pnl:.2f}"
        ),
    },
    "pnl_range_header": {
        "en": "💰 <b>PnL Report for {name}</b> - Last {days} Days\n\n",
        "uk": "💰 <b>Звіт PnL для {name}</b> - Останні {days} днів\n\n",
        "ru": "💰 <b>Отчёт PnL для {name}</b> - Последние {days} дней\n\n",
    },
    "stats_header": {
        "en": "📊 <b>Statistics for {name}</b> - Last {days} Days\n\n",
        "uk": "📊 <b>Статистика для {name}</b> - Останні {days} днів\n\n",
        "ru": "📊 <b>Статистика для {name}</b> - Последние {days} дней\n\n",
    },
    "stat_position_value": {
        "en": "💼 Position Value: <b>${value:,.2f}</b>\n",
        "uk": "💼 Вартість позицій: <b>${value:,.2f}</b>\n",
        "ru": "💼 Стоимость позиций: <b>${value:,.2f}</b>\n",
    },
    "stat_biggest_win": {
        "en": "🏆 Biggest Win: <b>+${value:,.2f}</b>\n",
        "uk": "🏆 Найбільший виграш: <b>+${value:,.2f}</b>\n",
        "ru": "🏆 Крупнейший выигрыш: <b>+${value:,.2f}</b>\n",
    },
    "biggest_win_label": {
        "en": "Biggest Win",
        "uk": "Найбільший виграш",
        "ru": "Крупнейший выигрыш",
    },
    "predictions_label": {
        "en": "Predictions",
        "uk": "Прогнози",
        "ru": "Прогнозы",
    },
    "stat_biggest_loss": {
        "en": "🔻 Biggest Loss: <b>${value:,.2f}</b>\n",
        "uk": "🔻 Найбільша втрата: <b>${value:,.2f}</b>\n",
        "ru": "🔻 Крупнейший проигрыш: <b>${value:,.2f}</b>\n",
    },
    "interval_pnl_section": {
        "en": "📊 <b>{interval} Period PnL:</b>\n",
        "uk": "📊 <b>{interval} Період PnL:</b>\n",
        "ru": "📊 <b>{interval} Период PnL:</b>\n",
    },
    "gain_label": {
        "en": "📈 Gain: <b>{emoji} ${value}</b>\n",
        "uk": "📈 Прибуток: <b>{emoji} ${value}</b>\n",
        "ru": "📈 Прибыль: <b>{emoji} ${value}</b>\n",
    },
    "loss_label": {
        "en": "📉 Loss: <b>{emoji} ${value}</b>\n",
        "uk": "📉 Втрата: <b>{emoji} ${value}</b>\n",
        "ru": "📉 Убыток: <b>{emoji} ${value}</b>\n",
    },
    "net_total_label": {
        "en": "🏆 Net Total: <b>{emoji} ${value}</b>",
        "uk": "🏆 Чистий підсумок: <b>{emoji} ${value}</b>",
        "ru": "🏆 Чистый итог: <b>{emoji} ${value}</b>",
    },
    "stat_predictions": {
        "en": "🔮 Predictions: <b>{count}</b>\n",
        "uk": "🔮 Прогнозів: <b>{count}</b>\n",
        "ru": "🔮 Прогнозов: <b>{count}</b>\n",
    },
    "stat_wins_losses": {
        "en": "📈 Wins: <b>{wins}</b> | 📉 Losses: <b>{losses}</b>\n",
        "uk": "📈 Виграшів: <b>{wins}</b> | 📉 Програшів: <b>{losses}</b>\n",
        "ru": "📈 Выигрышей: <b>{wins}</b> | 📉 Проигрышей: <b>{losses}</b>\n",
    },
    "stat_total_won_lost": {
        "en": "💰 Total Won: <b>+${won:,.2f}</b> | 💸 Total Lost: <b>${lost:,.2f}</b>\n",
        "uk": "💰 Всього виграно: <b>+${won:,.2f}</b> | 💸 Всього втрачено: <b>${lost:,.2f}</b>\n",
        "ru": "💰 Всего выиграно: <b>+${won:,.2f}</b> | 💸 Всего проиграно: <b>${lost:,.2f}</b>\n",
    },
    "stat_net_pnl": {
        "en": "📊 Net PnL: <b>{sign}${value:,.2f}</b>\n",
        "uk": "📊 Чистий PnL: <b>{sign}${value:,.2f}</b>\n",
        "ru": "📊 Чистый PnL: <b>{sign}${value:,.2f}</b>\n",
    },
    "portfolio_pnl_section": {
        "en": "<b>📊 Portfolio PnL:</b>\n",
        "uk": "<b>📊 PnL Портфеля:</b>\n",
        "ru": "<b>📊 PnL Портфеля:</b>\n",
    },
    "unrealized_pnl_label": {
        "en": "📈 Unrealized PnL: <b>{emoji} ${value}</b>",
        "uk": "📈 Нереалізований PnL: <b>{emoji} ${value}</b>",
        "ru": "📈 Нереализованный PnL: <b>{emoji} ${value}</b>",
    },
    "realized_pnl_label": {
        "en": "💰 Realized PnL: <b>{emoji} ${value}</b>",
        "uk": "💰 Реалізований PnL: <b>{emoji} ${value}</b>",
        "ru": "💰 Реализованный PnL: <b>{emoji} ${value}</b>",
    },
    "total_pnl_label": {
        "en": "🏆 Total PnL: <b>{emoji} ${value}</b>",
        "uk": "🏆 Загальний PnL: <b>{emoji} ${value}</b>",
        "ru": "🏆 Общий PnL: <b>{emoji} ${value}</b>",
    },
    "period_performance_section": {
        "en": "<b>📈 Period Performance:</b>\n",
        "uk": "<b>📈 Прибутковість за період:</b>\n",
        "ru": "<b>📈 Прибыльность за период:</b>\n",
    },
    "net_pnl_period_label": {
        "en": "📊 Net PnL ({days}D): <b>{emoji} ${value}</b>",
        "uk": "📊 Чистий PnL ({days}Д): <b>{emoji} ${value}</b>",
        "ru": "📊 Чистый PnL ({days}Д): <b>{emoji} ${value}</b>",
    },
    "trading_activity_section": {
        "en": "<b>🎯 Trading Activity:</b>\n",
        "uk": "<b>🎯 Торгова активність:</b>\n",
        "ru": "<b>🎯 Торговая активность:</b>\n",
    },
    
    # ==================== RECENT TRADES ====================
    "recent_trades_header": {
        "en": "📈 <b>Recent Trades for {name}</b>\n\n",
        "uk": "📈 <b>Останні угоди {name}</b>\n\n",
        "ru": "📈 <b>Последние сделки {name}</b>\n\n",
    },
    "trade_item": {
        "en": (
            "{side_emoji} <b>{side}</b> {outcome}\n"
            "📊 {title}\n"
            "💵 ${usdc_size:.2f} @ ${price:.2f}\n"
            "🕐 {time}\n\n"
        ),
        "uk": (
            "{side_emoji} <b>{side}</b> {outcome}\n"
            "📊 {title}\n"
            "💵 ${usdc_size:.2f} @ ${price:.2f}\n"
            "🕐 {time}\n\n"
        ),
        "ru": (
            "{side_emoji} <b>{side}</b> {outcome}\n"
            "📊 {title}\n"
            "💵 ${usdc_size:.2f} @ ${price:.2f}\n"
            "🕐 {time}\n\n"
        ),
    },
    "no_recent_trades": {
        "en": "📭 No recent trades found for this wallet.",
        "uk": "📭 Немає останніх угод для цього гаманця.",
        "ru": "📭 Нет последних сделок для этого кошелька.",
    },
    
    
    # ==================== INTELLIGENCE / CATEGORIES ====================
    "intel_title": {
        "en": "📊 <b>MARKET SIGNALS</b>",
        "uk": "📊 <b>СИГНАЛИ РИНКІВ</b>",
        "ru": "📊 <b>СИГНАЛЫ РЫНКОВ</b>",
    },
    "intel_choose_category": {
        "en": "Choose a category to find top opportunities:",
        "uk": "Обери категорію для пошуку можливостей:",
        "ru": "Выберите категорию для поиска возможностей:",
    },
    "intel_header_category": {
        "en": "{emoji} <b>SIGNALS: {category}</b>",
        "uk": "{emoji} <b>СИГНАЛИ: {category}</b>",
        "ru": "{emoji} <b>СИГНАЛЫ: {category}</b>",
    },
    "intel_page_info": {
        "en": "<i>Page {page}/{total_pages} | Total: {total_items}</i>",
        "uk": "<i>Сторінка {page}/{total_pages} | Всього: {total_items}</i>",
        "ru": "<i>Страница {page}/{total_pages} | Всего: {total_items}</i>",
    },
    "intel_click_hint": {
        "en": "💡 <i>Click number for details</i>",
        "uk": "💡 <i>Натисни на номер для деталей</i>",
        "ru": "💡 <i>Нажми на номер для деталей</i>",
    },
    "intel_footer_links": {
        "en": "🔗 <b>Market Links:</b>",
        "uk": "🔗 <b>Посилання на ринки:</b>",
        "ru": "🔗 <b>Ссылки на рынки:</b>",
    },
    "intel_link_text": {
        "en": "Go to market ↗️",
        "uk": "Перейти до ринку ↗️",
        "ru": "Перейти к рынку ↗️",
    },
    
    # Category Names
    "cat_politics": {
        "en": "Politics",
        "uk": "Політика",
        "ru": "Политика",
    },
    "cat_sports": {
        "en": "Sports",
        "uk": "Спорт",
        "ru": "Спорт",
    },
    "cat_pop_culture": {
        "en": "Pop Culture",
        "uk": "Поп-культура",
        "ru": "Поп-культура",
    },
    "cat_business": {
        "en": "Business",
        "uk": "Бізнес",
        "ru": "Бизнес",
    },
    "cat_crypto": {
        "en": "Crypto",
        "uk": "Крипто",
        "ru": "Крипто",
    },
    "cat_science": {
        "en": "Science",
        "uk": "Наука",
        "ru": "Наука",
    },
    "cat_gaming": {
        "en": "Gaming",
        "uk": "Ігри",
        "ru": "Игры",
    },
    "cat_entertainment": {
        "en": "Entertainment",
        "uk": "Розваги",
        "ru": "Развлечения",
    },
    "cat_world": {
        "en": "World",
        "uk": "Світ",
        "ru": "Мир",
    },
    "cat_tech": {
        "en": "Tech",
        "uk": "Технології",
        "ru": "Технологии",
    },
    "cat_all": {
        "en": "All Categories",
        "uk": "Всі категорії",
        "ru": "Все категории",
    },
    "cat_economics": { # Fallback / alias
         "en": "Economics",
         "uk": "Економіка",
         "ru": "Экономика",
    },
    "cat_economics": { # Fallback / alias
         "en": "Economics",
         "uk": "Економіка",
         "ru": "Экономика",
    },
    
    # Market Card Labels
    "lbl_vol": {
        "en": "💰 Vol:",
        "uk": "💰 Обсяг:",
        "ru": "💰 Объем:",
    },
    "lbl_whales": {
        "en": "🐋 Whales:",
        "uk": "🐋 Кити:",
        "ru": "🐋 Киты:",
    },
    "lbl_signal": {
        "en": "Signal:",
        "uk": "Сигнал:",
        "ru": "Сигнал:",
    },
    "lbl_rec": {
        "en": "💡 Recommendation:",
        "uk": "💡 Рекомендація:",
        "ru": "💡 Рекомендация:",
    },
    "lbl_prices": {
        "en": "💰 PRICES:",
        "uk": "💰 ЦІНИ:",
        "ru": "💰 ЦЕНЫ:",
    },
    "lbl_today": {
        "en": "🕐 Today",
        "uk": "🕐 Сьогодні",
        "ru": "🕐 Сегодня",
    },
    "lbl_tomorrow": {
        "en": "🕐 Tomorrow",
        "uk": "🕐 Завтра",
        "ru": "🕐 Завтра",
    },
    "lbl_days_left": {
        "en": "🕐 {days} days",
        "uk": "🕐 {days} дн.",
        "ru": "🕐 {days} дн.",
    },
    "lbl_days_left": {
        "en": "🕐 {days} days",
        "uk": "🕐 {days} дн.",
        "ru": "🕐 {days} дн.",
    },
    
    # Detailed Analysis Labels
    "lbl_volume_title": {
        "en": "📊 <b>VOLUME:</b>",
        "uk": "📊 <b>ОБСЯГ:</b>",
        "ru": "📊 <b>ОБЪЕМ:</b>",
    },
    "lbl_whale_analysis": {
        "en": "🐋 <b>WHALE ANALYSIS:</b>",
        "uk": "🐋 <b>АНАЛІЗ КИТІВ:</b>",
        "ru": "🐋 <b>АНАЛИЗ КИТОВ:</b>",
    },
    "lbl_retail": {
        "en": "👥 <b>RETAIL:</b>",
        "uk": "👥 <b>РІТЕЙЛ:</b>",
        "ru": "👥 <b>РИТЕЙЛ:</b>",
    },
    "lbl_trend": {
        "en": "📈 <b>TREND:</b>",
        "uk": "📈 <b>ТРЕНД:</b>",
        "ru": "📈 <b>ТРЕНД:</b>",
    },
    "lbl_closing": {
        "en": "⏰ <b>CLOSING:</b>",
        "uk": "⏰ <b>ЗАКРИТТЯ:</b>",
        "ru": "⏰ <b>ЗАКРЫТИЕ:</b>",
    },
    "lbl_score_breakdown": {
        "en": "📊 <b>SCORE BREAKDOWN:</b>",
        "uk": "📊 <b>ДЕТАЛІ ОЦІНКИ:</b>",
        "ru": "📊 <b>ДЕТАЛИ ОЦЕНКИ:</b>",
    },
    "lbl_recommendation": {
        "en": "💡 <b>RECOMMENDATION:</b>",
        "uk": "💡 <b>РЕКОМЕНДАЦІЯ:</b>",
        "ru": "💡 <b>РЕКОМЕНДАЦИЯ:</b>",
    },
    "lbl_bet_yes": {
        "en": "✅ <b>BET: YES</b>",
        "uk": "✅ <b>СТАВИТИ: YES</b>",
        "ru": "✅ <b>СТАВИТЬ: YES</b>",
    },
    "lbl_bet_no": {
        "en": "✅ <b>BET: NO</b>",
        "uk": "✅ <b>СТАВИТИ: NO</b>",
        "ru": "✅ <b>СТАВИТЬ: NO</b>",
    },
    "lbl_dont_bet": {
        "en": "❌ <b>DO NOT BET</b>",
        "uk": "❌ <b>НЕ СТАВИТИ</b>",
        "ru": "❌ <b>НЕ СТАВИТЬ</b>",
    },
    "lbl_pros": {
        "en": "✅ <b>Pros:</b>",
        "uk": "✅ <b>Плюси:</b>",
        "ru": "✅ <b>Плюсы:</b>",
    },
    "lbl_cons": {
        "en": "⚠️ <b>Risks:</b>",
        "uk": "⚠️ <b>Ризики:</b>",
        "ru": "⚠️ <b>Риски:</b>",
    },
    "lbl_open_polymarket": {
        "en": "🔗 <a href='{url}'>Open on Polymarket ↗️</a>",
        "uk": "🔗 <a href='{url}'>Відкрити на Polymarket ↗️</a>",
        "ru": "🔗 <a href='{url}'>Открыть на Polymarket ↗️</a>",
    },
    "lbl_whales_yes": {
        "en": "├ Whales YES: {count}",
        "uk": "├ Кити YES: {count}",
        "ru": "├ Киты YES: {count}",
    },
    "lbl_whales_no": {
        "en": "└ Whales NO: {count}",
        "uk": "└ Кити NO: {count}",
        "ru": "└ Киты NO: {count}",
    },
    "lbl_not_enough_data": {
        "en": "└ Not enough data",
        "uk": "└ Недостатньо даних",
        "ru": "└ Недостаточно данных",
    },
    
    # ==================== SETTINGS ====================
    "settings_menu": {
        "en": "⚙️ <b>Settings</b>\n\nCurrent language: 🇬🇧 English",
        "uk": "⚙️ <b>Налаштування</b>\n\nПоточна мова: 🇺🇦 Українська",
        "ru": "⚙️ <b>Настройки</b>\n\nТекущий язык: 🇷🇺 Русский",
    },
    "select_language": {
        "en": "🌐 <b>Select Language</b>\n\nChoose your preferred language:",
        "uk": "🌐 <b>Вибір мови</b>\n\nОбери бажану мову:",
        "ru": "🌐 <b>Выбор языка</b>\n\nВыбери предпочитаемый язык:",
    },
    "language_changed": {
        "en": "✅ Language changed to English!",
        "uk": "✅ Мову змінено на Українську!",
        "ru": "✅ Язык изменён на Русский!",
    },
    
    # ==================== HELP ====================
    "help_text": {
        "en": (
            "❓ <b>Help</b>\n\n"
            "<b>How it works:</b>\n"
            "1. Add wallet addresses you want to track\n"
            "2. Get instant notifications when they trade\n"
            "3. View their positions and PnL anytime\n\n"
            "<b>Commands:</b>\n"
            "/start - Main menu\n"
            "/help - This help message\n\n"
            "<b>Tips:</b>\n"
            "• Find whale wallets on Polymarket leaderboard\n"
            "• Track top traders to copy their bets\n"
            "• Use notifications to react quickly"
        ),
        "uk": (
            "❓ <b>Допомога</b>\n\n"
            "<b>Як це працює:</b>\n"
            "1. Додай адреси гаманців для відстеження\n"
            "2. Отримуй миттєві сповіщення про їх угоди\n"
            "3. Переглядай позиції та PnL в будь-який час\n\n"
            "<b>Команди:</b>\n"
            "/start - Головне меню\n"
            "/help - Ця довідка\n\n"
            "<b>Поради:</b>\n"
            "• Знаходь гаманці китів у лідерборді Polymarket\n"
            "• Відстежуй топ-трейдерів, щоб копіювати їх ставки\n"
            "• Використовуй сповіщення для швидкої реакції"
        ),
        "ru": (
            "❓ <b>Помощь</b>\n\n"
            "<b>Как это работает:</b>\n"
            "1. Добавь адреса кошельков для отслеживания\n"
            "2. Получай мгновенные уведомления о их сделках\n"
            "3. Просматривай позиции и PnL в любое время\n\n"
            "<b>Команды:</b>\n"
            "/start - Главное меню\n"
            "/help - Эта справка\n\n"
            "<b>Советы:</b>\n"
            "• Находи кошельки китов в лидерборде Polymarket\n"
            "• Отслеживай топ-трейдеров, чтобы копировать их ставки\n"
            "• Используй уведомления для быстрой реакции"
        ),
    },
    
    # ==================== TRADE NOTIFICATIONS ====================
    "new_trade": {
        "en": (
            "👤 <b>NEW TRADE!</b>\n\n"
            "👤 Who: <b>{wallet_name}</b>\n"
            "📋 Market: {market_title}\n"
            "💰 Action: {side} <b>{outcome}</b>\n"
            "📊 Quantity: <b>{size:,.2f}</b> shares\n"
            "💵 Amount: <b>${usdc_size:,.2f}</b>\n"
            "💲 Price: <b>${price:.2f}</b>\n\n"
            "👉 <a href=\"{market_link}\">Open on Polymarket</a>"
        ),
        "uk": (
            "👤 <b>НОВА УГОДА!</b>\n\n"
            "👤 Хто: <b>{wallet_name}</b>\n"
            "📋 Ринок: {market_title}\n"
            "💰 Дія: {side} <b>{outcome}</b>\n"
            "📊 Кількість: <b>{size:,.2f}</b> акцій\n"
            "💵 Сума: <b>${usdc_size:,.2f}</b>\n"
            "💲 Ціна: <b>${price:.2f}</b>\n\n"
            "👉 <a href=\"{market_link}\">Відкрити на Polymarket</a>"
        ),
        "ru": (
            "👤 <b>НОВАЯ СДЕЛКА!</b>\n\n"
            "👤 Кто: <b>{wallet_name}</b>\n"
            "📋 Рынок: {market_title}\n"
            "💰 Действие: {side} <b>{outcome}</b>\n"
            "📊 Количество: <b>{size:,.2f}</b> акций\n"
            "💵 Сумма: <b>${usdc_size:,.2f}</b>\n"
            "💲 Цена: <b>${price:.2f}</b>\n\n"
            "👉 <a href=\"{market_link}\">Открыть на Polymarket</a>"
        ),
    },
    "side_buy": {
        "en": "🟢 BUY",
        "uk": "🟢 КУПІВЛЯ",
        "ru": "🟢 ПОКУПКА",
    },
    "side_sell": {
        "en": "🔴 SELL",
        "uk": "🔴 ПРОДАЖ",
        "ru": "🔴 ПРОДАЖА",
    },
    
    "btn_prev_page": {
        "en": "⬅️ Prev",
        "uk": "⬅️ Попер.",
        "ru": "⬅️ Пред.",
    },
    "btn_next_page": {
        "en": "Next ➡️",
        "uk": "Наст. ➡️",
        "ru": "След. ➡️",
    },
    "btn_refresh": {
        "en": "🔄 Refresh",
        "uk": "🔄 Оновити",
        "ru": "🔄 Обновить",
    },
    
    "no_signals": {
        "en": "<b>No active signals found.</b>\nTry later or check another category.",
        "uk": "<b>Не знайдено активних сигналів.</b>\nСпробуй пізніше або іншу категорію.",
        "ru": "<b>Не найдено активных сигналов.</b>\nПопробуй позже или другую категорию.",
    },
    
    # ==================== ERRORS ====================
    "error_generic": {
        "en": "❌ An error occurred. Please try again.",
        "uk": "❌ Сталася помилка. Спробуй ще раз.",
        "ru": "❌ Произошла ошибка. Попробуй ещё раз.",
    },
    "error_api": {
        "en": "❌ Failed to connect to Polymarket. Please try again later.",
        "uk": "❌ Не вдалося з'єднатися з Polymarket. Спробуй пізніше.",
        "ru": "❌ Не удалось подключиться к Polymarket. Попробуй позже.",
    },
    "loading": {
        "en": "⏳ Loading...",
        "uk": "⏳ Завантаження...",
        "ru": "⏳ Загрузка...",
    },
    "action_cancelled": {
        "en": "❌ Action cancelled.",
        "uk": "❌ Дію скасовано.",
        "ru": "❌ Действие отменено.",
    },
    
    # ==================== LANGUAGE BUTTONS ====================
    "btn_lang_en": {
        "en": "🇬🇧 English",
        "uk": "🇬🇧 English",
        "ru": "🇬🇧 English",
    },
    "btn_lang_uk": {
        "en": "🇺🇦 Українська",
        "uk": "🇺🇦 Українська",
        "ru": "🇺🇦 Українська",
    },
    "btn_lang_ru": {
        "en": "🇷🇺 Русский",
        "uk": "🇷🇺 Русский",
        "ru": "🇷🇺 Русский",
    },
}


def get_text(key: str, lang: str = "en", **kwargs: Any) -> str:
    """
    Get translated text by key and language.
    """
    if key not in TRANSLATIONS:
        return f"[Missing translation: {key}]"
    
    translation = TRANSLATIONS[key].get(lang, TRANSLATIONS[key].get("en", f"[{key}]"))
    
    if kwargs:
        try:
            return translation.format(**kwargs)
        except KeyError as e:
            return f"[Format error for {key}: {e}]"
    
    return translation


def get_side_text(side: str, lang: str = "en") -> str:
    """Get localized text for trade side (BUY/SELL)."""
    if side.upper() == "BUY":
        return get_text("side_buy", lang)
    return get_text("side_sell", lang)


def get_pnl_emoji(value: float) -> str:
    """Get emoji for PnL value."""
    if value > 0:
        return "🟢"
    elif value < 0:
        return "🔴"
    return "⚪"
