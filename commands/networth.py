# commands/networth.py
import json
import aiohttp
import asyncio
import traceback
from typing import Optional, Dict, Any, Tuple
from twitchio.ext import commands


class NetworthCommand:
    def __init__(self, bot):
        self.bot = bot
        self.NODE_SERVICE_URL = "http://localhost:3000/calculate-networth"  # Adjust to your Node service URL

    async def networth_command(self, ctx: commands.Context, *, args: str | None = None):
        """Calculate and display a player's SkyBlock networth using skyhelper-networth."""
        try:
            # Parse the command arguments and get profile data
            result = await self._get_player_profile_data(ctx, args)
            if not result:
                return

            target_ign, player_uuid, profile = result
            profile_name = profile.get('cute_name', 'Unknown')
            profile_id = profile.get('profile_id')  # Get the profile ID

            if not profile_id:
                print(f"[ERROR][Networth] No profile ID found for {target_ign}")
                await self.bot._send_message(ctx, f"Couldn't calculate networth for {target_ign}: Missing profile ID")
                return

            # Get museum data
            museum_data = await self._get_museum_data(player_uuid, profile_id)  # Pass both UUID and profile ID
            if museum_data:
                player_museum_data = museum_data.get('members', {}).get(player_uuid)
            else:
                player_museum_data = None
                print(f"[INFO][Networth] No museum data found for {target_ign}")

            # Prepare request data
            request_data = {
                'playerUUID': player_uuid,
                'profileData': profile,  # Complete profile with all members
                'museumData': player_museum_data,
                'bankBalance': profile.get('banking', {}).get('balance', 0)
            }

            # Send to Node.js service
            networth_info = await self._send_to_node_service(request_data)

            if networth_info and networth_info.get('success'):

                # Extract networth data
                total_networth = networth_info.get('networth', 0)
                categories = networth_info.get('categories', {})
                purse = networth_info.get('purse', 0)
                bank = networth_info.get('bank', 0)
                nonCosmeticNetworth = networth_info.get('nonCosmeticNetworth', 0)

                # Format values
                formatted_total = self._format_number(total_networth)
                formatted_purse = self._format_number(purse)
                formatted_bank = self._format_number(bank)
                formatted_nonCosmetic = self._format_number(nonCosmeticNetworth)

                # Prepare response message
                response = f"Networth for {target_ign} ({profile_name}): {formatted_total}"

                # Add liquid assets if available{'success': True, 'networth': 89633392724.8295, 'purse': 171342563.43398786, 'bank': 28015574869.56523}
                #
                # Warum habe ich der Response nicht auch den NonCosmetic Networth?
                if purse > 0 or bank > 0 or nonCosmeticNetworth > 0:
                    extra_infos = []
                    if purse > 0:
                        extra_infos.append(f"Purse: {formatted_purse}")
                    if bank > 0:
                        extra_infos.append(f"Bank: {formatted_bank}")
                    if nonCosmeticNetworth > 0:
                        extra_infos.append(f"Non-Cosmetic: {formatted_nonCosmetic}")


                    response += f" | {', '.join(extra_infos)}"

                # Add top categories
                if categories:
                    # Get top 3 categories by value
                    top_categories = sorted(
                        [(name, value) for name, value in categories.items() if value > 0],
                        key=lambda x: x[1],
                        reverse=True
                    )[:3]

                    if top_categories:
                        category_texts = []
                        for name, value in top_categories:
                            formatted_value = self._format_number(value)
                            category_texts.append(f"{name}: {formatted_value}")

                        response += f" | Top: {', '.join(category_texts)}"

                await self.bot._send_message(ctx, response)
            else:
                error_msg = networth_info.get('error',
                                              'Unknown error') if networth_info else 'Failed to calculate networth'
                await self.bot._send_message(ctx,
                                             f"Couldn't calculate networth for {target_ign}: {error_msg}")

        except Exception as e:
            print(f"[ERROR][Networth] Error processing networth command: {e}")
            traceback.print_exc()
            await self.bot._send_message(ctx, "An error occurred while calculating networth.")

    async def _get_player_profile_data(self, ctx: commands.Context, args: str | None) -> Optional[
        Tuple[str, str, Dict[str, Any]]]:
        """Get the player profile data using the bot's existing helper method."""
        # If the bot has _parse_command_args method, use it
        if hasattr(self.bot, '_parse_command_args'):
            parsed_args = await self.bot._parse_command_args(ctx, args, 'networth')
            if parsed_args is None:
                return None
            ign, requested_profile_name = parsed_args
        # Otherwise, parse manually
        else:
            if args:
                parts = args.split(None, 1)
                ign = parts[0]
                requested_profile_name = parts[1] if len(parts) > 1 else None
            else:
                ign = None
                requested_profile_name = None

        # Use the bot's _get_player_profile_data method
        return await self.bot._get_player_profile_data(ctx, ign, requested_profile_name, useCache=True)

    async def _get_museum_data(self, player_uuid: str, profile_id: str) -> Optional[Dict[str, Any]]:
        """Fetch museum data for the player from Hypixel API."""
        if not self.bot.hypixel_api_key or not self.bot.session or self.bot.session.closed:
            print("[ERROR][Networth] No API key or valid session available for museum data request")
            return None

        # Format UUID if needed
        formatted_uuid = player_uuid.replace("-", "")

        museum_url = "https://api.hypixel.net/v2/skyblock/museum"
        params = {
            "key": self.bot.hypixel_api_key,
            "player": formatted_uuid,
            "profile": profile_id  # Add the profile ID parameter
        }

        try:
            print(f"[INFO][Networth] Fetching museum data for UUID: {formatted_uuid}, Profile: {profile_id}")
            async with self.bot.session.get(museum_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success"):
                        print(f"[INFO][Networth] Successfully retrieved museum data")
                        return data
                    else:
                        print(f"[ERROR][Networth] Hypixel API returned error: {data.get('cause', 'Unknown error')}")
                else:
                    print(f"[ERROR][Networth] Museum API returned status {response.status}")
                    # Print response body for debugging
                    error_text = await response.text()
                    print(f"[ERROR][Networth] Response body: {error_text[:200]}")

        except Exception as e:
            print(f"[ERROR][Networth] Exception while fetching museum data: {e}")
            traceback.print_exc()

        return None

    async def _send_to_node_service(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send data to the Node.js service for networth calculation."""
        try:
            # Use an existing session if available
            session = getattr(self.bot, 'session', None)
            need_close = False

            if not session or session.closed:
                session = aiohttp.ClientSession()
                need_close = True

            print(f"[INFO][Networth] Sending data to Node service at {self.NODE_SERVICE_URL}")

            # Send request to Node service
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
            # Close session if we created it
            if need_close and session and not session.closed:
                await session.close()

    def _format_number(self, num: float) -> str:
        """Format a number with suffix (k, m, b)."""
        if num >= 1_000_000_000:
            return f"{num / 1_000_000_000:.2f}B"
        elif num >= 1_000_000:
            return f"{num / 1_000_000:.2f}M"
        elif num >= 1_000:
            return f"{num / 1_000:.2f}K"
        else:
            return f"{num:.0f}"