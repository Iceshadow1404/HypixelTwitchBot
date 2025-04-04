"""Module for handling auction house related commands."""
import traceback
from datetime import datetime

import aiohttp
from twitchio.ext import commands

import constants
from utils import _get_uuid_from_ign
from calculations import format_price


async def process_auctions_command(ctx: commands.Context, ign: str | None = None):
    """Shows active auctions for a player, limited by character count.
       This command currently DOES NOT support profile selection.
    """
    bot = ctx.bot
    if not bot.hypixel_api_key:  # API key check needed here as it uses a different endpoint helper
        await ctx.send("Hypixel API is not configured.")
        return

    target_ign = ign if ign else ctx.author.name
    target_ign = target_ign.lstrip('@')

    try:
        player_uuid = await _get_uuid_from_ign(target_ign)
        if not player_uuid:
            await ctx.send(f"Could not find Minecraft account for '{target_ign}'.")
            return

        # --- Fetch Auction Data ---
        url = constants.HYPIXEL_AUCTION_URL
        params = {"key": bot.hypixel_api_key, "player": player_uuid}
        print(f"[DEBUG][API] Hypixel Auctions request for UUID '{player_uuid}'...")
        auctions = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    print(f"[DEBUG][API] Hypixel Auctions response status: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        if data.get("success"):
                            auctions = data.get('auctions', [])
                        else:
                            reason = data.get('cause', 'Unknown reason')
                            print(f"[ERROR][API] Hypixel Auctions API Error: {reason}")
                            await ctx.send("Failed to fetch auction data (API error).")
                            return
                    else:
                        print(f"[ERROR][API] Hypixel Auctions API request failed: Status {response.status}")
                        await ctx.send("Failed to fetch auction data (HTTP error).")
                        return
        except aiohttp.ClientError as e:
            print(f"[ERROR][API] Network error during Hypixel Auctions API request: {e}")
            await ctx.send("Failed to fetch auction data (Network error).")
            return
        except Exception as e:
            print(f"[ERROR][API] Unexpected error during Hypixel Auctions API request: {e}")
            traceback.print_exc()
            await ctx.send("An unexpected error occurred while fetching auctions.")
            return
        # --- End Fetch Auction Data ---

        if not auctions:
            await bot._send_message(ctx, f"'{target_ign}' has no active auctions.")
            return

        # Count unique items before filtering
        total_unique_items = len({auction.get('item_name', 'Unknown Item') for auction in auctions})

        # Format output respecting character limit
        message_prefix = f"{target_ign}'s Auctions: "
        auction_list_parts = []
        shown_items_count = 0

        current_message = message_prefix
        for auction in auctions:
            item_name = auction.get('item_name', 'Unknown Item').replace("§.", "")  # Basic formatting code removal
            highest_bid = auction.get('highest_bid_amount', 0)
            if highest_bid == 0:
                highest_bid = auction.get('starting_bid', 0)

            price_str = format_price(highest_bid)
            auction_str = f"{item_name} {price_str}"

            # Check if adding the next item exceeds the limit
            separator = " | " if auction_list_parts else ""
            if len(current_message) + len(separator) + len(auction_str) <= constants.MAX_MESSAGE_LENGTH:
                auction_list_parts.append(auction_str)
                current_message += separator + auction_str
                shown_items_count += 1
            else:
                # Stop adding more items if limit is reached
                break

        if not auction_list_parts:
            await bot._send_message(ctx, f"Could not format any auctions for '{target_ign}' within the character limit.")
            return

        # Add suffix if some items were hidden
        final_message = message_prefix + " | ".join(auction_list_parts)
        hidden_items = total_unique_items - shown_items_count
        if hidden_items > 0:
            suffix = f" (+{hidden_items} more)"
            # Check if suffix fits, otherwise omit it
            if len(final_message) + len(suffix) <= constants.MAX_MESSAGE_LENGTH:
                final_message += suffix

        await bot._send_message(ctx, final_message)

    except Exception as e:
        print(f"[ERROR][AuctionsCmd] Unexpected error processing auctions: {e}")
        traceback.print_exc()
        await bot._send_message(ctx, "An unexpected error occurred while fetching auctions.")
