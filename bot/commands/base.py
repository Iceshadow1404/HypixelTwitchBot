from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from bot.constants import MAX_MESSAGE_LENGTH
from bot.errors import UserError

if TYPE_CHECKING:
    from twitchio.ext import commands as twitch_commands

    from bot.hypixel.profiles import PlayerProfile
    from bot.services import Services

logger = logging.getLogger(__name__)

Handler = Callable[["CommandContext"], Awaitable[None]]


@dataclass(frozen=True)
class CommandSpec:
    name: str
    handler: Handler
    aliases: tuple[str, ...] = ()
    usage: str = ""
    hidden: bool = False


REGISTRY: list[CommandSpec] = []


def command(
    name: str, *, aliases: tuple[str, ...] = (), usage: str = "", hidden: bool = False
) -> Callable[[Handler], Handler]:
    """Registers a chat command; the bot wires every registered spec at startup."""

    def decorator(handler: Handler) -> Handler:
        REGISTRY.append(CommandSpec(name=name, handler=handler, aliases=aliases, usage=usage, hidden=hidden))
        return handler

    return decorator


# invisible characters Twitch clients (Chatterino, 7TV, ...) append to bypass
# the duplicate-message filter; they break int()/IGN parsing if kept
_INVISIBLE_CHARS = "\u034f\u200b\u200c\u200d\u2060\ufeff\U000e0000"
_INVISIBLE_TRANSLATION = dict.fromkeys(map(ord, _INVISIBLE_CHARS))


def clean_args(raw_args: str | None) -> str | None:
    if raw_args is None:
        return None
    cleaned = raw_args.translate(_INVISIBLE_TRANSLATION).strip()
    return cleaned or None


class CommandContext:
    """Everything a command handler needs: the twitchio context, shared services, raw args."""

    def __init__(
        self,
        ctx: twitch_commands.Context,
        services: Services,
        raw_args: str | None,
        spec: CommandSpec,
    ) -> None:
        self.ctx = ctx
        self.services = services
        self.raw_args = clean_args(raw_args)
        self.spec = spec

    @property
    def author_name(self) -> str:
        return self.ctx.author.name

    @property
    def channel_name(self) -> str:
        return self.ctx.channel.name

    @property
    def usage(self) -> str:
        prefix = self.ctx.prefix or "#"
        suffix = f" {self.spec.usage}" if self.spec.usage else ""
        return f"{prefix}{self.spec.name}{suffix}"

    async def reply(self, message: str) -> None:
        """Sends a reply with @mention after a short delay (deliberate rate-limit cushion)."""
        text = f"@{self.author_name}, {message}"
        if len(text) > MAX_MESSAGE_LENGTH:
            text = text[: MAX_MESSAGE_LENGTH - 3] + "..."

        logger.info("reply in #%s: %s", self.channel_name, text)
        await asyncio.sleep(0.3)
        # re-fetch the channel object instead of ctx.send; ctx can go stale on busy channels.
        # Any-cast: twitchio's @id_cache decorator hides get_channel's real signature from pyrefly
        channel = cast("Any", self.ctx.bot).get_channel(self.channel_name)
        if channel:
            await channel.send(text)
        else:
            logger.warning("could not re-fetch channel %s, falling back to ctx.send", self.channel_name)
            await self.ctx.send(text)

    def parse_ign_profile(self) -> tuple[str | None, str | None]:
        """Parses '<ign> [profile]' from the raw args; both parts are optional."""
        if not self.raw_args:
            return None, None
        parts = self.raw_args.split()
        if len(parts) > 2:
            raise UserError(f"Too many arguments. Usage: {self.usage}")
        ign = parts[0]
        profile_name = parts[1] if len(parts) > 1 else None
        return ign, profile_name

    async def fetch_profile(self, *, use_cache: bool = True) -> PlayerProfile:
        ign, profile_name = self.parse_ign_profile()
        return await self.fetch_profile_for(ign, profile_name, use_cache=use_cache)

    async def fetch_profile_for(
        self, ign: str | None, profile_name: str | None, *, use_cache: bool = True
    ) -> PlayerProfile:
        return await self.services.profiles.fetch(ign, profile_name, self.author_name, use_cache=use_cache)
