# NOTE: no `from __future__ import annotations` here — twitchio 2.x evals command
# callback annotations in this module's globals.
import asyncio
import logging

import aiohttp
from twitchio.ext import commands

from bot.commands import REGISTRY, CommandContext, CommandSpec
from bot.config import Settings
from bot.errors import UserError
from bot.services import Services, build_services

logger = logging.getLogger(__name__)

CACHE_CLEANUP_INTERVAL = 3600


class SkyBot(commands.Bot):
    """Twitch bot: owns the connection, dispatches registry commands, runs background tasks."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.services: Services | None = None
        self._ready_once = False
        super().__init__(
            token=settings.token,
            prefix=settings.prefix,
            nick=settings.nickname,
            initial_channels=list(settings.initial_channels),
        )
        self._register_commands()

    def _register_commands(self) -> None:
        for spec in REGISTRY:
            self.add_command(
                commands.Command(name=spec.name, func=self._make_callback(spec), aliases=list(spec.aliases))
            )

    def _make_callback(self, spec: CommandSpec):
        async def callback(ctx: commands.Context, *, args: str | None = None) -> None:
            if self.services is None:
                logger.warning("command %r invoked before bot was ready, ignoring", spec.name)
                return
            cc = CommandContext(ctx, self.services, args, spec)
            try:
                await spec.handler(cc)
            except UserError as e:
                await cc.reply(str(e))
            except Exception:
                logger.exception(
                    "command %r failed (channel #%s, args %r)", spec.name, ctx.channel.name, args
                )
                await cc.reply("An unexpected error occurred.")

        return callback

    # --- events ---

    async def event_ready(self) -> None:
        if self._ready_once:
            logger.info("event_ready re-fired (reconnect), skipping re-initialization")
            return
        self._ready_once = True

        session = aiohttp.ClientSession()
        self.services = build_services(self.settings, session)
        logger.info("logged in as %s (%s)", self.nick, self.user_id)

        connected = [ch.name for ch in self.connected_channels if ch is not None]
        logger.info("joined initial channels: %s", connected)

        asyncio.create_task(self._periodic_cache_cleanup())
        asyncio.create_task(self.services.networth.wait_until_ready())
        logger.info("bot is ready")

    async def event_message(self, message) -> None:
        if message.echo:
            return
        if not getattr(message.channel, "name", None) or not getattr(message.author, "name", None):
            return
        connected = {ch.name for ch in self.connected_channels if ch is not None}
        if message.channel.name not in connected:
            return
        await self.handle_commands(message)

    async def event_command_error(self, context: commands.Context, error: Exception) -> None:
        channel = getattr(context.channel, "name", "unknown")
        if isinstance(error, commands.CommandNotFound):
            logger.warning("command not found in #%s: %s", channel, error)
        else:
            logger.error("command error in #%s: %s", channel, error, exc_info=error)

    async def event_error(self, error: Exception, data: str | None = None) -> None:
        logger.error("unhandled bot error: %s", error, exc_info=error)

    # --- background tasks / lifecycle ---

    async def _periodic_cache_cleanup(self) -> None:
        while True:
            await asyncio.sleep(CACHE_CLEANUP_INTERVAL)
            try:
                if self.services:
                    removed = self.services.hypixel.cleanup_expired()
                    removed += self.services.mojang.cache.cleanup_expired()
                    logger.info("cache cleanup removed %d expired entries", removed)
            except Exception:
                logger.exception("cache cleanup failed")

    async def close(self) -> None:
        logger.info("shutting down bot")
        if self.services and not self.services.session.closed:
            await self.services.session.close()
        await super().close()
