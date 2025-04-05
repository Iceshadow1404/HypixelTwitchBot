import traceback
from twitchio.ext import commands

from utils import _parse_command_args

class BankCommand:
    def __init__(self, bot):
        self.bot = bot

    async def bank_command(self, ctx: commands.Context, *, args: str | None = None):
        """Shows the player's purse and bank balance.
        Syntax: #bank <username> [profile_name]
        Aliases: purse, money
        """
        parsed_args = await _parse_command_args(self.bot, ctx, args, 'bank')
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
            # Bank Balance (Profile wide)
            banking_data = selected_profile.get('banking', {})
            bank_balance = banking_data.get('balance', 0.0)

            # Purse and Personal Bank (Member specific)
            member_data = selected_profile.get('members', {}).get(player_uuid, {})
            currencies_data = member_data.get('currencies', {})
            purse_balance = currencies_data.get('coin_purse', 0.0)
            personal_bank_balance = member_data.get('profile', {}).get('bank_account', None)

            # Construct the output message
            parts = [
                f"{target_ign}'s Bank: {bank_balance:,.0f}",
                f"Purse: {purse_balance:,.0f}"
            ]
            if personal_bank_balance is not None:
                parts.append(f"Personal Bank: {personal_bank_balance:,.0f}")
            parts.append(f"(Profile: '{profile_name}')")

            output_message = ", ".join(parts)
            await self.bot._send_message(ctx, output_message)

        except Exception as e:
            print(f"[ERROR][BankCmd] Unexpected error processing balance data: {e}")
            traceback.print_exc()
            await self.bot._send_message(ctx, "An unexpected error occurred while fetching balance information.")
