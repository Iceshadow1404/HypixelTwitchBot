import traceback
import math
from twitchio.ext import commands

from utils import _parse_command_args
from calculations import calculate_dungeon_level, _get_xp_for_target_level

class RunsTillCataCommand:
    def __init__(self, bot):
        self.bot = bot

    async def runstillcata_command(self, ctx: commands.Context, *, args: str | None = None):
        print(f"[COMMAND] RunsTillCata command triggered by {ctx.author.name}: {args}")

        ign: str | None = None
        requested_profile_name: str | None = None
        target_level_str: str | None = None
        floor_str: str = 'm7'   # Default floor

        if not args:
            ign = ctx.author.name
            print(f"[DEBUG][RunsTillCataCmd] No arguments provided, defaulting IGN to: {ign}")
        else:
            parts = args.split()

            # First pass: Check if the first argument is a floor or target level
            if parts[0].lower() in ['m6', 'm7'] or (parts[0].isdigit() and int(parts[0]) < 100):
                ign = ctx.author.name
                print(f"[DEBUG][RunsTillCataCmd] First arg is floor or target: {parts[0]}, defaulting IGN to: {ign}")

                # Now treat all parts as remaining parts to be identified
                remaining_parts = parts
            else:
                # Original behavior: first part is the IGN
                ign = parts[0]
                remaining_parts = parts[1:]

            potential_profile_name = None
            potential_target_level = None
            potential_floor = None
            unidentified_parts = []

            for part in remaining_parts:
                part_lower = part.lower()
                if part_lower in ['m6', 'm7'] and potential_floor is None:
                    potential_floor = part_lower
                elif part.isdigit() and potential_target_level is None:
                    potential_target_level = part
                elif potential_profile_name is None and not (
                        part_lower in ['m6', 'm7'] or (part.isdigit() and int(part) < 100)):
                    potential_profile_name = part
                else:
                    unidentified_parts.append(part)

            requested_profile_name = potential_profile_name
            if potential_target_level is not None:
                target_level_str = potential_target_level
            if potential_floor is not None:
                floor_str = potential_floor

            if unidentified_parts:
                usage_message = f"Too many or ambiguous arguments: {unidentified_parts}. Usage: {self.bot._prefix}runstillcata <username> [profile_name] [target_level] [floor=m7]"
                await self.bot._send_message(ctx, usage_message)
                return
             
        target_level: int | None = None 
        try:
            # Validate floor
            if floor_str not in ['m6', 'm7']:
                raise ValueError("Invalid floor. Please specify 'm6' or 'm7'.")
            print(f"[DEBUG][RunsTillCataCmd] Validated floor_str: {floor_str}")

            if target_level_str:
                target_level = int(target_level_str)
                if not 1 <= target_level <= 99: 
                    raise ValueError("Target level must be between 1 and 99.")
                print(f"[DEBUG][RunsTillCataCmd] Validated target_level: {target_level}")

        except ValueError as e:
            await self.bot._send_message(ctx, f"Invalid argument: {e}. Usage: {self.bot._prefix}runstillcata <username> [profile_name] [target_level] [floor=m7]")
            return

        profile_data = await self.bot._get_player_profile_data(ctx, ign, requested_profile_name=requested_profile_name)
        if not profile_data:
            return 

        target_ign, player_uuid, selected_profile = profile_data
        profile_name = selected_profile.get('cute_name', 'Unknown')

        try:
            member_data = selected_profile.get('members', {}).get(player_uuid, {})
            dungeons_data = member_data.get('dungeons', {}).get('dungeon_types', {}).get('catacombs', {})
            current_xp = dungeons_data.get('experience', 0)
            current_level = calculate_dungeon_level(self.bot.leveling_data, current_xp)
            
            if target_level is None:
                target_level_calc = math.ceil(current_level) 
                if target_level_calc == math.floor(current_level):
                    target_level_calc += 1
            else:
                target_level_calc = target_level
                
            xp_for_target_level = _get_xp_for_target_level(self.bot.leveling_data, target_level_calc)
            xp_needed = xp_for_target_level - current_xp

            if xp_needed <= 0:
                await self.bot._send_message(ctx, f"{target_ign} has already reached Catacombs level {target_level_calc}!")
                return
            if floor_str == 'm6':
                xp_per_run = 180000 # Base M6 Cata XP
                floor_name = "M6"
            else: 
                xp_per_run = 500000 # Base M7 Cata XP
                floor_name = "M7"
            
            if xp_per_run <= 0:
                 await self.bot._send_message(ctx, "Invalid XP per run configured.")
                 return

            runs_needed = math.ceil(xp_needed / xp_per_run)

            output_message = (
                f"{target_ign} (Cata {current_level:.2f}) needs {xp_needed:,.0f} XP for level {target_level_calc}. "
                f"{floor_name}: {runs_needed:,} runs ({xp_per_run:,} XP/run)"
            )
            await self.bot._send_message(ctx, output_message)

        except Exception as e:
            print(f"[ERROR][RunsTillCataCmd] Unexpected error: {e}")
            traceback.print_exc()
            await self.bot._send_message(ctx, f"An unexpected error occurred while calculating runs needed for '{target_ign}'.")
