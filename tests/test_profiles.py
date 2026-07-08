from bot.hypixel.profiles import select_profile

UUID = "abc123"
OTHER_UUID = "other456"

APPLE = {
    "profile_id": "p1",
    "cute_name": "Apple",
    "members": {UUID: {"last_save": 100}},
}
BANANA_SELECTED = {
    "profile_id": "p2",
    "cute_name": "Banana",
    "selected": True,
    "members": {UUID: {"last_save": 50}},
}
CHERRY_NOT_MEMBER = {
    "profile_id": "p3",
    "cute_name": "Cherry",
    "members": {OTHER_UUID: {"last_save": 999}},
}

PROFILES = [APPLE, BANANA_SELECTED, CHERRY_NOT_MEMBER]


def test_requested_name_case_insensitive() -> None:
    assert select_profile(PROFILES, UUID, "apple") is APPLE
    assert select_profile(PROFILES, UUID, "APPLE") is APPLE


def test_selected_flag_wins_without_request() -> None:
    assert select_profile(PROFILES, UUID, None) is BANANA_SELECTED


def test_unknown_request_falls_back_to_selected() -> None:
    assert select_profile(PROFILES, UUID, "DoesNotExist") is BANANA_SELECTED


def test_requested_profile_where_player_not_member_falls_back() -> None:
    assert select_profile(PROFILES, UUID, "Cherry") is BANANA_SELECTED


def test_last_save_fallback_without_selected_flag() -> None:
    profiles = [APPLE, CHERRY_NOT_MEMBER]
    assert select_profile(profiles, UUID, None) is APPLE


def test_no_matching_profile_returns_none() -> None:
    assert select_profile([CHERRY_NOT_MEMBER], UUID, None) is None
    assert select_profile([], UUID, None) is None
