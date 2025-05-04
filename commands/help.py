from twitchio.ext import commands

class HelpCommand:
    def __init__(self, bot):
        self.bot = bot

    async def help_command(self, ctx: commands.Context):
        """Displays available commands."""
        print(f"[COMMAND] Help command triggered by {ctx.author.name} in #{ctx.channel.name}")
        prefix = self.bot._prefix # Get the bot's prefix
        
        help_parts = [f"Available commands (Prefix: {prefix}):"]
        
        # Sort commands alphabetically for clarity, access via self.bot
        command_list = sorted(self.bot.commands.values(), key=lambda cmd: cmd.name)
        
        for cmd in command_list:
            # Skip hidden commands
            if getattr(cmd, 'hidden', False):
                continue
                
            # Format aliases
            aliases = f" (Aliases: {', '.join(cmd.aliases)})" if cmd.aliases else ""
            
            help_parts.append(f"- {prefix}{cmd.name}{aliases}")

        help_message = " ".join(help_parts)
        
        await self.bot.send_message(ctx, help_message)