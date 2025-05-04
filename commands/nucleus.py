import traceback
from twitchio.ext import commands

import constants
from utils import _parse_command_args

class NucleusCommand:
    def __init__(self, bot):
        self.bot = bot

    async def nucleus_command(self, ctx: commands.Context, *, args: str | None = None):
        """Calculates the approximate number of nucleus runs completed.
        Syntax: #nucleus <username> [profile_name]
        """
        # Use the imported utility function to parse arguments
        parsed_args = await _parse_command_args(self.bot, ctx, args, 'nucleus')
        if parsed_args is None:
            return
        ign, requested_profile_name = parsed_args

        profile_data = await self.bot._get_player_profile_data(ctx, ign, requested_profile_name=requested_profile_name)
        if not profile_data:
            return

        target_ign, player_uuid, selected_profile = profile_data
        profile_name = selected_profile.get('cute_name', 'Unknown')

        try:
            member_data = selected_profile.get('members', {}).get(player_uuid, {})
            mining_core_data = member_data.get('mining_core', {})
            crystals_data = mining_core_data.get('crystals', {})

            sum_total_placed = 0
            print(f"[DEBUG][NucleusCmd] Calculating for {target_ign} ({profile_name}):")
            # Use constants from the bot instance
            for crystal_key in self.bot.constants.NUCLEUS_CRYSTALS:
                crystal_info = crystals_data.get(crystal_key, {})
                total_placed = crystal_info.get('total_placed', 0)
                sum_total_placed += total_placed
                print(f"  - {crystal_key}: {total_placed}")

            # Calculate result: sum divided by 5, rounded down
            nucleus_result = sum_total_placed // 5
            print(f"[DEBUG][NucleusCmd] Sum: {sum_total_placed}, Result (Sum // 5): {nucleus_result}")

            await self.bot.send_message(ctx, f"{target_ign}'s nucleus runs: {nucleus_result} (Profile: '{profile_name}')")

        except Exception as e:
            print(f"[ERROR][NucleusCmd] Unexpected error processing nucleus data: {e}")
            traceback.print_exc()
            await self.bot.send_message(ctx, "An unexpected error occurred while fetching Nucleus runs.")
