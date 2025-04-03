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

import constants
import utils
from calculations import _get_xp_for_target_level, calculate_hotm_level, \
    calculate_average_skill_level, calculate_dungeon_level, calculate_class_level, calculate_slayer_level, format_price
from commands.overflow_skills import process_overflow_skill_command
from commands.skills import process_skills_command
from profiletyping import Profile
from utils import _find_latest_profile, _get_uuid_from_ign, _get_skyblock_data


def _select_profile(profiles: list[Profile], player_uuid: str, requested_profile_name: str | None) -> Profile | None:
    """Selects a profile from a list based on requested cute_name or falls back to the latest."""
    # profile_list = list(profiles.values()) # Error: profiles is already a list

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
    def __init__(self, token: str, prefix: str, nickname: str, initial_channels: list[str], hypixel_api_key: str | None):
        """Initializes the Bot."""
        self.start_time = datetime.now()
        self.hypixel_api_key = hypixel_api_key
        self.leveling_data = utils._load_leveling_data()
        # Store initial channels from .env for later reference if needed
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

        # Ensure the message has a valid channel and author
        if not hasattr(message.channel, 'name') or not hasattr(message.author, 'name') or not message.author.name:
            return # Ignore system messages or messages without proper author/channel context

        # Check if the message came from a channel the bot is actually connected to
        # This is needed because twitchio might receive messages from channels it tried to join but failed
        # Using a set for potentially faster lookups if the channel list grows large
        # Filter out None values before accessing name
        connected_channel_names = {ch.name for ch in self.connected_channels if ch is not None}
        if message.channel.name not in connected_channel_names:
            # print(f"[DEBUG] Ignored message from non-connected channel: #{message.channel.name}")
            return

        # Print received message for debugging
        # print(f"[MSG] #{message.channel.name} - {message.author.name}: {message.content}")

        # Process commands defined in this class
        await self.handle_commands(message)

    async def _send_message(self, ctx: commands.Context, message: str):
        """Helper function to send messages, incorporating workarounds for potential issues."""
        # Truncate message for logging if it's too long
        log_message = message[:450] + '...' if len(message) > 450 else message
        print(f"[DEBUG][Send] Attempting to send to #{ctx.channel.name}: {log_message}") 
        try:
            # --- WORKAROUND: Small delay before sending ---
            # May help with potential silent rate limits or timing issues after await calls.
            await asyncio.sleep(0.3) 
            # ---------------------------------------------

            # --- WORKAROUND: Re-fetch channel object ---
            # May help if the context's channel object state becomes inconsistent after awaits.
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
            # -----------------------------------------

        except Exception as send_e:
            print(f"[ERROR][Send] FAILED to send message to #{ctx.channel.name}: {send_e}")
            traceback.print_exc()

    # --- Commands ---

    @commands.command(name='skills')
    async def skills_command(self, ctx: commands.Context, *, args: str | None = None):
        """Shows the average SkyBlock skill level for a player.
        Syntax: #skills <username> [profile_name]
        """
        ign: str | None = None
        requested_profile_name: str | None = None

        if not args:
            ign = ctx.author.name
        else:
            parts = args.split()
            ign = parts[0]
            if len(parts) > 1:
                requested_profile_name = parts[1]
            if len(parts) > 2:
                await self._send_message(ctx, f"Too many arguments. Usage: {self._prefix}skills <username> [profile_name]")
                return

        await process_skills_command(ctx, ign, requested_profile_name=requested_profile_name)

    @commands.command(name='kuudra')
    async def kuudra_command(self, ctx: commands.Context, *, args: str | None = None):
        """Shows Kuudra completions for different tiers and calculates a score.
        Syntax: #kuudra <username> [profile_name]
        """
        ign: str | None = None
        requested_profile_name: str | None = None

        if not args:
            ign = ctx.author.name
        else:
            parts = args.split()
            ign = parts[0]
            if len(parts) > 1:
                requested_profile_name = parts[1]
            if len(parts) > 2:
                await self._send_message(ctx, f"Too many arguments. Usage: {self._prefix}kuudra <username> [profile_name]")
                return

        profile_data = await self._get_player_profile_data(ctx, ign, requested_profile_name=requested_profile_name)
        if not profile_data:
            return # Error message already sent by helper

        target_ign, player_uuid, selected_profile = profile_data
        profile_name = selected_profile.get('cute_name', 'Unknown')

        try:
            member_data = selected_profile.get('members', {}).get(player_uuid, {})
            nether_island_data = member_data.get('nether_island_player_data', None) # Check for None first

            if nether_island_data is None:
                 # Don't send a message here, rely on the underlying send issue being the problem
                 # await self._send_message(ctx, f"'{target_ign}' has no Kuudra data available (missing nether island data) in profile '{profile_name}'.")
                 print(f"[INFO][KuudraCmd] No nether_island_player_data found for {target_ign} in profile {profile_name}.")
                 return

            kuudra_completed_tiers = nether_island_data.get('kuudra_completed_tiers', None) # Check for None

            if kuudra_completed_tiers is None or not kuudra_completed_tiers: # Check for None or empty dict
                # Don't send a message here
                # await self._send_message(ctx, f"'{target_ign}' has no Kuudra completions recorded in profile '{profile_name}'.")
                print(f"[INFO][KuudraCmd] No Kuudra completions recorded for {target_ign} in profile {profile_name}.")
                return

            # Format output
            completions = []
            total_score = 0
            for tier in constants.KUUDRA_TIERS_ORDER:
                count = kuudra_completed_tiers.get(tier, 0)
                tier_name = 'basic' if tier == 'none' else tier # Rename 'none' to 'basic'
                completions.append(f"{tier_name} {count}")
                total_score += count * constants.KUUDRA_TIER_POINTS.get(tier, 0) # Use .get for safety

            await self._send_message(ctx, f"{target_ign}'s Kuudra completions in profile '{profile_name}': {', '.join(completions)} | Score: {total_score:,}")

        except Exception as e:
            print(f"[ERROR][KuudraCmd] Unexpected error processing Kuudra data: {e}")
            traceback.print_exc()
            await self._send_message(ctx, "An unexpected error occurred while fetching Kuudra completions.")

    @commands.command(name='oskill', aliases=['skillo', 'oskills', 'skillso', 'overflow'])
    async def skill_command(self, ctx: commands.Context, *, args: str | None = None):
        """Shows the overflow skill details for a player.
        Syntax: #oskill <username> [profile_name]
        """
        ign: str | None = None
        requested_profile_name: str | None = None

        if not args:
            ign = ctx.author.name
        else:
            parts = args.split()
            ign = parts[0]
            if len(parts) > 1:
                requested_profile_name = parts[1]
            if len(parts) > 2:
                await self._send_message(ctx, f"Too many arguments. Usage: {self._prefix}oskill <username> [profile_name]")
                return

        # Call the separate processing function, passing the profile name
        await process_overflow_skill_command(ctx, ign, requested_profile_name=requested_profile_name)

    @commands.command(name='auctions', aliases=['ah'])
    async def auctions_command(self, ctx: commands.Context, *, ign: str | None = None):
        """Shows active auctions for a player, limited by character count.
           This command currently DOES NOT support profile selection.
        """
        if not self.hypixel_api_key: # API key check needed here as it uses a different endpoint helper
            await ctx.send("Hypixel API is not configured.")
            return

        target_ign = ign if ign else ctx.author.name
        target_ign = target_ign.lstrip('@')
        # await ctx.send(f"Searching active auctions for '{target_ign}'...") # Removed initial message

        try:
            player_uuid = await _get_uuid_from_ign(target_ign)
            if not player_uuid:
                await ctx.send(f"Could not find Minecraft account for '{target_ign}'.")
                return

            # --- Fetch Auction Data ---
            url = constants.HYPIXEL_AUCTION_URL
            params = {"key": self.hypixel_api_key, "player": player_uuid}
            print(f"[DEBUG][API] Hypixel Auctions request for UUID '{player_uuid}'...")
            auctions = []
            try:
                 async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=params) as response:
                        print(f"[DEBUG][API] Hypixel Auctions response status: {response.status}")
                        if response.status == 200:
                            data = await response.json()
                            if data.get("success"):
                                auctions = data.get('auctions', [])
                            else:
                                reason = data.get('cause', 'Unknown reason')
                                print(f"[ERROR][API] Hypixel Auctions API Error: {reason}")
                                await ctx.send("Failed to fetch auction data (API error).")
                                return
                        else:
                            print(f"[ERROR][API] Hypixel Auctions API request failed: Status {response.status}")
                            await ctx.send("Failed to fetch auction data (HTTP error).")
                            return
            except aiohttp.ClientError as e:
                print(f"[ERROR][API] Network error during Hypixel Auctions API request: {e}")
                await ctx.send("Failed to fetch auction data (Network error).")
                return
            except Exception as e:
                print(f"[ERROR][API] Unexpected error during Hypixel Auctions API request: {e}")
                traceback.print_exc()
                await ctx.send("An unexpected error occurred while fetching auctions.")
                return
            # --- End Fetch Auction Data ---

            if not auctions:
                await self._send_message(ctx, f"'{target_ign}' has no active auctions.")
                return

            # Count unique items before filtering
            total_unique_items = len({auction.get('item_name', 'Unknown Item') for auction in auctions})

            # Format output respecting character limit
            message_prefix = f"{target_ign}'s Auctions: "
            auction_list_parts = []
            shown_items_count = 0

            current_message = message_prefix
            for auction in auctions:
                item_name = auction.get('item_name', 'Unknown Item').replace("§.", "") # Basic formatting code removal
                highest_bid = auction.get('highest_bid_amount', 0)
                if highest_bid == 0:
                    highest_bid = auction.get('starting_bid', 0)

                price_str = format_price(highest_bid)
                auction_str = f"{item_name} {price_str}"

                # Check if adding the next item exceeds the limit
                separator = " | " if auction_list_parts else ""
                if len(current_message) + len(separator) + len(auction_str) <= constants.MAX_MESSAGE_LENGTH:
                    auction_list_parts.append(auction_str)
                    current_message += separator + auction_str
                    shown_items_count += 1
                else:
                    # Stop adding more items if limit is reached
                    break

            if not auction_list_parts:
                 await self._send_message(ctx, f"Could not format any auctions for '{target_ign}' within the character limit.")
                 return

            # Add suffix if some items were hidden
            final_message = message_prefix + " | ".join(auction_list_parts)
            hidden_items = total_unique_items - shown_items_count
            if hidden_items > 0:
                suffix = f" (+{hidden_items} more)"
                # Check if suffix fits, otherwise omit it
                if len(final_message) + len(suffix) <= constants.MAX_MESSAGE_LENGTH:
                     final_message += suffix

            await self._send_message(ctx, final_message)

        except Exception as e:
            print(f"[ERROR][AuctionsCmd] Unexpected error processing auctions: {e}")
            traceback.print_exc()
            await self._send_message(ctx, "An unexpected error occurred while fetching auctions.")

    @commands.command(name='dungeon', aliases=['dungeons', 'cata'])
    async def dungeon_command(self, ctx: commands.Context, *, args: str | None = None):
        """Shows the player's Catacombs level and XP.
        Syntax: #dungeon <username> [profile_name]
        """
        ign: str | None = None
        requested_profile_name: str | None = None

        if not args:
            ign = ctx.author.name
        else:
            parts = args.split()
            ign = parts[0]
            if len(parts) > 1:
                requested_profile_name = parts[1]
            if len(parts) > 2:
                await self._send_message(ctx, f"Too many arguments. Usage: {self._prefix}dungeon <username> [profile_name]")
                return

        profile_data = await self._get_player_profile_data(ctx, ign, requested_profile_name=requested_profile_name)
        if not profile_data:
            return

        target_ign, player_uuid, selected_profile = profile_data
        profile_name = selected_profile.get('cute_name', 'Unknown')

        try:
            member_data = selected_profile.get('members', {}).get(player_uuid, {})
            dungeons_data = member_data.get('dungeons', {}).get('dungeon_types', {}).get('catacombs', {})
            catacombs_xp = dungeons_data.get('experience', 0)

            level = calculate_dungeon_level(self.leveling_data, catacombs_xp)
            await self._send_message(ctx, f"{target_ign}'s Catacombs level in profile '{profile_name}' is {level:.2f} (XP: {catacombs_xp:,.0f})")

        except Exception as e:
            print(f"[ERROR][DungeonCmd] Unexpected error processing dungeon data: {e}")
            traceback.print_exc()
            await self._send_message(ctx, "An unexpected error occurred while fetching Catacombs level.")

    @commands.command(name='sblvl')
    async def sblvl_command(self, ctx: commands.Context, *, args: str | None = None):
        """Shows the player's SkyBlock level (based on XP/100).
        Syntax: #sblvl <username> [profile_name]
        """
        ign: str | None = None
        requested_profile_name: str | None = None

        if not args:
            ign = ctx.author.name
        else:
            parts = args.split()
            ign = parts[0]
            if len(parts) > 1:
                requested_profile_name = parts[1]
            if len(parts) > 2:
                await self._send_message(ctx, f"Too many arguments. Usage: {self._prefix}sblvl <username> [profile_name]")
                return

        profile_data = await self._get_player_profile_data(ctx, ign, requested_profile_name=requested_profile_name)
        if not profile_data:
            return

        target_ign, player_uuid, selected_profile = profile_data
        profile_name = selected_profile.get('cute_name', 'Unknown')

        try:
            member_data = selected_profile.get('members', {}).get(player_uuid, {})
            leveling_data = member_data.get('leveling', {})
            sb_xp = leveling_data.get('experience', 0) # This is total profile XP, not level XP

            # Calculate level by dividing XP by 100 as specifically requested
            sb_level = sb_xp / 100.0

            await self._send_message(ctx, f"{target_ign}'s SkyBlock level in profile '{profile_name}' is {sb_level:.2f}.")

        except Exception as e:
            print(f"[ERROR][SblvlCmd] Unexpected error processing level data: {e}")
            traceback.print_exc()
            await self._send_message(ctx, "An unexpected error occurred while fetching SkyBlock level.")

    @commands.command(name='classaverage', aliases=['ca'])
    async def classaverage_command(self, ctx: commands.Context, *, args: str | None = None):
        """Shows the player's dungeon class levels and their average.
        Syntax: #ca <username> [profile_name]
        """
        ign: str | None = None
        requested_profile_name: str | None = None

        if not args:
            ign = ctx.author.name
        else:
            parts = args.split()
            ign = parts[0]
            if len(parts) > 1:
                requested_profile_name = parts[1]
            if len(parts) > 2:
                await self._send_message(ctx, f"Too many arguments. Usage: {self._prefix}ca <username> [profile_name]")
                return

        profile_data = await self._get_player_profile_data(ctx, ign, requested_profile_name=requested_profile_name)
        if not profile_data:
            return

        target_ign, player_uuid, selected_profile = profile_data
        profile_name = selected_profile.get('cute_name', 'Unknown')

        try:
            member_data = selected_profile.get('members', {}).get(player_uuid, {})
            dungeons_data = member_data.get('dungeons', {})
            player_classes_data = dungeons_data.get('player_classes', None) # Check for None

            if player_classes_data is None:
                 # Don't send message due to sending issues
                 print(f"[INFO][ClassAvgCmd] No player_classes data found for {target_ign} in profile {profile_name}.")
                 # await self._send_message(ctx, f"'{target_ign}' has no class data in profile '{profile_name}'.")
                 return

            class_levels = {}
            total_level = 0.0
            valid_classes_counted = 0

            for class_name in constants.CLASS_NAMES:
                class_xp = player_classes_data.get(class_name, {}).get('experience', 0)
                level = calculate_class_level(self.leveling_data, class_xp)
                class_levels[class_name.capitalize()] = level
                total_level += level
                valid_classes_counted += 1 # Count even if level is 0

            if valid_classes_counted > 0:
                 average_level = total_level / valid_classes_counted
                 levels_str = " | ".join([f"{name} {lvl:.2f}" for name, lvl in class_levels.items()])
                 await self._send_message(ctx, f"{target_ign}'s class levels in profile '{profile_name}': {levels_str} | Average: {average_level:.2f}")
            else:
                 # Should not happen if CLASS_NAMES is populated, but safety check
                 print(f"[WARN][ClassAvgCmd] No valid classes found to calculate average for {target_ign}.")
                 await self._send_message(ctx, f"Could not calculate class average for '{target_ign}'.")


        except Exception as e:
            print(f"[ERROR][ClassAvgCmd] Unexpected error processing class levels: {e}")
            traceback.print_exc()
            await self._send_message(ctx, "An unexpected error occurred while fetching class levels.")

    @commands.command(name='mayor')
    async def mayor_command(self, ctx: commands.Context):
        """Shows the current SkyBlock Mayor and Minister."""
        if not self.hypixel_api_key:
            await ctx.send("Hypixel API Key is not configured.")
            return

        print(f"[DEBUG][API] Fetching SkyBlock election data from {constants.HYPIXEL_ELECTION_URL}")
        # await ctx.send("Fetching current SkyBlock Mayor...") # Removed initial message

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(constants.HYPIXEL_ELECTION_URL) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("success"):
                            mayor_data = data.get('mayor')
                            if mayor_data:
                                mayor_name = mayor_data.get('name', 'Unknown')
                                perks = mayor_data.get('perks', [])
                                perk_names = [p.get('name', '') for p in perks if p.get('name')]
                                perks_str = " | ".join(perk_names) if perk_names else "No Perks"
                                num_perks = len(perk_names)

                                # Extract Minister info
                                minister_data = mayor_data.get('minister')
                                minister_str = ""
                                if minister_data:
                                    minister_name = minister_data.get('name', 'Unknown')
                                    minister_perk = minister_data.get('perk', {}).get('name', 'Unknown Perk')
                                    minister_str = f" | Minister: {minister_name} ({minister_perk})"

                                output_message = f"Current Mayor: {num_perks} perk {mayor_name} ({perks_str}){minister_str}"
                                await self._send_message(ctx, output_message)
                            else:
                                await self._send_message(ctx, "Could not find current mayor data in the API response.")
                        else:
                            await self._send_message(ctx, "API request failed (success=false). Could not fetch election data.")
                    else:
                        await self._send_message(ctx, f"Error fetching election data. API returned status {response.status}.")

        except aiohttp.ClientError as e:
            print(f"[ERROR][API] Network error fetching election data: {e}")
            await self._send_message(ctx, "Network error while fetching election data.")
        except json.JSONDecodeError:
             print(f"[ERROR][API] Failed to parse JSON from election API.")
             await self._send_message(ctx, "Error parsing election data from API.")
        except Exception as e:
            print(f"[ERROR][MayorCmd] Unexpected error: {e}")
            traceback.print_exc()
            await self._send_message(ctx, "An unexpected error occurred while fetching mayor information.")

    @commands.command(name='bank', aliases=['purse', 'money'])
    async def bank_command(self, ctx: commands.Context, *, args: str | None = None):
        """Shows the player's bank, purse, and personal bank balance.
        Syntax: #bank <username> [profile_name]
        """
        ign: str | None = None
        requested_profile_name: str | None = None

        if not args:
            ign = ctx.author.name
        else:
            parts = args.split()
            ign = parts[0]
            if len(parts) > 1:
                requested_profile_name = parts[1]
            if len(parts) > 2:
                await self._send_message(ctx, f"Too many arguments. Usage: {self._prefix}bank <username> [profile_name]")
                return

        profile_data = await self._get_player_profile_data(ctx, ign, requested_profile_name=requested_profile_name)
        if not profile_data:
            return

        target_ign, player_uuid, selected_profile = profile_data
        profile_name = selected_profile.get('cute_name', 'Unknown')

        try:
            # Bank Balance (Profile wide)
            banking_data = selected_profile.get('banking', {})
            bank_balance = banking_data.get('balance', 0.0)

            # Purse and Personal Bank (Member specific)
            member_data = selected_profile.get('members', {}).get(player_uuid, {})
            currencies_data = member_data.get('currencies', {})
            purse_balance = currencies_data.get('coin_purse', 0.0)
            personal_bank_balance = member_data.get('profile', {}).get('bank_account', None)

            # Construct the output message
            parts = [
                f"{target_ign}'s Bank: {bank_balance:,.0f}",
                f"Purse: {purse_balance:,.0f}"
            ]
            if personal_bank_balance is not None:
                parts.append(f"Personal Bank: {personal_bank_balance:,.0f}")
            parts.append(f"(Profile: '{profile_name}')")

            output_message = ", ".join(parts)
            await self._send_message(ctx, output_message)

        except Exception as e:
            print(f"[ERROR][BankCmd] Unexpected error processing balance data: {e}")
            traceback.print_exc()
            await self._send_message(ctx, "An unexpected error occurred while fetching balance information.")

    @commands.command(name='nucleus')
    async def nucleus_command(self, ctx: commands.Context, *, args: str | None = None):
        """Shows the calculated Nucleus runs based on placed crystals.
        Syntax: #nucleus <username> [profile_name]
        """
        ign: str | None = None
        requested_profile_name: str | None = None

        if not args:
            ign = ctx.author.name
        else:
            parts = args.split()
            ign = parts[0]
            if len(parts) > 1:
                requested_profile_name = parts[1]
            if len(parts) > 2:
                await self._send_message(ctx, f"Too many arguments. Usage: {self._prefix}nucleus <username> [profile_name]")
                return

        profile_data = await self._get_player_profile_data(ctx, ign, requested_profile_name=requested_profile_name)
        if not profile_data:
            return

        target_ign, player_uuid, selected_profile = profile_data
        profile_name = selected_profile.get('cute_name', 'Unknown')

        try:
            member_data = selected_profile.get('members', {}).get(player_uuid, {})
            mining_core_data = member_data.get('mining_core', {})
            crystals_data = mining_core_data.get('crystals', {})

            sum_total_placed = 0
            print(f"[DEBUG][NucleusCmd] Calculating for {target_ign} ({profile_name}):")
            for crystal_key in constants.NUCLEUS_CRYSTALS:
                crystal_info = crystals_data.get(crystal_key, {})
                total_placed = crystal_info.get('total_placed', 0)
                sum_total_placed += total_placed
                print(f"  - {crystal_key}: {total_placed}") # Debug print activated

            # Calculate result: sum divided by 5, rounded down
            nucleus_result = sum_total_placed // 5
            print(f"[DEBUG][NucleusCmd] Sum: {sum_total_placed}, Result (Sum // 5): {nucleus_result}")

            await self._send_message(ctx, f"{target_ign}'s nucleus runs: {nucleus_result} (Profile: '{profile_name}')") # Added profile name back

        except Exception as e:
            print(f"[ERROR][NucleusCmd] Unexpected error processing nucleus data: {e}")
            traceback.print_exc()
            await self._send_message(ctx, "An unexpected error occurred while fetching Nucleus runs.")

    @commands.command(name='hotm')
    async def hotm_command(self, ctx: commands.Context, *, args: str | None = None):
        """Shows the player's Heart of the Mountain level.
        Syntax: #hotm <username> [profile_name]
        """
        ign: str | None = None
        requested_profile_name: str | None = None

        if not args:
            ign = ctx.author.name
        else:
            parts = args.split()
            ign = parts[0]
            if len(parts) > 1:
                requested_profile_name = parts[1]
            if len(parts) > 2:
                await self._send_message(ctx, f"Too many arguments. Usage: {self._prefix}hotm <username> [profile_name]")
                return

        profile_data = await self._get_player_profile_data(ctx, ign, requested_profile_name=requested_profile_name)
        if not profile_data:
             return

        target_ign, player_uuid, selected_profile = profile_data
        profile_name = selected_profile.get('cute_name', 'Unknown')

        try:
            member_data = selected_profile.get('members', {}).get(player_uuid, {})
            mining_core_data = member_data.get('mining_core', {})
            hotm_xp = mining_core_data.get('experience', 0.0)

            level = calculate_hotm_level(self.leveling_data, hotm_xp)
            await self._send_message(ctx, f"{target_ign}'s HotM level is {level:.2f} (XP: {hotm_xp:,.0f}) (Profile: '{profile_name}')") # Added profile name

        except Exception as e:
            print(f"[ERROR][HotmCmd] Unexpected error processing HotM data: {e}")
            traceback.print_exc()
            await self._send_message(ctx, "An unexpected error occurred while fetching HotM level.")

    @commands.command(name='essence')
    async def essence_command(self, ctx: commands.Context, *, args: str | None = None):
        """Shows the player's essence amounts.
        Syntax: #essence <username> [profile_name]
        """
        ign: str | None = None
        requested_profile_name: str | None = None

        if not args:
            ign = ctx.author.name
        else:
            parts = args.split()
            ign = parts[0]
            if len(parts) > 1:
                requested_profile_name = parts[1]
            if len(parts) > 2:
                await self._send_message(ctx, f"Too many arguments. Usage: {self._prefix}essence <username> [profile_name]")
                return

        profile_data = await self._get_player_profile_data(ctx, ign, requested_profile_name=requested_profile_name)
        if not profile_data:
             return

        target_ign, player_uuid, selected_profile = profile_data
        profile_name = selected_profile.get('cute_name', 'Unknown')

        try:
            member_data = selected_profile.get('members', {}).get(player_uuid, {})
            currencies_data = member_data.get('currencies', {})

            # Get the main essence container
            all_essence_data = currencies_data.get('essence', {})

            if not all_essence_data:
                print(f"[INFO][EssenceCmd] No essence data found for {target_ign} in profile {profile_name}.")
                # Optionally send message if needed
                # await self._send_message(ctx, f"No essence data found for '{target_ign}' in profile '{profile_name}'.")
                return

            essence_amounts = []
            for essence_type in constants.ESSENCE_TYPES:
                # Access the specific essence type's dictionary
                essence_type_data = all_essence_data.get(essence_type, {})
                # Get the 'current' amount from within that dictionary
                amount = essence_type_data.get('current', 0)

                # Use capitalized full name
                display_name = essence_type.capitalize() 
                amount_str = format_price(amount)
                essence_amounts.append(f"{display_name}: {amount_str}")

            output_message = f"{target_ign} (Profile: '{profile_name}'): { ' | '.join(essence_amounts) }"
            await self._send_message(ctx, output_message)

        except Exception as e:
            print(f"[ERROR][EssenceCmd] Unexpected error processing essence data: {e}")
            traceback.print_exc()
            await self._send_message(ctx, "An unexpected error occurred while fetching essences.")

    @commands.command(name='powder')
    async def powder_command(self, ctx: commands.Context, *, args: str | None = None):
        """Shows the player's current and total Mithril and Gemstone powder.
        Syntax: #powder <username> [profile_name]
        """
        ign: str | None = None
        requested_profile_name: str | None = None

        if not args:
            ign = ctx.author.name
        else:
            parts = args.split()
            ign = parts[0]
            if len(parts) > 1:
                requested_profile_name = parts[1]
            if len(parts) > 2:
                await self._send_message(ctx, f"Too many arguments. Usage: {self._prefix}powder <username> [profile_name]")
                return

        profile_data = await self._get_player_profile_data(ctx, ign, requested_profile_name=requested_profile_name)
        if not profile_data:
            return

        target_ign, player_uuid, selected_profile = profile_data
        profile_name = selected_profile.get('cute_name', 'Unknown')

        try:
            member_data = selected_profile.get('members', {}).get(player_uuid, {})
            mining_core_data = member_data.get('mining_core', {})

            # Get current powder values
            current_mithril = mining_core_data.get('powder_mithril', 0)
            current_gemstone = mining_core_data.get('powder_gemstone', 0)

            # Get spent powder values
            spent_mithril = mining_core_data.get('powder_spent_mithril', 0)
            spent_gemstone = mining_core_data.get('powder_spent_gemstone', 0)

            # Calculate totals
            total_mithril = current_mithril + spent_mithril
            total_gemstone = current_gemstone + spent_gemstone

            # Format the output string
            output_message = (
                f"{target_ign}'s powder ({profile_name}): "
                f"mithril powder: {current_mithril:,.0f} (total: {total_mithril:,.0f}) | "
                f"gemstone powder: {current_gemstone:,.0f} (total: {total_gemstone:,.0f})"
            )

            await self._send_message(ctx, output_message)

        except Exception as e:
            print(f"[ERROR][PowderCmd] Unexpected error processing powder data: {e}")
            traceback.print_exc()
            await self._send_message(ctx, "An unexpected error occurred while fetching powder amounts.")

    @commands.command(name='slayer')
    async def slayer_command(self, ctx: commands.Context, *, args: str | None = None):
        """Shows the player's slayer levels.
        Syntax: #slayer <username> [profile_name]
        """
        ign: str | None = None
        requested_profile_name: str | None = None

        if not args:
            ign = ctx.author.name
        else:
            parts = args.split()
            ign = parts[0]
            if len(parts) > 1:
                requested_profile_name = parts[1]
            if len(parts) > 2:
                await self._send_message(ctx, f"Too many arguments. Usage: {self._prefix}slayer <username> [profile_name]")
                return

        profile_data = await self._get_player_profile_data(ctx, ign, requested_profile_name=requested_profile_name)
        if not profile_data:
            return

        target_ign, player_uuid, selected_profile = profile_data
        profile_name = selected_profile.get('cute_name', 'Unknown')

        try:
            member_data = selected_profile.get('members', {}).get(player_uuid, {})
            slayer_data = member_data.get('slayer', {}).get('slayer_bosses', {})

            if not slayer_data:
                print(f"[INFO][SlayerCmd] No slayer data found for {target_ign} in profile {profile_name}.")
                await self._send_message(ctx, f"'{target_ign}' has no slayer data in profile '{profile_name}'.")
                return

            slayer_levels = []
            for boss_key in constants.SLAYER_BOSS_KEYS:
                boss_data = slayer_data.get(boss_key, {})
                xp = boss_data.get('xp', 0)
                level = calculate_slayer_level(self.leveling_data, xp, boss_key)
                # Capitalize boss name for display
                display_name = boss_key.capitalize()
                # Format with integer level and formatted XP
                xp_str = format_price(xp) # Use format_price for consistency
                slayer_levels.append(f"{display_name} {level} ({xp_str} XP)")

            output_message = f"{target_ign}'s Slayers (Profile: '{profile_name}'): { ' | '.join(slayer_levels) }"
            await self._send_message(ctx, output_message)

        except Exception as e:
            print(f"[ERROR][SlayerCmd] Unexpected error processing slayer data: {e}")
            traceback.print_exc()
            await self._send_message(ctx, "An unexpected error occurred while fetching slayer levels.")

    @commands.command(name='networth', aliases=["nw"])
    async def networth_command(self, ctx: commands.Context, *, ign: str | None = None):
        """Informs the user that networth calculation is not supported and suggests alternatives."""
        await self._send_message(ctx, "Networth calculation is not supported. Please use mods like NEU or SkyHelper for accurate networth calculations.")

    @commands.command(name='dexter')
    async def dexter_command(self, ctx: commands.Context):
        """Hidden command that responds with a skill issue confirmation."""
        await self._send_message(ctx, "YEP skill issue confirmed!")
    dexter_command.hidden = True

    @commands.command(name='dongo')
    async def dexter_command(self, ctx: commands.Context):
        """Hidden command that responds with a skill issue confirmation."""
        await self._send_message(ctx, "🥚")

    dexter_command.hidden = True

    @commands.command(name='help')
    async def help_command(self, ctx: commands.Context):
        """Shows this help message listing all available commands."""
        print(f"[COMMAND] Help command triggered by {ctx.author.name} in #{ctx.channel.name}")
        prefix = self._prefix # Get the bot's prefix
        
        help_parts = [f"Available commands (Prefix: {prefix}):"]
        
        # Sort commands alphabetically for clarity
        command_list = sorted(self.commands.values(), key=lambda cmd: cmd.name)
        
        for cmd in command_list:
            # Skip hidden commands
            if getattr(cmd, 'hidden', False):
                continue
                
            # Format aliases
            aliases = f" (Aliases: {', '.join(cmd.aliases)})" if cmd.aliases else ""
            
            # Get description from docstring (first line)
            description = "No description available." # Default
            if cmd._callback.__doc__:
                first_line = cmd._callback.__doc__.strip().split('\n')[0]
                description = first_line
                
            help_parts.append(f"- {prefix}{cmd.name}{aliases}")
            
        # Join parts into a single message (consider potential length limits)
        # For now, send as one message. If it gets too long, splitting logic would be needed.
        help_message = " ".join(help_parts) # Use space as separator for better readability in chat
        
        await self._send_message(ctx, help_message)

    @commands.command(name='rtca')
    async def rtca_command(self, ctx: commands.Context, *, args: str | None = None):
        """Estimates M6/M7 runs needed for a target class average using simulation.
        Syntax: #rtca <username> [profile_name] [target_ca=50] [floor=m7]
        Simulates runs considering 100% active XP / 25% passive XP.
        """
        print(f"[COMMAND] Rtca command triggered by {ctx.author.name}: {args}")

        # --- 1. Argument Parsing ---
        ign: str | None = None
        requested_profile_name: str | None = None
        target_ca_str: str = '50' # Default target CA
        floor_str: str = 'm7'   # Default floor

        if not args:
            ign = ctx.author.name # Default to message author if no args provided
            print(f"[DEBUG][RtcaCmd] No arguments provided, defaulting IGN to: {ign}")
        else:
            parts = args.split()
            ign = parts[0] # First part is always IGN
            remaining_parts = parts[1:]

            potential_profile_name = None
            potential_target_ca = None
            potential_floor = None
            unidentified_parts = [] # Store parts that don't match known patterns

            # Iterate through remaining parts to identify them
            for part in remaining_parts:
                part_lower = part.lower()
                if part_lower in ['m6', 'm7'] and potential_floor is None:
                    potential_floor = part_lower
                elif part.isdigit() and potential_target_ca is None:
                    potential_target_ca = part
                else:
                    if potential_profile_name is None:
                        potential_profile_name = part
                    else:
                        unidentified_parts.append(part)
            
            requested_profile_name = potential_profile_name
            if potential_target_ca is not None:
                target_ca_str = potential_target_ca
            if potential_floor is not None:
                floor_str = potential_floor

            if unidentified_parts:
                usage_message = f"Too many or ambiguous arguments: {unidentified_parts}. Usage: {self._prefix}rtca <username> [profile_name] [target_ca=50] [floor=m7]"
                await self._send_message(ctx, usage_message)
                return

        # --- Argument Validation (Moved here to run after potential defaulting) ---
        try:
            # Validate floor
            if floor_str not in ['m6', 'm7']:
                raise ValueError("Invalid floor. Please specify 'm6' or 'm7'.")
            print(f"[DEBUG][RtcaCmd] Validated floor_str: {floor_str}")

            # Validate target level if provided
            target_level = None
            if target_ca_str:
                target_level = int(target_ca_str)
                if not 1 <= target_level <= 99:
                    raise ValueError("Target level must be between 1 and 99.")
                print(f"[DEBUG][RtcaCmd] Validated target_level: {target_level}")

        except ValueError as e:
            await self._send_message(ctx, f"Invalid argument: {e}. Usage: {self._prefix}rtca <username> [profile_name] [target_ca=50] [floor=m7]")
            return
        # --- End Argument Parsing & Validation ---

        # --- 2. Get Player Data ---
        profile_data = await self._get_player_profile_data(ctx, ign, requested_profile_name=requested_profile_name)
        if not profile_data:
            return # Error message already sent by helper

        target_ign, player_uuid, selected_profile = profile_data
        profile_name = selected_profile.get('cute_name', 'Unknown')
        print(f"[INFO][RtcaCmd] Using profile: {profile_name}")
        # --- End Fetch Player Data ---

        try:
            member_data = selected_profile.get('members', {}).get(player_uuid, {})
            dungeons_data = member_data.get('dungeons', {})
            player_classes_data = dungeons_data.get('player_classes', None)
            # --- Fetch Selected Class --- (Use selected profile's data)
            selected_class = dungeons_data.get('selected_dungeon_class')
            selected_class_lower = selected_class.lower() if selected_class else None # Lowercase for comparison
            print(f"[DEBUG][RtcaCmd] Fetched selected class from profile '{profile_name}': {selected_class}")
            # -----------------------------

            if player_classes_data is None:
                 print(f"[INFO][RtcaCmd] No player_classes data found for {target_ign} in profile {profile_name}.")
                 await self._send_message(ctx, f"'{target_ign}' has no class data in profile '{profile_name}'.")
                 return

            # --- 3. Calculate Current State ---
            current_class_levels = {}
            total_level_sum = 0.0
            class_xps = {}
            for class_name in constants.CLASS_NAMES:
                class_xp = player_classes_data.get(class_name, {}).get('experience', 0)
                level = calculate_class_level(self.leveling_data, class_xp)
                current_class_levels[class_name] = level
                class_xps[class_name] = class_xp
                total_level_sum += level
            
            current_ca = total_level_sum / len(constants.CLASS_NAMES) if constants.CLASS_NAMES else 0.0
            print(f"[DEBUG][RtcaCmd] {target_ign} - Current CA: {current_ca:.2f}, Target CA: {target_ca_str}")

            # Check if target is already reached
            if current_ca >= target_level:
                 await self._send_message(ctx, f"{target_ign} (CA {current_ca:.2f}) has already reached or surpassed the target Class Average {target_level}.")
                 return
            # --- End Calculate Current State ---

            # --- 4. Setup Simulation Parameters ---
            target_level_for_milestone = target_level # Target level for each class is the target CA

            # Determine XP per run based on selected floor
            if floor_str == 'm6':
                xp_per_run = constants.BASE_M6_CLASS_XP
                selected_floor_name = "M6"
            else: # Default or 'm7'
                xp_per_run = constants.BASE_M7_CLASS_XP
                selected_floor_name = "M7"
                
            # --- TEMPORARY TEST: Increase XP by 10% --- 
            xp_per_run *= 1.06 # Disabled for now
            print(f"[DEBUG][RtcaCmd][TEST] Applying +10% XP boost. New XP/Run: {xp_per_run:,.0f}")
            # -----------------------------------------

            if xp_per_run <= 0: # Safety check
                print(f"[ERROR][RtcaCmd] Base XP per run is zero or negative for {selected_floor_name}.")
                await self._send_message(ctx, "Error with base XP configuration. Cannot estimate runs.")
                return

            # Calculate target XP threshold (XP needed to COMPLETE the target level)
            xp_required_for_target_level = _get_xp_for_target_level(self.leveling_data, target_level_for_milestone)
            print(f"[DEBUG][RtcaCmd] Target Level XP Threshold: {xp_required_for_target_level:,.0f}")
            print(f"[DEBUG][RtcaCmd] XP/Run Used ({selected_floor_name}): {xp_per_run:,.0f}")
            # --- End Setup Simulation Parameters ---

            # --- 5. Initialize Simulation ---
            total_runs_simulated = 0
            xp_needed_dict = {} # Stores remaining XP needed for each class
            active_runs_per_class = {cn: 0 for cn in constants.CLASS_NAMES} # Tracks active runs per class
            
            print(f"[DEBUG][RtcaSim] --- Initializing Simulation Needs ---")
            for class_name in constants.CLASS_NAMES:
                current_xp = class_xps[class_name]
                current_lvl = current_class_levels[class_name]
                if current_lvl < target_level_for_milestone:
                    needed = xp_required_for_target_level - current_xp
                    if needed > 0:
                        xp_needed_dict[class_name] = needed
                        print(f"[DEBUG][RtcaSim] Initial Need - {class_name.capitalize()}: {needed:,.0f} XP")
                    else:
                        print(f"[DEBUG][RtcaSim] Initial Need - {class_name.capitalize()}: 0 XP (Already Met)")
                else:
                    print(f"[DEBUG][RtcaSim] Initial Need - {class_name.capitalize()}: 0 XP (Level Met)")

            # Check if simulation is necessary
            if not xp_needed_dict:
                await self._send_message(ctx, f"{target_ign} already meets the XP requirements for CA {target_level}.")
                return
            # --- End Initialize Simulation ---

            # --- 6. Run Simulation ---
            print(f"[DEBUG][RtcaSim] --- Starting Simulation Loop ---")
            max_iterations = 100000 # Safety break
            iteration = 0
            active_gain = xp_per_run
            passive_gain = 0.25 * xp_per_run
            
            while xp_needed_dict and iteration < max_iterations:
                iteration += 1
                total_runs_simulated += 1

                # Find bottleneck class (needs most runs if played actively)
                bottleneck_class = None
                max_runs_if_active = -1
                for cn, needed in xp_needed_dict.items():
                    runs_if_active = math.ceil(needed / active_gain)
                    if runs_if_active > max_runs_if_active:
                        max_runs_if_active = runs_if_active
                        bottleneck_class = cn
                    # Optional: Add tie-breaking logic here if needed

                if bottleneck_class is None: # Should not happen if xp_needed_dict is not empty
                    print("[ERROR][RtcaSim] Could not determine bottleneck class during simulation. Breaking loop.")
                    break
                
                # Track the active class for this run
                active_runs_per_class[bottleneck_class] += 1 

                # Apply XP gains and update needed XP for the next iteration
                next_xp_needed = {}
                for cn, needed in xp_needed_dict.items():
                    xp_gained = active_gain if cn == bottleneck_class else passive_gain
                    remaining_needed = needed - xp_gained
                    if remaining_needed > 0:
                        next_xp_needed[cn] = remaining_needed
                    # else: Optional: log class completion here
                
                xp_needed_dict = next_xp_needed # Update for the next loop iteration

            print(f"[DEBUG][RtcaSim] --- Simulation Finished after {iteration} iterations ---")
            print(f"[DEBUG][RtcaSim] Total Runs Simulated: {total_runs_simulated}")
            print(f"[DEBUG][RtcaSim] Active Runs Breakdown: {active_runs_per_class}") 
            if iteration >= max_iterations:
                 print(f"[ERROR][RtcaSim] Simulation reached max iterations ({max_iterations}). Result might be inaccurate.")
            # --- End Run Simulation ---

            # --- 7. Format and Send Output ---
            # Prepare items for sorting (only those with > 0 runs)
            items_to_sort = [(cn, count) for cn, count in active_runs_per_class.items() if count > 0]

            # Sort: selected class first, then by descending run count
            sorted_items = sorted(
                items_to_sort,
                key=lambda item: (item[0].lower() != selected_class_lower if selected_class_lower else True, -item[1]) # Handle case where selected_class is None
                # Explanation:
                # - item[0].lower() != selected_class_lower if selected_class_lower else True:
                #   This is False (sorts first) if item[0] IS the selected class.
                #   This is True (sorts later) if item[0] is NOT the selected class.
                # - -item[1]: Sorts by run count descending (negated for ascending sort on negative numbers)
            )

            # Build the breakdown string from sorted items
            breakdown_parts = [
                f"{'🔸 ' if selected_class_lower and cn.lower() == selected_class_lower else ''}{cn.capitalize()}: {count}" 
                for cn, count in sorted_items
            ]
            breakdown_str = " | ".join(breakdown_parts) if breakdown_parts else ""

            base_message = (

                f"{target_ign} (CA {current_ca:.2f}) -> Target CA {target_level}: "
                f"Needs approx {total_runs_simulated:,} {selected_floor_name} runs "
            )

            output_message = base_message + breakdown_str

            # Check length and potentially remove breakdown if too long
            if len(output_message) > constants.MAX_MESSAGE_LENGTH:
                print("[WARN][RtcaCmd] Output message with breakdown too long. Sending without breakdown.")
                output_message = base_message # Fallback to message without breakdown

            await self._send_message(ctx, output_message)
            # --- End Format and Send Output ---

        except Exception as e:
            print(f"[ERROR][RtcaCmd] Unexpected error calculating RTCA for {ign}: {e}")
            traceback.print_exc()
            await self._send_message(ctx, f"An unexpected error occurred while calculating RTCA for '{target_ign}'.")

    @commands.command(name='currdungeon')
    async def currdungeon_command(self, ctx: commands.Context, *, args: str | None = None):
        """Checks if a player finished a dungeon run in the last 10 minutes.
        Syntax: #currdungeon <username> [profile_name]
        """
        print(f"[COMMAND] CurrDungeon command triggered by {ctx.author.name}: {args}")

        # --- 1. Determine Target IGN ---
        target_ign = ign if ign else ctx.author.name
        target_ign = target_ign.lstrip('@') # Remove potential @ prefix
        print(f"[INFO][CurrDungeonCmd] Target player: {target_ign}")
        # -----------------------------

        # --- 2. Fetch Player Profile ---
        profile_data = await self._get_player_profile_data(ctx, target_ign) # Use cleaned target_ign
        if not profile_data:
            return # Error message already sent by helper
        _fetched_ign, player_uuid, latest_profile = profile_data # Use _ign as target_ign might differ slightly (case)
        profile_name = latest_profile.get('cute_name', 'Unknown')
        # -----------------------------

        try:
            # --- 3. Find Latest Run ---
            member_data = latest_profile.get('members', {}).get(player_uuid, {})
            dungeons_data = member_data.get('dungeons', {})
            treasures_data = dungeons_data.get('treasures', None)
            runs_list = treasures_data.get('runs', []) if treasures_data else [] # Default to empty list

            if not runs_list:
                print(f"[INFO][CurrDungeonCmd] No runs found for {target_ign} in profile {profile_name}.")
                await self._send_message(ctx, f"'{target_ign}' has no recorded dungeon runs in profile '{profile_name}'.")
                return

            latest_run = None
            max_ts = 0
            for run in runs_list:
                if isinstance(run, dict):
                     current_ts = run.get('completion_ts', 0)
                     if isinstance(current_ts, (int, float)) and current_ts > max_ts:
                         max_ts = current_ts
                         latest_run = run

            if latest_run is None:
                print(f"[INFO][CurrDungeonCmd] Could not determine the latest run for {target_ign} (no valid timestamps).")
                await self._send_message(ctx, f"Could not find a valid latest run for '{target_ign}' in profile '{profile_name}'.")
                return
            # -----------------------------

            # --- 4. Check Run Recency ---
            completion_timestamp_ms = latest_run.get('completion_ts', 0)
            current_time_sec = datetime.now().timestamp()
            completion_time_sec = completion_timestamp_ms / 1000.0
            time_diff_sec = current_time_sec - completion_time_sec

            print(f"[DEBUG][CurrDungeonCmd] Latest Run TS: {completion_time_sec}, Current TS: {current_time_sec}, Diff: {time_diff_sec:.2f} sec")

            if time_diff_sec > 600: # More than 10 minutes
                await self._send_message(ctx, f"{target_ign} didn't finish a run in the last 10min.")
                return
            # -----------------------------

            # --- 5. Format Output for Recent Run ---
            # Format relative time
            relative_time_str = self._format_relative_time(time_diff_sec)

            # Format run type
            dungeon_type = latest_run.get('dungeon_type', 'Unknown Type')
            dungeon_tier = latest_run.get('dungeon_tier', '?')
            run_info = self._format_run_type(dungeon_type, dungeon_tier)

            # Format teammates
            participants_data = latest_run.get('participants', [])
            teammate_strings = []
            target_ign_lower = target_ign.lower() # Lowercase for comparison
            if isinstance(participants_data, list):
                for participant in participants_data:
                     if isinstance(participant, dict):
                         raw_name = participant.get('display_name')
                         if raw_name:
                             parsed_teammate = self._parse_participant(raw_name, target_ign_lower)
                             if parsed_teammate: # Add only if parsing succeeded and it's not the target player
                                 teammate_strings.append(parsed_teammate)

            teammates_str = ", ".join(teammate_strings) if teammate_strings else "No other participants listed"

            # Construct final message
            output_message = (
                f"{target_ign}'s last run was {run_info} finished {relative_time_str}. "
                f"Teammates: {teammates_str}"
            )
            await self._send_message(ctx, output_message)
            # -----------------------------

        except Exception as e:
             print(f"[ERROR][CurrDungeonCmd] Unexpected error processing current run for {target_ign}: {e}")
             traceback.print_exc()
             await self._send_message(ctx, f"An unexpected error occurred while checking the current run for '{target_ign}'.")

    @commands.command(name='runstillcata')
    async def runstillcata_command(self, ctx: commands.Context, *, args: str | None = None):
        """Shows how many M6/M7 runs are needed until the next Catacombs level.
        Syntax: #runstillcata <username> [profile_name] [target_level] [floor=m7]
        """
        print(f"[COMMAND] RunsTillCata command triggered by {ctx.author.name}: {args}")

        # --- 1. Argument Parsing ---
        ign: str | None = None
        requested_profile_name: str | None = None
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

    # --- Helper Methods (Add these within the TwitchCog class) ---

    def _format_relative_time(self, time_diff_sec: float) -> str:
        """Formats a time difference in seconds into 'X seconds/minutes ago'."""
        if time_diff_sec < 60:
            seconds_ago = round(time_diff_sec)
            # Handle pluralization correctly
            return f"{seconds_ago} second{'s' if seconds_ago != 1 else ''} ago"
        else:
            minutes_ago = math.floor(time_diff_sec / 60)
            # Handle pluralization correctly
            return f"{minutes_ago} minute{'s' if minutes_ago != 1 else ''} ago"

    def _format_run_type(self, dungeon_type: str, dungeon_tier: str | int) -> str:
        """Formats dungeon type and tier into F{tier} or M{tier}."""
        dtype_lower = dungeon_type.lower()
        if dtype_lower == 'catacombs':
            return f"F{dungeon_tier}"
        elif dtype_lower == 'master_catacombs':
            return f"M{dungeon_tier}"
        else:
            # Fallback for unexpected dungeon types
            return f"{dungeon_type.capitalize()} {dungeon_tier}"

    def _parse_participant(self, raw_display_name: str, target_ign_lower: str) -> str | None:
        """Parses participant display name, cleans it, and extracts info.
        Returns 'Username (Class Level)' or None if it's the target player or parsing fails."""
        try:
            # 1. Remove color codes
            cleaned_name = re.sub(r'§[0-9a-fk-or]', '', raw_display_name)
            # 2. Split username and class info
            parts = cleaned_name.split(':', 1)
            username_part = parts[0].strip()

            # 3. Skip the target player themselves (case-insensitive)
            if username_part.lower() == target_ign_lower:
                return None

            # 4. Extract Class Name and Level (if available)
            final_class = 'Unknown'
            final_level = '?'
            if len(parts) > 1:
                class_info_part = parts[1].strip() # e.g., "Tank (50)"
                class_match = re.match(r'^([a-zA-Z]+)', class_info_part)
                if class_match:
                    final_class = class_match.group(1)
                level_match = re.search(r'\((\d+)\)', class_info_part)
                if level_match:
                    final_level = level_match.group(1)

            if username_part:
                return f"{username_part} ({final_class} {final_level})"
            else:
                return None # Return None if username part is empty after cleaning
        except Exception as e:
            print(f"[WARN][CurrDungeon] Error parsing participant '{raw_display_name}': {e}")
            return None # Return None on any parsing error

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
