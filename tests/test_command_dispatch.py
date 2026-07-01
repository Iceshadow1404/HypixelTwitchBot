"""Plumbing net for the Stage 4b dispatch unification.

Registry + ruff confirm a command still *registers* and imports resolve; they do
NOT confirm it still *routes* to the right impl with the right args. These tests
stub the underlying impl, fire the cog command callback, and assert the impl got
the exact args — catching wrong-target, dropped-kwarg and changed-guard slips.

They pin CURRENT behaviour, including the latent quirk that _parse_command_args
returns (None, None) on "too many args" (not None), so the cog guard never fires
and the impl still runs with ign=None after the error message is sent.
"""
import pytest

from conftest import FakeCtx, run


class Recorder:
    def __init__(self):
        self.calls = []

    async def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))


def _fire(bot, command_name, args):
    cog = bot.cogs.get("CommandsCog")
    cmd = bot.get_command(command_name)
    ctx = FakeCtx(bot=bot)
    run(cmd._callback(cog, ctx, args=args))
    return ctx


# (command, module-qualified impl to stub) for the "parse happens in dispatch" group.
PARSE_COMMANDS = [
    ("skills", "hypixelbot.commands.skills.process_skills_command"),
    ("oskill", "hypixelbot.commands.overflow_skills.process_overflow_skill_command"),
    ("dungeon", "hypixelbot.commands.cata.process_dungeon_command"),
    ("sblvl", "hypixelbot.commands.sblvl.process_sblvl_command"),
]


@pytest.mark.parametrize("command,target", PARSE_COMMANDS)
def test_parse_command_routes_ign_and_profile(bot, monkeypatch, command, target):
    rec = Recorder()
    monkeypatch.setattr(target, rec)
    _fire(bot, command, "Notch Apple")
    assert len(rec.calls) == 1
    args, kwargs = rec.calls[0]
    # ctx is args[0]; ign is args[1]; profile passed as keyword.
    assert args[1] == "Notch"
    assert kwargs.get("requested_profile_name") == "Apple"


@pytest.mark.parametrize("command,target", PARSE_COMMANDS)
def test_parse_command_too_many_args_preserves_quirk(bot, monkeypatch, command, target):
    rec = Recorder()
    monkeypatch.setattr(target, rec)
    ctx = _fire(bot, command, "a b c")
    # Error message is sent...
    assert any("Too many arguments" in m for m in ctx.sent)
    # ...AND the impl still runs with ign=None (current behaviour, must be preserved).
    assert len(rec.calls) == 1
    assert rec.calls[0][0][1] is None


# Forward-only group: dispatch just hands the raw arg string to the impl.
FORWARD_COMMANDS = [
    ("auctions", "hypixelbot.commands.auction_house.process_auctions_command"),
    ("guild", "hypixelbot.commands.guild.process_guild_command"),
    ("secrets", "hypixelbot.commands.secrets.secrets_command"),
    ("skilllevel", "hypixelbot.commands.skill_level.skill_level_command"),
]


@pytest.mark.parametrize("command,target", FORWARD_COMMANDS)
def test_forward_command_passes_raw_args(bot, monkeypatch, command, target):
    rec = Recorder()
    monkeypatch.setattr(target, rec)
    _fire(bot, command, "Notch")
    assert len(rec.calls) == 1
    args, kwargs = rec.calls[0]
    # The raw arg string reaches the impl (positional or keyword).
    passed = list(args[1:]) + list(kwargs.values())
    assert "Notch" in passed
