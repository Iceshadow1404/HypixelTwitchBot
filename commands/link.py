# commands/link.py
import json
import os
from typing import Dict, Any, Optional
import traceback
from twitchio.ext import commands
from constants import LINKS_FILE


class LinkCommand:
    def __init__(self, bot):
        self.bot = bot
        self.links = self._load_links()

    def _load_links(self) -> Dict[str, str]:
        """Load existing user-IGN links from JSON file."""
        try:
            if os.path.exists(LINKS_FILE):
                with open(LINKS_FILE, 'r') as f:
                    links = json.load(f)
                print(f"[INFO][LinkCmd] Loaded {len(links)} user-IGN links from {LINKS_FILE}")
                return links
            else:
                print(f"[INFO][LinkCmd] No links file found at {LINKS_FILE}, creating new links dictionary")
                return {}
        except json.JSONDecodeError:
            print(f"[ERROR][LinkCmd] Error parsing {LINKS_FILE}, creating new links dictionary")
            return {}
        except Exception as e:
            print(f"[ERROR][LinkCmd] Unexpected error loading links: {e}")
            traceback.print_exc()
            return {}

    def _save_links(self) -> bool:
        """Save user-IGN links to JSON file."""
        try:
            with open(LINKS_FILE, 'w') as f:
                json.dump(self.links, f, indent=4)
            print(f"[INFO][LinkCmd] Saved {len(self.links)} user-IGN links to {LINKS_FILE}")
            return True
        except Exception as e:
            print(f"[ERROR][LinkCmd] Error saving links to {LINKS_FILE}: {e}")
            traceback.print_exc()
            return False

    async def _validate_minecraft_username(self, username: str) -> bool:
        """Verify that the Minecraft username exists via the bot's cache or Mojang API."""
        try:
            # Use the bot's existing method to validate through UUID lookup
            player_uuid = await self.bot.skyblock_client.get_uuid_from_ign(username)
            return player_uuid is not None
        except Exception as e:
            print(f"[ERROR][LinkCmd] Error validating Minecraft username: {e}")
            traceback.print_exc()
            return False

    async def link_command(self, ctx: commands.Context, *, args: str | None = None):
        """Links a Twitch username to a Minecraft IGN for use with other commands.
        Syntax: #link <minecraft_ign>
        """
        try:
            if not args:
                # Show current link if it exists
                twitch_username = ctx.author.name.lower()

                if twitch_username in self.links:
                    await self.bot._send_message(ctx,
                                                 f"@{ctx.author.name} You are currently linked to Minecraft IGN: {self.links[twitch_username]}")
                else:
                    await self.bot._send_message(ctx,
                                                 f"@{ctx.author.name} You are not currently linked to any Minecraft IGN. Use #link <minecraft_ign> to set your IGN.")
                return

            # Extract the Minecraft IGN from args
            minecraft_ign = args.strip()

            # Validate the Minecraft username
            if not await self._validate_minecraft_username(minecraft_ign):
                await self.bot._send_message(ctx,
                                             f"@{ctx.author.name} '{minecraft_ign}' does not appear to be a valid Minecraft username.")
                return

            # Store the link
            twitch_username = ctx.author.name.lower()
            self.links[twitch_username] = minecraft_ign

            if self._save_links():
                await self.bot._send_message(ctx,
                                             f"@{ctx.author.name} Successfully linked to Minecraft IGN: {minecraft_ign}")
            else:
                await self.bot._send_message(ctx,
                                             f"@{ctx.author.name} Failed to save your link. Please try again later.")

        except Exception as e:
            print(f"[ERROR][LinkCmd] Unexpected error in link command: {e}")
            traceback.print_exc()
            await self.bot._send_message(ctx, f"@{ctx.author.name} An error occurred while processing your request.")

    async def unlink_command(self, ctx: commands.Context):
        """Removes the link between a Twitch username and Minecraft IGN.
        Syntax: #unlink
        """
        try:
            twitch_username = ctx.author.name.lower()

            if twitch_username in self.links:
                previous_ign = self.links[twitch_username]
                del self.links[twitch_username]

                if self._save_links():
                    await self.bot._send_message(ctx,
                                                 f"@{ctx.author.name} Successfully unlinked from Minecraft IGN: {previous_ign}")
                else:
                    await self.bot._send_message(ctx,
                                                 f"@{ctx.author.name} Failed to remove your link. Please try again later.")
            else:
                await self.bot._send_message(ctx,
                                             f"@{ctx.author.name} You are not currently linked to any Minecraft IGN.")

        except Exception as e:
            print(f"[ERROR][LinkCmd] Unexpected error in unlink command: {e}")
            traceback.print_exc()
            await self.bot._send_message(ctx, f"@{ctx.author.name} An error occurred while processing your request.")

    def get_linked_ign(self, twitch_username: str) -> Optional[str]:
        """Gets the linked Minecraft IGN for a Twitch username if it exists."""
        return self.links.get(twitch_username.lower())