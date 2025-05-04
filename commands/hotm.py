import traceback
from twitchio.ext import commands

from utils import _parse_command_args
from calculations import calculate_hotm_level

class HotmCommand:
    def __init__(self, bot):
        self.bot = bot

    async def hotm_command(self, ctx: commands.Context, *, args: str | None = None):
        """Shows the player's Heart of the Mountain level and XP.
        Syntax: #hotm <username> [profile_name]
        """
        # Use the imported utility function to parse arguments
        parsed_args = await _parse_command_args(self.bot, ctx, args, 'hotm')
        if parsed_args is None:
            return
        ign, requested_profile_name = parsed_args

        # Use the bot's helper method to fetch profile data
        profile_data = await self.bot._get_player_profile_data(ctx, ign, requested_profile_name=requested_profile_name)
        if not profile_data:
             return

        target_ign, player_uuid, selected_profile = profile_data
        profile_name = selected_profile.get('cute_name', 'Unknown')

        try:
            member_data = selected_profile.get('members', {}).get(player_uuid, {})
            mining_core_data = member_data.get('mining_core', {})
            hotm_xp = mining_core_data.get('experience', 0.0)

            # Use the imported calculation function and bot's leveling data
            level = calculate_hotm_level(self.bot.leveling_data, hotm_xp)
            await self.bot.send_message(ctx, f"{target_ign}'s HotM level is {level:.2f} (XP: {hotm_xp:,.0f}) (Profile: '{profile_name}')")

        except Exception as e:
            print(f"[ERROR][HotmCmd] Unexpected error processing HotM data: {e}")
            traceback.print_exc()
            await self.bot.send_message(ctx, "An unexpected error occurred while fetching HotM level.")
