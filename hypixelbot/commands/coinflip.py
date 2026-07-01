from twitchio.ext import commands
import random
import string

class coinflip:
    def __init__(self, bot):
        self.bot = bot

    async def coinflip_command(self, ctx: commands.Context, *, args: str | None = None):
        bot = ctx.bot

        result = random.choice(['Heads', 'Tails'])
        print("The coin landed on:", result)

        await bot.send_message(ctx, f"{result}, {''.join(random.choices(string.ascii_letters + string.digits, k=10))}")





