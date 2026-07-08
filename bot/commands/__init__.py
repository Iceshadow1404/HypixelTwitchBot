# importing a command module runs its @command decorators, filling the REGISTRY
from bot.commands import fun  # noqa: F401
from bot.commands.base import REGISTRY, CommandContext, CommandSpec, command

__all__ = ["REGISTRY", "CommandContext", "CommandSpec", "command"]
