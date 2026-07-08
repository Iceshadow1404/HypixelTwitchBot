import asyncio
import logging
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

Json = dict[str, Any]


class NetworthClient:
    """Talks to the local Node.js skyhelper-networth service."""

    def __init__(self, base_url: str, session: aiohttp.ClientSession) -> None:
        self._calculate_url = f"{base_url.rstrip('/')}/calculate-networth"
        self._health_url = f"{base_url.rstrip('/')}/health"
        self._session = session

    async def wait_until_ready(self, attempts: int = 10, delay: float = 1.0) -> bool:
        """Polls the health endpoint so early commands don't hit a still-starting Node process."""
        for attempt in range(attempts):
            try:
                async with self._session.get(self._health_url) as response:
                    if response.status == 200:
                        logger.info("networth service is ready")
                        return True
            except aiohttp.ClientError:
                pass
            await asyncio.sleep(delay * (attempt + 1))
        logger.warning("networth service not reachable after %d attempts", attempts)
        return False

    async def calculate(
        self, player_uuid: str, profile: Json, museum_member: Json | None, bank_balance: float
    ) -> Json | None:
        payload = {
            "playerUUID": player_uuid,
            "profileData": profile,
            "museumData": museum_member,
            "bankBalance": bank_balance,
        }
        try:
            async with self._session.post(self._calculate_url, json=payload) as response:
                if response.status == 200:
                    return await response.json()
                body = await response.text()
                logger.error("networth service returned status %d: %s", response.status, body[:200])
                return None
        except aiohttp.ClientError as e:
            logger.error("failed to reach networth service: %s", e)
            return None
