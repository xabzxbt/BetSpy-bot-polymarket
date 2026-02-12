import asyncio
import aiohttp
import json

async def check_activity():
    # Use the working endpoint
    url = "https://data-api.polymarket.com/activity"
    params = {
        "user": "0x4195265DBDc9B42165961364Cd75875D754644f0",
        "limit": 1,
        "sortBy": "TIMESTAMP",
        "sortDirection": "ASC" # Try to get the FIRST activity ever
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        print(f"Trying: {url} with params {params}")
        async with session.get(url, params=params) as response:
            print(f"Status: {response.status}")
            if response.status == 200:
                data = await response.json()
                print(json.dumps(data, indent=2))
            else:
                print(await response.text())

if __name__ == "__main__":
    asyncio.run(check_activity())
