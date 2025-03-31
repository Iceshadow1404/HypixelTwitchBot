# twitch.py
import asyncio
import json
import traceback
from datetime import datetime
import math
import re

import aiohttp
from twitchio.ext import commands

import constants
import utils
from calculations import _get_xp_for_target_level, calculate_hotm_level, \
    calculate_average_skill_level, calculate_dungeon_level, calculate_class_level, calculate_slayer_level, format_price
from utils import _find_latest_profile, _get_uuid_from_ign, _get_skyblock_data


class Bot(commands.Bot):
    """
    Twitch Bot for interacting with Hypixel SkyBlock API and providing commands.
    """
    def __init__(self, token: str, prefix: str, nickname: str, initial_channels: list[str], hypixel_api_key: str | None):
        """Initializes the Bot."""
        self.start_time = datetime.now()
        self.hypixel_api_key = hypixel_api_key
        self.leveling_data = utils._load_leveling_data()

        super().__init__(token=token, prefix=prefix, nick=nickname, initial_channels=initial_channels)
        print(f"[INFO] Bot initialized for channels: {initial_channels}")

    # --- Helper Methods ---

    async def _get_player_profile_data(self, ctx: commands.Context, ign: str | None) -> tuple[str, str, dict] | None:
        """
        Handles the common boilerplate for commands needing player profile data.
        Checks API key, gets UUID, fetches profiles, finds latest profile.
        Sends error messages to chat if steps fail.
        Returns (target_ign, player_uuid, latest_profile_data) or None if an error occurred.
        """
        if not self.hypixel_api_key:
            # Use direct ctx.send for initial API key check as _send_message might fail early
            await ctx.send("Hypixel API is not configured. Please check the .env file.")
            return None

        target_ign = ign if ign else ctx.author.name
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

        latest_profile = _find_latest_profile(profiles, player_uuid)
        if not latest_profile:
            # Use _send_message for this potentially delayed error message
            await self._send_message(ctx, f"Could not find an active profile for '{target_ign}'. Player must be a member of at least one profile.")
            return None

        return target_ign, player_uuid, latest_profile

    # --- Bot Events ---

    async def event_ready(self):
        """Called once the bot has successfully connected to Twitch."""
        try:
            print("[INFO] Bot starting up...")

            print(f'------')
            print(f'Logged in as: {self.nick} ({self.user_id})')
            connected_channel_names = [ch.name for ch in self.connected_channels]
            print(f'Connected to channels: {connected_channel_names}')
            print(f'------')

            if self.connected_channels:
                print(f"[INFO] Bot successfully connected to {len(self.connected_channels)} channel(s).")
                print("Bot is ready!")
            else:
                print("[WARN] Bot connected to Twitch but did not join any channels.")

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
        connected_channel_names = [ch.name for ch in self.connected_channels]
        if message.channel.name not in connected_channel_names:
            # print(f"[DEBUG] Ignored message from non-connected channel: #{message.channel.name}")
            return

        # Print received message for debugging
        # print(f"[MSG] #{message.channel.name} - {message.author.name}: {message.content}")

        # Process commands defined in this class
        await self.handle_commands(message)

    async def _send_message(self, ctx: commands.Context, message: str):
        """Helper function to send messages, incorporating workarounds for potential issues."""
        print(f"[DEBUG][Send] Attempting to send to #{ctx.channel.name}: {message[:100]}...") # Log first 100 chars
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
    async def skills_command(self, ctx: commands.Context, *, ign: str | None = None):
        """Shows the average SkyBlock skill level for a player."""
        profile_data = await self._get_player_profile_data(ctx, ign)
        if not profile_data:
            return # Error message already sent by helper

        target_ign, player_uuid, latest_profile = profile_data
        profile_name = latest_profile.get('cute_name', 'Unknown')

        try:
            average_level = calculate_average_skill_level(self.leveling_data, latest_profile, player_uuid)
            if average_level is not None:
                await self._send_message(ctx, f"{target_ign}'s Skill Average in profile '{profile_name}' is approximately {average_level:.2f}.")
            else:
                await self._send_message(ctx, f"Could not calculate skill level for '{target_ign}' in profile '{profile_name}'. Skill data might be missing.")
        except Exception as e:
            print(f"[ERROR][SkillsCmd] Unexpected error calculating skills: {e}")
            traceback.print_exc()
            await self._send_message(ctx, "An unexpected error occurred while calculating skill levels.")

    @commands.command(name='kuudra')
    async def kuudra_command(self, ctx: commands.Context, *, ign: str | None = None):
        """Shows Kuudra completions for different tiers and calculates a score."""
        profile_data = await self._get_player_profile_data(ctx, ign)
        if not profile_data:
            return # Error message already sent by helper

        target_ign, player_uuid, latest_profile = profile_data
        profile_name = latest_profile.get('cute_name', 'Unknown')

        try:
            member_data = latest_profile.get('members', {}).get(player_uuid, {})
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

    @commands.command(name='auctions', aliases=['ah'])
    async def auctions_command(self, ctx: commands.Context, *, ign: str | None = None):
        """Shows active auctions for a player, limited by character count."""
        if not self.hypixel_api_key: # API key check needed here as it uses a different endpoint helper
            await ctx.send("Hypixel API is not configured.")
            return

        target_ign = ign if ign else ctx.author.name
        target_ign = target_ign.lstrip('@')
        await ctx.send(f"Searching active auctions for '{target_ign}'...")

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
    async def dungeon_command(self, ctx: commands.Context, *, ign: str | None = None):
        """Shows the player's Catacombs level and XP."""
        profile_data = await self._get_player_profile_data(ctx, ign)
        if not profile_data:
            return

        target_ign, player_uuid, latest_profile = profile_data
        profile_name = latest_profile.get('cute_name', 'Unknown')

        try:
            member_data = latest_profile.get('members', {}).get(player_uuid, {})
            dungeons_data = member_data.get('dungeons', {}).get('dungeon_types', {}).get('catacombs', {})
            catacombs_xp = dungeons_data.get('experience', 0)

            level = calculate_dungeon_level(self.leveling_data, catacombs_xp)
            await self._send_message(ctx, f"{target_ign}'s Catacombs level in profile '{profile_name}' is {level:.2f} (XP: {catacombs_xp:,.0f})")

        except Exception as e:
            print(f"[ERROR][DungeonCmd] Unexpected error processing dungeon data: {e}")
            traceback.print_exc()
            await self._send_message(ctx, "An unexpected error occurred while fetching Catacombs level.")

    @commands.command(name='sblvl')
    async def sblvl_command(self, ctx: commands.Context, *, ign: str | None = None):
        """Shows the player's SkyBlock level (based on XP/100)."""
        profile_data = await self._get_player_profile_data(ctx, ign)
        if not profile_data:
            return

        target_ign, player_uuid, latest_profile = profile_data
        profile_name = latest_profile.get('cute_name', 'Unknown')

        try:
            member_data = latest_profile.get('members', {}).get(player_uuid, {})
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
    async def classaverage_command(self, ctx: commands.Context, *, ign: str | None = None):
        """Shows the player's dungeon class levels and their average."""
        profile_data = await self._get_player_profile_data(ctx, ign)
        if not profile_data:
            return

        target_ign, player_uuid, latest_profile = profile_data
        profile_name = latest_profile.get('cute_name', 'Unknown')

        try:
            member_data = latest_profile.get('members', {}).get(player_uuid, {})
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
        await ctx.send("Fetching current SkyBlock Mayor...")

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
    async def bank_command(self, ctx: commands.Context, *, ign: str | None = None):
        """Shows the player's bank, purse, and personal bank balance."""
        profile_data = await self._get_player_profile_data(ctx, ign)
        if not profile_data:
            return

        target_ign, player_uuid, latest_profile = profile_data
        profile_name = latest_profile.get('cute_name', 'Unknown')

        try:
            # Bank Balance (Profile wide)
            banking_data = latest_profile.get('banking', {})
            bank_balance = banking_data.get('balance', 0.0)

            # Purse and Personal Bank (Member specific)
            member_data = latest_profile.get('members', {}).get(player_uuid, {})
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
    async def nucleus_command(self, ctx: commands.Context, *, ign: str | None = None):
        """Shows the calculated Nucleus runs based on placed crystals."""
        profile_data = await self._get_player_profile_data(ctx, ign)
        if not profile_data:
            return

        target_ign, player_uuid, latest_profile = profile_data
        profile_name = latest_profile.get('cute_name', 'Unknown')

        try:
            member_data = latest_profile.get('members', {}).get(player_uuid, {})
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
    async def hotm_command(self, ctx: commands.Context, *, ign: str | None = None):
        """Shows the player's Heart of the Mountain level."""
        profile_data = await self._get_player_profile_data(ctx, ign)
        if not profile_data:
             return

        target_ign, player_uuid, latest_profile = profile_data
        profile_name = latest_profile.get('cute_name', 'Unknown')

        try:
            member_data = latest_profile.get('members', {}).get(player_uuid, {})
            mining_core_data = member_data.get('mining_core', {})
            hotm_xp = mining_core_data.get('experience', 0.0)

            level = calculate_hotm_level(self.leveling_data, hotm_xp)
            await self._send_message(ctx, f"{target_ign}'s HotM level is {level:.2f} (XP: {hotm_xp:,.0f})")

        except Exception as e:
            print(f"[ERROR][HotmCmd] Unexpected error processing HotM data: {e}")
            traceback.print_exc()
            await self._send_message(ctx, "An unexpected error occurred while fetching HotM level.")

    @commands.command(name='essence')
    async def essence_command(self, ctx: commands.Context, *, ign: str | None = None):
        """Shows the player's essence amounts."""
        profile_data = await self._get_player_profile_data(ctx, ign)
        if not profile_data:
             return

        target_ign, player_uuid, latest_profile = profile_data
        profile_name = latest_profile.get('cute_name', 'Unknown')

        try:
            member_data = latest_profile.get('members', {}).get(player_uuid, {})
            currencies_data = member_data.get('currencies', {})

            # Get the main essence container
            all_essence_data = currencies_data.get('essence', {})

            if not all_essence_data:
                print(f"[INFO][EssenceCmd] No essence data found for {target_ign} in profile {profile_name}.")
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

            output_message = f"{target_ign}: { ' | '.join(essence_amounts) }"
            await self._send_message(ctx, output_message)

        except Exception as e:
            print(f"[ERROR][EssenceCmd] Unexpected error processing essence data: {e}")
            traceback.print_exc()
            await self._send_message(ctx, "An unexpected error occurred while fetching essences.")

    @commands.command(name='powder')
    async def powder_command(self, ctx: commands.Context, *, ign: str | None = None):
        """Shows the player's current and total Mithril and Gemstone powder."""
        profile_data = await self._get_player_profile_data(ctx, ign)
        if not profile_data:
            return

        target_ign, player_uuid, latest_profile = profile_data
        profile_name = latest_profile.get('cute_name', 'Unknown')

        try:
            member_data = latest_profile.get('members', {}).get(player_uuid, {})
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
    async def slayer_command(self, ctx: commands.Context, *, ign: str | None = None):
        """Shows the player's slayer levels."""
        profile_data = await self._get_player_profile_data(ctx, ign)
        if not profile_data:
            return

        target_ign, player_uuid, latest_profile = profile_data
        profile_name = latest_profile.get('cute_name', 'Unknown')

        try:
            member_data = latest_profile.get('members', {}).get(player_uuid, {})
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

            output_message = f"{target_ign}'s Slayers: { ' | '.join(slayer_levels) }"
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
        Syntax: #rtca <username> [target_ca=50] [floor=m7]
        Simulates runs considering 100% active XP / 25% passive XP.
        """
        print(f"[COMMAND] Rtca command triggered by {ctx.author.name}: {args}")
        # Removed early return if not args

        # --- 1. Argument Parsing ---
        ign: str | None = None
        target_ca_str: str = '50' # Default target CA
        floor_str: str = 'm7'   # Default floor

        if not args:
            ign = ctx.author.name # Default to message author if no args provided
            print(f"[DEBUG][RtcaCmd] No arguments provided, defaulting IGN to: {ign}")
        else:
            parts = args.split()
            ign = parts[0] # First part is always IGN if args are provided
            print(f"[DEBUG][RtcaCmd] Arguments provided, parsed IGN: {ign}")

            # Only attempt to parse target_ca and floor if more than one part exists
            if len(parts) > 1:
                target_ca_str = parts[1]
                print(f"[DEBUG][RtcaCmd] Parsed target_ca_str: {target_ca_str}")
            if len(parts) > 2:
                floor_str = parts[2].lower() # Normalize floor to lowercase
                print(f"[DEBUG][RtcaCmd] Parsed floor_str: {floor_str}")
            if len(parts) > 3:
                 await self._send_message(ctx, f"Too many arguments. Usage: {self._prefix}rtca <username> [target_ca=50] [floor=m7]")
                 return

        # --- Argument Validation (Moved here to run after potential defaulting) ---
        try:
            # Validate target_ca
            target_ca_milestone = int(target_ca_str)
            if not 1 <= target_ca_milestone <= 50:
                raise ValueError("Target CA must be between 1 and 50.")
            print(f"[DEBUG][RtcaCmd] Validated target_ca_milestone: {target_ca_milestone}")

            # Validate floor
            if floor_str not in ['m6', 'm7']:
                 raise ValueError("Invalid floor. Please specify 'm6' or 'm7'.")
            print(f"[DEBUG][RtcaCmd] Validated floor_str: {floor_str}")

        except ValueError as e:
            await self._send_message(ctx, f"Invalid argument: {e}. Usage: {self._prefix}rtca <username> [target_ca=50] [floor=m7]")
            return
        # --- End Argument Parsing & Validation ---

        # --- 2. Fetch Player Data ---
        # ign is guaranteed to be set here, either from default or parsing
        profile_data = await self._get_player_profile_data(ctx, ign)
        if not profile_data:
            return # Error message already sent by helper

        target_ign, player_uuid, latest_profile = profile_data
        profile_name = latest_profile.get('cute_name', 'Unknown')
        # --- End Fetch Player Data ---

        try:
            member_data = latest_profile.get('members', {}).get(player_uuid, {})
            dungeons_data = member_data.get('dungeons', {})
            player_classes_data = dungeons_data.get('player_classes', None)
            # --- Fetch Selected Class --- (Moved extraction here)
            selected_class = dungeons_data.get('selected_dungeon_class')
            selected_class_lower = selected_class.lower() if selected_class else None # Lowercase for comparison
            print(f"[DEBUG][RtcaCmd] Fetched selected class: {selected_class}")
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
                level = calculate_class_level(self.leveling_data, class_xp)  # Uses Catacombs table, max 50
                current_class_levels[class_name] = level
                class_xps[class_name] = class_xp
                total_level_sum += level
            
            current_ca = total_level_sum / len(constants.CLASS_NAMES) if constants.CLASS_NAMES else 0.0
            print(f"[DEBUG][RtcaCmd] {target_ign} - Current CA: {current_ca:.2f}, Target CA: {target_ca_milestone}")

            # Check if target is already reached
            if current_ca >= target_ca_milestone:
                 await self._send_message(ctx, f"{target_ign} (CA {current_ca:.2f}) has already reached or surpassed the target Class Average {target_ca_milestone}.")
                 return
            # --- End Calculate Current State ---

            # --- 4. Setup Simulation Parameters ---
            target_level_for_milestone = target_ca_milestone # Target level for each class is the target CA

            # Determine XP per run based on selected floor
            if floor_str == 'm6':
                xp_per_run = constants.BASE_M6_CLASS_XP
                selected_floor_name = "M6"
            else: # Default or 'm7'
                xp_per_run = constants.BASE_M7_CLASS_XP
                selected_floor_name = "M7"
                
            # --- TEMPORARY TEST: Increase XP by 10% ---
            xp_per_run *= 1.06
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
                await self._send_message(ctx, f"{target_ign} already meets the XP requirements for CA {target_ca_milestone}. Runs needed: 0")
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
                    runs_if_active = math.ceil(needed / xp_per_run)
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
                key=lambda item: (item[0].lower() != selected_class_lower, -item[1])
                # Explanation:
                # - item[0].lower() != selected_class_lower:
                #   This is False (sorts first) if item[0] IS the selected class.
                #   This is True (sorts later) if item[0] is NOT the selected class.
                # - -item[1]: Sorts by run count descending (negated for ascending sort on negative numbers)
            )

            # Build the breakdown string from sorted items
            breakdown_parts = [
                f"{'🔸 ' if cn.lower() == selected_class_lower else ''}{cn.capitalize()}: {count}" 
                for cn, count in sorted_items
            ]
            breakdown_str = " | ".join(breakdown_parts) if breakdown_parts else ""

            base_message = (

                f"{target_ign} (CA {current_ca:.2f}) -> Target CA {target_ca_milestone}: "
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
    async def currdungeon_command(self, ctx: commands.Context, *, ign: str | None = None):
        """Checks if a player finished a dungeon run in the last 10 minutes."""
        print(f"[COMMAND] CurrDungeon command triggered by {ctx.author.name}: {ign}")

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
        Syntax: #runstillcata <username> [target_level] [floor=m7]
        """
        print(f"[COMMAND] RunsTillCata command triggered by {ctx.author.name}: {args}")

        # --- 1. Argument Parsing ---
        ign: str | None = None
        target_level_str: str | None = None
        floor_str: str = 'm7'   # Default floor

        if not args:
            ign = ctx.author.name # Default to message author if no args provided
            print(f"[DEBUG][RunsTillCataCmd] No arguments provided, defaulting IGN to: {ign}")
        else:
            parts = args.split()
            ign = parts[0] # First part is always IGN if args are provided
            print(f"[DEBUG][RunsTillCataCmd] Arguments provided, parsed IGN: {ign}")

            # Only attempt to parse target_level and floor if more than one part exists
            if len(parts) > 1:
                target_level_str = parts[1]
                print(f"[DEBUG][RunsTillCataCmd] Parsed target_level_str: {target_level_str}")
            if len(parts) > 2:
                floor_str = parts[2].lower() # Normalize floor to lowercase
                print(f"[DEBUG][RunsTillCataCmd] Parsed floor_str: {floor_str}")
            if len(parts) > 3:
                await self._send_message(ctx, f"Too many arguments. Usage: {self._prefix}runstillcata <username> [target_level] [floor=m7]")
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
            await self._send_message(ctx, f"Invalid argument: {e}. Usage: {self._prefix}runstillcata <username> [target_level] [floor=m7]")
            return
        # --- End Argument Parsing & Validation ---

        # --- 2. Get Player Data ---
        profile_data = await self._get_player_profile_data(ctx, ign)
        if not profile_data:
            return # Error message already sent by helper

        target_ign, player_uuid, latest_profile = profile_data
        profile_name = latest_profile.get('cute_name', 'Unknown')

        try:
            # --- 3. Get Current Catacombs XP and Level ---
            member_data = latest_profile.get('members', {}).get(player_uuid, {})
            dungeons_data = member_data.get('dungeons', {}).get('dungeon_types', {}).get('catacombs', {})
            current_xp = dungeons_data.get('experience', 0)
            current_level = calculate_dungeon_level(self.leveling_data, current_xp)
            
            # --- 4. Calculate XP for Target Level ---
            if target_level is None:
                # If no target level provided, use next level
                target_level = math.ceil(current_level)
            xp_for_target_level = _get_xp_for_target_level(self.leveling_data, target_level)
            xp_needed = xp_for_target_level - current_xp

            if xp_needed <= 0:
                await self._send_message(ctx, f"{target_ign} has already reached Catacombs level {target_level}!")
                return

            # --- 5. Calculate Runs Needed for Selected Floor ---
            if floor_str == 'm6':
                runs_needed = math.ceil(xp_needed / 180000)  # 180k XP per M6 run
                floor_name = "M6"
            else:  # m7
                runs_needed = math.ceil(xp_needed / 500000)  # 500k XP per M7 run
                floor_name = "M7"

            # --- 6. Format and Send Output ---
            output_message = (
                f"{target_ign} (Cata {current_level:.2f}) needs {xp_needed:,.0f} XP for level {target_level}. "
                f"{floor_name}: {runs_needed:,} runs ({180000 if floor_str == 'm6' else 500000:,} XP/run)"
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

    async def _get_current_mayor_name(self) -> str | None:
        if not self.hypixel_api_key:
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(constants.HYPIXEL_ELECTION_URL) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("success"):
                            mayor_data = data.get('mayor')
                            if mayor_data:
                                return mayor_data.get('name', 'Unknown')
                            else:
                                return None
                        else:
                            return None
                    else:
                        return None
        except Exception as e:
            print(f"[ERROR][MayorCmd] Network error fetching election data: {e}")
            return None
