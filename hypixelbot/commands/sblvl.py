"""Module for handling SkyBlock level command."""
import traceback
from datetime import datetime

from twitchio.ext import commands
from hypixelbot.utils import _parse_command_args


async def process_sblvl_command(ctx: commands.Context, ign: str | None = None, requested_profile_name: str | None = None):
    """Shows the player's SkyBlock level (based on XP/100).
    Syntax: #sblvl <username> [profile_name]
    """
    bot = ctx.bot
    profile_data = await bot._get_player_profile_data(ctx, ign, requested_profile_name=requested_profile_name)
    if not profile_data:
        return

    target_ign, player_uuid, selected_profile = profile_data
    profile_name = selected_profile.get('cute_name', 'Unknown')

    try:
        member_data = selected_profile.get('members', {}).get(player_uuid, {})
        leveling_data = member_data.get('leveling', {})
        sb_xp = leveling_data.get('experience', 0)

        # Calculate level by dividing XP by 100
        sb_level = sb_xp / 100.0

        await bot.send_message(ctx, f"{target_ign}'s SkyBlock level in profile '{profile_name}' is {sb_level:.2f}.")

    except Exception as e:
        print(f"[ERROR][SblvlCmd] Unexpected error processing level data: {e}")
        traceback.print_exc()
        await bot.send_message(ctx, "An unexpected error occurred while fetching SkyBlock level.")


class SblvlCommand:
    """Dispatch wrapper for #sblvl; delegates to process_sblvl_command."""

    def __init__(self, bot):
        self.bot = bot

    async def sblvl_command(self, ctx: commands.Context, *, args: str | None = None):
        parsed_args = await _parse_command_args(self.bot, ctx, args, 'sblvl')
        if parsed_args is None:
            return
        ign, requested_profile_name = parsed_args
        await process_sblvl_command(ctx, ign, requested_profile_name=requested_profile_name)
