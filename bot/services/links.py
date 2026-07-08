import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class LinkStore:
    """Persists Twitch username -> Minecraft IGN links as a JSON file."""

    def __init__(self, data_dir: Path) -> None:
        self._file = data_dir / "user_links.json"
        self._links: dict[str, str] = self._load()

    def _load(self) -> dict[str, str]:
        if not self._file.exists():
            logger.info("no links file at %s, starting empty", self._file)
            return {}
        try:
            with open(self._file, encoding="utf-8") as f:
                links = json.load(f)
            logger.info("loaded %d user-IGN links from %s", len(links), self._file)
            return links
        except (json.JSONDecodeError, OSError) as e:
            logger.error("failed to load links from %s: %s", self._file, e)
            return {}

    def _save(self) -> bool:
        try:
            with open(self._file, "w", encoding="utf-8") as f:
                json.dump(self._links, f, indent=4)
            return True
        except OSError as e:
            logger.error("failed to save links to %s: %s", self._file, e)
            return False

    def get(self, twitch_username: str) -> str | None:
        return self._links.get(twitch_username.lower())

    def set(self, twitch_username: str, ign: str) -> bool:
        self._links[twitch_username.lower()] = ign
        return self._save()

    def remove(self, twitch_username: str) -> str | None:
        """Removes a link and returns the previously linked IGN, or None if there was none."""
        previous = self._links.pop(twitch_username.lower(), None)
        if previous is not None and not self._save():
            return None
        return previous
