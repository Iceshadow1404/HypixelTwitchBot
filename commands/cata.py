"""Module for handling Catacombs/dungeon related commands."""
import traceback
from datetime import datetime

from twitchio.ext import commands

from calculations import calculate_dungeon_level


async def process_dungeon_command(ctx: commands.Context, ign: str | None = None, requested_profile_name: str | None = None):
    """Shows the player's Catacombs level and XP.
    Syntax: #dungeon <username> [profile_name]
    """
    bot = ctx.bot
    profile_data = await bot._get_player_profile_data(ctx, ign, requested_profile_name=requested_profile_name)
    if not profile_data:
        return

    target_ign, player_uuid, selected_profile = profile_data
    profile_name = selected_profile.get('cute_name', 'Unknown')

    try:
        member_data = selected_profile.get('members', {}).get(player_uuid, {})
        dungeons_data = member_data.get('dungeons', {}).get('dungeon_types', {}).get('catacombs', {})
        catacombs_xp = dungeons_data.get('experience', 0)

        level = calculate_dungeon_level(bot.leveling_data, catacombs_xp)
        await bot.send_message(ctx, f"{target_ign}'s Catacombs level in profile '{profile_name}' is {level:.2f} (XP: {catacombs_xp:,.0f})")

    except Exception as e:
        print(f"[ERROR][DungeonCmd] Unexpected error processing dungeon data: {e}")
        traceback.print_exc()
        await bot.send_message(ctx, "An unexpected error occurred while fetching Catacombs level.")
