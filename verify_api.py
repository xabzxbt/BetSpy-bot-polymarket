
import asyncio
import aiohttp
import sys

# Remove Windows policy setting unless necessary. Usually auto-detected.

async def main():
    wallet = "0x4195265DBDc9B42165961364Cd75875D754644f0"
    base_url = "https://data-api.polymarket.com"
    
    print(f"Testing for {wallet}...")
    
    async with aiohttp.ClientSession() as session:
        # Positions
        print(f"\n--- Positions ---")
        try:
            async with session.get(f"{base_url}/positions", params={"user": wallet, "limit": 5}) as r:
                print(f"Status: {r.status}")
                if r.status == 200:
                    text = await r.text()
                    print(f"Response: {text}")
                else:
                    print(await r.text())
        except Exception as e:
            print(f"Error: {e}")

        # Trades
        print(f"\n--- Trades ---")
        try:
            async with session.get(f"{base_url}/trades", params={"user": wallet, "limit": 5}) as r:
                print(f"Status: {r.status}")
                if r.status == 200:
                    text = await r.text()
                    print(f"Response: {text}")
                else:
                    print(await r.text())
        except Exception as e:
            print(f"Error: {e}")

        # Activity
        print(f"\n--- Activity ---")
        try:
            async with session.get(f"{base_url}/activity", params={"user": wallet, "limit": 5}) as r:
                print(f"Status: {r.status}")
                if r.status == 200:
                    text = await r.text()
                    print(f"Response: {text}")
                else:
                    print(await r.text())
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
