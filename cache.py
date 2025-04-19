import time
from typing import Dict, Tuple, TypeVar, Generic, Any, Optional, List

# Define generic type for cached values
T = TypeVar('T')


class Cache(Generic[T]):
    # Generic cache class for storing values with expiration

    def __init__(self, ttl: int):
        # Initialize the cache with a time-to-live in seconds
        self.cache: Dict[str, Tuple[T, float]] = {}
        self.ttl = ttl

    def get(self, key: str) -> Optional[T]:
        # Get a value from cache if it exists and hasn't expired
        current_time = time.time()

        if key in self.cache:
            value, timestamp = self.cache[key]

            # Check if entry has expired
            if current_time - timestamp < self.ttl:
                print(f"[Cache] Cache hit for '{key}' (Age: {int(current_time - timestamp)}s)")
                return value
            else:
                print(f"[Cache] Cache expired for '{key}' (Age: {int(current_time - timestamp)}s)")
                return None

        return None

    def set(self, key: str, value: T) -> None:
        # Store a value in the cache with current timestamp
        self.cache[key] = (value, time.time())
        print(f"[Cache] Stored '{key}' in cache")

    def delete(self, key: str) -> bool:
        # Delete a specific key from the cache
        if key in self.cache:
            self.cache.pop(key)
            print(f"[Cache] Deleted '{key}' from cache")
            return True

        print(f"[Cache] Key '{key}' not found in cache for deletion")
        return False

    def clear(self) -> None:
        # Clear all entries from the cache
        self.cache.clear()
        print(f"[Cache] Cache cleared completely")

    def cleanup_expired(self) -> int:
        # Remove all expired entries from the cache and return count
        current_time = time.time()
        expired_keys = [
            key for key, (_, timestamp) in self.cache.items()
            if current_time - timestamp >= self.ttl
        ]

        for key in expired_keys:
            self.cache.pop(key)

        if expired_keys:
            print(f"[Cache] Cleaned up {len(expired_keys)} expired entries")

        return len(expired_keys)

    def size(self) -> int:
        # Get the current number of entries in the cache
        return len(self.cache)


class SkyblockCache:
    # Specialized cache manager for Skyblock API data

    def __init__(self, ttl: int):
        # Initialize the Skyblock cache with specified TTL
        # Cache for username to UUID mapping
        self.uuid_cache = Cache[str](ttl)

        # Cache for UUID to profile data mapping
        self.skyblock_data_cache = Cache[List[Dict[str, Any]]](ttl)

        self.ttl = ttl

    def get_uuid(self, username: str) -> Optional[str]:
        # Get a cached UUID for a username
        return self.uuid_cache.get(username)

    def set_uuid(self, username: str, uuid: str) -> None:
        # Cache a UUID for a username
        self.uuid_cache.set(username, uuid)

    def get_skyblock_data(self, uuid: str) -> Optional[List[Dict[str, Any]]]:
        # Get cached Skyblock data for a UUID
        return self.skyblock_data_cache.get(uuid)

    def set_skyblock_data(self, uuid: str, data: List[Dict[str, Any]]) -> None:
        # Cache Skyblock data for a UUID
        self.skyblock_data_cache.set(uuid, data)

    def invalidate_player(self, username: str) -> None:
        # Invalidate all cached data for a specific player by username
        # Get UUID first
        uuid = self.get_uuid(username)

        # Delete from both caches
        self.uuid_cache.delete(username)

        if uuid:
            self.skyblock_data_cache.delete(uuid)
            print(f"[SkyblockCache] Invalidated all data for player '{username}' (UUID: {uuid})")
        else:
            print(f"[SkyblockCache] Invalidated username data for '{username}' (No UUID found)")

    def clear_all(self) -> None:
        # Clear all cached data
        self.uuid_cache.clear()
        self.skyblock_data_cache.clear()
        print("[SkyblockCache] All caches cleared")

    def cleanup_expired(self) -> Tuple[int, int]:
        # Clean up expired entries from all caches
        uuid_count = self.uuid_cache.cleanup_expired()
        skyblock_count = self.skyblock_data_cache.cleanup_expired()

        return (uuid_count, skyblock_count)

    def get_stats(self) -> Dict[str, int]:
        # Get current cache statistics
        return {
            "uuid_cache_size": self.uuid_cache.size(),
            "skyblock_data_cache_size": self.skyblock_data_cache.size()
        }