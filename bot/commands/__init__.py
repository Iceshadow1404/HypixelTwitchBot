# importing a command module runs its @command decorators, filling the REGISTRY
from bot.commands import (  # noqa: F401
    combat,
    dungeon_runs,
    dungeons,
    economy,
    fun,
    mining,
    player,
    server,
    skills,
)
from bot.commands.base import REGISTRY, CommandContext, CommandSpec, command

__all__ = ["REGISTRY", "CommandContext", "CommandSpec", "command"]
