from typing import TYPE_CHECKING

from twitchio.ext import commands

if TYPE_CHECKING:
    from twitch import Bot


class CommandsCog(commands.Cog):
    def __init__(self, bot: "Bot"):
        self.bot = bot

    @commands.command(name='skills', aliases=['sa'])
    async def skills_command(self, ctx: commands.Context, *, args: str | None = None):
        """Displays the specified player's Hypixel SkyBlock skills."""
        await self.bot._skills_command.skills_command(ctx, args=args)

    @commands.command(name='skilllevel', aliases=['sl'])
    async def skill_level_command(self, ctx: commands.Context, *, args: str | None = None):
        """Displays the specified player's level for a specific skill."""
        await self.bot._skilllevel_command.skilllevel_command(ctx, args=args)

    @commands.command(name='kuudra')
    async def kuudra_command(self, ctx: commands.Context, *, args: str | None = None):
        """Displays the specified player's Kuudra completion stats."""
        await self.bot._kuudra_command.kuudra_command(ctx, args=args)

    @commands.command(name='oskill', aliases=['skillo', 'oskills', 'skillso', 'overflow'])
    async def overflow_skill_command(self, ctx: commands.Context, *, args: str | None = None):
        """Calculates and displays the specified player's Hypixel SkyBlock overflow skill XP."""
        await self.bot._oskill_command.overflow_skill_command(ctx, args=args)

    @commands.command(name='auctions', aliases=['ah'])
    async def auctions_command(self, ctx: commands.Context, *, args: str | None = None):
        """Displays the specified player's active auctions."""
        await self.bot._auctions_command.auctions_command(ctx, args=args)

    @commands.command(name='dungeon', aliases=['dungeons', 'cata'])
    async def dungeon_command(self, ctx: commands.Context, *, args: str | None = None):
        """Displays the specified player's Catacombs stats."""
        await self.bot._dungeon_command.dungeon_command(ctx, args=args)

    @commands.command(name='sblvl', aliases=['lvl'])
    async def sblvl_command(self, ctx: commands.Context, *, args: str | None = None):
        """Displays the specified player's SkyBlock level."""
        await self.bot._sblvl_command.sblvl_command(ctx, args=args)

    @commands.command(name='classaverage', aliases=['ca'])
    async def classaverage_command(self, ctx: commands.Context, *, args: str | None = None):
        """Calculates and displays the specified player's dungeon class average level."""
        await self.bot._classaverage_command.classaverage_command(ctx, args=args)

    @commands.command(name='mayor')
    async def mayor_command(self, ctx: commands.Context):
        """Displays the current SkyBlock Mayor and perks."""
        await self.bot._mayor_command.mayor_command(ctx)

    @commands.command(name='bank', aliases=['purse', 'money'])
    async def bank_command(self, ctx: commands.Context, *, args: str | None = None):
        """Displays the specified player's purse and bank balance."""
        await self.bot._bank_command.bank_command(ctx, args=args)

    @commands.command(name='nucleus')
    async def nucleus_command(self, ctx: commands.Context, *, args: str | None = None):
        """Displays the specified player's Crystal Nucleus runs."""
        await self.bot._nucleus_command.nucleus_command(ctx, args=args)

    @commands.command(name='hotm')
    async def hotm_command(self, ctx: commands.Context, *, args: str | None = None):
        """Displays the specified player's Heart of the Mountain stats."""
        await self.bot._hotm_command.hotm_command(ctx, args=args)

    @commands.command(name='essence')
    async def essence_command(self, ctx: commands.Context, *, args: str | None = None):
        """Displays the specified player's held essences."""
        await self.bot._essence_command.essence_command(ctx, args=args)

    @commands.command(name='powder')
    async def powder_command(self, ctx: commands.Context, *, args: str | None = None):
        """Displays the specified player's Mithril and Gemstone powder."""
        await self.bot._powder_command.powder_command(ctx, args=args)

    @commands.command(name='slayer', aliases=['slayers'])
    async def slayer_command(self, ctx: commands.Context, *, args: str | None = None):
        """Displays the specified player's slayer stats."""
        await self.bot._slayer_command.slayer_command(ctx, args=args)

    @commands.command(name='networth', aliases=["nw"])
    async def networth_command(self, ctx: commands.Context, *, args: str | None = None):
        """Calculates and displays the specified player's networth."""
        await self.bot._networth_command.networth_command(ctx, args=args)

    @commands.command(name='dexter')
    async def dexter_command(self, ctx: commands.Context):
        """Hidden command."""
        await self.bot.send_message(ctx, "YEP skill issue confirmed!")
    dexter_command.hidden = True

    @commands.command(name='dongo')
    async def dongo_command(self, ctx: commands.Context):
        """Hidden command."""
        await self.bot.send_message(ctx, "🥚")
    dongo_command.hidden = True

    @commands.command(name='rtca')
    async def rtca_command(self, ctx: commands.Context, *, args: str | None = None):
        """Calculates runs/time until a target Catacombs level average."""
        await self.bot._rtca_command.rtca_command(ctx, args=args)

    @commands.command(name='currdungeon')
    async def currdungeon_command(self, ctx: commands.Context, *, args: str | None = None):
        """Displays the current dungeon run information for a player, if available."""
        await self.bot._currdungeon_command.currdungeon_command(ctx, args=args)

    @commands.command(name='runstillcata', aliases=["rtc"])
    async def runstillcata_command(self, ctx: commands.Context, *, args: str | None = None):
        """Calculates runs needed until a target Catacombs level."""
        await self.bot._runstillcata_command.runstillcata_command(ctx, args=args)

    @commands.command(name='link')
    async def link_command(self, ctx: commands.Context, *, args: str | None = None):
        """Links your Twitch username to a Minecraft IGN."""
        await self.bot._link_command.link_command(ctx, args=args)

    @commands.command(name='unlink')
    async def unlink_command(self, ctx: commands.Context):
        """Removes the link between your Twitch username and Minecraft IGN."""
        await self.bot._link_command.unlink_command(ctx)

    @commands.command(name='guild', aliases=['g', 'guildof'])
    async def guild_command(self, ctx: commands.Context, *, args: str | None = None):
        """Displays the Hypixel guild the specified player is in."""
        await self.bot._guild_command.guild_command(ctx, args=args)

    @commands.command(name='whatdoing', aliases=['wd'])
    async def whatdoing_command(self, ctx: commands.Context, *, args: str | None = None):
        await self.bot._whatdoing_command.whatdoing_command(ctx, args=args)

    @commands.command(name='rtcl')  # Name des Befehls für Twitch
    async def rtcl_command(self, ctx: commands.Context, *, args: str | None = None):
        """Calculates runs for the active class to reach a target level."""
        await self.bot._rtcl_command.rtcl_command(ctx, args=args)

    @commands.command(name='secrets')
    async def secrets_command(self, ctx: commands.Context, *, args: str | None = None):
        """Displays the specified player's secret amount"""
        await self.bot._secrets_command.secrets_command(ctx, args=args)

    @commands.command(name='status')
    async def status_command(self, ctx: commands.Context, *, args: str | None = None):
        """Calculates runs/time until a target Catacombs level average."""
        await self.bot._hypixel_command.status_command(ctx, args=args)

    @commands.command(name='coinflip')
    async def coinflip_command(self, ctx: commands.Context, *, args: str | None = None):
        """Flips a coin."""
        await self.bot._coinflip_command.coinflip_command(ctx, args=args)

    @commands.command(name='roll')
    async def roll_command(self, ctx: commands.Context, *, args: str | None = None):
        """Rolls a number between 1 and 1000."""
        await self.bot._roll_command.roll_command(ctx, args=args)

    @commands.command(name='help', aliases=['info'])
    async def help_command(self, ctx: commands.Context):
        """Lists all avaible commands."""
        command_names = []
        for command in self.bot.commands.values():
            if getattr(command, 'hidden', False):
                continue
            command_names.append(command.name)
        command_names.sort()
        formatted_commands = " | ".join([f"{'#'}{name}" for name in command_names])
        formatted_commands += ' | made by Iceshadow_'

        await self.bot.send_message(ctx, formatted_commands)
