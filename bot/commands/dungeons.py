import math
import re
import time

from bot.commands.base import CommandContext, command
from bot.constants import CLASS_NAMES
from bot.errors import UserError
from bot.hypixel.leveling import calculate_class_level, calculate_dungeon_level


@command("dungeon", aliases=("dungeons", "cata"), usage="<ign> [profile]")
async def dungeon(cc: CommandContext) -> None:
    p = await cc.fetch_profile()
    dungeons_data = p.member.get("dungeons", {})
    catacombs_xp = dungeons_data.get("dungeon_types", {}).get("catacombs", {}).get("experience", 0)
    level = calculate_dungeon_level(cc.services.leveling, catacombs_xp)

    selected_class = dungeons_data.get("selected_dungeon_class")
    class_xp = 0
    if selected_class:
        class_xp = (
            dungeons_data.get("player_classes", {}).get(selected_class.lower(), {}).get("experience", 0)
        )

    if selected_class and class_xp > 0:
        class_level = calculate_class_level(cc.services.leveling, class_xp)
        await cc.reply(
            f"{p.ign}'s Catacombs level in profile '{p.profile_name}' is {level:.2f} "
            f"(Class: {selected_class.capitalize()} {class_level:.2f})"
        )
    else:
        await cc.reply(
            f"{p.ign}'s Catacombs level in profile '{p.profile_name}' is {level:.2f} "
            f"(XP: {catacombs_xp:,.0f})"
        )


@command("classaverage", aliases=("ca",), usage="<ign> [profile]")
async def class_average(cc: CommandContext) -> None:
    p = await cc.fetch_profile()
    player_classes = p.member.get("dungeons", {}).get("player_classes")
    if player_classes is None:
        raise UserError(f"No class data found for {p.ign} in profile '{p.profile_name}'.")

    levels = {
        name.capitalize(): calculate_class_level(
            cc.services.leveling, player_classes.get(name, {}).get("experience", 0)
        )
        for name in CLASS_NAMES
    }
    average = sum(levels.values()) / len(levels)
    levels_str = " | ".join(f"{name} {level:.2f}" for name, level in levels.items())
    await cc.reply(
        f"{p.ign}'s class levels in profile '{p.profile_name}': {levels_str} | Average: {average:.2f}"
    )


@command("secrets", usage="<ign> [profile]")
async def secrets(cc: CommandContext) -> None:
    p = await cc.fetch_profile()
    found = p.member.get("dungeons", {}).get("secrets", 0)
    formatted = f"{found:,}".replace(",", ".")
    await cc.reply(f"{p.ign} has {formatted} secrets")


def _format_relative_time(seconds: float) -> str:
    if seconds < 60:
        seconds_ago = round(seconds)
        return f"{seconds_ago} second{'s' if seconds_ago != 1 else ''} ago"
    minutes_ago = math.floor(seconds / 60)
    return f"{minutes_ago} minute{'s' if minutes_ago != 1 else ''} ago"


def _format_run_type(dungeon_type: str, dungeon_tier: str | int) -> str:
    dtype = dungeon_type.lower()
    if dtype == "catacombs":
        return f"F{dungeon_tier}"
    if dtype == "master_catacombs":
        return f"M{dungeon_tier}"
    return f"{dungeon_type.capitalize()} {dungeon_tier}"


def _parse_participant(raw_display_name: str, target_ign_lower: str) -> str | None:
    """'§bSteve: §eMage§b (§e42§b)' -> 'Steve (Mage 42)'; None for the target player."""
    cleaned = re.sub(r"§[0-9a-fk-or]", "", raw_display_name)
    username, _, class_info = cleaned.partition(":")
    username = username.strip()
    if not username or username.lower() == target_ign_lower:
        return None

    final_class, final_level = "Unknown", "?"
    class_match = re.match(r"^([a-zA-Z]+)", class_info.strip())
    if class_match:
        final_class = class_match.group(1)
    level_match = re.search(r"\((\d+)\)", class_info)
    if level_match:
        final_level = level_match.group(1)
    return f"{username} ({final_class} {final_level})"


@command("currdungeon", usage="<ign> [profile]")
async def current_dungeon(cc: CommandContext) -> None:
    p = await cc.fetch_profile()
    treasures = p.member.get("dungeons", {}).get("treasures") or {}
    runs = [run for run in treasures.get("runs", []) if isinstance(run, dict)]
    if not runs:
        raise UserError(f"'{p.ign}' has no recorded dungeon runs in profile '{p.profile_name}'.")

    latest_run = max(runs, key=lambda run: run.get("completion_ts", 0))
    completion_ts = latest_run.get("completion_ts", 0)
    if not completion_ts:
        raise UserError(f"Could not find a valid latest run for '{p.ign}' in profile '{p.profile_name}'.")

    seconds_since = time.time() - completion_ts / 1000.0
    if seconds_since > 600:
        raise UserError(f"{p.ign} didn't finish a run in the last 10min.")

    run_info = _format_run_type(
        latest_run.get("dungeon_type", "Unknown Type"), latest_run.get("dungeon_tier", "?")
    )
    teammates = [
        parsed
        for participant in latest_run.get("participants", [])
        if isinstance(participant, dict) and participant.get("display_name")
        if (parsed := _parse_participant(participant["display_name"], p.ign.lower()))
    ]
    teammates_str = ", ".join(teammates) if teammates else "No other participants listed"
    await cc.reply(
        f"{p.ign}'s last run was {run_info} finished {_format_relative_time(seconds_since)}. "
        f"Teammates: {teammates_str}"
    )
