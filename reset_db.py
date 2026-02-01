"""
Database reset script.
WARNING: This will DELETE all data and recreate tables!

Usage:
    python reset_db.py
    
Or with confirmation skip:
    python reset_db.py --yes
"""

import asyncio
import sys

from sqlalchemy import text
from loguru import logger

from config import get_settings
from database import db
from models import Base


async def reset_database(skip_confirmation: bool = False) -> None:
    """Drop all tables and recreate them."""
    
    if not skip_confirmation:
        print("\n" + "=" * 60)
        print("⚠️  WARNING: DATABASE RESET")
        print("=" * 60)
        print("\nThis will DELETE ALL DATA in the database:")
        print("  - All users")
        print("  - All tracked wallets")
        print("  - All settings")
        print("\nThis action CANNOT be undone!")
        print("=" * 60)
        
        confirm = input("\nType 'YES' to confirm: ")
        
        if confirm != "YES":
            print("\n❌ Operation cancelled.")
            return
    
    print("\n🔄 Starting database reset...")
    
    # Initialize database connection
    await db.init()
    
    try:
        # Drop all tables
        print("📦 Dropping existing tables...")
        async with db._engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        print("✅ Tables dropped")
        
        # Create all tables
        print("📦 Creating new tables...")
        async with db._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Tables created")
        
        print("\n" + "=" * 60)
        print("✅ DATABASE RESET COMPLETE!")
        print("=" * 60)
        print("\nYou can now start the bot with: python main.py")
        
    except Exception as e:
        logger.exception(f"Error during reset: {e}")
        print(f"\n❌ Error: {e}")
        sys.exit(1)
    
    finally:
        await db.close()


async def show_stats() -> None:
    """Show current database statistics."""
    await db.init()
    
    try:
        async with db.session() as session:
            # Count users
            result = await session.execute(text("SELECT COUNT(*) FROM users"))
            users_count = result.scalar()
            
            # Count wallets
            result = await session.execute(text("SELECT COUNT(*) FROM tracked_wallets"))
            wallets_count = result.scalar()
            
            print("\n📊 Current Database Stats:")
            print(f"   Users: {users_count}")
            print(f"   Tracked Wallets: {wallets_count}")
            
    except Exception as e:
        print(f"   (Could not get stats: {e})")
    
    finally:
        await db.close()


def main():
    """Main entry point."""
    # Setup basic logging
    logger.remove()
    logger.add(sys.stdout, level="WARNING")
    
    skip_confirmation = "--yes" in sys.argv or "-y" in sys.argv
    show_stats_only = "--stats" in sys.argv
    
    if show_stats_only:
        asyncio.run(show_stats())
    else:
        asyncio.run(reset_database(skip_confirmation))


if __name__ == "__main__":
    main()
