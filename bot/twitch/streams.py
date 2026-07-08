import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import aiohttp

logger = logging.getLogger(__name__)

TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
TWITCH_STREAMS_URL = "https://api.twitch.tv/helix/streams"
MINECRAFT_GAME_ID = "27471"
SKYBLOCK_TITLE_TERMS = ("skyblock", "sky block", "sky-block")

T = TypeVar("T")


def retry_on_network_error(
    retries: int = 3, delay: int = 5
) -> Callable[[Callable[..., Awaitable[T | None]]], Callable[..., Awaitable[T | None]]]:
    def decorator(func: Callable[..., Awaitable[T | None]]) -> Callable[..., Awaitable[T | None]]:
        async def wrapper(*args: Any, **kwargs: Any) -> T | None:
            for attempt in range(retries):
                try:
                    return await func(*args, **kwargs)
                except (TimeoutError, aiohttp.ClientError) as e:
                    logger.warning(
                        "network error in %r (attempt %d/%d): %s", func.__name__, attempt + 1, retries, e
                    )
                    await asyncio.sleep(delay * (attempt + 1))
            logger.error("%r failed permanently after %d attempts", func.__name__, retries)
            return None

        return wrapper

    return decorator


class StreamScanner:
    """Finds live Twitch streams playing Hypixel SkyBlock via the Helix API."""

    def __init__(self, client_id: str, client_secret: str, session: aiohttp.ClientSession) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._session = session

    @retry_on_network_error(retries=3, delay=5)
    async def _get_access_token(self) -> str | None:
        params = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "grant_type": "client_credentials",
        }
        async with self._session.post(TWITCH_TOKEN_URL, params=params) as response:
            if response.status != 200:
                logger.error(
                    "failed to get Twitch token: status %d, %s", response.status, await response.text()
                )
                return None
            data = await response.json()
            token = data.get("access_token")
            if not token:
                logger.error("Twitch token response contained no access_token")
            return token

    @retry_on_network_error(retries=3, delay=5)
    async def fetch_live_skyblock_streamers(self) -> list[str] | None:
        """Login names of live Minecraft streams with 'hypixel' + a skyblock term in the title."""
        access_token = await self._get_access_token()
        if not access_token:
            return None

        headers = {"Client-ID": self._client_id, "Authorization": f"Bearer {access_token}"}
        streamers: set[str] = set()
        cursor: str | None = None

        while True:
            params: dict[str, str] = {"game_id": MINECRAFT_GAME_ID, "first": "100"}
            if cursor:
                params["after"] = cursor

            async with self._session.get(TWITCH_STREAMS_URL, headers=headers, params=params) as response:
                if response.status == 401:
                    logger.warning("Helix returned 401, refreshing token")
                    access_token = await self._get_access_token()
                    if not access_token:
                        return None
                    headers["Authorization"] = f"Bearer {access_token}"
                    continue
                if response.status != 200:
                    logger.error(
                        "failed to fetch streams page: status %d, %s", response.status, await response.text()
                    )
                    break
                data = await response.json()

            for stream in data.get("data", []):
                title = stream.get("title", "").lower()
                if "hypixel" in title and any(term in title for term in SKYBLOCK_TITLE_TERMS):
                    login_name = stream.get("user_login")
                    if login_name:
                        streamers.add(login_name)

            cursor = data.get("pagination", {}).get("cursor")
            if not cursor:
                break

        return list(streamers)
