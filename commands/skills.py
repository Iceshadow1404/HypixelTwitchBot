import itertools
import typing
import traceback
from typing import Iterator
from twitchio.ext import commands
from utils import LevelingData
from calculations import calculate_average_skill_level


if typing.TYPE_CHECKING:
    from twitch import IceBot
    import calculations

async def process_skills_command(ctx: commands.Context, ign: str | None = None, requested_profile_name: str | None = None):
    bot: IceBot = ctx.bot
    if not ign:
        ign = ctx.author.name

    profile_data = await bot._get_player_profile_data(ctx, ign, requested_profile_name=requested_profile_name)
    if not profile_data:
        return  # Error message already sent by helper

    target_ign, player_uuid, selected_profile = profile_data
    profile_name = selected_profile.get('cute_name', 'Unknown')

    try:
        average_level = calculate_average_skill_level(bot.leveling_data, selected_profile, player_uuid)
        if average_level is not None:
            await bot._send_message(ctx,
                                 f"{target_ign}'s Skill Average in profile '{profile_name}' is approximately {average_level:.2f}.")
        else:
            await bot._send_message(ctx,
                                 f"Could not calculate skill level for '{target_ign}' in profile '{profile_name}'. Skill data might be missing.")
    except Exception as e:
        print(f"[ERROR][SkillsCmd] Unexpected error calculating skills: {e}")
        traceback.print_exc()
        await bot._send_message(ctx, "An unexpected error occurred while calculating skill levels.")
