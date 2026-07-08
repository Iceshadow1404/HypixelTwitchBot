MOJANG_API_URL = "https://mowojang.matdoes.dev/{username}"
MOJANG_API_URL_FALLBACK = "https://api.mojang.com/users/profiles/minecraft/{username}"
HYPIXEL_API_URL = "https://api.hypixel.net/v2/skyblock/profiles"
HYPIXEL_AUCTION_URL = "https://api.hypixel.net/v2/skyblock/auction"
HYPIXEL_ELECTION_URL = "https://api.hypixel.net/v2/resources/skyblock/election"
HYPIXEL_MUSEUM_URL = "https://api.hypixel.net/v2/skyblock/museum"
HYPIXEL_GUILD_API_URL = "https://api.hypixel.net/v2/guild"
HYPIXEL_STATUS_URL = "https://api.hypixel.net/status"
HYPIXEL_STATUS_RSS_URL = "https://status.hypixel.net/history.rss"

AVERAGE_SKILLS_LIST = [
    "farming",
    "mining",
    "combat",
    "foraging",
    "fishing",
    "enchanting",
    "alchemy",
    "taming",
    "carpentry",
    "hunting",
]
KUUDRA_TIERS_ORDER = ["none", "hot", "burning", "fiery", "infernal"]
KUUDRA_TIER_POINTS = {"none": 1, "hot": 2, "burning": 3, "fiery": 4, "infernal": 5}
CLASS_NAMES = ["healer", "mage", "berserk", "archer", "tank"]
NUCLEUS_CRYSTALS = ["amber_crystal", "topaz_crystal", "amethyst_crystal", "jade_crystal", "sapphire_crystal"]
ESSENCE_TYPES = ["WITHER", "DRAGON", "DIAMOND", "SPIDER", "UNDEAD", "GOLD", "ICE", "CRIMSON"]
SLAYER_BOSS_KEYS = ["zombie", "spider", "wolf", "enderman", "blaze", "vampire"]

BASE_M6_CLASS_XP = 105_000
BASE_M7_CLASS_XP = 340_000
BASE_M6_XP = 180_000
BASE_M7_XP = 500_000
# XP-per-run fudge applied to class XP simulations (matches observed in-game gains)
CLASS_XP_BUFF_FACTOR = 1.06
DERPY_XP_MULTIPLIER = 1.5

MAX_MESSAGE_LENGTH = 480  # approx limit to avoid Twitch cutting messages
CACHE_TTL = 300
