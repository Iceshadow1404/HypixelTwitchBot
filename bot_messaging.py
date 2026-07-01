# bot_messaging.py
# Outbound chat + debug-log helpers for the Bot. Mixed into Bot via MRO.
import asyncio
import os
import traceback
from datetime import datetime

from twitchio.ext import commands

import constants


class MessagingMixin:
    """Reply pipeline and debug logging.

    Behaviour is intentionally byte-for-byte identical to the original Bot
    methods: every reply is prefixed with ``@{user}, `` and rate-limited by a
    0.3s sleep. Do not "tidy" the prefix, the 450-char log slice, or the sleep.
    """

    async def send_message(self, ctx: commands.Context, message: str):
        # Truncate message for logging if it's too long
        log_message = message[:450] + '...' if len(message) > 450 else message
        print(f"[DEBUG][Reply] Attempting to reply in #{ctx.channel.name}: {log_message}")

        try:
            await asyncio.sleep(0.3)

            # Format message to include mention of the original sender
            reply_message = f"@{ctx.author.name}, {message}"

            channel_name = ctx.channel.name
            channel = self.get_channel(channel_name)
            if channel:
                print(f"[DEBUG][Reply] Re-fetched channel object for {channel_name}. Sending reply via channel object.")
                await channel.send(reply_message)
                self.write_debug_log(channel_name + " " + reply_message)
                print(f"[DEBUG][Reply] Successfully sent reply via channel object to #{channel_name}.")
            else:
                # Fallback if channel couldn't be re-fetched (should not happen if connected)
                print(
                    f"[WARN][Reply] Could not re-fetch channel object for {channel_name}. Falling back to ctx.send().")
                await ctx.send(reply_message)
                print(f"[DEBUG][Reply] Successfully sent reply via ctx.send() to #{channel_name}.")

        except Exception as reply_e:
            print(f"[ERROR][Reply] FAILED to send reply to #{ctx.channel.name}: {reply_e}")
            traceback.print_exc()

    def write_debug_log(self, message: str):
        """Schreibt eine Nachricht mit Zeitstempel in die Debug-Log-Datei."""
        try:
            timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            log_entry = f"[{timestamp}] {message}\n"

            # Stelle sicher, dass das Verzeichnis existiert
            os.makedirs(os.path.dirname(constants.DEBUG_LOG), exist_ok=True)

            with open(constants.DEBUG_LOG, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except Exception as e:
            print(f"[ERROR] Failed to write to debug log: {e}")
