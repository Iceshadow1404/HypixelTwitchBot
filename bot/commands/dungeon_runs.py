import math
from dataclasses import dataclass

from bot.commands.base import CommandContext, command
from bot.constants import (
    BASE_M6_CLASS_XP,
    BASE_M6_XP,
    BASE_M7_CLASS_XP,
    BASE_M7_XP,
    CLASS_NAMES,
    CLASS_XP_BUFF_FACTOR,
    DERPY_XP_MULTIPLIER,
    MAX_MESSAGE_LENGTH,
)
from bot.errors import UserError
from bot.hypixel.leveling import calculate_class_level, calculate_dungeon_level, get_xp_for_target_level

FLOORS = ("m6", "m7")
MAX_SIM_ITERATIONS = 100_000

_CLASS_ALIASES = {
    "archer": ["arch", "a"],
    "healer": ["heal", "h", "heiler"],
    "mage": ["m"],
    "tank": ["t"],
    "berserk": ["berserker", "b", "bers"],
}
CLASS_ALIAS_TO_CANONICAL = {
    alias: canonical for canonical, aliases in _CLASS_ALIASES.items() for alias in [canonical, *aliases]
}


@dataclass(frozen=True)
class SimArgs:
    ign: str | None
    profile_name: str | None
    target: int | None
    floor: str
    class_name: str | None


def _is_target(part: str) -> bool:
    return part.isdigit() and int(part) < 100


def parse_sim_args(cc: CommandContext, *, with_class: bool = False) -> SimArgs:
    """Parses '[ign] [profile] [class] [target] [floor]' where order is flexible."""
    raw = cc.raw_args.strip() if cc.raw_args else None
    if raw and not any(c.isalnum() for c in raw):
        raw = None
    if not raw:
        return SimArgs(ign=None, profile_name=None, target=None, floor="m7", class_name=None)

    parts = raw.split()
    first = parts[0].lower()
    first_is_ign = not (
        first in FLOORS or _is_target(parts[0]) or (with_class and first in CLASS_ALIAS_TO_CANONICAL)
    )
    ign = parts[0] if first_is_ign else None
    remaining = parts[1:] if first_is_ign else parts

    profile_name: str | None = None
    target: int | None = None
    floor: str | None = None
    class_name: str | None = None
    unidentified: list[str] = []

    for part in remaining:
        part_lower = part.lower()
        if with_class and part_lower in CLASS_ALIAS_TO_CANONICAL and class_name is None:
            class_name = CLASS_ALIAS_TO_CANONICAL[part_lower]
        elif part_lower in FLOORS and floor is None:
            floor = part_lower
        elif _is_target(part) and target is None:
            target = int(part)
        elif profile_name is None and not (
            part_lower in FLOORS
            or _is_target(part)
            or (with_class and part_lower in CLASS_ALIAS_TO_CANONICAL)
        ):
            profile_name = part
        else:
            unidentified.append(part)

    if unidentified:
        raise UserError(f"Too many or ambiguous arguments: {', '.join(unidentified)}. Usage: {cc.usage}")
    return SimArgs(
        ign=ign, profile_name=profile_name, target=target, floor=floor or "m7", class_name=class_name
    )


def simulate_class_runs(
    needs: dict[str, float], active_gain: float, passive_gain: float
) -> tuple[int, dict[str, int]]:
    """Greedy simulation: each run is played actively on the bottleneck class,
    all other classes gain passive XP. Returns (total runs, active runs per class)."""
    total_runs = 0
    active_runs = dict.fromkeys(needs, 0)
    remaining = dict(needs)

    while remaining and total_runs < MAX_SIM_ITERATIONS:
        total_runs += 1
        bottleneck = max(remaining, key=lambda cn: math.ceil(remaining[cn] / active_gain))
        active_runs[bottleneck] += 1

        next_remaining: dict[str, float] = {}
        for class_name, needed in remaining.items():
            gained = active_gain if class_name == bottleneck else passive_gain
            if needed - gained > 0:
                next_remaining[class_name] = needed - gained
        remaining = next_remaining

    return total_runs, active_runs


async def _is_derpy_active(cc: CommandContext) -> bool:
    election = await cc.services.hypixel.get_election()
    mayor = election.get("mayor") if election else None
    return bool(mayor and mayor.get("name") == "Derpy")


@command("rtca", usage="<username> [profile_name] [target_ca=50] [floor=m7]")
async def rtca(cc: CommandContext) -> None:
    sim_args = parse_sim_args(cc)
    target = sim_args.target if sim_args.target is not None else 50

    p = await cc.fetch_profile_for(sim_args.ign, sim_args.profile_name, use_cache=False)
    dungeons_data = p.member.get("dungeons", {})
    player_classes = dungeons_data.get("player_classes")
    if player_classes is None:
        raise UserError(f"'{p.ign}' has no class data in profile '{p.profile_name}'.")
    selected_class = (dungeons_data.get("selected_dungeon_class") or "").lower()

    class_xps = {cn: player_classes.get(cn, {}).get("experience", 0) for cn in CLASS_NAMES}
    class_levels = {cn: calculate_class_level(cc.services.leveling, xp) for cn, xp in class_xps.items()}
    current_ca = sum(class_levels.values()) / len(CLASS_NAMES)

    if current_ca >= target and all(level >= target for level in class_levels.values()):
        raise UserError(
            f"{p.ign} (CA {current_ca:.2f}) has already reached or surpassed "
            f"the target Class Average {target}."
        )

    derpy = await _is_derpy_active(cc)
    base_xp = BASE_M6_CLASS_XP if sim_args.floor == "m6" else BASE_M7_CLASS_XP
    floor_name = sim_args.floor.upper()
    xp_per_run = base_xp * (DERPY_XP_MULTIPLIER if derpy else 1.0) * CLASS_XP_BUFF_FACTOR

    xp_for_target = get_xp_for_target_level(cc.services.leveling, target)
    needs = {
        cn: xp_for_target - class_xps[cn]
        for cn in CLASS_NAMES
        if class_levels[cn] < target and xp_for_target - class_xps[cn] > 0
    }
    if not needs:
        raise UserError(f"{p.ign} already meets the XP requirements for CA {target}.")

    total_runs, active_runs = simulate_class_runs(needs, xp_per_run, 0.25 * xp_per_run)

    sorted_counts = sorted(((cn, n) for cn, n in active_runs.items() if n > 0), key=lambda item: -item[1])

    def format_class_count(cn: str, count: int) -> str:
        marker_prefix = "🔸 " if cn == selected_class else ""
        marker_suffix = " 🔸" if cn == selected_class else ""
        return f"{marker_prefix}{cn.capitalize()}: {count}{marker_suffix}"

    breakdown = " | ".join(format_class_count(cn, count) for cn, count in sorted_counts)
    message = (
        f"{p.ign} (CA {current_ca:.2f}) -> Target CA {target}: Needs approx {total_runs:,} {floor_name} runs "
    )
    if derpy:
        message += "(Calculated with Derpy XP rates) "
    if len(message + breakdown) <= MAX_MESSAGE_LENGTH:
        message += breakdown
    await cc.reply(message)


@command("rtcl", usage="<username> [profile_name] [class_name|alias] [target_level] [floor=m7|m6]")
async def rtcl(cc: CommandContext) -> None:
    sim_args = parse_sim_args(cc, with_class=True)

    p = await cc.fetch_profile_for(sim_args.ign, sim_args.profile_name, use_cache=False)
    dungeons_data = p.member.get("dungeons", {})
    player_classes = dungeons_data.get("player_classes")
    if player_classes is None:
        raise UserError(f"'{p.ign}' has no class data in profile '{p.profile_name}'.")

    if sim_args.class_name:
        class_key = sim_args.class_name
        if class_key not in player_classes:
            raise UserError(
                f"'{p.ign}' has no data for class '{class_key.capitalize()}' in profile '{p.profile_name}'."
            )
    else:
        active_class = dungeons_data.get("selected_dungeon_class")
        if not active_class:
            raise UserError(f"'{p.ign}' has no active dungeon class selected in profile '{p.profile_name}'.")
        class_key = active_class.lower()

    class_display = class_key.capitalize()
    current_xp = player_classes.get(class_key, {}).get("experience", 0)
    current_level = calculate_class_level(cc.services.leveling, current_xp)

    if sim_args.target is not None:
        target = sim_args.target
        if target <= math.floor(current_level) and target != math.ceil(current_level):
            raise UserError(
                f"Target level {target} must be higher than current full level "
                f"{math.floor(current_level)} for {class_display}."
            )
        if target < 1:
            raise UserError("Target level must be at least 1.")
    else:
        target = math.floor(current_level) + 1

    if current_level >= target:
        raise UserError(
            f"{p.ign}'s {class_display} class (Lvl {current_level:.2f}) "
            f"has already reached or surpassed the target level {target}."
        )

    derpy = await _is_derpy_active(cc)
    base_xp = BASE_M6_CLASS_XP if sim_args.floor == "m6" else BASE_M7_CLASS_XP
    floor_name = sim_args.floor.upper()
    xp_per_run = base_xp * (DERPY_XP_MULTIPLIER if derpy else 1.0)

    remaining_xp = get_xp_for_target_level(cc.services.leveling, target) - current_xp
    if remaining_xp <= 0:
        raise UserError(
            f"{p.ign}'s {class_display} class already meets or exceeds the XP requirement for level {target}."
        )

    runs_needed = math.ceil(remaining_xp / xp_per_run)
    message = (
        f"{p.ign} needs approx. {runs_needed:,} {floor_name} runs "
        f"to reach {class_display} Lvl {target} (from Lvl {current_level:.2f})."
    )
    if derpy:
        message += " (Derpy active)"
    await cc.reply(message)


@command("runstillcata", aliases=("rtc",), usage="<username> [profile_name] [target_level] [floor=m7]")
async def runs_till_cata(cc: CommandContext) -> None:
    sim_args = parse_sim_args(cc)

    p = await cc.fetch_profile_for(sim_args.ign, sim_args.profile_name)
    catacombs = p.member.get("dungeons", {}).get("dungeon_types", {}).get("catacombs", {})
    current_xp = catacombs.get("experience", 0)
    current_level = calculate_dungeon_level(cc.services.leveling, current_xp)

    if sim_args.target is None:
        target = math.ceil(current_level)
        if target == math.floor(current_level):
            target += 1
    else:
        target = sim_args.target

    xp_needed = get_xp_for_target_level(cc.services.leveling, target) - current_xp
    if xp_needed <= 0:
        raise UserError(f"{p.ign} has already reached Catacombs level {target}!")

    derpy = await _is_derpy_active(cc)
    base_xp = BASE_M6_XP if sim_args.floor == "m6" else BASE_M7_XP
    floor_name = sim_args.floor.upper()
    xp_per_run = base_xp * DERPY_XP_MULTIPLIER if derpy else base_xp

    runs_needed = math.ceil(xp_needed / xp_per_run)
    await cc.reply(
        f"{p.ign} (Cata {current_level:.2f}) needs {xp_needed:,.0f} XP for level {target}. "
        f"{floor_name}: {runs_needed:,} runs ({xp_per_run:,} XP/run)"
    )
