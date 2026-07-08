from bot.commands import combat, dungeon_runs, dungeons, economy, fun, mining, player, server, skills
from bot.commands.base import REGISTRY, CommandContext, CommandSpec, command

# importing a command module runs its @command decorators, filling the REGISTRY
COMMAND_MODULES = (combat, dungeon_runs, dungeons, economy, fun, mining, player, server, skills)

__all__ = ["COMMAND_MODULES", "REGISTRY", "CommandContext", "CommandSpec", "command"]
