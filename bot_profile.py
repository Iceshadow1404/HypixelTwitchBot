# bot_profile.py
# Shared player-profile fetch/select boilerplate used by most commands.
# Mixed into Bot via MRO.
import aiohttp
from twitchio.ext import commands

from skyblock import SkyblockClient
from profiletyping import Profile


class ProfileMixin:
    """Resolves IGN -> UUID -> selected SkyBlock profile with the cached client."""

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
