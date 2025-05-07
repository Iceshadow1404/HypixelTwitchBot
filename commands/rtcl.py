# commands/rtcl.py
import traceback
import math
from twitchio.ext import commands

from calculations import calculate_class_level, _get_xp_for_target_level
from commands.mayor import MayorCommand

CANONICAL_CLASS_NAMES = {
    'healer', 'archer', 'mage', 'tank', 'berserk'
}

_CLASS_DEFINITIONS_WITH_ALIASES = {
    'archer': ['arch', 'a'],
    'healer': ['heal', 'h'],
    'mage': ['m'],
    'tank': ['t'],
    'berserk': ['berserker', 'b', 'bers']
}

CANONICAL_CLASS_NAMES = set(_CLASS_DEFINITIONS_WITH_ALIASES.keys())

CLASS_ALIASES_TO_CANONICAL = {}
for canonical_name, additional_aliases in _CLASS_DEFINITIONS_WITH_ALIASES.items():
    CLASS_ALIASES_TO_CANONICAL[canonical_name] = canonical_name
    for alias in additional_aliases:
        CLASS_ALIASES_TO_CANONICAL[alias] = canonical_name

VALID_CLASS_INPUTS_LOWER = set(CLASS_ALIASES_TO_CANONICAL.keys())

class RtclCommand:
    def __init__(self, bot):
        self.bot = bot

    async def rtcl_command(self, ctx: commands.Context, *, args: str | None = None):
        """Calculates runs needed to reach a target Class Level.
        """
        print(f"[COMMAND] Rtcl command triggered by {ctx.author.name}: {args}")

        ign: str | None = None
        requested_profile_name: str | None = None
        requested_canonical_class_name: str | None = None
        target_level_str: str | None = None
        floor_str: str = 'm7'

        args_stripped = args.strip() if args else None
        if args_stripped and not any(c.isalnum() for c in args_stripped):
            args_stripped = None

        if not args_stripped:
            ign = ctx.author.name
            print(f"[DEBUG][RtclCmd] No arguments provided, defaulting IGN to: {ign}")
        else:
            parts = args_stripped.split()
            potential_ign_or_class_or_level_or_floor = parts[0]
            part0_lower = potential_ign_or_class_or_level_or_floor.lower()

            is_first_part_ign = not (
                    part0_lower in ['m6', 'm7'] or
                    part0_lower in VALID_CLASS_INPUTS_LOWER or
                    (potential_ign_or_class_or_level_or_floor.isdigit() and int(
                        potential_ign_or_class_or_level_or_floor) < 100)
            )

            if is_first_part_ign:
                ign = parts[0]
                remaining_parts = parts[1:]
            else:
                ign = ctx.author.name
                remaining_parts = parts

            potential_profile_name = None
            potential_target_level = None
            potential_floor = None
            _temp_class_input = None
            unidentified_parts = []

            for part in remaining_parts:
                part_lower = part.lower()
                if part_lower in VALID_CLASS_INPUTS_LOWER and _temp_class_input is None:
                    _temp_class_input = CLASS_ALIASES_TO_CANONICAL[part_lower]
                elif part_lower in ['m6', 'm7'] and potential_floor is None:
                    potential_floor = part_lower
                elif part.isdigit() and int(part) < 100 and potential_target_level is None:
                    potential_target_level = part
                elif potential_profile_name is None and not (
                        part_lower in VALID_CLASS_INPUTS_LOWER or
                        part_lower in ['m6', 'm7'] or
                        (part.isdigit() and int(part) < 100)
                ):
                    potential_profile_name = part
                else:
                    unidentified_parts.append(part)

            requested_profile_name = potential_profile_name
            requested_canonical_class_name = _temp_class_input

            if potential_target_level is not None:
                target_level_str = potential_target_level
            if potential_floor is not None:
                floor_str = potential_floor

            if unidentified_parts:
                usage_message = (
                    f"Too many or ambiguous arguments: {', '.join(unidentified_parts)}. "
                    f"Syntax: {self.bot._prefix}rtcl <username> [profile_name] [class_name|alias] [target_level] [floor=m7|m6]"
                )
                await self.bot.send_message(ctx, usage_message)
                return

        profile_data = await self.bot._get_player_profile_data(ctx, ign, requested_profile_name=requested_profile_name,
                                                               useCache=False)
        if not profile_data:
            return

        target_ign, player_uuid, selected_profile = profile_data
        profile_name_cute = selected_profile.get('cute_name', 'Unknown')
        print(f"[INFO][RtclCmd] Using profile: {profile_name_cute} for {target_ign}")

        try:
            member_data = selected_profile.get('members', {}).get(player_uuid, {})
            dungeons_data = member_data.get('dungeons', {})
            player_classes_data = dungeons_data.get('player_classes', None)

            if player_classes_data is None:
                await self.bot.send_message(ctx, f"'{target_ign}' has no class data in profile '{profile_name_cute}'.")
                return

            class_for_calculation_name_display: str
            current_xp_for_calculation: float
            current_level_for_calculation: float
            class_key_for_data: str

            if requested_canonical_class_name:
                class_key_for_data = requested_canonical_class_name
                if class_key_for_data not in player_classes_data:
                    await self.bot.send_message(ctx,
                                                f"'{target_ign}' has no data for class '{class_key_for_data.capitalize()}' in profile '{profile_name_cute}'.")
                    return
                class_for_calculation_name_display = class_key_for_data.capitalize()
                current_xp_for_calculation = player_classes_data.get(class_key_for_data, {}).get('experience', 0)
                current_level_for_calculation = calculate_class_level(self.bot.leveling_data,
                                                                      current_xp_for_calculation)
                print(
                    f"[DEBUG][RtclCmd] Using specified class: {class_for_calculation_name_display} (Lvl {current_level_for_calculation:.2f}) for {target_ign}")
            else:
                active_class_name_hypixel = dungeons_data.get('selected_dungeon_class')
                if not active_class_name_hypixel:
                    await self.bot.send_message(ctx,
                                                f"'{target_ign}' has no active dungeon class selected in profile '{profile_name_cute}'.")
                    return
                class_key_for_data = active_class_name_hypixel.lower()
                class_for_calculation_name_display = class_key_for_data.capitalize()
                current_xp_for_calculation = player_classes_data.get(class_key_for_data, {}).get('experience', 0)
                current_level_for_calculation = calculate_class_level(self.bot.leveling_data,
                                                                      current_xp_for_calculation)
                print(
                    f"[DEBUG][RtclCmd] Using active class: {class_for_calculation_name_display} (Lvl {current_level_for_calculation:.2f}) for {target_ign}")

            target_level: int
            if target_level_str:
                try:
                    target_level = int(target_level_str)
                    if target_level <= math.floor(current_level_for_calculation) and target_level != math.ceil(
                            current_level_for_calculation):
                        if not (current_level_for_calculation < target_level):
                            await self.bot.send_message(ctx,
                                                        f"Target level {target_level} must be higher than current full level {math.floor(current_level_for_calculation)} for {class_for_calculation_name_display}.")
                            return
                    if target_level < 1:
                        await self.bot.send_message(ctx, f"Target level must be at least 1.")
                        return
                    print(f"[DEBUG][RtclCmd] User specified target_level: {target_level}")
                except ValueError:
                    await self.bot.send_message(ctx, f"Invalid target level: '{target_level_str}'. Must be a number.")
                    return
            else:
                target_level = math.floor(current_level_for_calculation) + 1
                print(f"[DEBUG][RtclCmd] No target level specified, defaulting to next level: {target_level}")

            if current_level_for_calculation >= target_level:
                await self.bot.send_message(ctx,
                                            f"{target_ign}'s {class_for_calculation_name_display} class (Lvl {current_level_for_calculation:.2f}) "
                                            f"has already reached or surpassed the target level {target_level}.")
                return

            if floor_str == 'm6':
                xp_per_run_base = self.bot.constants.BASE_M6_CLASS_XP
                selected_floor_name = "M6"
            elif floor_str == 'm7':
                xp_per_run_base = self.bot.constants.BASE_M7_CLASS_XP
                selected_floor_name = "M7"
            else:
                await self.bot.send_message(ctx, f"Invalid floor specified: {floor_str}. Use 'm6' or 'm7'.")
                return

            xp_per_run = xp_per_run_base
            mayor_command = MayorCommand(self.bot)
            mayor_data = await mayor_command.mayor_command_logic()
            is_derpy_active = False
            if mayor_data and mayor_data.get("name") == "Derpy":
                xp_per_run *= 1.5
                is_derpy_active = True
                print(f"[DEBUG][RtclCmd] Derpy is active, XP per run multiplied by 1.5")

            print(f"[DEBUG][RtclCmd] XP/Run ({selected_floor_name}) after boosts: {xp_per_run:,.0f}")

            if xp_per_run <= 0:
                print(f"[ERROR][RtclCmd] XP per run is zero or negative for {selected_floor_name}.")
                await self.bot.send_message(ctx, "Error with XP per run configuration. Cannot estimate runs.")
                return

            xp_needed_for_target_level = _get_xp_for_target_level(self.bot.leveling_data, target_level)
            remaining_xp_to_gain = xp_needed_for_target_level - current_xp_for_calculation

            if remaining_xp_to_gain <= 0:
                await self.bot.send_message(ctx,
                                            f"{target_ign}'s {class_for_calculation_name_display} class already meets or exceeds the XP requirement for level {target_level}.")
                return

            runs_needed = math.ceil(remaining_xp_to_gain / xp_per_run)

            output_message = (
                f"{target_ign} needs approx. {runs_needed:,} {selected_floor_name} runs "
                f"to reach {class_for_calculation_name_display} Lvl {target_level} (from Lvl {current_level_for_calculation:.2f})."
            )
            if is_derpy_active:
                output_message += " (Derpy active)"

            await self.bot.send_message(ctx, output_message)

        except Exception as e:
            print(f"[ERROR][RtclCmd] Unexpected error calculating RTCL for {ign} (profile: {profile_name_cute}): {e}")
            traceback.print_exc()
            await self.bot.send_message(ctx,
                                        f"An unexpected error occurred while calculating runs for '{target_ign}'.")