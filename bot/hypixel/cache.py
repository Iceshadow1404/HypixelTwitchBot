import logging
import time
from typing import Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class TTLCache(Generic[T]):
    """In-memory cache whose entries expire after a fixed time-to-live."""

    def __init__(self, ttl: int) -> None:
        self._entries: dict[str, tuple[T, float]] = {}
        self.ttl = ttl

    def get(self, key: str) -> T | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        value, timestamp = entry
        age = time.time() - timestamp
        if age >= self.ttl:
            logger.debug("cache expired for %r (age %ds)", key, int(age))
            return None
        logger.debug("cache hit for %r (age %ds)", key, int(age))
        return value

    def set(self, key: str, value: T) -> None:
        self._entries[key] = (value, time.time())

    def cleanup_expired(self) -> int:
        now = time.time()
        expired = [key for key, (_, ts) in self._entries.items() if now - ts >= self.ttl]
        for key in expired:
            del self._entries[key]
        return len(expired)

    def size(self) -> int:
        return len(self._entries)
