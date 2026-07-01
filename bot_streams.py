# bot_streams.py
# Live Hypixel-SkyBlock stream discovery + auto join/leave monitoring.
# Mixed into Bot via MRO.
import asyncio
import os
import traceback
from datetime import datetime
from typing import Any, Callable

import aiohttp


def retry_on_network_error(retries: int = 3, delay: int = 5):
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs) -> Any | None:
            last_exception = None
            for attempt in range(retries):
                try:
                    return await func(*args, **kwargs)
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    last_exception = e
                    print(f"[WARN][Retry] Network error in '{func.__name__}' (Attempt {attempt + 1}/{retries}): {e}")
                    await asyncio.sleep(delay * (attempt + 1))
            print(f"[ERROR][Retry] Function '{func.__name__}' failed permanently after {retries} attempts.")
            if last_exception:
                traceback.print_exception(type(last_exception), last_exception, last_exception.__traceback__)
            return None
        return wrapper
    return decorator


class StreamMonitorMixin:
    """Twitch Helix stream discovery + the background join/leave monitor."""

    # --- Helper Methods (for Stream Monitoring) ---
    @retry_on_network_error(retries=3, delay=5)
    async def fetch_live_hypixel_streamers(self) -> list[str] | None:
        """Fetches live Minecraft streams, filters for Hypixel SkyBlock, and returns a list of usernames."""
        client_id = os.getenv("TWITCH_CLIENT_ID")
        client_secret = os.getenv("TWITCH_CLIENT_SECRET")

        if not client_id or not client_secret:
            print("[ERROR][StreamFetch] TWITCH_CLIENT_ID or TWITCH_CLIENT_SECRET not found.")
            return None

        access_token = await self.get_twitch_access_token(client_id, client_secret)
        if not access_token:
            print("[ERROR][StreamFetch] Failed to get access token.")
            return None

        live_streamer_usernames = []
        url = "https://api.twitch.tv/helix/streams"
        headers = {"Client-ID": client_id, "Authorization": f"Bearer {access_token}"}
        cursor = None

        try:
            async with aiohttp.ClientSession() as session:
                while True:
                    params = {"game_id": "27471", "first": 100} # Minecraft game ID
                    if cursor:
                        params["after"] = cursor

                    async with session.get(url, headers=headers, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            streams = data.get("data", [])

                            for stream in streams:
                                title_lower = stream.get("title", "").lower()
                                if "hypixel" in title_lower and any(term in title_lower for term in ["skyblock", "sky block", "sky-block"]):
                                    login_name = stream.get("user_login")
                                    if login_name:
                                        live_streamer_usernames.append(login_name)

                            cursor = data.get("pagination", {}).get("cursor")
                            if not cursor:
                                break # No more pages
                        elif response.status == 401: # Unauthorized - Token might have expired
                            print("[WARN][StreamFetch] Received 401 Unauthorized. Attempting to refresh token.")
                            access_token = await self.get_twitch_access_token(client_id, client_secret) # Try refreshing
                            if not access_token:
                                print("[ERROR][StreamFetch] Failed to refresh access token after 401.")
                                return None # Give up if refresh fails
                            headers["Authorization"] = f"Bearer {access_token}" # Update header
                            # Loop will continue with the new token
                        else:
                            print(f"[ERROR][StreamFetch] Failed to get streams page. Status: {response.status}, Response: {await response.text()}")
                            # Don't return None here, maybe some pages worked. Return what we have.
                            break # Stop pagination on error

            # Use a set to remove duplicates before returning
            return list(set(live_streamer_usernames))

        except Exception as e:
            print(f"[ERROR][StreamFetch] Unexpected error fetching streams: {e}")
            traceback.print_exc()
            return None # Return None on unexpected errors

    async def monitor_hypixel_streams(self):
        """Continuously monitors for Hypixel SkyBlock streams, joins new ones and leaves irrelevant ones after 15 minutes."""
        print("[INFO][Monitor] Background stream monitor starting...")
        self.write_debug_log("MONITOR_STARTED: Background stream monitoring began")

        # Dictionary to track channels that might need to be left, with timestamps
        channels_pending_leave = {}  # format: {channel_name: timestamp_when_marked}

        while True:
            try:
                live_streamer_names = await self.fetch_live_hypixel_streamers()
                current_time = datetime.now()

                if live_streamer_names is None:
                    print("[WARN][Monitor] Failed to fetch live streamers. Will retry later.")
                else:
                    # Get current connected channels (excluding None values)
                    currently_connected_channels = [ch for ch in self.connected_channels if ch is not None]
                    currently_connected_names = {ch.name for ch in currently_connected_channels}
                    live_streamer_names_set = set(live_streamer_names)

                    # Find channels that need to be joined (new live channels)
                    streamers_to_join = [name for name in live_streamer_names if name not in currently_connected_names]

                    # Find channels that might need to be left
                    initial_env_channels_set = set(self._initial_env_channels)

                    # Process currently connected channels
                    for channel in currently_connected_channels:
                        channel_name = channel.name

                        # Skip initial channels as these should never be left
                        if channel_name.lower() in initial_env_channels_set:
                            continue

                        # Check if channel is still live and relevant
                        if channel_name not in live_streamer_names_set:
                            # If not in live list, mark for potential leaving
                            if channel_name not in channels_pending_leave:
                                channels_pending_leave[channel_name] = current_time
                                self.write_debug_log(f"MARKED_FOR_LEAVE: #{channel_name} (15min timeout started)")
                        else:
                            # Channel is live again, remove from pending leave list if present
                            if channel_name in channels_pending_leave:
                                del channels_pending_leave[channel_name]
                                self.write_debug_log(f"UNMARKED_FOR_LEAVE: #{channel_name} (channel is live again)")

                    # Process channels that have been pending leave for 15+ minutes
                    channels_to_leave = []
                    channels_to_remove_from_pending = []

                    for channel_name, marked_time in channels_pending_leave.items():
                        # Calculate how long the channel has been pending leave
                        time_offline = (current_time - marked_time).total_seconds() / 60  # in minutes

                        # Check if channel has been offline/irrelevant for 15+ minutes
                        if time_offline >= 15:
                            # Only add to leave list if still connected
                            if channel_name in currently_connected_names:
                                channels_to_leave.append(channel_name)
                            # Mark for removal from pending dictionary regardless
                            channels_to_remove_from_pending.append(channel_name)

                    # Clean up pending list
                    for channel_name in channels_to_remove_from_pending:
                        channels_pending_leave.pop(channel_name, None)

                    # Handle leaving channels
                    if channels_to_leave:
                        print(
                            f"[INFO][Monitor] Leaving {len(channels_to_leave)} channels (15+ min timeout): {channels_to_leave}")
                        self.write_debug_log(
                            f"LEAVING_CHANNELS: {', '.join([f'#{ch}' for ch in channels_to_leave])} (15min timeout)")

                        try:
                            await self.part_channels(channels_to_leave)
                        except Exception as leave_error:
                            print(f"[ERROR][Monitor] Error leaving channels: {leave_error}")
                            self.write_debug_log(f"LEAVE_ERROR: {channels_to_leave} - {str(leave_error)}")

                    if streamers_to_join:
                        print(
                            f"[INFO][Monitor] Joining {len(streamers_to_join)} new live channels: {streamers_to_join}")
                        try:
                            await self.safe_join_channels(streamers_to_join)  # Use safe join method
                            await asyncio.sleep(3)  # Brief delay for channels to connect
                        except Exception as join_error:
                            print(f"[ERROR][Monitor] Error joining channels: {join_error}")

                    # Periodic status report (only if changes occurred)
                    if channels_to_leave or streamers_to_join or len(channels_pending_leave) > 0:
                        currently_connected = [ch.name for ch in self.connected_channels if ch is not None]

                        # Format pending leave channels with their timestamps
                        pending_channels_info = ""
                        if channels_pending_leave:
                            # Group channels by their marked time
                            time_to_channels = {}
                            for ch_name, mark_time in channels_pending_leave.items():
                                time_str = mark_time.strftime("%H:%M:%S")
                                if time_str not in time_to_channels:
                                    time_to_channels[time_str] = []
                                time_to_channels[time_str].append(ch_name)

                            # Format the grouped channels
                            grouped_entries = []
                            for time_str, channel_list in time_to_channels.items():
                                channels_str = ", ".join(channel_list)
                                grouped_entries.append(f"{channels_str} ({time_str})")

                            pending_channels_info = " | Pending: " + " | ".join(grouped_entries)

                        # Add blacklist info to status
                        blacklist_info = ""
                        if self.blacklisted_channels:
                            blacklist_info = f" | Blacklisted: {len(self.blacklisted_channels), self.blacklisted_channels}"

                        print(f"[STATUS][Monitor] Connected: {len(currently_connected)}{pending_channels_info}{blacklist_info}")

                # Wait before next check
                await asyncio.sleep(120)

            except Exception as e:
                print(f"[ERROR][Monitor] Unexpected error: {e}")
                self.write_debug_log(f"MONITOR_ERROR: {str(e)}")
                await asyncio.sleep(300)  # 5 minute retry delay after errors

    @retry_on_network_error(retries=3, delay=5)
    async def get_twitch_access_token(self, client_id: str, client_secret: str) -> str | None:
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
                        token = data.get("access_token")
                        if token:
                            return token
                        else:
                            print("[ERROR] Got 200 OK but no access token in response.")
                            return None
                    else:
                        print(
                            f"[ERROR] Failed to get access token. Status: {response.status}, Response: {await response.text()}")
                        return None
        except Exception as e:
            print(f"[ERROR] Error getting access token: {e}")
            traceback.print_exc()
            return None

    async def safe_join_channels(self, channels: list[str]):
        """Safely join channels with retry logic, filtering out blacklisted channels."""
        if not channels:
            return

        # Filter out blacklisted channels
        channels_to_join = [ch for ch in channels if ch.lower() not in self.blacklisted_channels]

        if not channels_to_join:
            if len(channels) > len(channels_to_join):
                print(f"[INFO] Skipped {len(channels) - len(channels_to_join)} blacklisted channels, {channels}")
            return

        if len(channels) > len(channels_to_join):
            blacklisted_count = len(channels) - len(channels_to_join)
            print(
                f"[INFO] Filtered out {blacklisted_count} blacklisted channels, attempting to join {len(channels_to_join)} channels")

        # Log join attempt
        self.write_debug_log(f"ATTEMPTING_JOIN: {', '.join([f'#{ch}' for ch in channels_to_join])}")

        try:
            await self.join_channels(channels_to_join)
        except Exception as e:
            print(f"[ERROR] Error in bulk join for channels {channels_to_join}: {e}")
            self.write_debug_log(f"BULK_JOIN_ERROR: {channels_to_join} - {str(e)}")

            # Try individual joins as fallback
            for channel in channels_to_join:
                try:
                    await self.join_channels([channel])
                    await asyncio.sleep(1)  # Brief delay between individual attempts
                except Exception as individual_error:
                    print(f"[ERROR] Failed individual join for {channel}: {individual_error}")
                    # Individual failures are already logged by event_channel_join_failure
