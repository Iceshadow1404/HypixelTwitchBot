import logging
from typing import Any

import aiohttp

from bot.constants import (
    CACHE_TTL,
    HYPIXEL_API_URL,
    HYPIXEL_AUCTION_URL,
    HYPIXEL_ELECTION_URL,
    HYPIXEL_GUILD_API_URL,
    HYPIXEL_MUSEUM_URL,
    HYPIXEL_STATUS_URL,
)
from bot.hypixel.cache import TTLCache

logger = logging.getLogger(__name__)

Json = dict[str, Any]


class HypixelClient:
    """Typed wrapper around the Hypixel SkyBlock HTTP API."""

    def __init__(self, api_key: str, session: aiohttp.ClientSession) -> None:
        self._api_key = api_key
        self._session = session
        self.profiles_cache: TTLCache[list[Json]] = TTLCache(CACHE_TTL)
        self._museum_cache: TTLCache[Json] = TTLCache(CACHE_TTL)
        self._election_cache: TTLCache[Json] = TTLCache(CACHE_TTL)

    async def _get_json(self, url: str, params: dict[str, str]) -> Json | None:
        """Returns the parsed response body on success=true, otherwise None."""
        try:
            async with self._session.get(url, params=params) as response:
                if response.status != 200:
                    body = await response.text()
                    logger.warning("GET %s failed: status %d, body %s", url, response.status, body[:300])
                    return None
                data: Json = await response.json()
        except aiohttp.ClientError as e:
            logger.warning("GET %s failed: %s", url, e)
            return None
        if not data.get("success"):
            logger.warning("GET %s: success=false, cause: %s", url, data.get("cause", "unknown"))
            return None
        return data

    async def get_profiles(self, uuid: str, use_cache: bool = True) -> list[Json] | None:
        """All SkyBlock profiles for a player. None on API error, [] if the player has none."""
        if use_cache:
            cached = self.profiles_cache.get(uuid)
            if cached is not None:
                return cached

        data = await self._get_json(HYPIXEL_API_URL, {"key": self._api_key, "uuid": uuid})
        if data is None:
            return None
        profiles = data.get("profiles")
        if profiles is None:
            logger.warning("profiles field missing/null for uuid %s", uuid)
            return []
        if not isinstance(profiles, list):
            logger.error("profiles is not a list for uuid %s: %s", uuid, type(profiles))
            return None
        self.profiles_cache.set(uuid, profiles)
        return profiles

    async def get_museum(self, uuid: str, profile_id: str) -> Json | None:
        cache_key = f"{uuid}:{profile_id}"
        cached = self._museum_cache.get(cache_key)
        if cached is not None:
            return cached
        params = {"key": self._api_key, "player": uuid.replace("-", ""), "profile": profile_id}
        data = await self._get_json(HYPIXEL_MUSEUM_URL, params)
        if data is not None:
            self._museum_cache.set(cache_key, data)
        return data

    async def get_guild_by_player(self, uuid: str) -> Json | None:
        """Full guild response (its 'guild' key is null when the player has no guild); None on error."""
        return await self._get_json(HYPIXEL_GUILD_API_URL, {"key": self._api_key, "player": uuid})

    async def get_player_status(self, uuid: str) -> Json | None:
        """Online status ('session' key) for a player; None on error."""
        return await self._get_json(HYPIXEL_STATUS_URL, {"key": self._api_key, "uuid": uuid})

    async def get_election(self) -> Json | None:
        cached = self._election_cache.get("election")
        if cached is not None:
            return cached
        data = await self._get_json(HYPIXEL_ELECTION_URL, {})
        if data is not None:
            self._election_cache.set("election", data)
        return data

    async def get_player_auctions(self, uuid: str) -> list[Json] | None:
        data = await self._get_json(HYPIXEL_AUCTION_URL, {"key": self._api_key, "player": uuid})
        if data is None:
            return None
        auctions = data.get("auctions")
        return auctions if isinstance(auctions, list) else []

    def cleanup_expired(self) -> int:
        return (
            self.profiles_cache.cleanup_expired()
            + self._museum_cache.cleanup_expired()
            + self._election_cache.cleanup_expired()
        )
