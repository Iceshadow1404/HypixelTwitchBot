# twitch.py
import asyncio
import json
import os
import traceback
from datetime import datetime

import aiohttp
from twitchio.ext import commands

# --- Constants ---
CUSTOM_COMMANDS_FILE = 'custom_commands.json'
MOJANG_API_URL = "https://mowojang.matdoes.dev/{username}"
HYPIXEL_API_URL = "https://api.hypixel.net/v2/skyblock/profiles"
HYPIXEL_AUCTION_URL = "https://api.hypixel.net/v2/skyblock/auction"
HYPIXEL_ELECTION_URL = "https://api.hypixel.net/v2/resources/skyblock/election"

AVERAGE_SKILLS_LIST = [
    'farming', 'mining', 'combat', 'foraging', 'fishing',
    'enchanting', 'alchemy', 'taming', 'carpentry'
]
KUUDRA_TIERS_ORDER = ['none', 'hot', 'burning', 'fiery', 'infernal']
KUUDRA_TIER_POINTS = {'none': 1, 'hot': 2, 'burning': 3, 'fiery': 4, 'infernal': 5}
CLASS_NAMES = ['healer', 'mage', 'berserk', 'archer', 'tank']
NUCLEUS_CRYSTALS = ['amber_crystal', 'topaz_crystal', 'amethyst_crystal', 'jade_crystal', 'sapphire_crystal']

MAX_MESSAGE_LENGTH = 480 # Approx limit to avoid Twitch cutting messages

class Bot(commands.Bot):
    """
    Twitch Bot for interacting with Hypixel SkyBlock API and providing commands.
    """
    def __init__(self, token: str, prefix: str, nickname: str, initial_channels: list[str], hypixel_api_key: str | None):
        """Initializes the Bot."""
        self.start_time = datetime.now()
        self.hypixel_api_key = hypixel_api_key
        self.leveling_data = self._load_leveling_data()
        # Load custom commands (implementation missing in provided snippet, assuming it exists)
        # self.custom_commands = self._load_custom_commands()

        super().__init__(token=token, prefix=prefix, nick=nickname, initial_channels=initial_channels)
        print(f"[INFO] Bot initialized for channels: {initial_channels}")

    # --- Helper Methods ---

    def _load_leveling_data(self) -> dict:
        """Loads leveling data from leveling.json."""
        try:
            with open('leveling.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"[INFO] Loaded leveling data. Catacombs XP table length: {len(data.get('catacombs', []))}")
                return {
                    'xp_table': data.get('leveling_xp', []),
                    'level_caps': data.get('leveling_caps', {}),
                    'catacombs_xp': data.get('catacombs', [])
                }
        except FileNotFoundError:
            print("[ERROR] leveling.json not found. Level calculations will fail.")
            return {'xp_table': [], 'level_caps': {}, 'catacombs_xp': []}
        except json.JSONDecodeError as e:
             print(f"[ERROR] Error decoding leveling.json: {e}. Level calculations will fail.")
             return {'xp_table': [], 'level_caps': {}, 'catacombs_xp': []}
        except Exception as e:
            print(f"[ERROR] Unexpected error loading leveling.json: {e}")
            traceback.print_exc()
            return {'xp_table': [], 'level_caps': {}, 'catacombs_xp': []}

    def _find_latest_profile(self, profiles: list, player_uuid: str) -> dict | None:
        """Finds the most recently played profile for a player from a list of profiles."""
        print(f"[DEBUG][Profile] Searching profile for UUID {player_uuid} from {len(profiles)} profiles.")
        if not profiles:
            print("[DEBUG][Profile] No profiles to search.")
            return None

        # Check for 'selected' profile first
        for profile in profiles:
            cute_name = profile.get('cute_name', 'Unknown')
            if profile.get('selected', False) and player_uuid in profile.get('members', {}):
                print(f"[DEBUG][Profile] Found selected profile: '{cute_name}'")
                return profile

        # If no 'selected' profile, find the one with the latest 'last_save' for the member
        latest_profile = None
        latest_save = 0
        for profile in profiles:
            cute_name = profile.get('cute_name', 'Unknown')
            member_data = profile.get('members', {}).get(player_uuid)
            if member_data:
                last_save = member_data.get('last_save', 0)
                if last_save > latest_save:
                    latest_save = last_save
                    latest_profile = profile
                    print(f"[DEBUG][Profile] Found newer profile: '{cute_name}' (Last Save: {last_save})")

        if latest_profile:
            print(f"[DEBUG][Profile] Latest profile selected: '{latest_profile.get('cute_name')}'")
            return latest_profile

        print(f"[DEBUG][Profile] No suitable profile found for UUID {player_uuid}.")
        return None

    async def _get_uuid_from_ign(self, username: str) -> str | None:
        """Gets the Minecraft UUID for a given username using Mojang API."""
        url = MOJANG_API_URL.format(username=username)
        print(f"[DEBUG][API] Mojang request for '{username}'...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        uuid = data.get('id')
                        if not uuid:
                            print(f"[WARN][API] Mojang API: No UUID found for '{username}'.")
                        return uuid
                    elif response.status == 204: # No content -> User not found
                        print(f"[WARN][API] Mojang API: Username '{username}' not found.")
                        return None
                    else:
                        print(f"[ERROR][API] Mojang API error: Status {response.status}")
                        return None
        except aiohttp.ClientError as e:
            print(f"[ERROR][API] Network error during Mojang API request: {e}")
            return None
        except Exception as e:
            print(f"[ERROR][API] Unexpected error during Mojang API request: {e}")
            traceback.print_exc()
            return None

    async def _get_skyblock_data(self, uuid: str) -> list | None:
        """Gets SkyBlock profile data for a given UUID using Hypixel API."""
        if not self.hypixel_api_key:
            print("[ERROR][API] Hypixel API Key not configured.")
            return None

        params = {"key": self.hypixel_api_key, "uuid": uuid}
        print(f"[DEBUG][API] Hypixel profiles request for UUID '{uuid}'...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(HYPIXEL_API_URL, params=params) as response:
                    print(f"[DEBUG][API] Hypixel profiles response status: {response.status}")
                    response_text = await response.text() # Read text first for debugging
                    if response.status == 200:
                        try:
                            data = json.loads(response_text)
                            # Save the full response for debugging
                            debug_file = f"hypixel_response_{uuid}.json"
                            try:
                                with open(debug_file, 'w', encoding='utf-8') as f:
                                    json.dump(data, f, indent=4)
                                print(f"[DEBUG][API] Hypixel response saved to '{debug_file}'.")
                            except IOError as io_err:
                                 print(f"[WARN][API] Failed to save debug file '{debug_file}': {io_err}")

                            if data.get("success"):
                                profiles = data.get('profiles')
                                if profiles is None:
                                     print(f"[WARN][API] Hypixel API success, but 'profiles' field is missing or null for {uuid}.")
                                     return [] # Return empty list instead of None if success=true but no profiles
                                if not isinstance(profiles, list):
                                    print(f"[ERROR][API] Hypixel API success, but 'profiles' is not a list ({type(profiles)}).")
                                    return None
                                return profiles
                            else:
                                reason = data.get('cause', 'Unknown reason')
                                print(f"[ERROR][API] Hypixel API request failed: {reason}")
                                return None
                        except json.JSONDecodeError as json_e:
                            print(f"[ERROR][API] Error decoding Hypixel JSON response: {json_e}")
                            print(f"--- Response Text Start ---\n{response_text}\n--- Response Text End ---")
                            return None
                    else:
                        print(f"[ERROR][API] Hypixel API request failed: Status {response.status}")
                        print(f"--- Response Text Start ---\n{response_text}\n--- Response Text End ---")
                        return None
        except aiohttp.ClientError as e:
            print(f"[ERROR][API] Network error during Hypixel API request: {e}")
            return None
        except Exception as e:
            print(f"[ERROR][API] Unexpected error during Hypixel API request: {e}")
            traceback.print_exc()
            return None

    async def _get_player_profile_data(self, ctx: commands.Context, ign: str | None) -> tuple[str, str, dict] | None:
        """
        Handles the common boilerplate for commands needing player profile data.
        Checks API key, session, gets UUID, fetches profiles, finds latest profile.
        Sends error messages to chat if steps fail.
        Returns (target_ign, player_uuid, latest_profile_data) or None if an error occurred.
        """
        if not self.hypixel_api_key:
            await ctx.send("Hypixel API is not configured. Please check the .env file.")
            return None

        target_ign = ign if ign else ctx.author.name
        target_ign = target_ign.lstrip('@')
        await ctx.send(f"Searching data for '{target_ign}'...") # Generic initial message

        player_uuid = await self._get_uuid_from_ign(target_ign)
        if not player_uuid:
            await ctx.send(f"Could not find Minecraft account for '{target_ign}'. Please check the username.")
            return None

        profiles = await self._get_skyblock_data(player_uuid)
        if profiles is None: # API error occurred
            await ctx.send(f"Could not fetch SkyBlock profiles for '{target_ign}'. An API error occurred.")
            return None
        if not profiles: # API succeeded but returned no profiles
            await ctx.send(f"'{target_ign}' seems to have no SkyBlock profiles yet.")
            return None

        latest_profile = self._find_latest_profile(profiles, player_uuid)
        if not latest_profile:
            await ctx.send(f"Could not find an active profile for '{target_ign}'. Player must be a member of at least one profile.")
            return None

        return target_ign, player_uuid, latest_profile


    # --- Calculation Methods ---

    def calculate_skill_level(self, xp: float, skill_name: str, member_data: dict | None = None) -> float:
        """Calculates the level of a skill based on XP, considering level caps and special skills."""
        if not self.leveling_data['xp_table']:
            return 0.0

        # Determine base max level (usually 50 or 60)
        base_max_level = self.leveling_data['level_caps'].get(skill_name, 50)
        xp_table_to_use = self.leveling_data['xp_table'] # Use standard XP table

        # Calculate effective max level considering special rules
        effective_max_level = base_max_level
        if skill_name == 'taming' and member_data:
            pets_data = member_data.get('pets_data', {}).get('pet_care', {})
            sacrificed_count = len(pets_data.get('pet_types_sacrificed', []))
            effective_max_level = 50 + min(sacrificed_count, 10) # Cap bonus at +10
        elif skill_name == 'farming' and member_data:
            jacobs_perks = member_data.get('jacobs_contest', {}).get('perks', {})
            farming_level_cap_bonus = jacobs_perks.get('farming_level_cap', 0)
            effective_max_level = 50 + farming_level_cap_bonus

        # Calculate total XP required for the effective max level
        total_xp_for_max = sum(xp_table_to_use[:effective_max_level]) # Sum only up to the effective cap

        # If XP meets or exceeds the requirement for the max level, return max level
        if xp >= total_xp_for_max:
            return float(effective_max_level)

        # Find level based on XP progression
        total_xp_required = 0
        level = 0
        # Iterate only up to the XP required for levels below the effective max
        for i, required_xp in enumerate(xp_table_to_use):
            if i >= effective_max_level: # Stop if we exceed the effective max level index
                 break
            total_xp_required += required_xp
            if xp >= total_xp_required:
                level += 1
            else:
                # Calculate progress towards the next level
                current_level_xp = total_xp_required - required_xp
                next_level_xp_needed = required_xp
                if next_level_xp_needed > 0:
                    progress = (xp - current_level_xp) / next_level_xp_needed
                    # Ensure progress doesn't make level exceed effective max
                    calculated_level = level + progress
                    return min(calculated_level, float(effective_max_level))
                else: # Avoid division by zero if xp table is malformed
                    return min(float(level), float(effective_max_level))

        # If loop finishes, player is exactly max level or below
        return min(float(level), float(effective_max_level))


    def calculate_average_skill_level(self, profile: dict, player_uuid: str) -> float | None:
        """Calculates the average skill level, excluding cosmetics like Carpentry and Runecrafting if desired."""
        print(f"[DEBUG][Calc] Calculating Skill Average for profile {profile.get('profile_id', 'UNKNOWN')}")
        member_data = profile.get('members', {}).get(player_uuid)
        if not member_data:
            print(f"[WARN][Calc] Member data not found for {player_uuid} in profile.")
            return None

        experience_data = member_data.get('player_data', {}).get('experience', {})
        total_level_estimate = 0
        skills_counted = 0

        print("\n[DEBUG][Calc] Skill Levels:")
        print("-" * 40)

        for skill_name in AVERAGE_SKILLS_LIST: # Use the predefined list
            xp_field = f'SKILL_{skill_name.upper()}'
            skill_xp = experience_data.get(xp_field)

            if skill_xp is not None:
                level = self.calculate_skill_level(skill_xp, skill_name, member_data)
                total_level_estimate += level
                skills_counted += 1
                print(f"{skill_name.capitalize():<11}: {level:>5.2f} (XP: {skill_xp:,.0f})")
            else:
                # Still count skill as 0 if API doesn't provide XP (e.g., new skill)
                total_level_estimate += 0
                skills_counted += 1
                print(f"{skill_name.capitalize():<11}: {0.00:>5.2f} (XP: Not Available)")

        print("-" * 40)

        if skills_counted > 0:
            average = total_level_estimate / skills_counted
            print(f"[DEBUG][Calc] Skill Average calculated: {average:.4f}")
            return average
        else:
            print("[WARN][Calc] No skills counted for average calculation.")
            return 0.0

    def calculate_dungeon_level(self, xp: float) -> float:
        """Calculates the Catacombs level based on XP, including progress as decimal points."""
        if not self.leveling_data['catacombs_xp']:
            print("[WARN][Calc] Catacombs XP table not loaded.")
            return 0.0

        max_level = 100  # Catacombs max level
        xp_table = self.leveling_data['catacombs_xp']

        # Calculate total XP for max level (sum all entries)
        total_xp_for_max = sum(xp_table)

        if xp >= total_xp_for_max:
            return float(max_level)

        total_xp_required = 0
        level = 0
        for i, required_xp in enumerate(xp_table):
            if i >= max_level: # Should not happen if xp_table has 100 entries, but safety check
                break
            current_level_xp_threshold = total_xp_required
            total_xp_required += required_xp

            if xp >= total_xp_required:
                level += 1
            else:
                # Calculate progress within the current level
                xp_in_level = xp - current_level_xp_threshold
                xp_needed_for_level = required_xp
                if xp_needed_for_level > 0:
                    progress = xp_in_level / xp_needed_for_level
                    return level + progress
                else: # Avoid division by zero
                    return float(level)

        # If loop completes, player is exactly level 100 (or table is shorter than 100)
        return float(level)

    def calculate_class_level(self, xp: float) -> float:
        """Calculates the class level based on XP using the Catacombs XP table up to level 50."""
        if not self.leveling_data['catacombs_xp']:
            print("[WARN][Calc] Catacombs XP table not loaded for class calculation.")
            return 0.0

        max_class_level = 50
        # Use only the first 50 entries from the Catacombs XP table for class levels
        xp_table = self.leveling_data['catacombs_xp'][:max_class_level]

        total_xp_for_max_class_level = sum(xp_table)

        if xp >= total_xp_for_max_class_level:
            return float(max_class_level)

        total_xp_required = 0
        level = 0
        for i, required_xp in enumerate(xp_table):
            # No need to check i >= max_class_level due to slicing xp_table
            current_level_xp_threshold = total_xp_required
            total_xp_required += required_xp

            if xp >= total_xp_required:
                level += 1
            else:
                xp_in_level = xp - current_level_xp_threshold
                xp_needed_for_level = required_xp
                if xp_needed_for_level > 0:
                    progress = xp_in_level / xp_needed_for_level
                    return level + progress
                else:
                    return float(level)

        # If loop completes, player is exactly level 50
        return float(level)

    def format_price(self, price: int | float) -> str:
        """Formats a price into a shorter form (e.g., 1.3m instead of 1,300,000)."""
        price = float(price) # Ensure float for division
        if price >= 1_000_000_000:
            return f"{price / 1_000_000_000:.1f}b"
        elif price >= 1_000_000:
            return f"{price / 1_000_000:.1f}m"
        elif price >= 1_000:
            return f"{price / 1_000:.1f}k"
        else:
            return f"{price:.0f}" # Display small numbers as integers

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

        # Handle custom commands (if implementation exists)
        # await self.handle_custom_commands(message)

    # --- Commands ---

    @commands.command(name='ping')
    async def ping_command(self, ctx: commands.Context):
        """Responds with pong."""
        print(f"[COMMAND] Ping command received from {ctx.author.name} in #{ctx.channel.name}")
        await self._send_message(ctx, f'pong, {ctx.author.name}!')

    @commands.command(name='skills')
    async def skills_command(self, ctx: commands.Context, *, ign: str | None = None):
        """Shows the average SkyBlock skill level for a player."""
        profile_data = await self._get_player_profile_data(ctx, ign)
        if not profile_data:
            return # Error message already sent by helper

        target_ign, player_uuid, latest_profile = profile_data
        profile_name = latest_profile.get('cute_name', 'Unknown')

        try:
            average_level = self.calculate_average_skill_level(latest_profile, player_uuid)
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
            for tier in KUUDRA_TIERS_ORDER:
                count = kuudra_completed_tiers.get(tier, 0)
                tier_name = 'basic' if tier == 'none' else tier # Rename 'none' to 'basic'
                completions.append(f"{tier_name} {count}")
                total_score += count * KUUDRA_TIER_POINTS.get(tier, 0) # Use .get for safety

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
            player_uuid = await self._get_uuid_from_ign(target_ign)
            if not player_uuid:
                await ctx.send(f"Could not find Minecraft account for '{target_ign}'.")
                return

            # --- Fetch Auction Data ---
            url = HYPIXEL_AUCTION_URL
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

                price_str = self.format_price(highest_bid)
                auction_str = f"{item_name} {price_str}"

                # Check if adding the next item exceeds the limit
                separator = " | " if auction_list_parts else ""
                if len(current_message) + len(separator) + len(auction_str) <= MAX_MESSAGE_LENGTH:
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
                if len(final_message) + len(suffix) <= MAX_MESSAGE_LENGTH:
                     final_message += suffix

            await self._send_message(ctx, final_message)

        except Exception as e:
            print(f"[ERROR][AuctionsCmd] Unexpected error processing auctions: {e}")
            traceback.print_exc()
            await self._send_message(ctx, "An unexpected error occurred while fetching auctions.")

    @commands.command(name='dungeon', aliases=['dungeons'])
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

            level = self.calculate_dungeon_level(catacombs_xp)
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

            for class_name in CLASS_NAMES:
                class_xp = player_classes_data.get(class_name, {}).get('experience', 0)
                level = self.calculate_class_level(class_xp)
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
            await self._send_message(ctx, "Error connecting to external APIs.")
            return

        print(f"[DEBUG][API] Fetching SkyBlock election data from {HYPIXEL_ELECTION_URL}")
        await ctx.send("Fetching current SkyBlock Mayor...") # Initial feedback

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(HYPIXEL_ELECTION_URL) as response:
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

    @commands.command(name='bank', aliases=['purse', 'money', 'bal'])
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
            for crystal_key in NUCLEUS_CRYSTALS:
                crystal_info = crystals_data.get(crystal_key, {})
                total_placed = crystal_info.get('total_placed', 0)
                sum_total_placed += total_placed
                print(f"  - {crystal_key}: {total_placed}") # Debug print activated

            # Calculate result: sum divided by 5, rounded down
            nucleus_result = sum_total_placed // 5
            print(f"[DEBUG][NucleusCmd] Sum: {sum_total_placed}, Result (Sum // 5): {nucleus_result}")

            await self._send_message(ctx, f"{target_ign}'s nucleus runs: {nucleus_result})")

        except Exception as e:
            print(f"[ERROR][NucleusCmd] Unexpected error processing nucleus data: {e}")
            traceback.print_exc()
            await self._send_message(ctx, "An unexpected error occurred while fetching Nucleus runs.")

    @commands.command(name='testsend')
    async def testsend_command(self, ctx: commands.Context):
        """Sends a simple test message to check channel connectivity."""
        test_message = f"Simple test response for #{ctx.channel.name} at {datetime.now()}"
        print(f"[DEBUG][TestSendCmd] Attempting send: {test_message}")
        await self._send_message(ctx, test_message) # Use the helper send method

    # --- Cleanup ---
    async def close(self):
        """Gracefully shuts down the bot and closes sessions."""
        print("[INFO] Shutting down bot...")
        await super().close()
        print("[INFO] Bot connection closed.")