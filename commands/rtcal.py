# commands/rtcas.py
import traceback
import math
from twitchio.ext import commands

import constants
from utils import _parse_command_args  # Wiederverwenden, falls die Argument-Analyse ähnlich bleibt
from calculations import calculate_class_level, _get_xp_for_target_level
from commands.mayor import MayorCommand

# TODO Argument parsing for classes

class RtcalCommand:
    def __init__(self, bot):
        self.bot = bot

    async def rtcal_command(self, ctx: commands.Context, *, args: str | None = None):  # Methodenname ändern
        """Calculates runs needed to reach a target Class Level playing only the active class.
        Syntax: #rtcal <username> [profile_name] [target_level=50] [floor=m7]
        Example: #rtcal Player1 Apple 55 m6
        """
        print(f"[COMMAND] Rtcal command triggered by {ctx.author.name}: {args}")

        ign: str | None = None
        requested_profile_name: str | None = None
        target_level_str: str = '50'
        floor_str: str = 'm7'

        args_stripped = args.strip() if args else None
        if args_stripped and not any(c.isalnum() for c in args_stripped):
            args_stripped = None

        if not args_stripped:
            ign = ctx.author.name
            print(f"[DEBUG][RtcalCmd] No arguments provided, defaulting IGN to: {ign}")
        else:
            parts = args_stripped.split()

            if parts[0].lower() in ['m6', 'm7'] or (parts[0].isdigit() and int(parts[0]) < 100):
                ign = ctx.author.name
                remaining_parts = parts
            else:
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
                elif part.isdigit() and int(
                        part) < 100 and potential_target_level is None:
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
                usage_message = f"Too many or ambiguous arguments: {unidentified_parts}. Usage: {self.bot._prefix}rtcal <username> [profile_name] [target_level=50] [floor=m7]"
                await self.bot.send_message(ctx, usage_message)
                return

        target_level: int
        try:
            target_level = int(target_level_str)
            if not 1 <= target_level <= 99:
                raise ValueError("Target class level must be between 1 and 99.")
            print(f"[DEBUG][RtcalCmd] Validated target_level: {target_level}")
        except ValueError as e:
            await self.bot.send_message(ctx,
                                        f"Invalid argument: {e}. Usage: {self.bot._prefix}rtcal <username> [profile_name] [target_level=50] [floor=m7]")
            return

        profile_data = await self.bot._get_player_profile_data(ctx, ign, requested_profile_name=requested_profile_name,
                                                               useCache=False)
        if not profile_data:
            return

        target_ign, player_uuid, selected_profile = profile_data
        profile_name = selected_profile.get('cute_name', 'Unknown')
        print(f"[INFO][RtcalCmd] Using profile: {profile_name}")

        try:
            member_data = selected_profile.get('members', {}).get(player_uuid, {})
            dungeons_data = member_data.get('dungeons', {})
            player_classes_data = dungeons_data.get('player_classes', None)

            active_class_name = dungeons_data.get('selected_dungeon_class')
            if not active_class_name:
                await self.bot.send_message(ctx,
                                            f"'{target_ign}' has no active dungeon class selected in profile '{profile_name}'.")
                return

            active_class_name_lower = active_class_name.lower()
            print(f"[DEBUG][RtcalCmd] Active class for {target_ign}: {active_class_name.capitalize()}")

            if player_classes_data is None:
                await self.bot.send_message(ctx, f"'{target_ign}' has no class data in profile '{profile_name}'.")
                return

            active_class_xp = player_classes_data.get(active_class_name_lower, {}).get('experience', 0)
            current_active_class_level = calculate_class_level(self.bot.leveling_data, active_class_xp)

            print(
                f"[DEBUG][RtcalCmd] {target_ign} - Active Class: {active_class_name.capitalize()} (Lvl {current_active_class_level:.2f}), Target Level: {target_level}")

            if current_active_class_level >= target_level:
                await self.bot.send_message(ctx,
                                            f"{target_ign}'s {active_class_name.capitalize()} class (Lvl {current_active_class_level:.2f}) has already reached or surpassed the target level {target_level}.")
                return

            if floor_str == 'm6':
                xp_per_run_base = self.bot.constants.BASE_M6_CLASS_XP
                selected_floor_name = "M6"
            else:
                xp_per_run_base = self.bot.constants.BASE_M7_CLASS_XP
                selected_floor_name = "M7"

            xp_per_run = xp_per_run_base

            # --- Mayor Check ---
            mayor_command = MayorCommand(self.bot)
            mayor_data = await mayor_command.mayor_command_logic()
            is_derpy_active = False
            if mayor_data and mayor_data.get("name") == "Derpy":
                xp_per_run *= 1.5
                is_derpy_active = True
                print(f"[DEBUG][RtcalCmd] Derpy is active, XP per run multiplied by 1.5")

            xp_per_run *= 1.06  # Beispiel für einen allgemeinen Boost
            print(f"[DEBUG][RtcalCmd] XP/Run ({selected_floor_name}) after boosts: {xp_per_run:,.0f}")

            if xp_per_run <= 0:
                print(f"[ERROR][RtcalCmd] XP per run is zero or negative for {selected_floor_name}.")
                await self.bot.send_message(ctx, "Error with XP per run configuration. Cannot estimate runs.")
                return

            xp_needed_for_target_level = _get_xp_for_target_level(self.bot.leveling_data, target_level)
            remaining_xp_to_gain = xp_needed_for_target_level - active_class_xp

            if remaining_xp_to_gain <= 0:
                await self.bot.send_message(ctx,
                                            f"{target_ign}'s {active_class_name.capitalize()} class already meets the XP requirement for level {target_level}.")
                return

            runs_needed = math.ceil(remaining_xp_to_gain / xp_per_run)

            output_message = (
                f"{target_ign} needs approx. {runs_needed:,} {selected_floor_name} runs "
                f"to reach {active_class_name.capitalize()} Lvl {target_level} (from Lvl {current_active_class_level:.2f})."
            )
            if is_derpy_active:
                output_message += " (Derpy active)"

            await self.bot.send_message(ctx, output_message)

        except Exception as e:
            print(f"[ERROR][RtcalCmd] Unexpected error calculating RTCAL for {ign}: {e}")
            traceback.print_exc()
            await self.bot.send_message(ctx,
                                        f"An unexpected error occurred while calculating runs for '{target_ign}'.")