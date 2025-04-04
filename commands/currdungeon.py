"""Module for handling current dungeon status checking."""
import traceback
import re
from datetime import datetime
import math

from twitchio.ext import commands


async def process_currdungeon_command(ctx: commands.Context, ign: str | None = None, requested_profile_name: str | None = None):
    bot = ctx.bot
    print(f"[INFO][CurrDungeonCmd] Checking recent runs for player: {ign}")
    
    # Clean up the IGN
    ign = ign.lstrip('@') if ign else ctx.author.name

    profile_data = await bot._get_player_profile_data(ctx, ign, requested_profile_name=requested_profile_name)
    if not profile_data:
        return 
    
    target_ign, player_uuid, selected_profile = profile_data
    profile_name = selected_profile.get('cute_name', 'Unknown')
    try:
        member_data = selected_profile.get('members', {}).get(player_uuid, {})
        dungeons_data = member_data.get('dungeons', {})
        treasures_data = dungeons_data.get('treasures', None)
        runs_list = treasures_data.get('runs', []) if treasures_data else []  # Default to empty list

        if not runs_list:
            print(f"[INFO][CurrDungeonCmd] No runs found for {target_ign} in profile {profile_name}.")
            await bot._send_message(ctx, f"'{target_ign}' has no recorded dungeon runs in profile '{profile_name}'.")
            return

        latest_run = None
        max_ts = 0
        for run in runs_list:
            if isinstance(run, dict):
                current_ts = run.get('completion_ts', 0)
                if isinstance(current_ts, (int, float)) and current_ts > max_ts:
                    max_ts = current_ts
                    latest_run = run

        if latest_run is None:
            print(f"[INFO][CurrDungeonCmd] Could not determine the latest run for {target_ign} (no valid timestamps).")
            await bot._send_message(ctx, f"Could not find a valid latest run for '{target_ign}' in profile '{profile_name}'.")
            return

        completion_timestamp_ms = latest_run.get('completion_ts', 0)
        current_time_sec = datetime.now().timestamp()
        completion_time_sec = completion_timestamp_ms / 1000.0
        time_diff_sec = current_time_sec - completion_time_sec

        print(f"[DEBUG][CurrDungeonCmd] Latest Run TS: {completion_time_sec}, Current TS: {current_time_sec}, Diff: {time_diff_sec:.2f} sec")

        if time_diff_sec > 600:  # More than 10 minutes
            await bot._send_message(ctx, f"{target_ign} didn't finish a run in the last 10min.")
            return

        relative_time_str = _format_relative_time(time_diff_sec)

        # Format run type
        dungeon_type = latest_run.get('dungeon_type', 'Unknown Type')
        dungeon_tier = latest_run.get('dungeon_tier', '?')
        run_info = _format_run_type(dungeon_type, dungeon_tier)

        # Format teammates
        participants_data = latest_run.get('participants', [])
        teammate_strings = []
        target_ign_lower = target_ign.lower() 
        if isinstance(participants_data, list):
            for participant in participants_data:
                if isinstance(participant, dict):
                    raw_name = participant.get('display_name')
                    if raw_name:
                        parsed_teammate = _parse_participant(raw_name, target_ign_lower)
                        if parsed_teammate:  # Add only if parsing succeeded and it's not the target player
                            teammate_strings.append(parsed_teammate)

        teammates_str = ", ".join(teammate_strings) if teammate_strings else "No other participants listed"

        # Construct final message
        output_message = (
            f"{target_ign}'s last run was {run_info} finished {relative_time_str}. "
            f"Teammates: {teammates_str}"
        )
        await bot._send_message(ctx, output_message)

    except Exception as e:
        print(f"[ERROR][CurrDungeonCmd] Unexpected error processing current run for {target_ign}: {e}")
        traceback.print_exc()
        await bot._send_message(ctx, f"An unexpected error occurred while checking the current run for '{target_ign}'.")


def _format_relative_time(time_diff_sec: float) -> str:
    """Formats a time difference in seconds into 'X seconds/minutes ago'."""
    if time_diff_sec < 60:
        seconds_ago = round(time_diff_sec)
        # Handle pluralization correctly
        return f"{seconds_ago} second{'s' if seconds_ago != 1 else ''} ago"
    else:
        minutes_ago = math.floor(time_diff_sec / 60)
        # Handle pluralization correctly
        return f"{minutes_ago} minute{'s' if minutes_ago != 1 else ''} ago"


def _format_run_type(dungeon_type: str, dungeon_tier: str | int) -> str:
    """Formats dungeon type and tier into F{tier} or M{tier}."""
    dtype_lower = dungeon_type.lower()
    if dtype_lower == 'catacombs':
        return f"F{dungeon_tier}"
    elif dtype_lower == 'master_catacombs':
        return f"M{dungeon_tier}"
    else:
        # Fallback for unexpected dungeon types
        return f"{dungeon_type.capitalize()} {dungeon_tier}"


def _parse_participant(raw_display_name: str, target_ign_lower: str) -> str | None:
    """Parses participant display name, cleans it, and extracts info.
    Returns 'Username (Class Level)' or None if it's the target player or parsing fails."""
    try:
        # 1. Remove color codes
        cleaned_name = re.sub(r'§[0-9a-fk-or]', '', raw_display_name)
        # 2. Split username and class info
        parts = cleaned_name.split(':', 1)
        username_part = parts[0].strip()

        # 3. Skip the target player themselves (case-insensitive)
        if username_part.lower() == target_ign_lower:
            return None

        # 4. Extract Class Name and Level (if available)
        final_class = 'Unknown'
        final_level = '?'
        if len(parts) > 1:
            class_info_part = parts[1].strip() # e.g., "Tank (50)"
            class_match = re.match(r'^([a-zA-Z]+)', class_info_part)
            if class_match:
                final_class = class_match.group(1)
            level_match = re.search(r'\((\d+)\)', class_info_part)
            if level_match:
                final_level = level_match.group(1)

        if username_part:
            return f"{username_part} ({final_class} {final_level})"
        else:
            return None 
    except Exception as e:
        print(f"[WARN][CurrDungeon] Error parsing participant '{raw_display_name}': {e}")
        return None 
