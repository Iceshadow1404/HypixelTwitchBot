import json
import traceback
from typing import TypedDict

from twitchio.ext import commands


class LevelingData(TypedDict):
    xp_table: list[int]
    level_caps: dict[str, int]
    catacombs_xp: list[int]
    hotm_brackets: list[int]
    slayer_xp: dict[str, list[int]]


def _load_leveling_data() -> LevelingData:
    """Loads leveling data from leveling.json."""
    try:
        with open('leveling.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return {
                'xp_table': data.get('leveling_xp', []),
                'level_caps': data.get('leveling_caps', {}),
                'catacombs_xp': data.get('catacombs', []),
                'hotm_brackets': data.get('HOTM', []),
                'slayer_xp': data.get('slayer_xp', {})
            }
    except FileNotFoundError:
        print("[ERROR] leveling.json not found. Level calculations will fail.")
        return {'xp_table': [], 'level_caps': {}, 'catacombs_xp': [], 'hotm_brackets': [], 'slayer_xp': {}}
    except json.JSONDecodeError as e:
        print(f"[ERROR] Error decoding leveling.json: {e}. Level calculations will fail.")
        return {'xp_table': [], 'level_caps': {}, 'catacombs_xp': [], 'hotm_brackets': [], 'slayer_xp': {}}
    except Exception as e:
        print(f"[ERROR] Unexpected error loading leveling.json: {e}")
        traceback.print_exc()
        return {'xp_table': [], 'level_caps': {}, 'catacombs_xp': [], 'hotm_brackets': [], 'slayer_xp': {}}


def _find_latest_profile(profiles: list, player_uuid: str) -> dict | None:
    """Finds the most recently played profile for a player from a list of profiles."""
    print(f"[DEBUG][Profile] Searching profile for UUID {player_uuid} from {len(profiles)} profiles.")
    if not profiles:
        print("[DEBUG][Profile] No profiles to search.")
        return None

    # Check for 'selected' profile first
    for profile in profiles:
        cute_name = profile.get('cute_name', 'Unknown')
        if profile.get('selected', False) and player_uuid in profile.get('members', {}):
            print(f"[DEBUG][Profile] Found selected profile: '{cute_name}'")
            return profile

    # If no 'selected' profile, find the one with the latest 'last_save' for the member
    latest_profile = None
    latest_save = 0
    for profile in profiles:
        cute_name = profile.get('cute_name', 'Unknown')
        member_data = profile.get('members', {}).get(player_uuid)
        if member_data:
            last_save = member_data.get('last_save', 0)
            if last_save > latest_save:
                latest_save = last_save
                latest_profile = profile
                print(f"[DEBUG][Profile] Found newer profile: '{cute_name}' (Last Save: {last_save})")

    if latest_profile:
        print(f"[DEBUG][Profile] Latest profile selected: '{latest_profile.get('cute_name')}'")
        return latest_profile

    print(f"[DEBUG][Profile] No suitable profile found for UUID {player_uuid}.")
    return None


async def _parse_command_args(bot, ctx: commands.Context, args: str | None, command_name: str) -> tuple[str, str | None] | None:
    """Parses common command arguments for username and optional profile name."""
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
            # Use bot.send_message for sending messages
            await bot.send_message(ctx, f"Too many arguments. Usage: {bot._prefix}{command_name} <username> [profile_name]")
            return None, None # Return None, None to indicate failure

    if ign is None:
        # This case should ideally not be reached if ctx.author.name is always valid
        print("[WARN][ParseArgs] IGN became None unexpectedly.")
        await bot.send_message(ctx, "Could not determine username.")
        return None, None

    return ign.rstrip(), requested_profile_name

def format_number(num: float) -> str:
    """Format a number with suffix (k, m, b)."""
    if num >= 1_000_000_000:
        return f"{num / 1_000_000_000:.2f}B"
    elif num >= 1_000_000:
        return f"{num / 1_000_000:.2f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.2f}K"
    else:
        return f"{num:.0f}"