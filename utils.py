import json
import os
import traceback
from typing import TypedDict

import aiohttp
from dotenv import load_dotenv
from twitchio.ext import commands

import constants


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


async def _get_skyblock_data(hypixel_api_key, uuid: str) -> list | None:
    """Gets SkyBlock profile data for a given UUID using Hypixel API."""
    if not hypixel_api_key:
        print("[ERROR][API] Hypixel API Key not configured.")
        return None

    params = {"key": hypixel_api_key, "uuid": uuid}
    print(f"[DEBUG][API] Hypixel profiles request for UUID '{uuid}'...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(constants.HYPIXEL_API_URL, params=params) as response:
                print(f"[DEBUG][API] Hypixel profiles response status: {response.status}")
                response_text = await response.text()  # Read text first for debugging
            if response.status == 200:
                try:
                    data = json.loads(response_text)
                    # Save the full response for debugging
                    debug_file = f"hypixel_response_{uuid}.json"
                    load_dotenv()
                    DEBUG = os.getenv("Debug", "false").strip().lower() == "true"
                    try:
                        if DEBUG:
                            with open(debug_file, 'w', encoding='utf-8') as f:
                                json.dump(data, f, indent=4)
                            print(f"[DEBUG][API] Hypixel response saved to '{debug_file}'.")
                    except IOError as io_err:
                        print(f"[WARN][API] Failed to save debug file '{debug_file}': {io_err}")

                    if data.get("success"):
                        profiles = data.get('profiles')
                        if profiles is None:
                            print(
                                f"[WARN][API] Hypixel API success, but 'profiles' field is missing or null for {uuid}.")
                            return []  # Return empty list instead of None if success=true but no profiles
                        if not isinstance(profiles, list):
                            print(f"[ERROR][API] Hypixel API success, but 'profiles' is not a list ({type(profiles)}).")
                            return None
                        return profiles
                    else:
                        reason = data.get('cause', 'Unknown reason')
                        print(f"[ERROR][API] Hypixel API request failed: {reason}")
                        return None
                except json.JSONDecodeError as json_e:
                    print(f"[ERROR][API] Error decoding Hypixel JSON response: {json_e}")
                    print(f"--- Response Text Start ---\n{response_text}\n--- Response Text End ---")
                    return None
            else:
                print(f"[ERROR][API] Hypixel API request failed: Status {response.status}")
                print(f"--- Response Text Start ---\n{response_text}\n--- Response Text End ---")
                return None
    except aiohttp.ClientError as e:
        print(f"[ERROR][API] Network error during Hypixel API request: {e}")
        return None
    except Exception as e:
        print(f"[ERROR][API] Unexpected error during Hypixel API request: {e}")
        traceback.print_exc()
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