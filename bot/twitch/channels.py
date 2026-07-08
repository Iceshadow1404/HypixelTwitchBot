# NOTE: no `from __future__ import annotations` here — see bot/twitch/bot.py.
import asyncio
import logging
import time

from twitchio.ext import commands

from bot.twitch.streams import StreamScanner

logger = logging.getLogger(__name__)

MONITOR_INTERVAL = 120
MONITOR_ERROR_RETRY = 300
OFFLINE_TIMEOUT_MINUTES = 15
MAX_JOIN_ATTEMPTS = 5


class ChannelManager:
    """Joins live SkyBlock streamers' channels and leaves them after they go offline."""

    def __init__(
        self, bot: commands.Bot, scanner: StreamScanner, protected_channels: tuple[str, ...]
    ) -> None:
        self._bot = bot
        self._scanner = scanner
        # channels from the .env config are never left
        self._protected = {ch.lower() for ch in protected_channels}
        self._join_attempts: dict[str, int] = {}
        self.blacklisted: set[str] = set()
        self._pending_leave: dict[str, float] = {}

    def _connected_names(self) -> set[str]:
        return {ch.name for ch in self._bot.connected_channels if ch is not None}

    def on_joined(self, channel_name: str) -> None:
        self._join_attempts.pop(channel_name.lower(), None)

    def on_join_failure(self, channel_name: str) -> None:
        channel_lower = channel_name.lower()
        attempts = self._join_attempts.get(channel_lower, 0) + 1
        self._join_attempts[channel_lower] = attempts
        logger.warning("failed to join #%s (attempt %d/%d)", channel_name, attempts, MAX_JOIN_ATTEMPTS)

        if attempts >= MAX_JOIN_ATTEMPTS:
            self.blacklisted.add(channel_lower)
            del self._join_attempts[channel_lower]
            logger.error(
                "channel #%s blacklisted after %d failed attempts (until restart)", channel_name, attempts
            )

    async def safe_join(self, channels: list[str]) -> None:
        channels_to_join = [ch for ch in channels if ch.lower() not in self.blacklisted]
        skipped = len(channels) - len(channels_to_join)
        if skipped:
            logger.info("skipped %d blacklisted channels", skipped)
        if not channels_to_join:
            return

        try:
            await self._bot.join_channels(channels_to_join)
        except Exception as e:
            logger.error("bulk join failed for %s: %s", channels_to_join, e)
            for channel in channels_to_join:
                try:
                    await self._bot.join_channels([channel])
                    await asyncio.sleep(1)
                except Exception as individual_error:
                    logger.error("individual join failed for #%s: %s", channel, individual_error)

    async def initial_scan(self) -> None:
        live_streamers = await self._scanner.fetch_live_skyblock_streamers()
        if live_streamers is None:
            logger.warning("could not fetch live streamers during startup, monitoring will still run")
            return
        connected = {name.lower() for name in self._connected_names()}
        to_join = [name for name in live_streamers if name.lower() not in connected]
        if to_join:
            logger.info("joining %d live SkyBlock channels: %s", len(to_join), to_join)
            await self.safe_join(to_join)
            await asyncio.sleep(5)
        logger.info("connected channels after initial scan: %s", sorted(self._connected_names()))

    async def monitor_loop(self) -> None:
        logger.info("stream monitor started (interval %ds)", MONITOR_INTERVAL)
        while True:
            try:
                await self._monitor_once()
                await asyncio.sleep(MONITOR_INTERVAL)
            except Exception:
                logger.exception("stream monitor iteration failed")
                await asyncio.sleep(MONITOR_ERROR_RETRY)

    async def _monitor_once(self) -> None:
        live_streamers = await self._scanner.fetch_live_skyblock_streamers()
        if live_streamers is None:
            logger.warning("failed to fetch live streamers, will retry later")
            return

        now = time.time()
        connected_names = self._connected_names()
        live_set = set(live_streamers)

        to_join = [name for name in live_streamers if name not in connected_names]

        for channel_name in connected_names:
            if channel_name.lower() in self._protected:
                continue
            if channel_name not in live_set:
                self._pending_leave.setdefault(channel_name, now)
            else:
                self._pending_leave.pop(channel_name, None)

        to_leave = []
        for channel_name, marked_at in list(self._pending_leave.items()):
            if (now - marked_at) / 60 >= OFFLINE_TIMEOUT_MINUTES:
                del self._pending_leave[channel_name]
                if channel_name in connected_names:
                    to_leave.append(channel_name)

        if to_leave:
            logger.info(
                "leaving %d channels after %d min offline: %s",
                len(to_leave),
                OFFLINE_TIMEOUT_MINUTES,
                to_leave,
            )
            try:
                await self._bot.part_channels(to_leave)
            except Exception as e:
                logger.error("error leaving channels %s: %s", to_leave, e)

        if to_join:
            logger.info("joining %d new live channels: %s", len(to_join), to_join)
            await self.safe_join(to_join)
            await asyncio.sleep(3)

        if to_join or to_leave or self._pending_leave:
            logger.info(
                "monitor status: %d connected, %d pending leave, %d blacklisted",
                len(self._connected_names()),
                len(self._pending_leave),
                len(self.blacklisted),
            )
