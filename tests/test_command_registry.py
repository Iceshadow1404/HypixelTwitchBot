"""Frozen command surface — the primary safety net.

Every registered command's name, aliases and hidden-flag are frozen here.
If the refactor drops a command, breaks an import (construction fails), or
changes an alias, this test fails. Names + aliases are the public,
Twitch-facing contract and must not change during the refactor.
"""

# Captured from the pre-refactor bot. DO NOT edit to make a test pass —
# a diff here means observable behaviour changed.
EXPECTED_REGISTRY = {
    "auctions": {"aliases": ["ah"], "hidden": False},
    "bank": {"aliases": ["money", "purse"], "hidden": False},
    "classaverage": {"aliases": ["ca"], "hidden": False},
    "coinflip": {"aliases": [], "hidden": False},
    "currdungeon": {"aliases": [], "hidden": False},
    "dexter": {"aliases": [], "hidden": True},
    "dongo": {"aliases": [], "hidden": True},
    "dungeon": {"aliases": ["cata", "dungeons"], "hidden": False},
    "essence": {"aliases": [], "hidden": False},
    "guild": {"aliases": ["g", "guildof"], "hidden": False},
    "help": {"aliases": ["info"], "hidden": False},
    "hotm": {"aliases": [], "hidden": False},
    "kuudra": {"aliases": [], "hidden": False},
    "link": {"aliases": [], "hidden": False},
    "mayor": {"aliases": [], "hidden": False},
    "networth": {"aliases": ["nw"], "hidden": False},
    "nucleus": {"aliases": [], "hidden": False},
    "oskill": {"aliases": ["oskills", "overflow", "skillo", "skillso"], "hidden": False},
    "powder": {"aliases": [], "hidden": False},
    "roll": {"aliases": [], "hidden": False},
    "rtca": {"aliases": [], "hidden": False},
    "rtcl": {"aliases": [], "hidden": False},
    "runstillcata": {"aliases": ["rtc"], "hidden": False},
    "sblvl": {"aliases": ["lvl"], "hidden": False},
    "secrets": {"aliases": [], "hidden": False},
    "skilllevel": {"aliases": ["sl"], "hidden": False},
    "skills": {"aliases": ["sa"], "hidden": False},
    "slayer": {"aliases": ["slayers"], "hidden": False},
    "status": {"aliases": [], "hidden": False},
    "unlink": {"aliases": [], "hidden": False},
    "whatdoing": {"aliases": ["wd"], "hidden": False},
}


def _actual_registry(bot):
    registry = {}
    for cmd in bot.commands.values():
        registry[cmd.name] = {
            "aliases": sorted(getattr(cmd, "aliases", []) or []),
            "hidden": bool(getattr(cmd, "hidden", False)),
        }
    return registry


def test_command_registry_matches_frozen_snapshot(bot):
    assert _actual_registry(bot) == EXPECTED_REGISTRY


def test_command_count_unchanged(bot):
    assert len(bot.commands) == len(EXPECTED_REGISTRY)
