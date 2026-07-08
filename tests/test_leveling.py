from bot.format import format_number, format_price
from bot.hypixel.leveling import (
    LevelingData,
    calculate_class_level,
    calculate_dungeon_level,
    calculate_hotm_level,
    calculate_skill_level,
    calculate_slayer_level,
    get_xp_for_target_level,
)

# real values from bot/data/leveling.json
CATA_XP_L1 = 50
CATA_XP_L3_TOTAL = 50 + 75 + 110
SKILL_XP_L1 = 50
SKILL_XP_L2 = 125


def test_skill_level_exact_thresholds(leveling: LevelingData) -> None:
    assert calculate_skill_level(leveling, 0, "combat") == 0.0
    assert calculate_skill_level(leveling, SKILL_XP_L1, "combat") == 1.0
    assert calculate_skill_level(leveling, SKILL_XP_L1 + SKILL_XP_L2, "combat") == 2.0


def test_skill_level_fractional_progress(leveling: LevelingData) -> None:
    halfway_into_l2 = SKILL_XP_L1 + SKILL_XP_L2 / 2
    assert calculate_skill_level(leveling, halfway_into_l2, "combat") == 1.5


def test_skill_level_respects_caps(leveling: LevelingData) -> None:
    huge_xp = 10**12
    assert calculate_skill_level(leveling, huge_xp, "mining") == 60.0
    assert calculate_skill_level(leveling, huge_xp, "alchemy") == 50.0


def test_taming_cap_raised_by_sacrificed_pets(leveling: LevelingData) -> None:
    member = {"pets_data": {"pet_care": {"pet_types_sacrificed": ["A", "B", "C"]}}}
    assert calculate_skill_level(leveling, 10**12, "taming", member) == 53.0


def test_farming_cap_raised_by_jacobs_perks(leveling: LevelingData) -> None:
    member = {"jacobs_contest": {"perks": {"farming_level_cap": 10}}}
    assert calculate_skill_level(leveling, 10**12, "farming", member) == 60.0


def test_dungeon_level(leveling: LevelingData) -> None:
    assert calculate_dungeon_level(leveling, 0) == 0.0
    assert calculate_dungeon_level(leveling, CATA_XP_L1) == 1.0
    assert calculate_dungeon_level(leveling, 10**15) == 100.0


def test_class_level_caps_at_150(leveling: LevelingData) -> None:
    assert calculate_class_level(leveling, CATA_XP_L1) == 1.0
    assert calculate_class_level(leveling, 10**15) == 150.0


def test_hotm_level(leveling: LevelingData) -> None:
    # first HOTM bracket costs 0 XP, so level 1 is free
    assert calculate_hotm_level(leveling, 0) == 1.0
    assert calculate_hotm_level(leveling, 3000) == 2.0
    assert calculate_hotm_level(leveling, sum(leveling["hotm_brackets"])) == 10.0


def test_slayer_level(leveling: LevelingData) -> None:
    assert calculate_slayer_level(leveling, 0, "zombie") == 0
    assert calculate_slayer_level(leveling, 5, "zombie") == 1
    assert calculate_slayer_level(leveling, 4999, "zombie") == 4
    assert calculate_slayer_level(leveling, 0, "unknown_boss") == 0


def test_xp_for_target_level(leveling: LevelingData) -> None:
    assert get_xp_for_target_level(leveling, 0) == 0.0
    assert get_xp_for_target_level(leveling, 1) == CATA_XP_L1
    assert get_xp_for_target_level(leveling, 3) == CATA_XP_L3_TOTAL


def test_format_number() -> None:
    assert format_number(999) == "999"
    assert format_number(1_500) == "1.50K"
    assert format_number(2_500_000) == "2.50M"
    assert format_number(3_100_000_000) == "3.10B"


def test_format_price() -> None:
    assert format_price(999) == "999"
    assert format_price(1_300_000) == "1.3m"
    assert format_price(2_500) == "2.5k"
    assert format_price(1_000_000_000) == "1.0b"
