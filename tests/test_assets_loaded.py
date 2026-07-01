"""Guard against silently-broken asset loading.

Both loaders swallow errors and fall back to empty structures:
- utils._load_leveling_data() -> {} on FileNotFoundError (runs in Bot.__init__)
- WhatdoingCommand.load_island_mappings() -> area_names={} on any error

So a broken cwd-relative open() (e.g. after moving files into a package) would
still let the Bot construct and keep the registry test green, while every
skill/level/whatdoing command breaks at runtime. These assertions make that
failure visible.
"""

REQUIRED_LEVELING_KEYS = {
    "xp_table", "catacombs_xp", "level_caps", "hotm_brackets", "slayer_xp",
}


def test_leveling_data_loaded(bot):
    data = bot.leveling_data
    assert data, "leveling.json failed to load (empty leveling_data)"
    assert REQUIRED_LEVELING_KEYS <= set(data.keys())
    assert data["xp_table"], "xp_table empty"
    assert data["catacombs_xp"], "catacombs_xp empty"
    assert data["hotm_brackets"], "hotm_brackets empty"
    assert data["slayer_xp"], "slayer_xp empty"


def test_island_mappings_loaded(bot):
    area_names = bot._whatdoing_command.area_names
    assert isinstance(area_names, dict)
    assert area_names, "islands.json failed to load (empty area_names)"
