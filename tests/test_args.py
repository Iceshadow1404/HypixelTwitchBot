import pytest

from bot.errors import UserError
from tests.conftest import FakeCommandContext


def test_no_args_returns_none_pair() -> None:
    cc = FakeCommandContext(raw_args=None)
    assert cc.parse_ign_profile() == (None, None)


def test_ign_only() -> None:
    cc = FakeCommandContext(raw_args="Steve")
    assert cc.parse_ign_profile() == ("Steve", None)


def test_ign_and_profile() -> None:
    cc = FakeCommandContext(raw_args="Steve Apple")
    assert cc.parse_ign_profile() == ("Steve", "Apple")


def test_too_many_args_raises_with_usage() -> None:
    cc = FakeCommandContext(raw_args="Steve Apple extra")
    with pytest.raises(UserError, match=r"Too many arguments\. Usage: #test <ign> \[profile\]"):
        cc.parse_ign_profile()


def test_usage_string_uses_prefix_and_name() -> None:
    cc = FakeCommandContext()
    assert cc.usage == "#test <ign> [profile]"


def test_invisible_chat_client_suffixes_are_stripped() -> None:
    # Chatterino/7TV append invisible chars to bypass Twitch's duplicate filter
    cc = FakeCommandContext(raw_args="10 \u034f")
    assert cc.raw_args == "10"

    cc = FakeCommandContext(raw_args="Steve\U000e0000 Apple\u200b")
    assert cc.parse_ign_profile() == ("Steve", "Apple")

    cc = FakeCommandContext(raw_args="\u034f")
    assert cc.raw_args is None
