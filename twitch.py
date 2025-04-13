# twitch.py
import asyncio
import json
import logging
import traceback
from datetime import datetime
import math
import re
from typing import TypeAlias
import os
import aiohttp
from twitchio.ext import commands
from uvicorn.config import LOGGING_CONFIG

from profiletyping import Profile

import constants
import utils
from utils import _find_latest_profile, _get_uuid_from_ign, _get_skyblock_data, _parse_command_args
from commands.kuudra import KuudraCommand
from commands.classaverage import ClassAverageCommand
from commands.mayor import MayorCommand
from commands.bank import BankCommand
from commands.nucleus import NucleusCommand
from commands.hotm import HotmCommand
from commands.essence import EssenceCommand
from commands.powder import PowderCommand
from commands.slayer import SlayerCommand
from commands.help import HelpCommand
from commands.rtca import RtcaCommand
from commands.currdungeon import CurrDungeonCommand
from commands.runstillcata import RunsTillCataCommand
from commands_cog import CommandsCog


def _select_profile(profiles: list[Profile], player_uuid: str, requested_profile_name: str | None) -> Profile | None:
    """Selects a profile from a list based on requested cute_name or falls back to the latest."""

    # Try to find by cute_name if requested
    if requested_profile_name:
        requested_name_lower = requested_profile_name.lower()
        for profile in profiles: # Iterate directly over the list
            cute_name = profile.get('cute_name')
            if cute_name and cute_name.lower() == requested_name_lower:
                # Check if player is actually a member of this profile
                if player_uuid in profile.get('members', {}):
                    print(f"[DEBUG][ProfileSelect] Found matching profile by cute_name: '{cute_name}'")
                    return profile # Return the matched profile
                else:
                    # This case should be rare if the API returns profiles correctly
                    print(f"[WARN][ProfileSelect] Found profile '{cute_name}' matching request, but player UUID {player_uuid} is not a member.")
                    # Continue searching or fallback?
                    # Fallback seems safer, the player might have misspelled or the profile structure is odd.
                    pass # Let it fall back to latest profile logic

        # If loop finishes without finding a match by name
        print(f"[WARN][ProfileSelect] Requested profile name '{requested_profile_name}' not found or player not member. Falling back to latest profile.")
        # Fallthrough to latest profile logic below

    # Fallback: Find the latest profile (original logic)
    # Assuming _find_latest_profile also expects a list of profiles
    latest_profile = _find_latest_profile(profiles, player_uuid)
    if latest_profile:
        print(f"[DEBUG][ProfileSelect] Using latest profile: '{latest_profile.get('cute_name', 'Unknown')}'")
    else:
        print("[DEBUG][ProfileSelect] Could not find any latest profile.")
    return latest_profile


class Bot(commands.Bot):
    """
    Twitch Bot for interacting with Hypixel SkyBlock API and providing commands.
    """
    def __init__(self, token: str, prefix: str, nickname: str, initial_channels: list[str], hypixel_api_key: str | None = None):
        """Initializes the Bot."""
        self.start_time = datetime.now()
        self.hypixel_api_key = hypixel_api_key
        self.leveling_data = utils._load_leveling_data()
        self.constants = constants
        self._kuudra_command = KuudraCommand(self)
        self._classaverage_command = ClassAverageCommand(self)
        self._mayor_command = MayorCommand(self)
        self._bank_command = BankCommand(self)
        self._nucleus_command = NucleusCommand(self)
        self._hotm_command = HotmCommand(self)
        self._essence_command = EssenceCommand(self)
        self._powder_command = PowderCommand(self)
        self._slayer_command = SlayerCommand(self)
        self._help_command = HelpCommand(self)
        self._rtca_command = RtcaCommand(self)
        self._currdungeon_command = CurrDungeonCommand(self)
        self._runstillcata_command = RunsTillCataCommand(self)

        # Store initial channels from .env to avoid leaving them
        self._initial_env_channels = [ch.lower() for ch in initial_channels]

        # Initialize bot with only channels from .env first
        super().__init__(token=token, prefix=prefix, nick=nickname, initial_channels=initial_channels)
        print(f"[INFO] Bot initialized, attempting to join initial channels: {initial_channels}")

        # Register Cogs
        self.add_cog(CommandsCog(self))

    # --- Helper Methods ---

    async def _get_player_profile_data(self, ctx: commands.Context, ign: str | None, requested_profile_name: str | None = None) -> tuple[str, str, Profile] | None:
        """
        Handles the common boilerplate for commands needing player profile data.
        Checks API key, gets UUID, fetches profiles, selects the requested or latest profile.
        Sends error messages to chat if steps fail.
        Returns (target_ign, player_uuid, selected_profile_data) or None if an error occurred.
        """
        if not self.hypixel_api_key:
            # Use direct ctx.send for initial API key check as _send_message might fail early
            await ctx.send("Hypixel API is not configured. Please check the .env file.")
            return None

        target_ign = ign if ign.rstrip() != "" else ctx.author.name
        target_ign = target_ign.lstrip('@')
        # Use direct ctx.send for initial feedback message
        #await ctx.send(f"Searching data for '{target_ign}'...")

        player_uuid = await _get_uuid_from_ign(target_ign)
        if not player_uuid:
            # Use _send_message for this potentially delayed error message
            await self._send_message(ctx, f"Could not find Minecraft account for '{target_ign}'. Please check the username.")
            return None

        profiles = await _get_skyblock_data(self.hypixel_api_key, player_uuid)
        if profiles is None: # API error occurred
            # Use _send_message for this potentially delayed error message
            await self._send_message(ctx, f"Could not fetch SkyBlock profiles for '{target_ign}'. An API error occurred.")
            return None
        if not profiles: # API succeeded but returned no profiles
            # Use _send_message for this potentially delayed error message
            await self._send_message(ctx, f"'{target_ign}' seems to have no SkyBlock profiles yet.")
            return None

        # Select the profile using the new helper function
        selected_profile = _select_profile(profiles, player_uuid, requested_profile_name)

        if not selected_profile:
            # If _select_profile returned None (e.g., no latest found after fallback)
            profile_msg = f"the requested profile '{requested_profile_name}' or" if requested_profile_name else "an active"
            await self._send_message(ctx, f"Could not find {profile_msg} profile for '{target_ign}'. Player must be a member of at least one profile.")
            return None

        return target_ign, player_uuid, selected_profile

    # --- Bot Events ---

    async def event_ready(self):
        """Called once the bot has successfully connected to Twitch and joined initial channels."""
        try:
            print("[INFO] Bot starting up... Initial connection established.")

            print(f'------')
            print(f'Logged in as: {self.nick} ({self.user_id})')
            # Filter out None before accessing name
            initial_connected_channels = [ch.name for ch in self.connected_channels if ch is not None]
            print(f'Successfully joined initial channels from .env: {initial_connected_channels}')
            print(f'------')

            # --- Fetch and Join Live Hypixel Streamers ---
            print("[INFO] Performing initial scan for live Hypixel SkyBlock streamers...")
            live_streamer_names = await self._fetch_live_hypixel_streamers()

            if live_streamer_names is None:
                print("[WARN] Could not fetch live streamers during startup (API/Token issue?). Monitoring will still run.")
            else:
                print(f"[INFO] Found {len(live_streamer_names)} potential live Hypixel SkyBlock streamers.")
                # Determine which channels to join (those not already connected to)
                # Filter out None before accessing name
                # Use the potentially updated list of connected channels after the retry
                currently_connected = {ch.name.lower() for ch in self.connected_channels if ch is not None} # Use lowercase set
                streamers_to_join = [name for name in live_streamer_names if name.lower() not in currently_connected]
                # No need for streamers_to_join_lower now as we compare lowercase directly

                if streamers_to_join:
                    print(f"[INFO] Attempting to join {len(streamers_to_join)} newly found live channels: {streamers_to_join}")
                    try:
                        await self.join_channels(streamers_to_join) # Join using original case names from Twitch API
                        print("[INFO] Join command sent for live channels. Waiting briefly for channel list update...")
                        await asyncio.sleep(5) # Give TwitchIO time to process joins and update self.connected_channels
                    except Exception as join_error:
                        print(f"[ERROR] Error trying to join channels: {join_error}")
                else:
                    print("[INFO] All found live streamers are already in the connected channel list.")
            # --- End Fetch and Join ---

            # --- Final Output ---
            # Filter out None before accessing name
            final_connected_channels = [ch.name for ch in self.connected_channels if ch is not None]
            print(f'[INFO] Final connected channels list ({len(final_connected_channels)} total): {final_connected_channels}')

            if final_connected_channels:
                print(f"[INFO] Bot setup complete. Monitoring active streams.")
                print(f"[INFO] Bot is ready!")
            else:
                print("[WARN] Bot connected to Twitch but is not in any channels.")

            # --- Start Background Monitoring ---
            print("[INFO] Starting background stream monitor task...")
            asyncio.create_task(self._monitor_streams())

        except Exception as e:
            print(f"[ERROR] Error during event_ready: {e}")
            traceback.print_exc()

    async def event_message(self, message):
        """Processes incoming Twitch chat messages."""
        if message.echo:
            return  # Ignore messages sent by the bot itself

        if not hasattr(message.channel, 'name') or not hasattr(message.author, 'name') or not message.author.name:
            return # Ignore system messages or messages without proper author/channel context

        connected_channel_names = {ch.name for ch in self.connected_channels if ch is not None}
        if message.channel.name not in connected_channel_names:
            return

        await self.handle_commands(message)

    async def _send_message(self, ctx: commands.Context, message: str):
        """Helper function to send messages, incorporating workarounds for potential issues."""
        # Truncate message for logging if it's too long
        log_message = message[:450] + '...' if len(message) > 450 else message
        print(f"[DEBUG][Send] Attempting to send to #{ctx.channel.name}: {log_message}") 
        try:
            await asyncio.sleep(0.3) 

            channel_name = ctx.channel.name
            channel = self.get_channel(channel_name)
            if channel:
                print(f"[DEBUG][Send] Re-fetched channel object for {channel_name}. Sending via channel object.")
                await channel.send(message)
                print(f"[DEBUG][Send] Successfully sent message via channel object to #{channel_name}.")
            else:
                # Fallback if channel couldn't be re-fetched (should not happen if connected)
                print(f"[WARN][Send] Could not re-fetch channel object for {channel_name}. Falling back to ctx.send().")
                await ctx.send(message)
                print(f"[DEBUG][Send] Successfully sent message via ctx.send() to #{channel_name}.")

        except Exception as send_e:
            print(f"[ERROR][Send] FAILED to send message to #{ctx.channel.name}: {send_e}")
            traceback.print_exc()

    # --- Cleanup ---
    async def close(self):
        """Gracefully shuts down the bot and closes sessions."""
        print("[INFO] Shutting down bot...")
        await super().close()
        print("[INFO] Bot connection closed.")

    # --- Helper Methods (for Stream Monitoring) ---

    async def _fetch_live_hypixel_streamers(self) -> list[str] | None:
        """Fetches live Minecraft streams, filters for Hypixel SkyBlock, and returns a list of usernames."""
        client_id = os.getenv("TWITCH_CLIENT_ID")
        client_secret = os.getenv("TWITCH_CLIENT_SECRET")

        if not client_id or not client_secret:
            print("[ERROR][StreamFetch] TWITCH_CLIENT_ID or TWITCH_CLIENT_SECRET not found.")
            return None

        access_token = await self._get_twitch_access_token(client_id, client_secret)
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
                            access_token = await self._get_twitch_access_token(client_id, client_secret) # Try refreshing
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

    async def _monitor_streams(self):
        """Continuously monitors for Hypixel SkyBlock streams, joins new ones and leaves irrelevant ones after 15 minutes."""
        print("[INFO][Monitor] Background stream monitor starting...")

        # Dictionary to track channels that might need to be left, with timestamps
        channels_pending_leave = {}  # format: {channel_name: timestamp_when_marked}

        while True:
            try:
                live_streamer_names = await self._fetch_live_hypixel_streamers()
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

                    # Handle joining new channels
                    if streamers_to_join:
                        print(
                            f"[INFO][Monitor] Joining {len(streamers_to_join)} new live channels: {streamers_to_join}")
                        try:
                            await self.join_channels(streamers_to_join)
                            await asyncio.sleep(3)  # Brief delay for channels to connect
                        except Exception as join_error:
                            print(f"[ERROR][Monitor] Error joining channels in bulk: {join_error}")
                            # Fallback: individual joins
                            for channel_name in streamers_to_join:
                                try:
                                    await self.join_channels([channel_name])
                                except Exception:
                                    pass  # Skip detailed error logging for individual failures

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

                        logging.INFO(f"[STATUS][Monitor] Connected: {len(currently_connected)}{pending_channels_info}")

                # Wait before next check
                await asyncio.sleep(120)

            except Exception as e:
                print(f"[ERROR][Monitor] Unexpected error: {e}")
                await asyncio.sleep(300)  # 5 minute retry delay after errors

    async def _get_twitch_access_token(self, client_id: str, client_secret: str) -> str | None:
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
                             # print("[DEBUG] Successfully obtained/refreshed Twitch access token.")
                             return token
                        else:
                             print("[ERROR] Got 200 OK but no access token in response.")
                             return None
                    else:
                        print(f"[ERROR] Failed to get access token. Status: {response.status}, Response: {await response.text()}")
                        return None
        except Exception as e:
            print(f"[ERROR] Error getting access token: {e}")
            traceback.print_exc()
            return None

IceBot: TypeAlias = Bot
