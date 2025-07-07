import os
import aiohttp
import asyncio
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()


async def get_twitch_access_token(client_id: str, client_secret: str) -> str | None:
    """Get an access token from Twitch using client credentials."""
    url = "https://id.twitch.tv/oauth2/token"
    params = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("access_token")
                else:
                    print(f"Failed to get access token. Status: {response.status}")
                    return None
    except Exception as e:
        print(f"Error getting access token: {e}")
        return None


async def check_hypixel_streams():
    """Check for Minecraft streams with 'hypixel' and 'skyblock' in their title."""
    client_id = os.getenv("TWITCH_CLIENT_ID")
    client_secret = os.getenv("TWITCH_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("Error: TWITCH_CLIENT_ID or TWITCH_CLIENT_SECRET not found in environment variables")
        return

    # Get access token
    access_token = await get_twitch_access_token(client_id, client_secret)
    if not access_token:
        print("Failed to get access token")
        return

    # Search for streams
    url = "https://api.twitch.tv/helix/streams"
    headers = {
        "Client-ID": client_id,
        "Authorization": f"Bearer {access_token}"
    }

    all_hypixel_streams = []
    cursor = None

    try:
        async with aiohttp.ClientSession() as session:
            while True:
                params = {
                    "game_id": "27471",  # Minecraft game ID
                    "first": 100,  # Maximum allowed by API
                }
                if cursor:
                    params["after"] = cursor

                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        streams = data.get("data", [])

                        # Filter streams with "hypixel" and "skyblock" in title
                        hypixel_streams = [
                            stream for stream in streams
                            if "hypixel" in stream["title"].lower() and
                               any(term in stream["title"].lower() for term in ["skyblock", "sky block", "sky-block"])
                        ]
                        all_hypixel_streams.extend(hypixel_streams)

                        # Get cursor for next page
                        cursor = data.get("pagination", {}).get("cursor")
                        if not cursor:
                            break
                    else:
                        print(f"Failed to get streams. Status: {response.status}")
                        break

        if all_hypixel_streams:
            # Sort streams by viewer count in descending order
            sorted_streams = sorted(all_hypixel_streams, key=lambda x: x['viewer_count'], reverse=True)

            print(f"\nFound {len(sorted_streams)} Hypixel SkyBlock streams:")
            print("-" * 30)
            for stream in sorted_streams:
                print(f"{stream['user_name']} ({stream['viewer_count']:,} viewers)")
            print("-" * 30)
        else:
            print("No Hypixel SkyBlock streams found")

    except Exception as e:
        print(f"Error checking streams: {e}")


async def monitor_new_streams():
    """Continuously monitor for new Hypixel SkyBlock streams every 2 minutes."""
    client_id = os.getenv("TWITCH_CLIENT_ID")
    client_secret = os.getenv("TWITCH_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("Error: TWITCH_CLIENT_ID or TWITCH_CLIENT_SECRET not found in environment variables")
        return

    # Get initial access token
    access_token = await get_twitch_access_token(client_id, client_secret)
    if not access_token:
        print("Failed to get access token")
        return

    # Keep track of seen streams
    seen_streams = set()

    print("\nStarting stream monitor (checking every 2 minutes)...")
    print("Press Ctrl+C to stop")
    print("-" * 50)

    try:
        while True:
            current_time = datetime.now().strftime("%H:%M:%S")
            print(f"\n[{current_time}] Checking for new streams...")

            # Get access token (refresh if needed)
            access_token = await get_twitch_access_token(client_id, client_secret)
            if not access_token:
                print("Failed to get access token")
                await asyncio.sleep(120)  # Wait 2 minutes before retrying
                continue

            # Search for streams
            url = "https://api.twitch.tv/helix/streams"
            headers = {
                "Client-ID": client_id,
                "Authorization": f"Bearer {access_token}"
            }

            new_streams = []
            cursor = None

            try:
                async with aiohttp.ClientSession() as session:
                    while True:
                        params = {
                            "game_id": "27471",  # Minecraft game ID
                            "first": 100,  # Maximum allowed by API
                        }
                        if cursor:
                            params["after"] = cursor

                        async with session.get(url, headers=headers, params=params) as response:
                            if response.status == 200:
                                data = await response.json()
                                streams = data.get("data", [])

                                # Filter streams with "hypixel" and "skyblock" in title
                                hypixel_streams = [
                                    stream for stream in streams
                                    if "hypixel" in stream["title"].lower() and
                                       any(term in stream["title"].lower() for term in
                                           ["skyblock", "sky block", "sky-block"])
                                ]

                                # Check for new streams
                                for stream in hypixel_streams:
                                    stream_id = stream["id"]
                                    if stream_id not in seen_streams:
                                        new_streams.append(stream)
                                        seen_streams.add(stream_id)

                                # Get cursor for next page
                                cursor = data.get("pagination", {}).get("cursor")
                                if not cursor:
                                    break
                            else:
                                print(f"Failed to get streams. Status: {response.status}")
                                break

                # Display new streams
                if new_streams:
                    print(f"\nFound {len(new_streams)} new Hypixel SkyBlock streams:")
                    print("-" * 30)
                    for stream in new_streams:
                        print(f"{stream['user_name']} ({stream['viewer_count']:,} viewers)")
                        print(f"Title: {stream['title']}")
                        print("-" * 30)
                else:
                    print("No new streams found")

                # Wait 2 minutes before next check
                await asyncio.sleep(120)

            except Exception as e:
                print(f"Error checking streams: {e}")
                await asyncio.sleep(120)  # Wait 2 minutes before retrying

    except KeyboardInterrupt:
        print("\nStopping stream monitor...")


async def main():
    """Main function to run the stream monitor."""
    await monitor_new_streams()


if __name__ == "__main__":
    asyncio.run(main())
