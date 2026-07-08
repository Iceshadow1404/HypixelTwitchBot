"""Game-data files (leveling.json, islands.json) sourced from the NEU repo.

On startup the bot downloads fresh copies into DATA_DIR; loaders prefer the
downloaded copy and fall back to the bundled files in bot/data/.
"""

import json
import logging
from pathlib import Path

import aiohttp

logger = logging.getLogger(__name__)

BUNDLED_DIR = Path(__file__).resolve().parent / "data"
NEU_RAW_BASE = "https://raw.githubusercontent.com/NotEnoughUpdates/NotEnoughUpdates-REPO/master/constants"

# key that must exist for a downloaded file to be accepted
REQUIRED_KEYS = {"leveling.json": "leveling_xp", "islands.json": "area_names"}


def data_file_path(name: str, data_dir: Path | None = None) -> Path:
    """The synced copy in data_dir if present, otherwise the bundled file."""
    if data_dir is not None:
        synced = data_dir / name
        if synced.exists():
            return synced
    return BUNDLED_DIR / name


async def sync_game_data(session: aiohttp.ClientSession, data_dir: Path) -> None:
    """Downloads the game-data files from the NEU repo into data_dir.

    Any failure just keeps the previous copy (synced or bundled) — the bot
    must be able to start without GitHub being reachable.
    """
    for name, required_key in REQUIRED_KEYS.items():
        url = f"{NEU_RAW_BASE}/{name}"
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.warning(
                        "game-data sync: GET %s returned %d, keeping local %s", url, response.status, name
                    )
                    continue
                text = await response.text()
            data = json.loads(text)
        except (aiohttp.ClientError, json.JSONDecodeError) as e:
            logger.warning("game-data sync: fetching %s failed (%s), keeping local copy", name, e)
            continue

        if required_key not in data:
            logger.warning(
                "game-data sync: downloaded %s is missing %r, keeping local copy", name, required_key
            )
            continue

        current = data_file_path(name, data_dir)
        if current.exists() and current.read_text(encoding="utf-8") == text:
            logger.info("game-data sync: %s is up to date", name)
            continue

        (data_dir / name).write_text(text, encoding="utf-8")
        logger.info("game-data sync: updated %s from the NEU repo", name)


def load_area_names(data_dir: Path | None = None) -> dict[str, str]:
    """Island-code -> readable name mapping from islands.json."""
    path = data_file_path("islands.json", data_dir)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("area_names", {})
    except (OSError, json.JSONDecodeError) as e:
        logger.error("failed to load %s: %s", path, e)
        return {}
