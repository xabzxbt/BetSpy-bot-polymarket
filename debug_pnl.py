
import asyncio
from polymarket_api import PolymarketApiClient
from config import get_settings

async def main():
    async with PolymarketApiClient() as client:
        print("Searching for market...")
        # Search for markets
        url = f"{client.data_api_url}/events"
        params = {"q": "Trump", "limit": 5, "closed": False}
        data = await client._request("GET", url, params)
        
        market_id = None
        if data:
            print(f"Raw search data type: {type(data)}")
            if isinstance(data, list):
                print(f"Items found: {len(data)}")
            else:
                print(f"Data: {data}")

            for event in data:
                print(f"Checking event: {event.get('title')}")
                if "markets" in event:
                    for m in event["markets"]:
                        print(f"  - {m.get('question')} (ID: {m.get('conditionId')})")
                        if "Trump" in m.get("question", ""):
                            market_id = m.get("conditionId")
                            break
                if market_id: break
        
        if not market_id:
            print("Market not found via search. Using fallback ID (Trump Inauguration).")
            market_id = "0x2e65c0ee817fdf8b0c2013144cce5d29944062016550672776c59c5512762266" # Example ID

        print(f"Using Condition ID: {market_id}")

        # Fetch holders
        print("Fetching holders...")
        # We use a lower level call to get raw holders first to pick a wallet
        h_url = f"{client.data_api_url}/holders"
        h_params = {"market": market_id, "limit": 50}
        h_data = await client._request("GET", h_url, h_params)
        
        if not h_data:
            print("No holders found.")
            return

        holders = h_data if isinstance(h_data, list) else h_data.get("holders", [])
        
        print(f"Found {len(holders)} holders. Checking top 5 for PnL...")
        
        for i, h in enumerate(holders[:5]):
            wallet = h.get("proxyWallet") or h.get("address")
            print(f"\n--- Holder {i+1}: {wallet} ---")
            
            # Test get_profile
            profile = await client.get_profile(wallet)
            print(f"Profile PnL: {profile.pnl}")
            print(f"Profile Volume: {profile.volume}")
            
            # Debug get_user_pnl_series specifically
            print("Debugging series fetch...")
            series = await client.get_user_pnl_series(wallet, interval="ALL")
            if series:
                print(f"Series found: {len(series)} points")
                print(f"First: {series[0]}")
                print(f"Last: {series[-1]}")
            else:
                print("Series EMPTY or FAILED.")

if __name__ == "__main__":
    asyncio.run(main())
