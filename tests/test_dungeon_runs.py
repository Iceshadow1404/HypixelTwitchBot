import pytest

from bot.commands.dungeon_runs import parse_sim_args, simulate_class_runs
from bot.errors import UserError
from tests.conftest import FakeCommandContext


def parse(raw: str | None, *, with_class: bool = False):
    return parse_sim_args(FakeCommandContext(raw_args=raw), with_class=with_class)


def test_no_args_defaults() -> None:
    args = parse(None)
    assert (args.ign, args.profile_name, args.target, args.floor) == (None, None, None, "m7")


def test_full_argument_set_any_order() -> None:
    args = parse("Steve Apple 55 m6")
    assert (args.ign, args.profile_name, args.target, args.floor) == ("Steve", "Apple", 55, "m6")

    args = parse("Steve m6 55 Apple")
    assert (args.ign, args.profile_name, args.target, args.floor) == ("Steve", "Apple", 55, "m6")


def test_first_arg_floor_or_target_defaults_ign_to_author() -> None:
    args = parse("m6 55")
    assert (args.ign, args.target, args.floor) == (None, 55, "m6")

    args = parse("42")
    assert (args.ign, args.target, args.floor) == (None, 42, "m7")


def test_class_alias_resolution() -> None:
    args = parse("Steve b 50", with_class=True)
    assert args.class_name == "berserk"
    assert args.target == 50

    args = parse("h", with_class=True)
    assert (args.ign, args.class_name) == (None, "healer")


def test_class_token_is_profile_without_class_mode() -> None:
    args = parse("Steve b 50", with_class=False)
    assert (args.class_name, args.profile_name) == (None, "b")


def test_ambiguous_extra_args_raise() -> None:
    with pytest.raises(UserError, match="Too many or ambiguous arguments: extra"):
        parse("Steve Apple 55 m6 extra")


def test_simulation_bottleneck_and_passive_gain() -> None:
    # class a needs 10 active runs; b drains passively (2.5/run) and needs one active run at the end
    total_runs, active_runs = simulate_class_runs({"a": 100.0, "b": 30.0}, active_gain=10.0, passive_gain=2.5)
    assert total_runs == 11
    assert active_runs == {"a": 10, "b": 1}


def test_simulation_single_class() -> None:
    total_runs, active_runs = simulate_class_runs({"mage": 25.0}, active_gain=10.0, passive_gain=2.5)
    assert total_runs == 3
    assert active_runs == {"mage": 3}
