from pathlib import Path

from bot.gamedata import BUNDLED_DIR, data_file_path, load_area_names


def test_falls_back_to_bundled_file(tmp_path: Path) -> None:
    assert data_file_path("leveling.json", tmp_path) == BUNDLED_DIR / "leveling.json"
    assert data_file_path("leveling.json", None) == BUNDLED_DIR / "leveling.json"


def test_prefers_synced_copy(tmp_path: Path) -> None:
    synced = tmp_path / "leveling.json"
    synced.write_text("{}", encoding="utf-8")
    assert data_file_path("leveling.json", tmp_path) == synced


def test_load_area_names_from_bundled() -> None:
    area_names = load_area_names()
    assert isinstance(area_names, dict)
    assert area_names  # bundled islands.json has mappings


def test_load_area_names_bad_file_returns_empty(tmp_path: Path) -> None:
    (tmp_path / "islands.json").write_text("not json", encoding="utf-8")
    assert load_area_names(tmp_path) == {}


def test_upstream_catacombs_table_is_extended_to_150(tmp_path: Path) -> None:
    # upstream NEU ships only 99 catacombs entries; class levels up to 150 must keep working
    import json

    from bot.hypixel.leveling import calculate_class_level, load_leveling_data

    upstream = json.loads((BUNDLED_DIR / "leveling.json").read_text(encoding="utf-8"))
    upstream["catacombs"] = upstream["catacombs"][:99]
    (tmp_path / "leveling.json").write_text(json.dumps(upstream), encoding="utf-8")

    leveling = load_leveling_data(tmp_path)
    assert len(leveling["catacombs_xp"]) == 150
    assert calculate_class_level(leveling, 10**15) == 150.0
