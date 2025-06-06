# skill_level.py
import traceback
import itertools
from typing import Iterator, TYPE_CHECKING
from twitchio.ext import commands

from constants import AVERAGE_SKILLS_LIST
from utils import LevelingData, _parse_command_args
from commands.overflow_skills import XPProvider

if TYPE_CHECKING:
    from twitch import IceBot


async def skill_level_command(ctx: commands.Context, args: str | None = None):
    bot: 'IceBot' = ctx.bot

    if not args:
        await bot.send_message(ctx, f"Usage: #skilllevel <skill> [ign] [<profile>]")
        return

    arg_parts = args.split()
    skill_name = arg_parts.pop(0)

    remaining_args = " ".join(arg_parts) if arg_parts else None

    parsed_args = await _parse_command_args(bot, ctx, remaining_args, 'skilllevel')
    if parsed_args is None:
        return

    ign, requested_profile_name = parsed_args
    await process_skill_level_command(ctx, skill_name, ign, requested_profile_name)


async def process_skill_level_command(ctx: commands.Context, skill_name: str, ign: str | None = None,
                                      requested_profile_name: str | None = None):
    """
    Processes the request to display a specific skill level for a player using overflow calculation.
    """
    bot: 'IceBot' = ctx.bot

    if not ign:
        ign = ctx.author.name

    if skill_name.lower() not in AVERAGE_SKILLS_LIST:
        valid_skills = ", ".join([s.capitalize() for s in AVERAGE_SKILLS_LIST])
        await bot.send_message(ctx, f"Invalid skill '{skill_name}'. Valid skills are: {valid_skills}.")
        return

    profile_data = await bot._get_player_profile_data(ctx, ign, requested_profile_name=requested_profile_name)
    if not profile_data:
        return

    target_ign, player_uuid, selected_profile = profile_data
    profile_name = selected_profile.get('cute_name', 'Unknown')

    try:
        member_data = selected_profile.get('members', {}).get(player_uuid)
        if not member_data:
            await bot.send_message(ctx, f"Could not find member data for '{target_ign}' in profile '{profile_name}'.")
            return

        experience_data = member_data.get('player_data', {}).get('experience', {})
        xp_field = f'SKILL_{skill_name.upper()}'
        total_xp_for_skill = experience_data.get(xp_field, 0)

        leveling_data: LevelingData = bot.leveling_data
        provider = XPProvider(leveling_data['xp_table'], None)

        current_xp = total_xp_for_skill
        achieved_level = 0
        required_next_xp = 0

        # Calculate the achieved level by iterating through the XP generator
        for level, xp in enumerate(provider.xp_generator()):
            if current_xp < xp:
                required_next_xp = xp
                break
            achieved_level = level
            current_xp -= xp

        # Calculate the level with decimals for progress
        decimal_level = achieved_level + (current_xp / required_next_xp if required_next_xp > 0 else 0)

        # Send the formatted response message with the newly calculated level
        await bot.send_message(ctx,
                               f"{target_ign}'s {skill_name.capitalize()} level: {decimal_level:.2f} ({total_xp_for_skill:,.0f} exp)")

    except Exception as e:
        print(f"[ERROR][SkillLevelCmd] Unexpected error calculating skill level: {e}")
        traceback.print_exc()
        await bot.send_message(ctx, "An unexpected error occurred while calculating the skill level.")