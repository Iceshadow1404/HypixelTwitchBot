# twitch.py
import asyncio
import traceback
from datetime import datetime
import re
from typing import TypeAlias
import os
import aiohttp
from twitchio.ext import commands
from profiletyping import Profile

import constants
import utils
from skyblock import SkyblockClient
from commands.kuudra import KuudraCommand
from commands.classaverage import ClassAverageCommand
from commands.mayor import MayorCommand
from commands.bank import BankCommand
from commands.nucleus import NucleusCommand
from commands.hotm import HotmCommand
from commands.essence import EssenceCommand
from commands.powder import PowderCommand
from commands.slayer import SlayerCommand
from commands.rtca import RtcaCommand
from commands.currdungeon import CurrDungeonCommand
from commands.runstillcata import RunsTillCataCommand
from commands_cog import CommandsCog
from commands.link import LinkCommand
from commands.networth import NetworthCommand
from commands.guild import GuildCommand
from commands.whatdoing import WhatdoingCommand
from commands.rtcl import RtclCommand


class Bot(commands.Bot):
    # Twitch Bot for interacting with Hypixel SkyBlock API and providing commands.

    def __init__(self, token: str, prefix: str, nickname: str, initial_channels: list[str],
                 hypixel_api_key: str | None = None, local_mode: bool = False):
        # Initializes the Bot.
        self.start_time = datetime.now()
        self.hypixel_api_key = hypixel_api_key
        self.leveling_data = utils._load_leveling_data()
        self.constants = constants
        self.local_mode = local_mode

        # Initialize the SkyblockClient for caching
        self.session = None  # Will be initialized in event_ready
        self.skyblock_client = None  # Will be initialized in event_ready

        self.channel_join_attempts = {}
        self.blacklisted_channels = set()

        self._kuudra_command = KuudraCommand(self)
        self._classaverage_command = ClassAverageCommand(self)
        self._mayor_command = MayorCommand(self)
        self._bank_command = BankCommand(self)
        self._nucleus_command = NucleusCommand(self)
        self._hotm_command = HotmCommand(self)
        self._essence_command = EssenceCommand(self)
        self._powder_command = PowderCommand(self)
        self._slayer_command = SlayerCommand(self)
        self._rtca_command = RtcaCommand(self)
        self._currdungeon_command = CurrDungeonCommand(self)
        self._runstillcata_command = RunsTillCataCommand(self)
        self._link_command = LinkCommand(self)
        self._networth_command = NetworthCommand(self)
        self._guild_command = GuildCommand(self)
        self._whatdoing_command = WhatdoingCommand(self)
        self._rtcl_command = RtclCommand(self)

        # Store initial channels from .env to avoid leaving them
        self._initial_env_channels = [ch.lower() for ch in initial_channels]

        # Initialize bot with only channels from .env first
        super().__init__(token=token, prefix=prefix, nick=nickname, initial_channels=initial_channels)
        print(f"[INFO] Bot initialized, attempting to join initial channels from .env: {initial_channels}")

        # Register Cogs
        self.add_cog(CommandsCog(self))

    # --- Helper Methods ---
    async def event_command_error(self, ctx: commands.Context, error: Exception):
        # Handle command errors with additional channel context information.
        if isinstance(error, commands.CommandNotFound):
            # Extract the command name from the error message
            match = re.search(r'No command "([^"]+)" was found', str(error))
            cmd_name = match.group(1) if match else "unknown"

            # Get channel name safely
            channel_name = ctx.channel.name if hasattr(ctx.channel, 'name') else "unknown_channel"

            # Get username safely
            username = ctx.author.name if hasattr(ctx.author, 'name') else "unknown_user"

            # Log with the channel information
            print(f"[WARN] Command not found: '{cmd_name}' from channel: #{channel_name} by user: {username}")
        else:
            # Log other command errors
            channel_name = ctx.channel.name if hasattr(ctx.channel, 'name') else "unknown_channel"
            print(f"[ERROR] Error in command from channel #{channel_name}: {str(error)}")
            traceback.print_exc()

    async def _get_player_profile_data(self, ctx: commands.Context, ign: str | None,
                                       requested_profile_name: str | None = None, useCache=True) -> tuple[
                                                                                                        str, str, Profile] | None:
        # Handles the common boilerplate for commands needing player profile data.
        # Uses the SkyblockClient with caching for API calls.
        # Returns (target_ign, player_uuid, selected_profile_data) or None if an error occurred.
        if not self.hypixel_api_key:
            # Use direct ctx.send for initial API key check as send_message might fail early
            await ctx.send("Hypixel API is not configured. Please check the .env file.")
            return None

        # Ensure skyblock_client is initialized
        if not self.skyblock_client:
            print("[ERROR] SkyblockClient not initialized. Creating new instance.")
            self.session = aiohttp.ClientSession()
            self.skyblock_client = SkyblockClient(self.hypixel_api_key, self.session)

        # Check if using empty or default IGN
        if not ign or ign.rstrip() == "" or ign == ctx.author.name:
            # Try to get linked IGN first

            linked_ign = self._link_command.get_linked_ign(ctx.author.name)
            if linked_ign:
                target_ign = linked_ign
                print(f"[DEBUG] Using linked IGN '{linked_ign}' for user {ctx.author.name}")
            else:
                target_ign = ctx.author.name
        else:
            target_ign = ign

        target_ign = target_ign.lstrip('@')

        # Use cached client instead of utility functions
        player_uuid = await self.skyblock_client.get_uuid_from_ign(target_ign, ctx.author.name)
        if not player_uuid:
            # Use send_message for this potentially delayed error message
            await self.send_message(ctx,
                                     f"Could not find Minecraft account for '{target_ign}'. Please check the username. You can use #link IGN to link your Twitch account to your Minecraft IGN")
            return None

        # Use cached client instead of utility functions
        profiles = await self.skyblock_client.get_skyblock_data(player_uuid, useCache)
        if profiles is None:  # API error occurred
            # Use send_message for this potentially delayed error message
            await self.send_message(ctx,
                                     f"Could not fetch SkyBlock profiles for '{target_ign}'. An API error occurred.")
            return None
        if not profiles:  # API succeeded but returned no profiles
            # Use send_message for this potentially delayed error message
            await self.send_message(ctx, f"'{target_ign}' seems to have no SkyBlock profiles yet.")
            return None

        # Select the profile using the helper function
        selected_profile = SkyblockClient._select_profile(profiles, player_uuid, requested_profile_name)

        if not selected_profile:
            # If _select_profile returned None (e.g., no latest found after fallback)
            profile_msg = f"the requested profile '{requested_profile_name}' or" if requested_profile_name else "an active"
            await self.send_message(ctx,
                                     f"Could not find {profile_msg} profile for '{target_ign}'. Player must be a member of at least one profile.")
            return None

        return target_ign, player_uuid, selected_profile

    # --- Bot Events ---

    async def event_ready(self):
        # Called once the bot has successfully connected to Twitch and joined initial channels.
        try:
            print("[INFO] Bot starting up... Initial connection established.")

            # Initialize the aiohttp session and SkyblockClient for caching
            self.session = aiohttp.ClientSession()
            self.skyblock_client = SkyblockClient(self.hypixel_api_key, self.session)
            print("[INFO] SkyblockClient initialized with caching.")

            print(f'------')
            print(f'Logged in as: {self.nick} ({self.user_id})')
            # Filter out None before accessing name
            initial_connected_channels = [ch.name for ch in self.connected_channels if ch is not None]
            print(f'Successfully joined initial channels from .env: {initial_connected_channels}')
            print(f'------')

            # --- Fetch and Join Live Hypixel Streamers ONLY IF NOT IN LOCAL MODE ---
            if not self.local_mode:
                print("[INFO] LIVE MODE: Performing initial scan for live Hypixel SkyBlock streamers...")
                live_streamer_names = await self.fetch_live_hypixel_streamers()

                if live_streamer_names is None:
                    print(
                        "[WARN] Could not fetch live streamers during startup (API/Token issue?). Monitoring will still run.")
                else:
                    print(f"[INFO] Found {len(live_streamer_names)} potential live Hypixel SkyBlock streamers.")
                    # Determine which channels to join (those not already connected to)
                    # Filter out None before accessing name
                    # Use the potentially updated list of connected channels after the retry
                    currently_connected = {ch.name.lower() for ch in self.connected_channels if
                                           ch is not None}  # Use lowercase set
                    streamers_to_join = [name for name in live_streamer_names if name.lower() not in currently_connected]
                    # No need for streamers_to_join_lower now as we compare lowercase directly

                    if streamers_to_join:
                        print(
                            f"[INFO] Attempting to join {len(streamers_to_join)} newly found live channels: {streamers_to_join}")
                        try:
                            await self.safe_join_channels(streamers_to_join)
                            print("[INFO] Join command sent for live channels. Waiting briefly for channel list update...")
                            await asyncio.sleep(5)  # Give TwitchIO time to process joins and update self.connected_channels
                        except Exception as join_error:
                            print(f"[ERROR] Error trying to join channels: {join_error}")
                    else:
                        print("[INFO] All found live streamers are already in the connected channel list.")
            else: # <-- Optional: Log-Nachricht für Local Mode
                 print("[INFO] LOCAL MODE: Skipping dynamic joining of live streams on startup.")
            # --- End Fetch and Join ---

            # --- Final Output ---
            # Filter out None before accessing name
            final_connected_channels = [ch.name for ch in self.connected_channels if ch is not None]
            print(
                f'[INFO] Final connected channels list ({len(final_connected_channels)} total): {final_connected_channels}')

            if final_connected_channels:
                print(f"[INFO] Bot setup complete.")
                if not self.local_mode:
                    print(f"[INFO] Monitoring active streams.")
                print(f"[INFO] Bot is ready!")
            else:
                print("[WARN] Bot connected to Twitch but is not in any channels.")

            if not self.local_mode:
                print("[INFO] Starting background stream monitor task...")
                asyncio.create_task(self.monitor_hypixel_streams())

            # --- Start Cache Cleanup Task (läuft immer) ---
            print("[INFO] Starting background cache cleanup task...")
            asyncio.create_task(self.periodic_cache_cleanup())

        except Exception as e:
            print(f"[ERROR] Error during event_ready: {e}")
            traceback.print_exc()

    async def event_message(self, message):
        # Processes incoming Twitch chat messages.
        if message.echo:
            return  # Ignore messages sent by the bot itself

        if not hasattr(message.channel, 'name') or not hasattr(message.author, 'name') or not message.author.name:
            return  # Ignore system messages or messages without proper author/channel context

        connected_channel_names = {ch.name for ch in self.connected_channels if ch is not None}
        if message.channel.name not in connected_channel_names:
            return

        await self.handle_commands(message)

    async def send_message(self, ctx: commands.Context, message: str):
        # Truncate message for logging if it's too long
        log_message = message[:450] + '...' if len(message) > 450 else message
        print(f"[DEBUG][Reply] Attempting to reply in #{ctx.channel.name}: {log_message}")

        try:
            await asyncio.sleep(0.3)

            # Format message to include mention of the original sender
            reply_message = f"@{ctx.author.name}, {message}"

            channel_name = ctx.channel.name
            channel = self.get_channel(channel_name)
            if channel:
                print(f"[DEBUG][Reply] Re-fetched channel object for {channel_name}. Sending reply via channel object.")
                await channel.send(reply_message)
                print(f"[DEBUG][Reply] Successfully sent reply via channel object to #{channel_name}.")
            else:
                # Fallback if channel couldn't be re-fetched (should not happen if connected)
                print(
                    f"[WARN][Reply] Could not re-fetch channel object for {channel_name}. Falling back to ctx.send().")
                await ctx.send(reply_message)
                print(f"[DEBUG][Reply] Successfully sent reply via ctx.send() to #{channel_name}.")

        except Exception as reply_e:
            print(f"[ERROR][Reply] FAILED to send reply to #{ctx.channel.name}: {reply_e}")
            traceback.print_exc()

    async def periodic_cache_cleanup(self):
        # Periodically clears old entries from the cache to prevent memory growth.
        print("[INFO][CacheCleanup] Starting periodic cache cleanup task...")
        cleanup_interval = 3600  # Clean up every hour

        while True:
            try:
                await asyncio.sleep(cleanup_interval)
                if self.skyblock_client and hasattr(self.skyblock_client, 'cache'):

                    stats_before = self.skyblock_client.cache.get_stats()

                    uuid_removed, skyblock_removed = self.skyblock_client.cache.cleanup_expired()

                    stats_after = self.skyblock_client.cache.get_stats()
                    print(
                        f"[INFO][CacheCleanup] Cache cleaned. Before: {stats_before['uuid_cache_size']} UUID entries, "
                        f"{stats_before['skyblock_data_cache_size']} Skyblock data entries. "
                        f"After: {stats_after['uuid_cache_size']} UUID entries (-{uuid_removed}), "
                        f"{stats_after['skyblock_data_cache_size']} Skyblock data entries (-{skyblock_removed})")
                else:
                    print(
                        "[WARN][CacheCleanup] SkyblockClient not initialized or cache not available, skipping cleanup")
            except Exception as e:
                print(f"[ERROR][CacheCleanup] Error during cache cleanup: {e}")
                traceback.print_exc()

    # --- Cleanup ---
    async def close(self):
        # Gracefully shuts down the bot and closes sessions.
        print("[INFO] Shutting down bot...")

        # Close the aiohttp session when shutting down
        if self.session and not self.session.closed:
            await self.session.close()
            print("[INFO] aiohttp session closed.")

        await super().close()
        print("[INFO] Bot connection closed.")

    # --- Helper Methods (for Stream Monitoring) ---

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

        try:
            await self.join_channels(channels_to_join)
        except Exception as e:
            print(f"[ERROR] Error in bulk join for channels {channels_to_join}: {e}")
            # Try individual joins as fallback
            for channel in channels_to_join:
                try:
                    await self.join_channels([channel])
                    await asyncio.sleep(1)  # Brief delay between individual attempts
                except Exception as individual_error:
                    print(f"[ERROR] Failed individual join for {channel}: {individual_error}")

    async def event_channel_join_failure(self, channel: str):
        """Handle channel join failures with retry logic."""
        channel_lower = channel.lower()

        # Increment attempt counter
        if channel_lower not in self.channel_join_attempts:
            self.channel_join_attempts[channel_lower] = 0

        self.channel_join_attempts[channel_lower] += 1
        current_attempts = self.channel_join_attempts[channel_lower]

        print(f'[WARN] Failed to join channel "{channel}" (attempt {current_attempts}/5)')

        if current_attempts >= 5:
            # Add to blacklist after 5 failed attempts
            self.blacklisted_channels.add(channel_lower)
            print(
                f'[ERROR] Channel "{channel}" blacklisted after {current_attempts} failed attempts. Will ignore until bot restart.')

            # Clean up the attempts counter since we're blacklisting
            del self.channel_join_attempts[channel_lower]
        else:
            # Schedule a retry after a brief delay
            remaining_attempts = 5 - current_attempts
            print(f'[INFO] Will retry joining "{channel}" later ({remaining_attempts} attempts remaining)')

    async def monitor_hypixel_streams(self):
        """Continuously monitors for Hypixel SkyBlock streams, joins new ones and leaves irrelevant ones after 15 minutes."""
        print("[INFO][Monitor] Background stream monitor starting...")

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
                        else:
                            # Channel is live again, remove from pending leave list if present
                            if channel_name in channels_pending_leave:
                                del channels_pending_leave[channel_name]

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
                        try:
                            await self.part_channels(channels_to_leave)
                        except Exception as leave_error:
                            print(f"[ERROR][Monitor] Error leaving channels: {leave_error}")

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
                await asyncio.sleep(300)  # 5 minute retry delay after errors

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

IceBot: TypeAlias = Bot
