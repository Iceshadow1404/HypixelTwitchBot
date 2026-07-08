# importing a command module runs its @command decorators, filling the REGISTRY
from bot.commands import combat, dungeon_runs, dungeons, fun, mining, skills  # noqa: F401
from bot.commands.base import REGISTRY, CommandContext, CommandSpec, command

__all__ = ["REGISTRY", "CommandContext", "CommandSpec", "command"]
