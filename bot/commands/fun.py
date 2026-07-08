import random
import string

from bot.commands.base import REGISTRY, CommandContext, command
from bot.errors import UserError


@command("coinflip")
async def coinflip(cc: CommandContext) -> None:
    result = random.choice(["Heads", "Tails"])
    nonce = "".join(random.choices(string.ascii_letters + string.digits, k=10))
    await cc.reply(f"{result}, {nonce}")


@command("roll", usage="[min] [max]")
async def roll(cc: CommandContext) -> None:
    min_val, max_val = 1, 1000
    if cc.raw_args:
        parts = cc.raw_args.split()
        try:
            if len(parts) >= 2:
                min_val, max_val = int(parts[0]), int(parts[1])
            elif len(parts) == 1:
                max_val = int(parts[0])
        except ValueError:
            raise UserError(f"Error: Invalid numbers. Usage: {cc.usage}") from None
        if min_val >= max_val:
            raise UserError("Error: min must be less than max")
    await cc.reply(f"You rolled: {random.randint(min_val, max_val)}")


@command("dexter", hidden=True)
async def dexter(cc: CommandContext) -> None:
    await cc.reply("YEP skill issue confirmed!")


@command("dongo", hidden=True)
async def dongo(cc: CommandContext) -> None:
    await cc.reply("🥚")


@command("help", aliases=("info",))
async def help_command(cc: CommandContext) -> None:
    prefix = cc.ctx.prefix or "#"
    names = sorted(spec.name for spec in REGISTRY if not spec.hidden)
    listing = " | ".join(f"{prefix}{name}" for name in names)
    await cc.reply(f"{listing} | made by Iceshadow_")
