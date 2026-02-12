import asyncio
import aiohttp
import json
import random

async def check_profile():
    # Try different URL construction patterns for gamma API
    urls = [
        "https://gamma-api.polymarket.com/profiles?id=0x4195265DBDc9B42165961364Cd75875D754644f0",
        "https://gamma-api.polymarket.com/users/0x4195265DBDc9B42165961364Cd75875D754644f0",
        "https://data-api.polymarket.com/activity?user=0x4195265DBDc9B42165961364Cd75875D754644f0&limit=1"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        for url in urls:
            print(f"Trying: {url}")
            try:
                async with session.get(url) as response:
                    print(f"Status: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        print(json.dumps(data, indent=2))
                        return
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_profile())
