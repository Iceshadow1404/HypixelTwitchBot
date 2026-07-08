import logging
from typing import Any

import aiohttp

from bot.constants import CACHE_TTL, MOJANG_API_URL, MOJANG_API_URL_FALLBACK
from bot.hypixel.cache import TTLCache

logger = logging.getLogger(__name__)


class MojangClient:
    """Resolves Minecraft IGNs to UUIDs, with caching and a fallback API."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self.cache: TTLCache[str] = TTLCache(CACHE_TTL)

    async def get_uuid(self, ign: str) -> str | None:
        cached = self.cache.get(ign.lower())
        if cached:
            return cached

        urls = [
            MOJANG_API_URL.format(username=ign),
            MOJANG_API_URL_FALLBACK.format(username=ign),
        ]
        for i, url in enumerate(urls):
            api_name = "Mojang fallback" if i > 0 else "Mojang primary"
            try:
                async with self._session.get(url) as response:
                    if response.status == 200:
                        data: dict[str, Any] = await response.json()
                        uuid = data.get("id")
                        if uuid:
                            self.cache.set(ign.lower(), uuid)
                            return uuid
                        logger.warning("%s returned no 'id' for %r", api_name, ign)
                    elif response.status == 204:
                        logger.info("%s: user %r not found", api_name, ign)
                        return None
                    else:
                        logger.warning(
                            "%s request for %r failed with status %d", api_name, ign, response.status
                        )
            except aiohttp.ClientError as e:
                logger.warning("%s request for %r failed: %s", api_name, ign, e)
        return None
