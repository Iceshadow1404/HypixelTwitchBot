from collections.abc import Iterator

from bot.commands.base import CommandContext, command
from bot.constants import AVERAGE_SKILLS_LIST
from bot.errors import UserError
from bot.hypixel.leveling import calculate_skill_level


def overflow_xp_generator(xp_table: list[int]) -> Iterator[int]:
    """Yields per-level XP costs beyond the normal cap, extrapolating the table's slope."""
    yield 0  # level 0 is always given
    yield from xp_table
    current_xp = xp_table[-1]
    current_slope = (current_xp - xp_table[-2]) * 2
    current_level = len(xp_table)
    current_xp += current_slope
    while True:
        yield current_xp
        current_level += 1
        current_xp += current_slope
        if current_level % 10 == 0:
            current_slope *= 2


def overflow_level(xp_table: list[int], total_xp: float) -> float:
    """Level (with fractional progress) allowing overflow past the table's max level."""
    current_xp = total_xp
    achieved_level = 0
    required_next_xp = 0
    for level, xp in enumerate(overflow_xp_generator(xp_table)):
        if current_xp < xp:
            required_next_xp = xp
            break
        achieved_level = level
        current_xp -= xp
    return achieved_level + (current_xp / required_next_xp if required_next_xp > 0 else 0)


@command("skills", aliases=("sa",), usage="<ign> [profile]")
async def skills(cc: CommandContext) -> None:
    p = await cc.fetch_profile()
    experience = p.member.get("player_data", {}).get("experience", {})

    skill_levels: list[str] = []
    total_level = 0.0
    for skill_name in AVERAGE_SKILLS_LIST:
        skill_xp = experience.get(f"SKILL_{skill_name.upper()}", 0)
        level = calculate_skill_level(cc.services.leveling, skill_xp, skill_name, p.member)
        total_level += level
        skill_levels.append(f"{skill_name.capitalize()} {level:.2f}")

    average = total_level / len(AVERAGE_SKILLS_LIST)
    await cc.reply(f"{p.ign}'s skill levels (SA {average:.2f}) {' | '.join(skill_levels)}")


@command("oskill", aliases=("skillo", "oskills", "skillso", "overflow"), usage="<ign> [profile]")
async def overflow_skills(cc: CommandContext) -> None:
    p = await cc.fetch_profile()
    experience = p.member.get("player_data", {}).get("experience", {})
    xp_table = cc.services.leveling["xp_table"]

    skill_levels: list[str] = []
    total_level = 0.0
    for skill_name in AVERAGE_SKILLS_LIST:
        level = overflow_level(xp_table, experience.get(f"SKILL_{skill_name.upper()}", 0))
        total_level += level
        skill_levels.append(f"{skill_name.title()} {level:.2f}")

    average = total_level / len(AVERAGE_SKILLS_LIST)
    await cc.reply(f"{p.ign}'s overflow skill levels (SA {average:.2f}) {' | '.join(skill_levels)}")


@command("skilllevel", aliases=("sl",), usage="<skill> [ign] [profile]")
async def skill_level(cc: CommandContext) -> None:
    if not cc.raw_args:
        raise UserError(f"Usage: {cc.usage}")

    parts = cc.raw_args.split()
    skill_name = parts[0]
    if skill_name.lower() not in AVERAGE_SKILLS_LIST:
        valid = ", ".join(s.capitalize() for s in AVERAGE_SKILLS_LIST)
        raise UserError(f"Invalid skill '{skill_name}'. Valid skills are: {valid}.")

    ign = parts[1] if len(parts) > 1 else None
    profile_name = parts[2] if len(parts) > 2 else None
    if len(parts) > 3:
        raise UserError(f"Too many arguments. Usage: {cc.usage}")

    p = await cc.fetch_profile_for(ign, profile_name)
    experience = p.member.get("player_data", {}).get("experience", {})
    total_xp = experience.get(f"SKILL_{skill_name.upper()}", 0)
    level = overflow_level(cc.services.leveling["xp_table"], total_xp)
    await cc.reply(f"{p.ign}'s {skill_name.capitalize()} level: {level:.2f} ({total_xp:,.0f} exp)")


@command("sblvl", aliases=("lvl",), usage="<ign> [profile]")
async def sblvl(cc: CommandContext) -> None:
    p = await cc.fetch_profile()
    sb_xp = p.member.get("leveling", {}).get("experience", 0)
    await cc.reply(f"{p.ign}'s SkyBlock level in profile '{p.profile_name}' is {sb_xp / 100.0:.2f}.")
