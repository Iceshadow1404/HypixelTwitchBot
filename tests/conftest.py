"""Shared fixtures/helpers for the safety-net test suite (Stage 0).

These tests exist purely to guarantee that the structural refactor does NOT
change the bot's observable behaviour: command names/aliases, the help output,
and the core output-producing helpers. They construct the real Bot offline
(twitchio 2.10 does not connect until .run()) and never touch the network.
"""
import asyncio

import pytest

from twitch import Bot


def make_bot() -> Bot:
    """Construct the real Bot offline with dummy credentials.

    twitchio's Client.__init__ calls asyncio.get_event_loop(); on Python 3.11
    that raises once an earlier asyncio.run() has closed the loop. Ensure a
    current loop exists so construction is robust to test ordering.
    """
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    return Bot(
        token="oauth:faketoken",
        prefix="#",
        nickname="testbot",
        initial_channels=["testchannel"],
        hypixel_api_key="fake-key",
        local_mode=True,
    )


@pytest.fixture
def bot() -> Bot:
    return make_bot()


class CapturingChannel:
    """Fake twitchio channel that records what would be sent to chat."""

    def __init__(self, name: str, sink: list[str]):
        self.name = name
        self._sink = sink

    async def send(self, message: str):
        self._sink.append(message)


class FakeAuthor:
    def __init__(self, name: str):
        self.name = name


class FakeCtx:
    """Minimal stand-in for twitchio's commands.Context.

    Captures everything sent via ``ctx.send`` into ``sent`` so tests can
    assert on the exact reply strings the bot would produce.
    """

    def __init__(self, bot=None, author_name: str = "viewer", channel_name: str = "chan"):
        self.bot = bot
        self.author = FakeAuthor(author_name)
        self.channel = CapturingChannel(channel_name, [])
        self.sent: list[str] = []

    async def send(self, message: str):
        self.sent.append(message)


def run(coro):
    """Run an async coroutine from a synchronous test (no pytest-asyncio needed)."""
    return asyncio.run(coro)
