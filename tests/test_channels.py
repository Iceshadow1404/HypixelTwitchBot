import time
from typing import Any, cast

from bot.twitch.channels import MAX_JOIN_ATTEMPTS, ChannelManager


class FakeChannel:
    def __init__(self, name: str) -> None:
        self.name = name


class FakeConnection:
    def __init__(self) -> None:
        self._websocket = object()


class FakeBot:
    """Mimics twitchio: connected_channels is a cache that survives a reconnect."""

    def __init__(self, cached: list[str]) -> None:
        self._connection = FakeConnection()
        self.connected_channels = [FakeChannel(name) for name in cached]
        self.joined: list[str] = []
        self.parted: list[str] = []

    def reconnect(self) -> None:
        self._connection._websocket = object()

    async def join_channels(self, channels: list[str]) -> None:
        self.joined.extend(channels)

    async def part_channels(self, channels: list[str]) -> None:
        self.parted.extend(channels)


class FakeScanner:
    def __init__(self, live: list[str]) -> None:
        self._live = live

    async def fetch_live_skyblock_streamers(self) -> list[str]:
        return self._live


def _manager(cached: list[str], live: list[str]) -> tuple[ChannelManager, FakeBot]:
    bot = FakeBot(cached)
    manager = ChannelManager(cast(Any, bot), cast(Any, FakeScanner(live)), ("home",))
    return manager, bot


async def test_no_rejoin_while_socket_is_unchanged() -> None:
    manager, bot = _manager(cached=["streamer"], live=["streamer"])
    await manager._monitor_once()
    assert bot.joined == []


async def test_rejoins_live_channels_after_reconnect() -> None:
    manager, bot = _manager(cached=["streamer"], live=["streamer"])
    bot.reconnect()
    await manager._monitor_once()
    assert bot.joined == ["streamer"]


async def test_blacklist_expires_and_channel_is_retried() -> None:
    manager, bot = _manager(cached=[], live=["streamer"])
    for _ in range(MAX_JOIN_ATTEMPTS):
        manager.on_join_failure("streamer")
    await manager.safe_join(["streamer"])
    assert bot.joined == []

    manager.blacklisted["streamer"] = time.time() - 1
    await manager.safe_join(["streamer"])
    assert bot.joined == ["streamer"]
    assert manager.blacklisted == {}


async def test_reconnect_resets_join_attempts() -> None:
    manager, bot = _manager(cached=[], live=[])
    for _ in range(MAX_JOIN_ATTEMPTS - 1):
        manager.on_join_failure("streamer")
    bot.reconnect()
    await manager._monitor_once()
    manager.on_join_failure("streamer")
    assert "streamer" not in manager.blacklisted
