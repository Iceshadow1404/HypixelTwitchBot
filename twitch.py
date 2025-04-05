# twitch.py
import asyncio
import json
import traceback
from datetime import datetime
import math
import re
from typing import TypeAlias
import os
import aiohttp
from twitchio.ext import commands
from profiletyping import Profile

import constants
import utils
from calculations import _get_xp_for_target_level, calculate_hotm_level, \
    calculate_average_skill_level, calculate_dungeon_level, calculate_class_level, calculate_slayer_level, format_price
from utils import _find_latest_profile, _get_uuid_from_ign, _get_skyblock_data, _parse_command_args

from commands.kuudra import KuudraCommand
from commands.auction_house import process_auctions_command
from commands.cata import process_dungeon_command
from commands.sblvl import process_sblvl_command
from commands.currdungeon import process_currdungeon_command
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
from commands.overflow_skills import process_overflow_skill_command
from commands.skills import process_skills_command


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
        self._initial_env_channels = initial_channels 

        # Initialize bot with only channels from .env first
        super().__init__(token=token, prefix=prefix, nick=nickname, initial_channels=initial_channels)
        print(f"[INFO] Bot initialized, attempting to join initial channels: {initial_channels}")
        # Streamer monitoring will be started in event_ready after joining initial channels

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
                currently_connected = {ch.name for ch in self.connected_channels if ch is not None} # Use a set for efficient lookup
                streamers_to_join = [name for name in live_streamer_names if name not in currently_connected]

                if streamers_to_join:
                    print(f"[INFO] Attempting to join {len(streamers_to_join)} newly found live channels: {streamers_to_join}")
                    try:
                        await self.join_channels(streamers_to_join)
                        print("[INFO] Join command sent. Waiting briefly for channel list update...")
                        await asyncio.sleep(5) # Give TwitchIO time to process joins and update self.connected_channels
                    except Exception as join_error:
                        print(f"[ERROR] Error trying to join channels {streamers_to_join}: {join_error}")
                else:
                    print("[INFO] All found live streamers are already in the connected channel list.")
            # --- End Fetch and Join ---

            # --- Final Output ---
            # Filter out None before accessing name
            final_connected_channels = [ch.name for ch in self.connected_channels if ch is not None]
            print(f'------')
            print(f'Final connected channels list ({len(final_connected_channels)} total): {final_connected_channels}')
            print(f'------')

            if final_connected_channels:
                print(f"[INFO] Bot setup complete. Monitoring active streams.")
                print("Bot is ready!")
            else:
                print("[WARN] Bot connected to Twitch but is not in any channels.")

            # --- Start Background Monitoring ---
            print("[INFO] Starting background stream monitor task...")
            asyncio.create_task(self._monitor_streams())
            # -----------------------------------

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

    # --- Commands ---

    @commands.command(name='skills')
    async def skills_command(self, ctx: commands.Context, *, args: str | None = None):
        parsed_args = await _parse_command_args(self, ctx, args, 'skills')
        if parsed_args is None:
            return
        ign, requested_profile_name = parsed_args
        await process_skills_command(ctx, ign, requested_profile_name=requested_profile_name)

    @commands.command(name='kuudra')
    async def kuudra_command(self, ctx: commands.Context, *, args: str | None = None):
        await self._kuudra_command.kuudra_command(ctx, args=args)

    @commands.command(name='oskill', aliases=['skillo', 'oskills', 'skillso', 'overflow'])
    async def overflow_skill_command(self, ctx: commands.Context, *, args: str | None = None):
        parsed_args = await _parse_command_args(self, ctx, args, 'oskill')
        if parsed_args is None:
            return
        ign, requested_profile_name = parsed_args
        await process_overflow_skill_command(ctx, ign, requested_profile_name=requested_profile_name)

    @commands.command(name='auctions', aliases=['ah'])
    async def auctions_command(self, ctx: commands.Context, *, ign: str | None = None):
        await process_auctions_command(ctx, ign)

    @commands.command(name='dungeon', aliases=['dungeons', 'cata'])
    async def dungeon_command(self, ctx: commands.Context, *, args: str | None = None):
        parsed_args = await _parse_command_args(self, ctx, args, 'dungeon')
        if parsed_args is None:
            return
        ign, requested_profile_name = parsed_args
        await process_dungeon_command(ctx, ign, requested_profile_name=requested_profile_name)

    @commands.command(name='sblvl')
    async def sblvl_command(self, ctx: commands.Context, *, args: str | None = None):
        parsed_args = await _parse_command_args(self, ctx, args, 'sblvl')
        if parsed_args is None:
            return
        ign, requested_profile_name = parsed_args
        await process_sblvl_command(ctx, ign, requested_profile_name=requested_profile_name)

    @commands.command(name='classaverage', aliases=['ca'])
    async def classaverage_command(self, ctx: commands.Context, *, args: str | None = None):
        await self._classaverage_command.classaverage_command(ctx, args=args)

    @commands.command(name='mayor')
    async def mayor_command(self, ctx: commands.Context):
        await self._mayor_command.mayor_command(ctx)

    @commands.command(name='bank', aliases=['purse', 'money'])
    async def bank_command(self, ctx: commands.Context, *, args: str | None = None):
        await self._bank_command.bank_command(ctx, args=args)

    @commands.command(name='nucleus')
    async def nucleus_command(self, ctx: commands.Context, *, args: str | None = None):
        await self._nucleus_command.nucleus_command(ctx, args=args)

    @commands.command(name='hotm')
    async def hotm_command(self, ctx: commands.Context, *, args: str | None = None):
        await self._hotm_command.hotm_command(ctx, args=args)

    @commands.command(name='essence')
    async def essence_command(self, ctx: commands.Context, *, args: str | None = None):
        await self._essence_command.essence_command(ctx, args=args)

    @commands.command(name='powder')
    async def powder_command(self, ctx: commands.Context, *, args: str | None = None):
        await self._powder_command.powder_command(ctx, args=args)

    @commands.command(name='slayer')
    async def slayer_command(self, ctx: commands.Context, *, args: str | None = None):
        await self._slayer_command.slayer_command(ctx, args=args)

    @commands.command(name='networth', aliases=["nw"])
    async def networth_command(self, ctx: commands.Context, *, ign: str | None = None):
        await self._send_message(ctx, "Networth calculation is not supported. Please use mods like NEU or SkyHelper for accurate networth calculations.")

    @commands.command(name='dexter')
    async def dexter_command(self, ctx: commands.Context):
        await self._send_message(ctx, "YEP skill issue confirmed!")
    dexter_command.hidden = True

    @commands.command(name='dongo')
    async def dexter_command(self, ctx: commands.Context):
        await self._send_message(ctx, "🥚")
    dexter_command.hidden = True

    @commands.command(name='help')
    async def help_command(self, ctx: commands.Context):
        await self._help_command.help_command(ctx)

    @commands.command(name='rtca')
    async def rtca_command(self, ctx: commands.Context, *, args: str | None = None):
        await self._rtca_command.rtca_command(ctx, args=args)

    @commands.command(name='currdungeon')
    async def currdungeon_command(self, ctx: commands.Context, *, args: str | None = None):
        parsed_args = await _parse_command_args(self, ctx, args, 'currdungeon')
        if parsed_args is None:
            return
        ign, requested_profile_name = parsed_args
        await process_currdungeon_command(ctx, ign, requested_profile_name=requested_profile_name)

    @commands.command(name='runstillcata')
    async def runstillcata_command(self, ctx: commands.Context, *, args: str | None = None):
        print(f"[COMMAND] RunsTillCata command triggered by {ctx.author.name}: {args}")

        # --- 1. Argument Parsing ---
        parsed_args = await _parse_command_args(self, ctx, args, 'runstillcata')
        if parsed_args is None: # Parsing failed
            return
        ign, requested_profile_name = parsed_args
        target_level_str: str | None = None
        floor_str: str = 'm7'   # Default floor

        if not args:
            ign = ctx.author.name # Default to message author if no args provided
            print(f"[DEBUG][RunsTillCataCmd] No arguments provided, defaulting IGN to: {ign}")
        else:
            parts = args.split()
            ign = parts[0] # First part is always IGN
            remaining_parts = parts[1:]

            potential_profile_name = None
            potential_target_level = None
            potential_floor = None
            unidentified_parts = []

            for part in remaining_parts:
                part_lower = part.lower()
                if part_lower in ['m6', 'm7'] and potential_floor is None:
                    potential_floor = part_lower
                elif part.isdigit() and potential_target_level is None:
                    potential_target_level = part
                else:
                    if potential_profile_name is None:
                        potential_profile_name = part
                    else:
                        unidentified_parts.append(part)
            
            requested_profile_name = potential_profile_name
            if potential_target_level is not None:
                target_level_str = potential_target_level
            if potential_floor is not None:
                floor_str = potential_floor

            if unidentified_parts:
                usage_message = f"Too many or ambiguous arguments: {unidentified_parts}. Usage: {self._prefix}runstillcata <username> [profile_name] [target_level] [floor=m7]"
                await self._send_message(ctx, usage_message)
                return

        # --- Argument Validation ---
        try:
            # Validate floor
            if floor_str not in ['m6', 'm7']:
                raise ValueError("Invalid floor. Please specify 'm6' or 'm7'.")
            print(f"[DEBUG][RunsTillCataCmd] Validated floor_str: {floor_str}")

            # Validate target level if provided
            target_level = None
            if target_level_str:
                target_level = int(target_level_str)
                if not 1 <= target_level <= 99:
                    raise ValueError("Target level must be between 1 and 99.")
                print(f"[DEBUG][RunsTillCataCmd] Validated target_level: {target_level}")

        except ValueError as e:
            await self._send_message(ctx, f"Invalid argument: {e}. Usage: {self._prefix}runstillcata <username> [profile_name] [target_level] [floor=m7]")
            return
        # --- End Argument Parsing & Validation ---

        # --- 2. Get Player Data ---
        profile_data = await self._get_player_profile_data(ctx, ign, requested_profile_name=requested_profile_name)
        if not profile_data:
            return # Error message already sent by helper

        target_ign, player_uuid, selected_profile = profile_data
        profile_name = selected_profile.get('cute_name', 'Unknown')

        try:
            # --- 3. Get Current Catacombs XP and Level ---
            member_data = selected_profile.get('members', {}).get(player_uuid, {})
            dungeons_data = member_data.get('dungeons', {}).get('dungeon_types', {}).get('catacombs', {})
            current_xp = dungeons_data.get('experience', 0)
            current_level = calculate_dungeon_level(self.leveling_data, current_xp)
            
            # --- 4. Calculate XP for Target Level ---
            if target_level is None:
                # If no target level provided, use next integer level
                target_level = math.ceil(current_level) 
                if target_level == math.floor(current_level): # If current level is integer, aim for next one
                    target_level += 1
            xp_for_target_level = _get_xp_for_target_level(self.leveling_data, target_level)
            xp_needed = xp_for_target_level - current_xp

            if xp_needed <= 0:
                await self._send_message(ctx, f"{target_ign} has already reached Catacombs level {target_level}!")
                return

            # --- 5. Calculate Runs Needed for Selected Floor ---
            if floor_str == 'm6':
                xp_per_run = 180000 # 180k XP per M6 run
                floor_name = "M6"
            else:  # m7
                xp_per_run = 500000 # 500k XP per M7 run
                floor_name = "M7"
            
            if xp_per_run <= 0:
                 await self._send_message(ctx, "Invalid XP per run configured.")
                 return

            runs_needed = math.ceil(xp_needed / xp_per_run)

            # --- 6. Format and Send Output ---
            output_message = (
                f"{target_ign} (Cata {current_level:.2f}) needs {xp_needed:,.0f} XP for level {target_level}. "
                f"{floor_name}: {runs_needed:,} runs ({xp_per_run:,} XP/run)"
            )
            await self._send_message(ctx, output_message)

        except Exception as e:
            print(f"[ERROR][RunsTillCataCmd] Unexpected error: {e}")
            traceback.print_exc()
            await self._send_message(ctx, f"An unexpected error occurred while calculating runs needed for '{target_ign}'.")

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
                                    username = stream.get("user_name", "").lower()
                                    if username:
                                        live_streamer_usernames.append(username)

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
        """Continuously monitors for new Hypixel SkyBlock streams and joins them."""
        print("[INFO][Monitor] Background stream monitor starting loop.")
        
        while True:
            try:
                print("[INFO][Monitor] Checking for live streams...")
                live_streamer_names = await self._fetch_live_hypixel_streamers()

                if live_streamer_names is None:
                    print("[WARN][Monitor] Failed to fetch live streamers in monitoring loop. Will retry later.")
                else:
                    # Filter out None values before accessing name
                    currently_connected = {ch.name for ch in self.connected_channels if ch is not None}
                    streamers_to_join = [name for name in live_streamer_names if name not in currently_connected]

                    if streamers_to_join:
                        print(f"[INFO][Monitor] Found new live channels to join: {streamers_to_join}")
                        try:
                            # Try to join channels directly without validation
                            # TwitchIO will handle invalid channels gracefully
                            await self.join_channels(streamers_to_join)
                            print(f"[INFO][Monitor] Join command sent for channels: {streamers_to_join}")
                            
                            # Wait a moment for the joins to process
                            await asyncio.sleep(5)
                            
                            # Check which channels were actually joined
                            new_connected = {ch.name for ch in self.connected_channels if ch is not None}
                            successfully_joined = set(streamers_to_join) & new_connected
                            failed_channels = set(streamers_to_join) - new_connected
                            
                            if successfully_joined:
                                print(f"[INFO][Monitor] Successfully joined channels: {successfully_joined}")
                                for channel in successfully_joined:
                                    channel_obj = self.get_channel(channel)
                                    if channel_obj:
                                        print(f"[DEBUG][Monitor] Channel '{channel}' details:")
                                        print(f"[DEBUG][Monitor] - ID: {channel_obj.id}")
                                        print(f"[DEBUG][Monitor] - Name: {channel_obj.name}")
                                        print(f"[DEBUG][Monitor] - Joined at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                            
                            if failed_channels:
                                print(f"[WARN][Monitor] Failed to join channels: {failed_channels}")
                                # Try to join failed channels individually with a delay
                                for channel in failed_channels:
                                    try:
                                        await asyncio.sleep(1)  # Small delay between individual joins
                                        await self.join_channels([channel])
                                        print(f"[INFO][Monitor] Retried joining channel: {channel}")
                                        # Check if retry was successful
                                        await asyncio.sleep(2)
                                        if channel in {ch.name for ch in self.connected_channels if ch is not None}:
                                            print(f"[INFO][Monitor] Retry successful for channel: {channel}")
                                        else:
                                            print(f"[WARN][Monitor] Retry failed for channel: {channel}")
                                    except Exception as e:
                                        print(f"[WARN][Monitor] Failed to join channel {channel} after retry: {e}")
                            
                        except Exception as join_error:
                            print(f"[ERROR][Monitor] Error trying to join channels: {join_error}")
                            # Try to join channels individually as a fallback
                            for channel in streamers_to_join:
                                try:
                                    await asyncio.sleep(1)  # Small delay between individual joins
                                    await self.join_channels([channel])
                                    print(f"[INFO][Monitor] Successfully joined channel: {channel}")
                                    # Verify the join was successful
                                    await asyncio.sleep(2)
                                    if channel in {ch.name for ch in self.connected_channels if ch is not None}:
                                        print(f"[DEBUG][Monitor] Verified successful join for channel: {channel}")
                                    else:
                                        print(f"[WARN][Monitor] Join verification failed for channel: {channel}")
                                except Exception as e:
                                    print(f"[WARN][Monitor] Failed to join channel {channel}: {e}")

                # Wait 2 minutes before next check
                await asyncio.sleep(120)

            except Exception as e:
                print(f"[ERROR][Monitor] Unexpected error in monitoring loop: {e}")
                traceback.print_exc()
                print("[INFO][Monitor] Waiting 5 minutes after error before retrying...")
                await asyncio.sleep(300) # Wait longer after an unexpected error

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
