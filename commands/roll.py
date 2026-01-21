from twitchio.ext import commands
import random

class roll:
    def __init__(self, bot):
        self.bot = bot

    async def roll_command(self, ctx: commands.Context, *, args: str | None = None):
        bot = ctx.bot

        result = random.randint(1, 1000)
        print(f"Rolled: {result}")

        await bot.send_message(ctx, f"You rolled: {result}")
