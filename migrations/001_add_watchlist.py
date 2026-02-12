"""
Migration: Add watchlist_items table.

Run: python migrations/001_add_watchlist.py

This migration is also handled automatically by SQLAlchemy metadata.create_all()
in main.py, but this script is provided for manual/explicit migration.
"""

import asyncio
from database import db


MIGRATION_SQL = """
CREATE TABLE IF NOT EXISTS watchlist_items (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    market_slug VARCHAR(255) NOT NULL,
    event_slug VARCHAR(255) NOT NULL,
    question VARCHAR(500) NOT NULL,
    condition_id VARCHAR(100),
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_watchlist_user_id ON watchlist_items(user_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_watchlist_user_market ON watchlist_items(user_id, market_slug);
"""


async def run_migration():
    await db.init()
    async with db.engine.begin() as conn:
        await conn.execute(db.text(MIGRATION_SQL))
    print("Migration complete: watchlist_items table created")
    await db.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
