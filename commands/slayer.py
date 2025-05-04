import traceback
from twitchio.ext import commands

import constants
from utils import _parse_command_args
from calculations import calculate_slayer_level, format_price

class SlayerCommand:
    def __init__(self, bot):
        self.bot = bot

    async def slayer_command(self, ctx: commands.Context, *, args: str | None = None):

        parsed_args = await _parse_command_args(self.bot, ctx, args, 'slayer')
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
            slayer_data = member_data.get('slayer', {}).get('slayer_bosses', {})

            if not slayer_data:
                print(f"[INFO][SlayerCmd] No slayer data found for {target_ign} in profile {profile_name}.")
                await self.bot.send_message(ctx, f"'{target_ign}' has no slayer data in profile '{profile_name}'.")
                return

            slayer_levels = []
            for boss_key in self.bot.constants.SLAYER_BOSS_KEYS:
                boss_data = slayer_data.get(boss_key, {})
                xp = boss_data.get('xp', 0)
                level = calculate_slayer_level(self.bot.leveling_data, xp, boss_key)
                # Capitalize boss name for display
                display_name = boss_key.capitalize()
                # Format with integer level and formatted XP
                xp_str = format_price(xp) 
                slayer_levels.append(f"{display_name} {level} ({xp_str} XP)")

            output_message = f"{target_ign}'s Slayers (Profile: '{profile_name}'): { ' | '.join(slayer_levels) }"
            await self.bot.send_message(ctx, output_message)

        except Exception as e:
            print(f"[ERROR][SlayerCmd] Unexpected error processing slayer data: {e}")
            traceback.print_exc()
            await self.bot.send_message(ctx, "An unexpected error occurred while fetching slayer levels.")
