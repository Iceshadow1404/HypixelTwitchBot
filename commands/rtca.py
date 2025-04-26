import traceback
import math
from twitchio.ext import commands

import constants
from utils import _parse_command_args
from calculations import calculate_class_level, _get_xp_for_target_level

class RtcaCommand:
    def __init__(self, bot):
        self.bot = bot

    async def rtca_command(self, ctx: commands.Context, *, args: str | None = None):
        """Calculates runs needed to reach a target Class Average (CA).
        Syntax: #rtca <username> [profile_name] [target_ca=50] [floor=m7]
        Example: #rtca Player1 Apple 55 m6
        """
        print(f"[COMMAND] Rtca command triggered by {ctx.author.name}: {args}")

        ign: str | None = None
        requested_profile_name: str | None = None
        target_ca_str: str = '50'
        floor_str: str = 'm7'

        args = args.strip() if args else None
        if args and not any(c.isalnum() for c in args):
            # If args has no alphanumeric characters, treat it as None
            args = None

        if not args:
            ign = ctx.author.name

            print(f"[DEBUG][RtcaCmd] No arguments (or only whitespace) provided, defaulting IGN to: {ign}")
        else:
            # This part now only runs if args contained non-whitespace characters
            parts = args.split()

            # Check if any part is a floor identifier
            has_floor = any(part.lower() in ['m6', 'm7'] for part in parts)
            # Check if any part is a potential target CA
            has_target_ca = any(part.isdigit() and int(part) < 100 for part in parts)

            # If the first argument is a floor or target CA, use author's name as IGN
            if parts[0].lower() in ['m6', 'm7'] or (parts[0].isdigit() and int(parts[0]) < 100):
                ign = ctx.author.name
                print(f"[DEBUG][RtcaCmd] First arg is floor or target: {parts[0]}, defaulting IGN to: {ign}")

                # Now treat all parts as remaining parts to be identified
                remaining_parts = parts
            else:
                # Original behavior: first part is the IGN
                ign = parts[0]
                remaining_parts = parts[1:]

            potential_profile_name = None
            potential_target_ca = None
            potential_floor = None
            unidentified_parts = []

            # Iterate through remaining parts to identify them
            for part in remaining_parts:
                part_lower = part.lower()
                if part_lower in ['m6', 'm7'] and potential_floor is None:
                    potential_floor = part_lower
                elif part.isdigit() and int(part) < 100 and potential_target_ca is None:
                    potential_target_ca = part
                elif potential_profile_name is None and not (
                        part_lower in ['m6', 'm7'] or (part.isdigit() and int(part) < 100)):
                    potential_profile_name = part
                else:
                    unidentified_parts.append(part)

            requested_profile_name = potential_profile_name
            if potential_target_ca is not None:
                target_ca_str = potential_target_ca
            if potential_floor is not None:
                floor_str = potential_floor

            if unidentified_parts:
                usage_message = f"Too many or ambiguous arguments: {unidentified_parts}. Usage: {self.bot._prefix}rtca <username> [profile_name] [target_ca=50] [floor=m7]"
                await self.bot._send_message(ctx, usage_message)
                return

        target_level: int
        try:
            # Validate target level (must be an integer)
            target_level = int(target_ca_str)
            if not 1 <= target_level <= 99: 
                raise ValueError("Target CA must be between 1 and 99.")
            print(f"[DEBUG][RtcaCmd] Validated target_level: {target_level}")

        except ValueError as e:
            await self.bot._send_message(ctx, f"Invalid argument: {e}. Usage: {self.bot._prefix}rtca <username> [profile_name] [target_ca=50] [floor=m7]")
            return

        profile_data = await self.bot._get_player_profile_data(ctx, ign, requested_profile_name=requested_profile_name, useCache=False)
        if not profile_data:
            return 

        target_ign, player_uuid, selected_profile = profile_data
        profile_name = selected_profile.get('cute_name', 'Unknown')
        print(f"[INFO][RtcaCmd] Using profile: {profile_name}") 

        try:
            member_data = selected_profile.get('members', {}).get(player_uuid, {})
            dungeons_data = member_data.get('dungeons', {})
            player_classes_data = dungeons_data.get('player_classes', None)

            selected_class = dungeons_data.get('selected_dungeon_class')
            selected_class_lower = selected_class.lower() if selected_class else None 
            print(f"[DEBUG][RtcaCmd] Fetched selected class from profile '{profile_name}': {selected_class}")

            if player_classes_data is None:
                 print(f"[INFO][RtcaCmd] No player_classes data found for {target_ign} in profile {profile_name}.")
                 await self.bot._send_message(ctx, f"'{target_ign}' has no class data in profile '{profile_name}'.")
                 return

            current_class_levels = {}
            total_level_sum = 0.0
            class_xps = {}

            for class_name in self.bot.constants.CLASS_NAMES:
                class_xp = player_classes_data.get(class_name, {}).get('experience', 0)

                level = calculate_class_level(self.bot.leveling_data, class_xp)
                current_class_levels[class_name] = level
                class_xps[class_name] = class_xp
                total_level_sum += level
            
            current_ca = total_level_sum / len(self.bot.constants.CLASS_NAMES) if self.bot.constants.CLASS_NAMES else 0.0
            print(f"[DEBUG][RtcaCmd] {target_ign} - Current CA: {current_ca:.2f}, Target CA: {target_level}") # Use validated int target_level

            if current_ca >= target_level:
                # Check if any class is still below target level
                classes_below_target = [cn for cn, level in current_class_levels.items() if level < target_level]

                if not classes_below_target:
                    await self.bot._send_message(ctx,
                                                 f"{target_ign} (CA {current_ca:.2f}) has already reached or surpassed the target Class Average {target_level}.")
                    return
                else:
                    # Continue with the calculation even though CA is reached, because individual classes need leveling
                    print(f"[DEBUG][RtcaCmd] CA target met but classes still below target: {classes_below_target}")

            target_level_for_milestone = target_level 

            if floor_str == 'm6':
                xp_per_run = self.bot.constants.BASE_M6_CLASS_XP
                selected_floor_name = "M6"
            else: 
                xp_per_run = self.bot.constants.BASE_M7_CLASS_XP
                selected_floor_name = "M7"
                
            # --- Optional XP boost logic (kept commented out) ---
            xp_per_run *= 1.06 # CURRENT FIX NEED TO IMPLEMENT CLASS XP BOOSTS

            if xp_per_run <= 0: # Safety check
                print(f"[ERROR][RtcaCmd] Base XP per run is zero or negative for {selected_floor_name}.")
                await self.bot._send_message(ctx, "Error with base XP configuration. Cannot estimate runs.")
                return

            xp_required_for_target_level = _get_xp_for_target_level(self.bot.leveling_data, target_level_for_milestone)
            print(f"[DEBUG][RtcaCmd] Target Level XP Threshold: {xp_required_for_target_level:,.0f}")
            print(f"[DEBUG][RtcaCmd] XP/Run Used ({selected_floor_name}): {xp_per_run:,.0f}")

            total_runs_simulated = 0
            xp_needed_dict = {} # Stores remaining XP needed for each class
            active_runs_per_class = {cn: 0 for cn in self.bot.constants.CLASS_NAMES}
            
            print(f"[DEBUG][RtcaSim] --- Initializing Simulation Needs ---")
            for class_name in self.bot.constants.CLASS_NAMES:
                current_xp = class_xps[class_name]
                current_lvl = current_class_levels[class_name]
                if current_lvl < target_level_for_milestone:
                    needed = xp_required_for_target_level - current_xp
                    if needed > 0:
                        xp_needed_dict[class_name] = needed
                        print(f"[DEBUG][RtcaSim] Initial Need - {class_name.capitalize()}: {needed:,.0f} XP")
                    else:
                        print(f"[DEBUG][RtcaSim] Initial Need - {class_name.capitalize()}: 0 XP (Already Met)")
                else:
                    print(f"[DEBUG][RtcaSim] Initial Need - {class_name.capitalize()}: 0 XP (Level Met)")

            # Check if simulation is necessary
            if not xp_needed_dict:
                await self.bot._send_message(ctx, f"{target_ign} already meets the XP requirements for CA {target_level}.")
                return
            
            print(f"[DEBUG][RtcaSim] --- Starting Simulation Loop ---")
            max_iterations = 100000
            iteration = 0
            active_gain = xp_per_run
            passive_gain = 0.25 * xp_per_run
            
            while xp_needed_dict and iteration < max_iterations:
                iteration += 1
                total_runs_simulated += 1

                # Find bottleneck class (needs most runs if played actively)
                bottleneck_class = None
                max_runs_if_active = -1
                for cn, needed in xp_needed_dict.items():

                    runs_if_active = math.ceil(needed / active_gain)
                    if runs_if_active > max_runs_if_active:
                        max_runs_if_active = runs_if_active
                        bottleneck_class = cn

                if bottleneck_class is None: # Should not happen if xp_needed_dict is not empty
                    print("[ERROR][RtcaSim] Could not determine bottleneck class during simulation. Breaking loop.")
                    break
                
                active_runs_per_class[bottleneck_class] += 1 

                # Apply XP gains and update needed XP for the next iteration
                next_xp_needed = {}
                for cn, needed in xp_needed_dict.items():
                    xp_gained = active_gain if cn == bottleneck_class else passive_gain
                    remaining_needed = needed - xp_gained
                    if remaining_needed > 0:
                        next_xp_needed[cn] = remaining_needed
                
                xp_needed_dict = next_xp_needed

            print(f"[DEBUG][RtcaSim] --- Simulation Finished after {iteration} iterations ---")
            print(f"[DEBUG][RtcaSim] Total Runs Simulated: {total_runs_simulated}")
            print(f"[DEBUG][RtcaSim] Active Runs Breakdown: {active_runs_per_class}") 
            if iteration >= max_iterations:
                 print(f"[ERROR][RtcaSim] Simulation reached max iterations ({max_iterations}). Result might be inaccurate.")

            # Prepare items for sorting (only those with > 0 runs)
            items_to_sort = [(cn, count) for cn, count in active_runs_per_class.items() if count > 0]

            # Sort by descending run count
            sorted_items = sorted(
                items_to_sort,
                key=lambda item: -item[1]  # Sort only by run count in descending order
            )

            # Build the breakdown string from sorted items
            breakdown_parts = [
                f"{'🔸 ' if selected_class_lower and cn.lower() == selected_class_lower else ''}{cn.capitalize()}: {count}{' 🔸' if selected_class_lower and cn.lower() == selected_class_lower else ''}"
                for cn, count in sorted_items
            ]
            breakdown_str = " | ".join(breakdown_parts) if breakdown_parts else ""

            base_message = (
                f"{target_ign} (CA {current_ca:.2f}) -> Target CA {target_level}: "
                f"Needs approx {total_runs_simulated:,} {selected_floor_name} runs "
            )

            output_message = base_message + breakdown_str

            # Check length and potentially remove breakdown if too long
            if len(output_message) > self.bot.constants.MAX_MESSAGE_LENGTH:
                print("[WARN][RtcaCmd] Output message with breakdown too long. Sending without breakdown.")
                output_message = base_message 
                
            await self.bot._send_message(ctx, output_message) 

        except Exception as e:
            print(f"[ERROR][RtcaCmd] Unexpected error calculating RTCA for {ign}: {e}")
            traceback.print_exc()
            await self.bot._send_message(ctx, f"An unexpected error occurred while calculating RTCA for '{target_ign}'.")
