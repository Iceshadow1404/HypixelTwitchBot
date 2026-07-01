"""Frozen #help output.

The help command builds its string from the live command registry plus a fixed
suffix. This freezes the exact bytes it produces so the refactor can't silently
change it (e.g. by dropping a command or altering the join/suffix).
"""
import types

from conftest import FakeCtx, run

EXPECTED_HELP = (
    "#auctions | #bank | #classaverage | #coinflip | #currdungeon | #dungeon | "
    "#essence | #guild | #help | #hotm | #kuudra | #link | #mayor | #networth | "
    "#nucleus | #oskill | #powder | #roll | #rtca | #rtcl | #runstillcata | "
    "#sblvl | #secrets | #skilllevel | #skills | #slayer | #status | #unlink | "
    "#whatdoing | made by Iceshadow_"
)


def test_help_output_frozen(bot):
    sent: list[str] = []

    async def capture(ctx, message):
        sent.append(message)

    # Replace the outbound pipeline with a capture so we assert on the exact
    # string the help logic builds, independent of chat delivery.
    bot.send_message = types.MethodType(lambda self, ctx, message: capture(ctx, message), bot)

    cog = bot.cogs.get("CommandsCog")
    help_cmd = bot.get_command("help")
    ctx = FakeCtx(bot=bot)

    run(help_cmd._callback(cog, ctx))

    assert sent == [EXPECTED_HELP]
