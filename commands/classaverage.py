from twitchio.ext import commands
import traceback
from calculations import calculate_class_level

class ClassAverageCommand:
    def __init__(self, bot):
        self.bot = bot

    async def classaverage_command(self, ctx: commands.Context, *, args: str | None = None):

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
                await self.bot.send_message(ctx, f"Too many arguments. Usage: {self.bot._prefix}classaverage <username> [profile_name]")
                return

        profile_data = await self.bot._get_player_profile_data(ctx, ign, requested_profile_name=requested_profile_name)
        if not profile_data:
            return

        target_ign, player_uuid, selected_profile = profile_data
        profile_name = selected_profile.get('cute_name', 'Unknown')

        try:
            member_data = selected_profile.get('members', {}).get(player_uuid, {})
            dungeons_data = member_data.get('dungeons', {})
            player_classes_data = dungeons_data.get('player_classes', None) # Check for None

            if player_classes_data is None:
                print(f"[INFO][ClassAvgCmd] No player_classes data found for {target_ign} in profile {profile_name}.")
                return

            class_levels = {}
            total_level = 0.0
            valid_classes_counted = 0

            for class_name in self.bot.constants.CLASS_NAMES:
                class_xp = player_classes_data.get(class_name, {}).get('experience', 0)
                level = calculate_class_level(self.bot.leveling_data, class_xp)
                class_levels[class_name.capitalize()] = level
                total_level += level
                valid_classes_counted += 1 # Count even if level is 0

            if valid_classes_counted > 0:
                average_level = total_level / valid_classes_counted
                levels_str = " | ".join([f"{name} {lvl:.2f}" for name, lvl in class_levels.items()])
                await self.bot.send_message(ctx, f"{target_ign}'s class levels in profile '{profile_name}': {levels_str} | Average: {average_level:.2f}")
            else:
                print(f"[WARN][ClassAvgCmd] No valid classes found to calculate average for {target_ign}.")
                await self.bot.send_message(ctx, f"Could not calculate class average for '{target_ign}'.")

        except Exception as e:
            print(f"[ERROR][ClassAvgCmd] Unexpected error processing class levels: {e}")
            traceback.print_exc()
            await self.bot.send_message(ctx, "An unexpected error occurred while fetching class levels.")
