import pytest

from bot.commands.combat import essence, kuudra, slayer
from bot.commands.dungeons import class_average, dungeon, secrets
from bot.commands.mining import hotm, nucleus, powder
from bot.commands.skills import sblvl, skills
from bot.errors import UserError
from bot.hypixel.profiles import PlayerProfile
from tests.conftest import FakeCommandContext

UUID = "abc123"

MEMBER = {
    "player_data": {"experience": {"SKILL_COMBAT": 50}},
    "leveling": {"experience": 12345},
    "dungeons": {
        "dungeon_types": {"catacombs": {"experience": 50}},
        "player_classes": {"healer": {"experience": 50}},
        "secrets": 1234567,
    },
    "mining_core": {
        "experience": 3000,
        "powder_mithril": 1000,
        "powder_spent_mithril": 500,
        "crystals": {"amber_crystal": {"total_placed": 3}, "topaz_crystal": {"total_placed": 4}},
    },
    "nether_island_player_data": {"kuudra_completed_tiers": {"none": 2, "infernal": 3}},
    "slayer": {"slayer_bosses": {"zombie": {"xp": 5}}},
    "currencies": {"essence": {"WITHER": {"current": 1500}}},
}

PROFILE = PlayerProfile(
    ign="Steve",
    uuid=UUID,
    profile={"cute_name": "Apple", "profile_id": "p1", "members": {UUID: MEMBER}},
    member=MEMBER,
)


def make_cc() -> FakeCommandContext:
    return FakeCommandContext(profile=PROFILE)


async def test_skills_output() -> None:
    cc = make_cc()
    await skills(cc)
    assert cc.replies == [
        "Steve's skill levels (SA 0.10) Farming 0.00 | Mining 0.00 | Combat 1.00 | Foraging 0.00 "
        "| Fishing 0.00 | Enchanting 0.00 | Alchemy 0.00 | Taming 0.00 | Carpentry 0.00 | Hunting 0.00"
    ]


async def test_sblvl_output() -> None:
    cc = make_cc()
    await sblvl(cc)
    assert cc.replies == ["Steve's SkyBlock level in profile 'Apple' is 123.45."]


async def test_dungeon_output_without_selected_class() -> None:
    cc = make_cc()
    await dungeon(cc)
    assert cc.replies == ["Steve's Catacombs level in profile 'Apple' is 1.00 (XP: 50)"]


async def test_class_average_output() -> None:
    cc = make_cc()
    await class_average(cc)
    assert cc.replies == [
        "Steve's class levels in profile 'Apple': Healer 1.00 | Mage 0.00 | Berserk 0.00 "
        "| Archer 0.00 | Tank 0.00 | Average: 0.20"
    ]


async def test_secrets_output() -> None:
    cc = make_cc()
    await secrets(cc)
    assert cc.replies == ["Steve has 1.234.567 secrets"]


async def test_kuudra_output() -> None:
    cc = make_cc()
    await kuudra(cc)
    assert cc.replies == [
        "Steve's Kuudra completions in profile 'Apple': basic 2, hot 0, burning 0, fiery 0, infernal 3 "
        "| Score: 17"
    ]


async def test_slayer_output() -> None:
    cc = make_cc()
    await slayer(cc)
    assert cc.replies == [
        "Steve's Slayers (Profile: 'Apple'): Total XP: 5 | Zombie 1 (5 XP) | Spider 0 (0 XP) "
        "| Wolf 0 (0 XP) | Enderman 0 (0 XP) | Blaze 0 (0 XP) | Vampire 0 (0 XP)"
    ]


async def test_essence_output() -> None:
    cc = make_cc()
    await essence(cc)
    assert cc.replies == [
        "Steve (Profile: 'Apple'): Wither: 1.5k | Dragon: 0 | Diamond: 0 | Spider: 0 "
        "| Undead: 0 | Gold: 0 | Ice: 0 | Crimson: 0"
    ]


async def test_hotm_output() -> None:
    cc = make_cc()
    await hotm(cc)
    assert cc.replies == ["Steve's HotM level is 2.00 (XP: 3,000) (Profile: 'Apple')"]


async def test_powder_output() -> None:
    cc = make_cc()
    await powder(cc)
    assert cc.replies == [
        "Steve's powder (Apple): mithril powder: 1,000 (total: 1,500) "
        "| gemstone powder: 0 (total: 0) | glacite powder: 0 (total: 0)"
    ]


async def test_nucleus_output() -> None:
    cc = make_cc()
    await nucleus(cc)
    assert cc.replies == ["Steve's nucleus runs: 1 (Profile: 'Apple')"]


async def test_empty_member_raises_user_error_for_slayer() -> None:
    empty_profile = PlayerProfile(
        ign="Steve", uuid=UUID, profile={"cute_name": "Apple", "members": {UUID: {}}}, member={}
    )
    cc = FakeCommandContext(profile=empty_profile)
    with pytest.raises(UserError, match="has no slayer data"):
        await slayer(cc)
