from twitchio.ext import commands
import random

class roll:
    def __init__(self, bot):
        self.bot = bot

    async def roll_command(self, ctx: commands.Context, *, args: str | None = None):
        bot = ctx.bot

        min_val = 1
        max_val = 1000

        if args:
            parts = args.strip().split()
            if len(parts) >= 2:
                try:
                    min_val = int(parts[0])
                    max_val = int(parts[1])
                    if min_val >= max_val:
                        await bot.send_message(ctx, f"Error: min must be less than max")
                        return
                except ValueError:
                    await bot.send_message(ctx, f"Error: Invalid numbers. Usage: #roll [min] [max]")
                    return
            elif len(parts) == 1:
                try:
                    max_val = int(parts[0])
                except ValueError:
                    await bot.send_message(ctx, f"Error: Invalid number. Usage: #roll [min] [max]")
                    return

        result = random.randint(min_val, max_val)
        print(f"Rolled: {result} (range: {min_val}-{max_val})")

        await bot.send_message(ctx, f"You rolled: {result}")
