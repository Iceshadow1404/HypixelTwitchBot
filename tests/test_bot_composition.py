"""Guard the god-object mixin split (Stage 4a).

Bot construction only runs __init__ and module-level imports, not the method
bodies that were moved into the mixins. These tests assert:
- every moved method is actually reachable on the composed Bot (catches an
  MRO / base-class-wiring slip like a forgotten mixin), and
- the messaging pipeline's write_debug_log actually writes (the one moved
  method with side effects that no other test exercises).
"""
from hypixelbot import constants
from conftest import FakeCtx, run

# Methods that were moved out of twitch.py into the mixins. If any mixin is
# dropped from the Bot bases, the corresponding getattr disappears.
MOVED_METHODS = [
    # MessagingMixin
    "send_message", "write_debug_log",
    # ProfileMixin
    "_get_player_profile_data",
    # StreamMonitorMixin
    "fetch_live_hypixel_streamers", "monitor_hypixel_streams",
    "get_twitch_access_token", "safe_join_channels",
    # EventsMixin
    "event_ready", "event_message", "event_error", "event_command_error",
    "periodic_cache_cleanup", "close",
    "event_channel_joined", "event_channel_left", "event_channel_join_failure",
]


def test_bot_exposes_all_moved_methods(bot):
    missing = [name for name in MOVED_METHODS if not callable(getattr(bot, name, None))]
    assert not missing, f"composed Bot is missing moved methods: {missing}"


def test_bot_mro_includes_all_mixins(bot):
    from hypixelbot.bot_messaging import MessagingMixin
    from hypixelbot.bot_profile import ProfileMixin
    from hypixelbot.bot_streams import StreamMonitorMixin
    from hypixelbot.bot_events import EventsMixin

    mro = type(bot).__mro__
    for mixin in (EventsMixin, StreamMonitorMixin, ProfileMixin, MessagingMixin):
        assert mixin in mro


def test_write_debug_log_writes_line(bot, tmp_path, monkeypatch):
    log_file = tmp_path / "debug_log.txt"
    monkeypatch.setattr(constants, "DEBUG_LOG", str(log_file))

    bot.write_debug_log("HELLO_TEST_LINE")

    assert log_file.exists()
    assert "HELLO_TEST_LINE" in log_file.read_text(encoding="utf-8")


def test_send_message_still_works_after_split(bot):
    # Re-assert the messaging contract from the composed Bot (mixin-provided).
    ctx = FakeCtx(bot=bot, author_name="viewer")
    run(bot.send_message(ctx, "post-split check"))
    assert ctx.sent == ["@viewer, post-split check"]
