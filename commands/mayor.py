import aiohttp
import json
import traceback
from twitchio.ext import commands

import constants

class MayorCommand:
    def __init__(self, bot):
        self.bot = bot

    async def mayor_command(self, ctx: commands.Context):
        """Shows the current SkyBlock mayor and perks."""
        print(f"[DEBUG][API] Fetching SkyBlock election data from {constants.HYPIXEL_ELECTION_URL}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(constants.HYPIXEL_ELECTION_URL) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("success"):
                            mayor_data = data.get('mayor')
                            if mayor_data:
                                mayor_name = mayor_data.get('name', 'Unknown')
                                perks = mayor_data.get('perks', [])
                                perk_names = [p.get('name', '') for p in perks if p.get('name')]
                                perks_str = " | ".join(perk_names) if perk_names else "No Perks"
                                num_perks = len(perk_names)

                                # Extract Minister info
                                minister_data = mayor_data.get('minister')
                                minister_str = ""
                                if minister_data:
                                    minister_name = minister_data.get('name', 'Unknown')
                                    minister_perk = minister_data.get('perk', {}).get('name', 'Unknown Perk')
                                    minister_str = f" | Minister: {minister_name} ({minister_perk})"

                                output_message = f"Current Mayor: {num_perks} perk {mayor_name} ({perks_str}){minister_str}"
                                await self.bot.send_message(ctx, output_message)
                            else:
                                await self.bot.send_message(ctx, "Could not find current mayor data in the API response.")
                        else:
                            await self.bot.send_message(ctx, "API request failed (success=false). Could not fetch election data.")
                    else:
                        await self.bot.send_message(ctx, f"Error fetching election data. API returned status {response.status}.")

        except aiohttp.ClientError as e:
            print(f"[ERROR][API] Network error fetching election data: {e}")
            await self.bot.send_message(ctx, "Network error while fetching election data.")
        except json.JSONDecodeError:
             print(f"[ERROR][API] Failed to parse JSON from election API.")
             await self.bot.send_message(ctx, "Error parsing election data from API.")
        except Exception as e:
            print(f"[ERROR][MayorCmd] Unexpected error: {e}")
            traceback.print_exc()
            await self.bot.send_message(ctx, "An unexpected error occurred while fetching mayor information.")

    async def mayor_command_logic(self):
        """Fetches the current SkyBlock mayor and perks and returns the data."""
        print(f"[DEBUG][API] Fetching SkyBlock election data from {constants.HYPIXEL_ELECTION_URL}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(constants.HYPIXEL_ELECTION_URL) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("success"):
                            mayor_data = data.get('mayor')
                            return mayor_data  # Return the mayor data
                        else:
                            print("[ERROR][MayorCmd] API request failed (success=false). Could not fetch election data.")
                            return None
                    else:
                        print(f"[ERROR][MayorCmd] Error fetching election data. API returned status {response.status}.")
                        return None

        except aiohttp.ClientError as e:
            print(f"[ERROR][API] Network error fetching election data: {e}")
            return None
        except json.JSONDecodeError:
             print(f"[ERROR][API] Failed to parse JSON from election API.")
             return None
        except Exception as e:
            print(f"[ERROR][MayorCmd] Unexpected error: {e}")
            traceback.print_exc()
            return None