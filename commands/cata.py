"""Module for handling Catacombs/dungeon related commands."""
import traceback
from datetime import datetime

from twitchio.ext import commands

from calculations import calculate_dungeon_level, calculate_class_level


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
        dungeons_data = member_data.get('dungeons', {})
        catacombs_data = dungeons_data.get('dungeon_types', {}).get('catacombs', {})
        catacombs_xp = catacombs_data.get('experience', 0)

        # Get the selected dungeon class and its level
        selected_class = dungeons_data.get('selected_dungeon_class')
        player_classes_data = dungeons_data.get('player_classes', {})

        current_class_level = None
        if selected_class and player_classes_data:
            selected_class_data = player_classes_data.get(selected_class.lower(), {})
            selected_class_xp = selected_class_data.get('experience', 0)
            if selected_class_xp > 0:
                current_class_level = calculate_class_level(bot.leveling_data, selected_class_xp)

        level = calculate_dungeon_level(bot.leveling_data, catacombs_xp)

        # Format the output message based on whether class level is available
        if current_class_level is not None and selected_class:

            display_class_name = selected_class.capitalize()
            await bot.send_message(ctx, f"{target_ign}'s Catacombs level in profile '{profile_name}' is {level:.2f} (Class: {display_class_name} {current_class_level:.2f})")
        else:
            await bot.send_message(ctx, f"{target_ign}'s Catacombs level in profile '{profile_name}' is {level:.2f} (XP: {catacombs_xp:,.0f})")

    except Exception as e:
        print(f"[ERROR][DungeonCmd] Unexpected error processing dungeon data: {e}")
        traceback.print_exc()
        await bot.send_message(ctx, "An unexpected error occurred while fetching Catacombs level.")