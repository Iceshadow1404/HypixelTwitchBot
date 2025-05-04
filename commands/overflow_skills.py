import itertools
import typing
from typing import Iterator
from twitchio.ext import commands
from constants import AVERAGE_SKILLS_LIST
from utils import LevelingData

if typing.TYPE_CHECKING:
    from twitch import IceBot


class XPProvider:

    def __init__(self,
                 levels: list[int],
                 max_level: int | None,
                 ):
        self.levels = levels
        self.max_level = max_level

    def xp_generator(self) -> Iterator[int]:
        def inner():
            yield 0  # For level 0 (always given)
            yield from self.levels
            current_xp = self.levels[-1]
            current_slope = (current_xp - self.levels[-2]) * 2
            current_level = len(self.levels)
            current_xp += current_slope
            while True:
                yield current_xp
                current_level += 1
                current_xp += current_slope
                if current_level % 10 == 0: current_slope *= 2

        return itertools.islice(inner(), self.max_level) if self.max_level is None else inner()


async def process_overflow_skill_command(ctx: commands.Context, ign: str | None,  requested_profile_name):
    bot: IceBot = ctx.bot
    leveling_data: LevelingData = bot.leveling_data
    data = await bot._get_player_profile_data(ctx, ign, requested_profile_name)
    if not data:
        return
    target_ign, uuid, profile = data
    profile_name = profile.get('cute_name', 'Unknown')
    member = profile.get('members', {}).get(uuid, {})
    if not member:
        return
    experience = member.get('player_data', {}).get('experience', {})
    skill_text = []
    total_skill_level = 0.0
    num_skills = 0
    
    for skill in AVERAGE_SKILLS_LIST:
        provider = XPProvider(leveling_data['xp_table'],
                              None)  # leveling_data['level_caps'].get(skill, 50)
        total_xp = current_xp = experience.get('SKILL_' + skill.upper())
        achieved_level = 0
        required_next_xp = 0
        for level, xp in enumerate(provider.xp_generator()):
            if current_xp < xp:
                required_next_xp = xp
                break
            achieved_level = level
            current_xp -= xp
            
        # Calculate the decimal level
        decimal_level = achieved_level + (current_xp / required_next_xp if required_next_xp > 0 else 0)
        
        # Add to total for average calculation
        total_skill_level += decimal_level
        num_skills += 1
        
        skill_text += [f'{skill.title()} {decimal_level:.2f}']
    
    # Calculate average
    average_skill_level = total_skill_level / num_skills if num_skills > 0 else 0
    
    # Format the output message with the new format
    skills_str = ' | '.join(skill_text)
    output_message = f"{target_ign}'s overflow skill levels (SA {average_skill_level:.2f}) {skills_str}"
    
    await bot.send_message(ctx, output_message)
