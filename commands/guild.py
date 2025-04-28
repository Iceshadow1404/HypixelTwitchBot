# commands/guild.py
import aiohttp
import traceback
from typing import Optional
from twitchio.ext import commands

import twitch

from utils import _parse_command_args

HYPIXEL_GUILD_API_URL = "https://api.hypixel.net/v2/guild"

class GuildCommand:
    def __init__(self, bot: 'twitch.IceBot'):
        self.bot = bot
        if not hasattr(bot, 'skyblock_client') or bot.skyblock_client is None:
            print("[GuildCommand][Error] SkyblockClient is not initialized in the bot!")

    async def _fetch_guild_data_by_uuid(self, uuid: str) -> Optional[dict]:
        """Fetches guild data from Hypixel API using player UUID."""
        if not self.bot.hypixel_api_key:
            print("[GuildCommand][API] Error: Hypixel API Key not configured.")
            return None
        # Simplified session check assuming bot manages session lifecycle
        if not hasattr(self.bot, 'session') or self.bot.session is None or self.bot.session.closed:
             print("[GuildCommand][API] Error: aiohttp Session not available or closed.")
             return None

        params = {"key": self.bot.hypixel_api_key, "player": uuid}
        print(f"[GuildCommand][API] Requesting guild data for UUID: {uuid}")
        try:
            async with self.bot.session.get(HYPIXEL_GUILD_API_URL, params=params) as response:
                print(f"[GuildCommand][API] Response status for {uuid}: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    if data and data.get("success"):
                        return data
                    elif data and not data.get("success"):
                        reason = data.get('cause', 'Unknown reason')
                        print(f"[GuildCommand][API] API Error (Success=False) for {uuid}: {reason}")
                        return None
                    else:
                        print(f"[GuildCommand][API] Unexpected successful response format for {uuid}: {data}")
                        return None
                elif response.status == 404:
                     print(f"[GuildCommand][API] Received 404 for {uuid}, player likely not found in any guild.")
                     # Treat 404 from /guild endpoint as "not in guild" for clarity
                     return {"success": True, "guild": None} # Return specific structure
                else:
                    error_text = await response.text()
                    print(f"[GuildCommand][API] HTTP Error fetching guild data for {uuid}: Status {response.status}, Body: {error_text[:200]}")
                    return None
        except aiohttp.ClientError as e:
            print(f"[GuildCommand][API] Network error fetching guild data for {uuid}: {e}")
            return None
        except Exception as e:
            print(f"[GuildCommand][API] Unexpected error fetching guild data for {uuid}: {e}")
            traceback.print_exc()
            return None

# --- Main Processing Function ---
async def process_guild_command(ctx: commands.Context, args: str | None = None):
    """Parses arguments and displays the Hypixel guild the specified player is in."""
    bot = ctx.bot # Get the bot instance from context

    # Ensure the command instance is available on the bot
    if not hasattr(bot, '_guild_command'):
        print("[ProcessGuildCmd][Error] GuildCommand instance not found on bot object (_guild_command).")
        await bot._send_message(ctx, "An internal error occurred (GuildCommand not initialized).")
        return

    # 1. Parse arguments using the utility function
    parsed_args = await _parse_command_args(bot, ctx, args, 'guild')
    if parsed_args is None:
        # _parse_command_args handles sending the error message if parsing fails
        return

    target_ign, _ = parsed_args

    # 2. Ensure SkyblockClient is ready
    if not bot.skyblock_client:
         await bot._send_message(ctx, "Error: SkyblockClient not ready.")
         return

    # 3. Get UUID using SkyblockClient
    player_uuid = await bot.skyblock_client.get_uuid_from_ign(target_ign)

    if not player_uuid:
        # Error message for UUID failure
        # Check if linked IGN was used by parser and failed
        linked_ign = bot._link_command.get_linked_ign(ctx.author.name) if hasattr(bot, '_link_command') else None
        if not args and linked_ign and target_ign == linked_ign:
             await bot._send_message(ctx, f"Could not find Minecraft account for your linked IGN '{target_ign}'. Maybe re-link?")
        elif not args and not linked_ign:
             await bot._send_message(ctx, f"Could not find Minecraft account for '{target_ign}'. Link your account with `#link <ign>` or specify a player: `#guild <player_ign>`")
        else:
             await bot._send_message(ctx, f"Could not find Minecraft account for '{target_ign}'.")
        return

    # 4. Fetch guild data using the UUID via the GuildCommand instance method
    # Use the instance attached to the bot
    guild_response = await bot._guild_command._fetch_guild_data_by_uuid(player_uuid)

    # 5. Process the response
    if guild_response is None:
        await bot._send_message(ctx, f"Could not fetch guild information for '{target_ign}'. An API error occurred or the player data is unavailable.")
    elif guild_response.get("guild") is None:
        await bot._send_message(ctx, f"'{target_ign}' is not currently in a Hypixel guild.")
    else:
        guild_data = guild_response.get("guild")
        guild_name = guild_data.get("name", "Unknown Guild Name")
        message = f"'{target_ign}' is in the guild: {guild_name}"
        await bot._send_message(ctx, message)