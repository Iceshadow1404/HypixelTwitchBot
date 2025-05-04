import traceback
from twitchio.ext import commands

import constants
from utils import _parse_command_args
from calculations import format_price

class EssenceCommand:
    def __init__(self, bot):
        self.bot = bot

    async def essence_command(self, ctx: commands.Context, *, args: str | None = None):
        """Shows the player's current essence amounts.
        Syntax: #essence <username> [profile_name]
        """
        # Use the imported utility function to parse arguments
        parsed_args = await _parse_command_args(self.bot, ctx, args, 'essence')
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
            currencies_data = member_data.get('currencies', {})

            # Get the main essence container
            all_essence_data = currencies_data.get('essence', {})

            if not all_essence_data:
                print(f"[INFO][EssenceCmd] No essence data found for {target_ign} in profile {profile_name}.")

                await self.bot.send_message(ctx, f"No essence data found for '{target_ign}' in profile '{profile_name}'.")
                return

            essence_amounts = []
            for essence_type in self.bot.constants.ESSENCE_TYPES:
                essence_type_data = all_essence_data.get(essence_type, {})
                amount = essence_type_data.get('current', 0)

                # Use capitalized full name
                display_name = essence_type.capitalize() 
                # Use imported format_price function
                amount_str = format_price(amount)
                essence_amounts.append(f"{display_name}: {amount_str}")

            output_message = f"{target_ign} (Profile: '{profile_name}'): { ' | '.join(essence_amounts) }"
            await self.bot.send_message(ctx, output_message)

        except Exception as e:
            print(f"[ERROR][EssenceCmd] Unexpected error processing essence data: {e}")
            traceback.print_exc()
            await self.bot.send_message(ctx, "An unexpected error occurred while fetching essences.")
