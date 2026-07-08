from types import SimpleNamespace
from typing import cast

import pytest

from bot.commands.base import CommandContext, CommandSpec
from bot.hypixel.leveling import LevelingData, load_leveling_data
from bot.hypixel.profiles import PlayerProfile
from bot.services import Services

_LEVELING = load_leveling_data()


@pytest.fixture(scope="session")
def leveling() -> LevelingData:
    return _LEVELING


class FakeCommandContext(CommandContext):
    """CommandContext for tests: captures replies, returns a canned profile."""

    def __init__(
        self,
        raw_args: str | None = None,
        profile: PlayerProfile | None = None,
        spec: CommandSpec | None = None,
        author: str = "viewer",
    ) -> None:
        fake_ctx = SimpleNamespace(
            author=SimpleNamespace(name=author),
            channel=SimpleNamespace(name="testchannel"),
            prefix="#",
            bot=None,
        )
        fake_services = SimpleNamespace(leveling=_LEVELING)
        fake_spec = spec or CommandSpec(name="test", handler=None, usage="<ign> [profile]")  # type: ignore[arg-type]
        super().__init__(cast("object", fake_ctx), cast(Services, fake_services), raw_args, fake_spec)  # type: ignore[arg-type]
        self.replies: list[str] = []
        self._profile = profile

    async def reply(self, message: str) -> None:
        self.replies.append(message)

    async def fetch_profile(self, *, use_cache: bool = True) -> PlayerProfile:
        assert self._profile is not None, "test did not provide a profile"
        return self._profile

    async def fetch_profile_for(
        self, ign: str | None, profile_name: str | None, *, use_cache: bool = True
    ) -> PlayerProfile:
        return await self.fetch_profile(use_cache=use_cache)
