import traceback
from twitchio.ext import commands

from utils import _parse_command_args

class PowderCommand:
    def __init__(self, bot):
        self.bot = bot

    async def powder_command(self, ctx: commands.Context, *, args: str | None = None):

        parsed_args = await _parse_command_args(self.bot, ctx, args, 'powder')
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

            # Get current powder values
            current_mithril = mining_core_data.get('powder_mithril', 0)
            current_gemstone = mining_core_data.get('powder_gemstone', 0)
            current_glacite = mining_core_data.get('powder_glacite', 0)

            # Get spent powder values
            spent_mithril = mining_core_data.get('powder_spent_mithril', 0)
            spent_gemstone = mining_core_data.get('powder_spent_gemstone', 0)
            spent_glacite = mining_core_data.get('powder_spent_glacite', 0)

            # Calculate totals
            total_mithril = current_mithril + spent_mithril
            total_gemstone = current_gemstone + spent_gemstone
            total_glacite = current_glacite + spent_glacite

            # Format the output string
            output_message = (
                f"{target_ign}'s powder ({profile_name}): "
                f"mithril powder: {current_mithril:,.0f} (total: {total_mithril:,.0f}) | "
                f"gemstone powder: {current_gemstone:,.0f} (total: {total_gemstone:,.0f}) | "
                f"glacite powder: {current_glacite:,.0f} (total: {total_glacite:,.0f})"
            )

            await self.bot.send_message(ctx, output_message)

        except Exception as e:
            print(f"[ERROR][PowderCmd] Unexpected error processing powder data: {e}")
            traceback.print_exc()
            await self.bot.send_message(ctx, "An unexpected error occurred while fetching powder amounts.")
