import json
import logging
from pathlib import Path
from typing import Any, TypedDict

from bot.constants import AVERAGE_SKILLS_LIST
from bot.gamedata import data_file_path

logger = logging.getLogger(__name__)


class LevelingData(TypedDict):
    xp_table: list[int]
    level_caps: dict[str, int]
    catacombs_xp: list[int]
    hotm_brackets: list[int]
    slayer_xp: dict[str, list[int]]


# the upstream NEU catacombs table ends at level 99; extend it so class/cata levels
# keep working up to 150 (local decision, see commit "Changed max Cata LVL to 150")
CATACOMBS_OVERFLOW_LEVEL_XP = 200_000_000
CATACOMBS_TABLE_SIZE = 150


def _extend_catacombs_table(catacombs_xp: list[int]) -> list[int]:
    if not catacombs_xp or len(catacombs_xp) >= CATACOMBS_TABLE_SIZE:
        return catacombs_xp
    missing = CATACOMBS_TABLE_SIZE - len(catacombs_xp)
    return catacombs_xp + [CATACOMBS_OVERFLOW_LEVEL_XP] * missing


def load_leveling_data(data_dir: Path | None = None) -> LevelingData:
    with open(data_file_path("leveling.json", data_dir), encoding="utf-8") as f:
        data = json.load(f)
    return {
        "xp_table": data.get("leveling_xp", []),
        "level_caps": data.get("leveling_caps", {}),
        "catacombs_xp": _extend_catacombs_table(data.get("catacombs", [])),
        "hotm_brackets": data.get("HOTM", []),
        "slayer_xp": data.get("slayer_xp", {}),
    }


def get_xp_for_target_level(leveling_data: LevelingData, target_level: int) -> float:
    """Total cumulative Catacombs XP required to complete a 1-based target level."""
    xp_table = leveling_data["catacombs_xp"]
    if not xp_table:
        logger.warning("catacombs XP table not loaded")
        return float("inf")

    target_level_index = target_level - 1
    if target_level_index < 0:
        return 0.0
    if target_level_index >= len(xp_table):
        logger.warning(
            "target level %d exceeds catacombs XP table length (%d), using max", target_level, len(xp_table)
        )
        return float(sum(xp_table))
    return float(sum(xp_table[: target_level_index + 1]))


def _level_from_cumulative_table(xp: float, xp_table: list[int], max_level: int) -> float:
    """Level (with fractional progress) from a per-level XP table, capped at max_level."""
    total_xp_for_max = sum(xp_table[:max_level])
    if xp >= total_xp_for_max:
        return float(max_level)

    total_xp_required = 0
    level = 0
    for i, required_xp in enumerate(xp_table):
        if i >= max_level:
            break
        current_level_threshold = total_xp_required
        total_xp_required += required_xp
        if xp >= total_xp_required:
            level += 1
        else:
            if required_xp > 0:
                progress = (xp - current_level_threshold) / required_xp
                return min(level + progress, float(max_level))
            return min(float(level), float(max_level))
    return min(float(level), float(max_level))


def calculate_skill_level(
    leveling_data: LevelingData, xp: float, skill_name: str, member_data: dict[str, Any] | None = None
) -> float:
    """Skill level from XP, honoring per-skill level caps and taming/farming cap bonuses."""
    if not leveling_data["xp_table"]:
        return 0.0

    effective_max_level = leveling_data["level_caps"].get(skill_name, 50)
    if skill_name == "taming" and member_data:
        pet_care = member_data.get("pets_data", {}).get("pet_care", {})
        sacrificed_count = len(pet_care.get("pet_types_sacrificed", []))
        effective_max_level = 50 + min(sacrificed_count, 10)
    elif skill_name == "farming" and member_data:
        jacobs_perks = member_data.get("jacobs_contest", {}).get("perks", {})
        effective_max_level = 50 + jacobs_perks.get("farming_level_cap", 0)

    return _level_from_cumulative_table(xp, leveling_data["xp_table"], effective_max_level)


def calculate_hotm_level(leveling_data: LevelingData, xp: float) -> float:
    brackets = leveling_data["hotm_brackets"]
    if not brackets:
        logger.warning("HOTM XP brackets not loaded")
        return 0.0
    return _level_from_cumulative_table(xp, brackets, len(brackets))


def calculate_dungeon_level(leveling_data: LevelingData, xp: float) -> float:
    xp_table = leveling_data["catacombs_xp"]
    if not xp_table:
        logger.warning("catacombs XP table not loaded")
        return 0.0
    return _level_from_cumulative_table(xp, xp_table, 100)


def calculate_class_level(leveling_data: LevelingData, xp: float) -> float:
    xp_table = leveling_data["catacombs_xp"]
    if not xp_table:
        logger.warning("catacombs XP table not loaded")
        return 0.0
    # ponytail: cap 150 with a ~100-entry table means the cap is effectively the table
    # length; kept as-is for output parity with the old calculate_class_level
    max_class_level = 150
    return _level_from_cumulative_table(xp, xp_table[:max_class_level], max_class_level)


def calculate_slayer_level(leveling_data: LevelingData, xp: float, boss_key: str) -> int:
    thresholds = leveling_data["slayer_xp"].get(boss_key)
    if not thresholds:
        logger.warning("slayer XP thresholds not loaded for boss %r", boss_key)
        return 0
    level = 0
    for i, threshold in enumerate(thresholds):
        if xp >= threshold:
            level = i + 1
        else:
            break
    return level


def calculate_average_skill_level(
    leveling_data: LevelingData, profile: dict[str, Any], player_uuid: str
) -> float | None:
    member_data = profile.get("members", {}).get(player_uuid)
    if not member_data:
        logger.warning("member data not found for %s in profile", player_uuid)
        return None

    experience_data = member_data.get("player_data", {}).get("experience", {})
    total = 0.0
    for skill_name in AVERAGE_SKILLS_LIST:
        skill_xp = experience_data.get(f"SKILL_{skill_name.upper()}")
        if skill_xp is not None:
            total += calculate_skill_level(leveling_data, skill_xp, skill_name, member_data)
    return total / len(AVERAGE_SKILLS_LIST)
