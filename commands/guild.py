import aiohttp
import traceback
from typing import Optional, TYPE_CHECKING
from twitchio.ext import commands

if TYPE_CHECKING:
    from twitch import IceBot

from utils import _parse_command_args
from constants import HYPIXEL_GUILD_API_URL

class GuildCommand:
    def __init__(self, bot: 'IceBot'):
        self.bot = bot

    async def _fetch_guild_data_by_uuid(self, uuid: str) -> Optional[dict]:
        """Fetches guild data from Hypixel API using player UUID."""
        if not self.bot.hypixel_api_key:
            print("[GuildCommand][API] Error: Hypixel API Key not configured.")
            return None

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
        except aiohttp.ClientError as e:
            # Network errors
            print(f"[GuildCommand][API] Network error fetching guild data for {uuid}: {e}")
            return None
        except Exception as e:
            # Other unexpected errors during the request
            print(f"[GuildCommand][API] Unexpected error fetching guild data for {uuid}: {e}")
            traceback.print_exc()
            return None

async def process_guild_command(ctx: commands.Context, args: str | None = None):
    bot: 'IceBot' = ctx.bot # Get the bot instance from context


    if not hasattr(bot, '_guild_command') or bot._guild_command is None:
        print("[ProcessGuildCmd][Error] GuildCommand instance not found on bot object (_guild_command).")
        await bot.send_message(ctx, "An internal error occurred (GC101: Guild module not ready).")
        return

    parsed_args = await _parse_command_args(bot, ctx, args, 'guild')

    ign = parsed_args[0]

    if not ign or ign.rstrip() == "" or ign == ctx.author.name:
        # Try to get linked IGN first

        linked_ign = bot._link_command.get_linked_ign(ctx.author.name)
        if linked_ign:
            target_ign = linked_ign
            print(f"[DEBUG] Using linked IGN '{linked_ign}' for user {ctx.author.name}")
        else:
            target_ign = ctx.author.name
    else:
        target_ign = ign

    if not bot.skyblock_client:
         print("[ProcessGuildCmd][Error] SkyblockClient not ready when command was executed.")
         await bot.send_message(ctx, "Error: The Skyblock data client is not ready. Please try again shortly.")
         return

    player_uuid = await bot.skyblock_client.get_uuid_from_ign(target_ign)

    if not player_uuid:
        # Get linked IGN for comparison, check if _link_command exists and is initialized
        linked_ign = None
        if hasattr(bot, '_link_command') and bot._link_command is not None:
             # Assuming get_linked_ign returns None if not linked
             linked_ign = bot._link_command.get_linked_ign(ctx.author.name)

        if not args and linked_ign:
            target_ign = linked_ign
        elif not args and not linked_ign:
             await bot.send_message(ctx, f"Please specify a player IGN (`#guild <player_ign>`) or link your account first using `#link <ign>`.")
             return
        else:
            await bot.send_message(ctx, f"Could not find a Minecraft account for '{target_ign}'. Please check the name.")
            return

    guild_response = await bot._guild_command._fetch_guild_data_by_uuid(player_uuid)

    if guild_response is None:
        await bot.send_message(ctx, f"Could not fetch guild information for '{target_ign}'. An API or network error occurred.")
    elif guild_response.get("guild") is None:
        await bot.send_message(ctx, f"'{target_ign}' is not currently in a Hypixel guild.")
    else:
        guild_data = guild_response.get("guild")
        guild_name = guild_data.get("name", "Unknown Guild Name")
        message = f"'{target_ign}' is in the guild: {guild_name}"
        await bot.send_message(ctx, message)