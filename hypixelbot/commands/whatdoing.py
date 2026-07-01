# commands/whatdoing.py
import traceback
import aiohttp
import json
from twitchio.ext import commands


class WhatdoingCommand:
    def __init__(self, bot):
        self.bot = bot
        self.area_names = {}
        self.load_island_mappings()

    def load_island_mappings(self):
        """Load island name mappings from islands.json file"""
        try:
            with open('islands.json', 'r') as file:
                data = json.load(file)
                self.area_names = data.get('area_names', {})
        except Exception as e:
            print(f"[ERROR][WhatdoingCmd] Failed to load islands.json: {e}")
            traceback.print_exc()

    async def whatdoing_command(self, ctx: commands.Context, *, args: str | None = None):
        """Shows what the player is currently doing on Hypixel (game type only).
        Syntax: #whatdoing [username]
        """
        if not hasattr(self.bot, 'session') or self.bot.session is None or self.bot.session.closed:
            print("[ERROR][WhatdoingCmd] aiohttp.ClientSession is not available or closed!")
            await self.bot.send_message(ctx, "An internal error has occurred (HTTP Session not ready).")
            return

        target_ign = ""

        if not args:
            # First try to get the linked IGN
            if hasattr(self.bot,
                       '_link_command') and self.bot._link_command:
                linked_ign = self.bot._link_command.get_linked_ign(ctx.author.name)
                if linked_ign:
                    target_ign = linked_ign
                    print(
                        f"[DEBUG][WhatdoingCmd] Using linked IGN '{linked_ign}' for user {ctx.author.name}")
                else:
                    target_ign = ctx.author.name  # By default use the sender's name if no arguments and no link exist
            else:
                target_ign = ctx.author.name
        else:
            target_ign = args.split(' ')[0]

        target_ign = target_ign.lstrip('@')

        if not self.bot.hypixel_api_key:
            await self.bot.send_message(ctx, "Hypixel API key is not configured for the bot.")
            return

        if not target_ign:  # Shouldn't happen due to the logic above
            await self.bot.send_message(ctx,
                                        f"Please provide a player name. Example: {ctx.prefix}whatdoing PlayerName")
            return

        player_uuid = None
        # 1. Get UUID from IGN
        try:
            if hasattr(self.bot, 'skyblock_client') and self.bot.skyblock_client:
                player_uuid = await self.bot.skyblock_client.get_uuid_from_ign(target_ign, ctx.author.name)

            if not player_uuid:
                # Message adjusted to mention link command
                link_command_name = getattr(self.bot._link_command, 'link_command_name',
                                            'link')  # Safe access to the link command name
                await self.bot.send_message(ctx,
                                            f"Could not find a Minecraft account for '{target_ign}'. You can use #{link_command_name} <IGN> to link your Twitch account.")
                return

        except Exception as e:
            print(f"[ERROR][WhatdoingCmd] Error getting UUID for {target_ign}: {e}")
            traceback.print_exc()
            await self.bot.send_message(ctx, f"An error occurred while looking up '{target_ign}'.")
            return

        # 2. Get player status from Hypixel API
        status_url = f"https://api.hypixel.net/status?uuid={player_uuid}&key={self.bot.hypixel_api_key}"
        try:
            async with self.bot.session.get(status_url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success"):
                        session_data = data.get("session")
                        if session_data and session_data.get("online"):
                            game_type = session_data.get("gameType", "Unknown")
                            mode = session_data.get("mode", "Unknown")

                            # Convert island code to readable name using the mappings
                            readable_island = self.get_readable_island_name(mode)

                            status_message = f"{target_ign} is currently playing {game_type}, ({readable_island})."
                            await self.bot.send_message(ctx, status_message)
                        else:
                            await self.bot.send_message(ctx,
                                                        f"{target_ign} is currently offline or not on Hypixel.")
                    else:
                        error_cause = data.get("cause", "Unknown Hypixel API error.")
                        if "Invalid API key" in error_cause or "API key" in error_cause.lower():
                            print(f"[ERROR][WhatdoingCmd] Hypixel API Key Problem: {error_cause}")
                            await self.bot.send_message(ctx,
                                                        "The bot's Hypixel API key appears to be invalid or missing permissions.")
                        else:
                            await self.bot.send_message(ctx,
                                                        f"Could not retrieve status for {target_ign}: {error_cause}")
                else:
                    # Additional debug info for API errors
                    error_text = await response.text()
                    print(
                        f"[ERROR][WhatdoingCmd] Error retrieving status for {target_ign}. Hypixel API Status: {response.status}, Response: {error_text[:200]}")
                    await self.bot.send_message(ctx,
                                                f"Error retrieving status for {target_ign}. (API Status: {response.status})")
        except aiohttp.ClientConnectorError as e:
            print(f"[ERROR][WhatdoingCmd] Network connection error: {e}")
            await self.bot.send_message(ctx,
                                        "Could not connect to the Hypixel API. Please try again later.")
        except Exception as e:
            print(f"[ERROR][WhatdoingCmd] Unexpected error processing status for {target_ign}: {e}")
            traceback.print_exc()
            await self.bot.send_message(ctx, "An unexpected error occurred while retrieving player status.")

    def get_readable_island_name(self, mode_code):
        return self.area_names.get(mode_code, mode_code)