import itertools
import typing
import traceback
from typing import Iterator
from twitchio.ext import commands
from utils import LevelingData
from calculations import calculate_average_skill_level, calculate_skill_level
from constants import AVERAGE_SKILLS_LIST


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
        member_data = selected_profile.get('members', {}).get(player_uuid)
        if not member_data:
            await bot.send_message(ctx, f"Could not find member data for '{target_ign}' in profile '{profile_name}'.")
            return

        experience_data = member_data.get('player_data', {}).get('experience', {})
        skill_levels = []
        total_level = 0
        skills_counted = 0

        for skill_name in AVERAGE_SKILLS_LIST:
            xp_field = f'SKILL_{skill_name.upper()}'
            skill_xp = experience_data.get(xp_field, 0)
            level = calculate_skill_level(bot.leveling_data, skill_xp, skill_name, member_data)
            total_level += level
            skills_counted += 1
            skill_levels.append(f"{skill_name.capitalize()} {level:.2f}")

        if skills_counted > 0:
            average_level = total_level / skills_counted
            skills_str = " | ".join(skill_levels)
            await bot.send_message(ctx, f"{target_ign}'s skill levels (SA {average_level:.2f}) {skills_str}")
        else:
            await bot.send_message(ctx, f"Could not calculate skill level for '{target_ign}' in profile '{profile_name}'. Skill data might be missing.")
    except Exception as e:
        print(f"[ERROR][SkillsCmd] Unexpected error calculating skills: {e}")
        traceback.print_exc()
        await bot.send_message(ctx, "An unexpected error occurred while calculating skill levels.")
