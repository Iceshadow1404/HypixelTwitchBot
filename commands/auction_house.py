"""Module for handling auction house related commands."""
import traceback
from datetime import datetime, timedelta

import aiohttp
from twitchio.ext import commands

import constants
from skyblock import SkyblockClient
from calculations import format_price


async def process_auctions_command(ctx: commands.Context, ign: str | None = None):

    bot = ctx.bot

    try:
        if hasattr(bot, 'skyblock_client'):
            skyblock_client = bot.skyblock_client
        else:
            skyblock_client = SkyblockClient(bot.hypixel_api_key, aiohttp.ClientSession())

        player_uuid = await skyblock_client.get_uuid_from_ign(ign, ctx.author.name)
        if not player_uuid:
            await ctx.send(f"Could not find Minecraft account for '{ign}'.")
            return

        if ign is None:
            ign = ctx.author.name

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
            await bot.send_message(ctx, f"'{ign}' has no active auctions.")
            return

        # Filter auctions that are less than 2 weeks old
        current_time = datetime.now()
        two_weeks_ago = current_time - timedelta(days=14)

        # For debugging
        print(f"[DEBUG][AuctionsCmd] Current time: {current_time}, Two weeks ago: {two_weeks_ago}")

        # Filter auctions by their timestamp, whether it's a start, end, or generic timestamp
        recent_auctions = []
        for auction in auctions:
            # Skip already claimed auctions
            if auction.get('claimed', False):
                continue

            timestamp_source = None
            auction_timestamp = None

            # Try to get any available timestamp in order of preference
            if 'start' in auction:
                auction_timestamp = auction['start']
                timestamp_source = 'start'
            # If we found a timestamp, check if it's within the last 2 weeks
            if auction_timestamp:
                try:
                    # Convert timestamp from milliseconds to datetime
                    timestamp_dt = datetime.fromtimestamp(auction_timestamp / 1000)

                    # Include auction if timestamp is within the last 2 weeks
                    if timestamp_dt >= two_weeks_ago:
                        recent_auctions.append(auction)
                except Exception as e:
                    print(f"[DEBUG][AuctionsCmd] Error processing timestamp: {e}")
                    # If there's an error processing the timestamp, include the auction to be safe
                    recent_auctions.append(auction)
            else:
                # If no timestamp is available, include the auction to be safe
                recent_auctions.append(auction)
                print(f"[DEBUG][AuctionsCmd] No timestamp found for auction {auction.get('item_name', auction.get('auction_id', 'Unknown'))}")

        if not recent_auctions:
            await bot.send_message(ctx, f"'{ign}' has no active auctions less than 2 weeks old.")
            return

        # Count unique items before filtering for character limit
        total_unique_items = len({auction.get('item_name', 'Unknown Item') for auction in recent_auctions})

        # Format output respecting character limit
        message_prefix = f"{ign}'s Auctions: "
        auction_list_parts = []
        shown_items_count = 0

        current_message = message_prefix
        for auction in recent_auctions:
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
            await bot.send_message(ctx, f"Could not format any auctions for '{ign}' within the character limit.")
            return

        # Add suffix if some items were hidden
        final_message = message_prefix + " | ".join(auction_list_parts)
        hidden_items = total_unique_items - shown_items_count
        if hidden_items > 0:
            suffix = f" (+{hidden_items} more)"
            # Check if suffix fits, otherwise omit it
            if len(final_message) + len(suffix) <= constants.MAX_MESSAGE_LENGTH:
                final_message += suffix

        await bot.send_message(ctx, final_message)

    except Exception as e:
        print(f"[ERROR][AuctionsCmd] Unexpected error processing auctions: {e}")
        traceback.print_exc()
        await bot.send_message(ctx, "An unexpected error occurred while fetching auctions.")