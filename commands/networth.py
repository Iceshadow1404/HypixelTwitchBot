# commands/networth.py
import json
import aiohttp
import asyncio
import traceback
from typing import Optional, Dict, Any, Tuple
from twitchio.ext import commands

from constants import HYPIXEL_MUSEUM_URL
from utils import format_number

class NetworthCommand:
    def __init__(self, bot):
        self.bot = bot
        self.NODE_SERVICE_URL = "http://localhost:3000/calculate-networth"

    async def networth_command(self, ctx: commands.Context, *, args: str | None = None):
        """Calculate and display a player's SkyBlock networth using skyhelper-networth."""
        try:
            target_ign_from_parser = None
            requested_profile_name = None
            if hasattr(self.bot, '_parse_command_args'):
                parsed_args = await self.bot._parse_command_args(ctx, args, 'networth')
                if parsed_args is None:
                    return
                target_ign_from_parser, requested_profile_name = parsed_args
            else:
                if args:
                    parts = args.split(None, 1)
                    target_ign_from_parser = parts[0]
                    requested_profile_name = parts[1] if len(parts) > 1 else None
                print("[WARN][Networth] Bot instance does not have '_parse_command_args' method. Manual parsing used for bot call.")

            result = await self.bot._get_player_profile_data(ctx, target_ign_from_parser, requested_profile_name, useCache=True)
            if not result:
                return

            target_ign, player_uuid, profile = result
            profile_name = profile.get('cute_name', 'Unknown')
            profile_id = profile.get('profile_id')

            if target_ign == "redhead968".lower() and ctx.channel.name == "jstjxel".lower():
                print(ctx.channel.name)
                await self.bot.send_message(ctx, f" < 10b")
                return

            if not profile_id:
                print(f"[ERROR][Networth] No profile ID found for {target_ign}")
                await self.bot.send_message(ctx, f"Couldn't calculate networth for {target_ign}: Missing profile ID")
                return

            museum_data = await self._get_museum_data(player_uuid, profile_id)
            if museum_data:
                player_museum_data = museum_data.get('members', {}).get(player_uuid)
            else:
                player_museum_data = None
                print(f"[INFO][Networth] No museum data found for {target_ign}")

            request_data = {
                'playerUUID': player_uuid,
                'profileData': profile,
                'museumData': player_museum_data,
                'bankBalance': profile.get('banking', {}).get('balance', 0)
            }

            networth_info = await self._send_to_node_service(request_data)

            if networth_info and networth_info.get('success'):
                total_networth = networth_info.get('networth', 0)
                categories = networth_info.get('categories', {})
                purse = networth_info.get('purse', 0)
                bank = networth_info.get('bank', 0)
                nonCosmeticNetworth = networth_info.get('nonCosmeticNetworth', 0)

                formatted_total = format_number(total_networth)
                formatted_purse = format_number(purse)
                formatted_bank = format_number(bank)
                formatted_nonCosmetic = format_number(nonCosmeticNetworth)

                response = f"Networth for {target_ign} ({profile_name}): {formatted_total}"

                extra_infos = []
                if purse > 0:
                    extra_infos.append(f"Purse: {formatted_purse}")
                if bank > 0:
                    extra_infos.append(f"Bank: {formatted_bank}")
                if nonCosmeticNetworth > 0:
                    extra_infos.append(f"Non-Cosmetic: {formatted_nonCosmetic}")

                if extra_infos:
                    response += f" | {', '.join(extra_infos)}"

                if categories:
                    top_categories = sorted(
                        [(name, value) for name, value in categories.items() if isinstance(value, (int, float)) and value > 0],
                        key=lambda x: x[1],
                        reverse=True
                    )[:3]

                    if top_categories:
                        category_texts = []
                        for name, value in top_categories:
                            formatted_value = format_number(value)
                            category_texts.append(f"{name}: {formatted_value}")

                        response += f" | Top: {', '.join(category_texts)}"

                await self.bot.send_message(ctx, response)
            else:
                error_msg = networth_info.get('error',
                                              'Unknown error') if networth_info else 'Failed to calculate networth'
                await self.bot.send_message(ctx,
                                             f"Couldn't calculate networth for {target_ign}: {error_msg}")

        except Exception as e:
            print(f"[ERROR][Networth] Error processing networth command: {e}")
            traceback.print_exc()
            await self.bot.send_message(ctx, "An error occurred while calculating networth.")

    async def _get_museum_data(self, player_uuid: str, profile_id: str) -> Optional[Dict[str, Any]]:
        """Fetch museum data for the player from Hypixel API."""
        if not self.bot.hypixel_api_key or not self.bot.session or self.bot.session.closed:
            print("[ERROR][Networth] No API key or valid session available for museum data request")
            return None

        formatted_uuid = player_uuid.replace("-", "")

        params = {
            "key": self.bot.hypixel_api_key,
            "player": formatted_uuid,
            "profile": profile_id
        }

        try:
            print(f"[INFO][Networth] Fetching museum data for UUID: {formatted_uuid}, Profile: {profile_id}")
            async with self.bot.session.get(HYPIXEL_MUSEUM_URL, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success"):
                        print(f"[INFO][Networth] Successfully retrieved museum data")
                        return data
                    else:
                        print(f"[ERROR][Networth] Hypixel API returned error: {data.get('cause', 'Unknown error')}")
                else:
                    print(f"[ERROR][Networth] Museum API returned status {response.status}")
                    error_text = await response.text()
                    print(f"[ERROR][Networth] Response body: {error_text[:200]}")

        except Exception as e:
            print(f"[ERROR][Networth] Exception while fetching museum data: {e}")
            traceback.print_exc()

        return None

    async def _send_to_node_service(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send data to the Node.js service for networth calculation."""
        try:
            session = getattr(self.bot, 'session', None)
            need_close = False

            if not session or session.closed:
                session = aiohttp.ClientSession()
                need_close = True
                print("[WARN][Networth] Bot session not found or closed, creating temporary session for Node call.")

            print(f"[INFO][Networth] Sending data to Node service at {self.NODE_SERVICE_URL}")

            async with session.post(
                    self.NODE_SERVICE_URL,
                    json=data,
                    headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"[INFO][Networth] Successfully received networth calculation")
                    return result
                else:
                    error_text = await response.text()
                    print(f"[ERROR][Networth] Node service returned status {response.status}: {error_text[:200]}")
                    return None

        except Exception as e:
            print(f"[ERROR][Networth] Exception communicating with Node service: {e}")
            traceback.print_exc()
            return None

        finally:
            if need_close and session and not session.closed:
                await session.close()
                print("[INFO][Networth] Closed temporary session for Node call.")
