"""Module for handling SkyBlock level command."""
import traceback
from datetime import datetime

from twitchio.ext import commands


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

        await bot._send_message(ctx, f"{target_ign}'s SkyBlock level in profile '{profile_name}' is {sb_level:.2f}.")

    except Exception as e:
        print(f"[ERROR][SblvlCmd] Unexpected error processing level data: {e}")
        traceback.print_exc()
        await bot._send_message(ctx, "An unexpected error occurred while fetching SkyBlock level.")
