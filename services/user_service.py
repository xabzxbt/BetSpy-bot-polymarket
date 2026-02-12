"""
User resolution service — eliminates handler boilerplate.

BEFORE (repeated in every handler):
    async with db.session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )
        lang = user.language

AFTER:
    user, lang = await resolve_user(callback.from_user)
"""

from typing import Tuple, Optional
from aiogram.types import User as TgUser

from database import db
from repository import UserRepository
from models import User


async def resolve_user(tg_user: TgUser) -> Tuple[User, str]:
    """Resolve Telegram user to DB user + language code.
    
    Creates user if not exists. Always returns (User, lang_code).
    """
    async with db.session() as session:
        repo = UserRepository(session)
        user = await repo.get_or_create(
            telegram_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
        )
        return user, user.language


async def get_user_lang(tg_user: TgUser) -> str:
    """Quick helper to just get language code."""
    _, lang = await resolve_user(tg_user)
    return lang


async def update_language(telegram_id: int, lang_code: str) -> None:
    """Update user's language preference."""
    async with db.session() as session:
        repo = UserRepository(session)
        await repo.update_language(telegram_id, lang_code)
