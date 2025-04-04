from twitchio.ext import commands
import traceback

class KuudraCommand:
    def __init__(self, bot):
        self.bot = bot

    async def kuudra_command(self, ctx: commands.Context, *, args: str | None = None):
        """Shows Kuudra completions for different tiers and calculates a score.
        Syntax: #kuudra <username> [profile_name]
        """
        ign: str | None = None
        requested_profile_name: str | None = None

        if not args:
            ign = ctx.author.name
        else:
            parts = args.split()
            ign = parts[0]
            if len(parts) > 1:
                requested_profile_name = parts[1]
            if len(parts) > 2:
                await self.bot._send_message(ctx, f"Too many arguments. Usage: {self.bot._prefix}kuudra <username> [profile_name]")
                return

        profile_data = await self.bot._get_player_profile_data(ctx, ign, requested_profile_name=requested_profile_name)
        if not profile_data:
            return # Error message already sent by helper

        target_ign, player_uuid, selected_profile = profile_data
        profile_name = selected_profile.get('cute_name', 'Unknown')

        try:
            member_data = selected_profile.get('members', {}).get(player_uuid, {})
            nether_island_data = member_data.get('nether_island_player_data', None) # Check for None first

            if nether_island_data is None:
                print(f"[INFO][KuudraCmd] No nether_island_player_data found for {target_ign} in profile {profile_name}.")
                return

            kuudra_completed_tiers = nether_island_data.get('kuudra_completed_tiers', None) # Check for None

            if kuudra_completed_tiers is None or not kuudra_completed_tiers: # Check for None or empty dict
                print(f"[INFO][KuudraCmd] No Kuudra completions recorded for {target_ign} in profile {profile_name}.")
                await self.bot._send_message(ctx, f"No Kuudra completions recorded for {target_ign} in profile {profile_name}.")
                return

            # Format output
            completions = []
            total_score = 0
            for tier in self.bot.constants.KUUDRA_TIERS_ORDER:
                count = kuudra_completed_tiers.get(tier, 0)
                tier_name = 'basic' if tier == 'none' else tier # Rename 'none' to 'basic'
                completions.append(f"{tier_name} {count}")
                total_score += count * self.bot.constants.KUUDRA_TIER_POINTS.get(tier, 0) # Use .get for safety

            await self.bot._send_message(ctx, f"{target_ign}'s Kuudra completions in profile '{profile_name}': {', '.join(completions)} | Score: {total_score:,}")

        except Exception as e:
            print(f"[ERROR][KuudraCmd] Unexpected error processing Kuudra data: {e}")
            traceback.print_exc()
            await self.bot._send_message(ctx, "An unexpected error occurred while fetching Kuudra completions.")
