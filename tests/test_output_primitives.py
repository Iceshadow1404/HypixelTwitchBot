"""Behavioural tests for the output-producing primitives the refactor touches.

- send_message: the @{user}, prefix pipeline (Stage 4a moves this code).
- format_number: K/M/B formatting used across commands.
- _parse_command_args: the single arg parser Stage 4b makes canonical; its
  edge behaviour (incl. the user-visible "Too many arguments" message) must
  not change.
"""
import types

import pytest

from conftest import FakeCtx, run
from hypixelbot import utils
# --- send_message: reply-format pipeline -----------------------------------

def test_send_message_prefixes_user_mention(bot):
    ctx = FakeCtx(bot=bot, author_name="viewer", channel_name="chan")
    # Offline, get_channel() returns None -> code path falls back to ctx.send().
    run(bot.send_message(ctx, "hello world"))
    assert ctx.sent == ["@viewer, hello world"]


def test_send_message_does_not_truncate_reply(bot):
    ctx = FakeCtx(bot=bot, author_name="u")
    long_msg = "x" * 600
    run(bot.send_message(ctx, long_msg))
    # The 450-char slice in send_message only affects the debug log, not the reply.
    assert ctx.sent == [f"@u, {long_msg}"]


# --- format_number ----------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    (0, "0"),
    (999, "999"),
    (999.4, "999"),
    (1000, "1.00K"),
    (1500, "1.50K"),
    (999_999, "1000.00K"),
    (1_000_000, "1.00M"),
    (2_500_000, "2.50M"),
    (1_000_000_000, "1.00B"),
    (12_340_000_000, "12.34B"),
])
def test_format_number(value, expected):
    assert utils.format_number(value) == expected


# --- _parse_command_args ----------------------------------------------------

class _FakeParseBot:
    """Minimal bot for the parser: only _prefix and send_message are used."""

    def __init__(self):
        self._prefix = "#"
        self.sent: list[str] = []

    async def send_message(self, ctx, message):
        self.sent.append(message)


def test_parse_no_args_uses_author():
    fbot = _FakeParseBot()
    ctx = FakeCtx(author_name="alice")
    result = run(utils._parse_command_args(fbot, ctx, None, "skills"))
    assert result == ("alice", None)
    assert fbot.sent == []


def test_parse_single_arg_is_ign():
    fbot = _FakeParseBot()
    ctx = FakeCtx(author_name="alice")
    result = run(utils._parse_command_args(fbot, ctx, "Notch", "skills"))
    assert result == ("Notch", None)


def test_parse_two_args_is_ign_and_profile():
    fbot = _FakeParseBot()
    ctx = FakeCtx(author_name="alice")
    result = run(utils._parse_command_args(fbot, ctx, "Notch Apple", "skills"))
    assert result == ("Notch", "Apple")


def test_parse_too_many_args_errors():
    fbot = _FakeParseBot()
    ctx = FakeCtx(author_name="alice")
    result = run(utils._parse_command_args(fbot, ctx, "Notch Apple Extra", "skills"))
    assert result == (None, None)
    assert fbot.sent == [
        "Too many arguments. Usage: #skills <username> [profile_name]"
    ]
