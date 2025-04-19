# --- Constants ---
MOJANG_API_URL = "https://mowojang.matdoes.dev/{username}"
HYPIXEL_API_URL = "https://api.hypixel.net/v2/skyblock/profiles"
HYPIXEL_AUCTION_URL = "https://api.hypixel.net/v2/skyblock/auction"
HYPIXEL_ELECTION_URL = "https://api.hypixel.net/v2/resources/skyblock/election"

AVERAGE_SKILLS_LIST = [
    'farming', 'mining', 'combat', 'foraging', 'fishing',
    'enchanting', 'alchemy', 'taming', 'carpentry'
]
KUUDRA_TIERS_ORDER = ['none', 'hot', 'burning', 'fiery', 'infernal']
KUUDRA_TIER_POINTS = {'none': 1, 'hot': 2, 'burning': 3, 'fiery': 4, 'infernal': 5}
CLASS_NAMES = ['healer', 'mage', 'berserk', 'archer', 'tank']
NUCLEUS_CRYSTALS = ['amber_crystal', 'topaz_crystal', 'amethyst_crystal', 'jade_crystal', 'sapphire_crystal']
ESSENCE_TYPES = ['WITHER', 'DRAGON', 'DIAMOND', 'SPIDER', 'UNDEAD', 'GOLD', 'ICE', 'CRIMSON']
SLAYER_BOSS_KEYS = ['zombie', 'spider', 'wolf', 'enderman', 'blaze', 'vampire']
BASE_M6_CLASS_XP = 105000 # From runs-to-class-average.ts
BASE_M7_CLASS_XP = 340000 # From runs-to-class-average.ts
PAUL_MULTIPLIER = 1.0 # Paul perk not considered

MAX_MESSAGE_LENGTH = 480 # Approx limit to avoid Twitch cutting messages

CACHE_TTL = 300