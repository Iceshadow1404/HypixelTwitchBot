import pytest

from bot.hypixel import cache as cache_module
from bot.hypixel.cache import TTLCache


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> dict[str, float]:
    state = {"now": 1000.0}
    monkeypatch.setattr(cache_module.time, "time", lambda: state["now"])
    return state


def test_get_within_ttl(clock: dict[str, float]) -> None:
    cache: TTLCache[str] = TTLCache(ttl=300)
    cache.set("key", "value")
    clock["now"] += 299
    assert cache.get("key") == "value"


def test_get_after_ttl_expires(clock: dict[str, float]) -> None:
    cache: TTLCache[str] = TTLCache(ttl=300)
    cache.set("key", "value")
    clock["now"] += 300
    assert cache.get("key") is None


def test_missing_key() -> None:
    cache: TTLCache[str] = TTLCache(ttl=300)
    assert cache.get("missing") is None


def test_cleanup_expired(clock: dict[str, float]) -> None:
    cache: TTLCache[str] = TTLCache(ttl=300)
    cache.set("old", "1")
    clock["now"] += 200
    cache.set("new", "2")
    clock["now"] += 150  # "old" is now 350s old, "new" 150s
    assert cache.cleanup_expired() == 1
    assert cache.size() == 1
    assert cache.get("new") == "2"
