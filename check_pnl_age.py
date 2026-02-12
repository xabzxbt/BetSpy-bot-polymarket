import asyncio
import aiohttp
import json
from datetime import datetime

async def check_pnl_history():
    # Try different URL construction patterns for PnL
    base_urls = [
        "https://data-api.polymarket.com/profit/history",
        "https://user-pnl-api.polymarket.com/user-pnl"
    ]
    
    params = {
        "user": "0x4195265DBDc9B42165961364Cd75875D754644f0",
        "window": "ALL",
        "limit": 500
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        for url in base_urls:
            print(f"Trying: {url}")
            try:
                # user-pnl-api params differ
                if "user-pnl" in url:
                     p = {
                         "user_address": params["user"],
                         "interval": "all",
                         "fidelity": "1d"
                     }
                else:
                    p = params

                async with session.get(url, params=p) as response:
                    print(f"Status: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        if isinstance(data, list) and len(data) > 0:
                            first = data[0]
                            last = data[-1]
                            print(f"Items: {len(data)}")
                            if "t" in first:
                                ts = int(first["t"])
                                dt = datetime.fromtimestamp(ts)
                                print(f"First Activity: {dt} (ts={ts})")
                            print(json.dumps(data[:2], indent=2))
                            return
                        else:
                            print("Empty list or invalid data")
                            print(data)
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_pnl_history())
