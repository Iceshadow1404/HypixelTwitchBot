# bot_events.py
# twitchio event handlers + lifecycle for the Bot. Mixed in via MRO; twitchio
# dispatches events with getattr(self, "event_<name>"), so these resolve through
# the composed Bot's MRO exactly as if defined on Bot.
import asyncio
import re
import traceback

import aiohttp
from twitchio.ext import commands

from skyblock import SkyblockClient


class EventsMixin:
    """Connection lifecycle, message routing, channel join/leave, cache cleanup."""

    # --- Helper Methods ---
    async def event_command_error(self, ctx: commands.Context, error: Exception):
        # Handle command errors with additional channel context information
        if isinstance(error, commands.CommandNotFound):
            # Extract the command name from the error message
            match = re.search(r'No command "([^"]+)" was found', str(error))
            cmd_name = match.group(1) if match else "unknown"

            # Get channel name safely
            channel_name = ctx.channel.name if hasattr(ctx.channel, 'name') else "unknown_channel"

            # Get username safely
            username = ctx.author.name if hasattr(ctx.author, 'name') else "unknown_user"

            # Log with the channel information
            print(f"[WARN] Command not found: '{cmd_name}' from channel: #{channel_name} by user: {username}")
        else:
            # Log other command errors
            channel_name = ctx.channel.name if hasattr(ctx.channel, 'name') else "unknown_channel"
            print(f"[ERROR] Error in command from channel #{channel_name}: {str(error)}")
            traceback.print_exc()

    # --- Bot Events ---

    async def event_error(self, error: Exception, data: str = None):
        print(f"[ERROR][event_error] An unhandled error occurred: {error}")
        traceback.print_exc()

    async def event_ready(self):
        # Called once the bot has successfully connected to Twitch and joined initial channels.
        try:
            print("[INFO] Bot starting up... Initial connection established.")
            self.write_debug_log("BOT_STARTUP: Bot successfully connected to Twitch")

            # Initialize the aiohttp session and SkyblockClient for caching
            self.session = aiohttp.ClientSession()
            self.skyblock_client = SkyblockClient(self.hypixel_api_key, self.session)
            print("[INFO] SkyblockClient initialized with caching.")

            print(f'------')
            print(f'Logged in as: {self.nick} ({self.user_id})')
            # Filter out None before accessing name
            initial_connected_channels = [ch.name for ch in self.connected_channels if ch is not None]
            print(f'Successfully joined initial channels from .env: {initial_connected_channels}')
            print(f'------')

            if initial_connected_channels:
                self.write_debug_log(f"INITIAL_CHANNELS: {', '.join([f'#{ch}' for ch in initial_connected_channels])}")

            # --- Fetch and Join Live Hypixel Streamers ONLY IF NOT IN LOCAL MODE ---
            if not self.local_mode:
                print("[INFO] LIVE MODE: Performing initial scan for live Hypixel SkyBlock streamers...")
                live_streamer_names = await self.fetch_live_hypixel_streamers()

                if live_streamer_names is None:
                    print(
                        "[WARN] Could not fetch live streamers during startup (API/Token issue?). Monitoring will still run.")
                else:
                    print(f"[INFO] Found {len(live_streamer_names)} potential live Hypixel SkyBlock streamers.")
                    # Determine which channels to join (those not already connected to)
                    # Filter out None before accessing name
                    # Use the potentially updated list of connected channels after the retry
                    currently_connected = {ch.name.lower() for ch in self.connected_channels if
                                           ch is not None}  # Use lowercase set
                    streamers_to_join = [name for name in live_streamer_names if name.lower() not in currently_connected]
                    # No need for streamers_to_join_lower now as we compare lowercase directly

                    if streamers_to_join:
                        print(
                            f"[INFO] Attempting to join {len(streamers_to_join)} newly found live channels: {streamers_to_join}")
                        try:
                            await self.safe_join_channels(streamers_to_join)
                            print("[INFO] Join command sent for live channels. Waiting briefly for channel list update...")
                            await asyncio.sleep(5)  # Give TwitchIO time to process joins and update self.connected_channels
                        except Exception as join_error:
                            print(f"[ERROR] Error trying to join channels: {join_error}")
                    else:
                        print("[INFO] All found live streamers are already in the connected channel list.")
            else: # <-- Optional: Log-Nachricht für Local Mode
                 print("[INFO] LOCAL MODE: Skipping dynamic joining of live streams on startup.")
            # --- End Fetch and Join ---

            # --- Final Output ---
            # Filter out None before accessing name
            final_connected_channels = [ch.name for ch in self.connected_channels if ch is not None]
            print(
                f'[INFO] Final connected channels list ({len(final_connected_channels)} total): {final_connected_channels}')

            if final_connected_channels:
                print(f"[INFO] Bot setup complete.")
                if not self.local_mode:
                    print(f"[INFO] Monitoring active streams.")
                print(f"[INFO] Bot is ready!")
            else:
                print("[WARN] Bot connected to Twitch but is not in any channels.")

            if not self.local_mode:
                print("[INFO] Starting background stream monitor task...")
                asyncio.create_task(self.monitor_hypixel_streams())

            # --- Start Cache Cleanup Task (läuft immer) ---
            print("[INFO] Starting background cache cleanup task...")
            asyncio.create_task(self.periodic_cache_cleanup())

        except Exception as e:
            print(f"[ERROR] Error during event_ready: {e}")
            traceback.print_exc()

    async def event_message(self, message):
        # Processes incoming Twitch chat messages.
        if message.echo:
            return  # Ignore messages sent by the bot itself

        if not hasattr(message.channel, 'name') or not hasattr(message.author, 'name') or not message.author.name:
            return  # Ignore system messages or messages without proper author/channel context

        connected_channel_names = {ch.name for ch in self.connected_channels if ch is not None}
        if message.channel.name not in connected_channel_names:
            return

        await self.handle_commands(message)

    async def periodic_cache_cleanup(self):
        # Periodically clears old entries from the cache to prevent memory growth.
        print("[INFO][CacheCleanup] Starting periodic cache cleanup task...")
        cleanup_interval = 3600  # Clean up every hour

        while True:
            try:
                await asyncio.sleep(cleanup_interval)
                if self.skyblock_client and hasattr(self.skyblock_client, 'cache'):

                    stats_before = self.skyblock_client.cache.get_stats()

                    uuid_removed, skyblock_removed = self.skyblock_client.cache.cleanup_expired()

                    stats_after = self.skyblock_client.cache.get_stats()
                    print(
                        f"[INFO][CacheCleanup] Cache cleaned. Before: {stats_before['uuid_cache_size']} UUID entries, "
                        f"{stats_before['skyblock_data_cache_size']} Skyblock data entries. "
                        f"After: {stats_after['uuid_cache_size']} UUID entries (-{uuid_removed}), "
                        f"{stats_after['skyblock_data_cache_size']} Skyblock data entries (-{skyblock_removed})")
                else:
                    print(
                        "[WARN][CacheCleanup] SkyblockClient not initialized or cache not available, skipping cleanup")
            except Exception as e:
                print(f"[ERROR][CacheCleanup] Error during cache cleanup: {e}")
                traceback.print_exc()

    # --- Cleanup ---
    async def close(self):
        """Gracefully shuts down the bot and closes sessions."""
        print("[INFO] Shutting down bot...")
        self.write_debug_log("BOT_SHUTDOWN: Bot is shutting down")

        # Close the aiohttp session when shutting down
        if self.session and not self.session.closed:
            await self.session.close()
            print("[INFO] aiohttp session closed.")

        await super().close()
        print("[INFO] Bot connection closed.")

    # --- Überschriebene Event-Handler für Channel Join/Leave ---

    async def event_channel_joined(self, channel):
        """Called when the bot successfully joins a channel."""
        channel_name = channel.name if hasattr(channel, 'name') else str(channel)

        self.write_debug_log(f"JOINED: #{channel_name}")

        # Reset join attempts counter if successful
        if channel_name.lower() in self.channel_join_attempts:
            del self.channel_join_attempts[channel_name.lower()]

    async def event_channel_left(self, channel):
        """Called when the bot leaves a channel."""
        channel_name = channel.name if hasattr(channel, 'name') else str(channel)

        print(f"[INFO] Left channel: #{channel_name}")
        self.write_debug_log(f"LEFT: #{channel_name}")

    async def event_channel_join_failure(self, channel: str):
        """Handle channel join failures with retry logic."""
        channel_lower = channel.lower()

        print(f"[WARN] Failed to join channel: #{channel}")
        self.write_debug_log(f"JOIN_FAILED: #{channel}")

        # Increment attempt counter
        if channel_lower not in self.channel_join_attempts:
            self.channel_join_attempts[channel_lower] = 0

        self.channel_join_attempts[channel_lower] += 1
        current_attempts = self.channel_join_attempts[channel_lower]

        print(f'[WARN] Failed to join channel "{channel}" (attempt {current_attempts}/5)')

        if current_attempts >= 5:
            # Add to blacklist after 5 failed attempts
            self.blacklisted_channels.add(channel_lower)
            print(
                f'[ERROR] Channel "{channel}" blacklisted after {current_attempts} failed attempts. Will ignore until bot restart.')
            self.write_debug_log(f"BLACKLISTED: #{channel} (after {current_attempts} failed attempts)")

            # Clean up the attempts counter since we're blacklisting
            del self.channel_join_attempts[channel_lower]
        else:
            # Schedule a retry after a brief delay
            remaining_attempts = 5 - current_attempts
            print(f'[INFO] Will retry joining "{channel}" later ({remaining_attempts} attempts remaining)')
