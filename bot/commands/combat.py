from bot.commands.base import CommandContext, command
from bot.constants import ESSENCE_TYPES, KUUDRA_TIER_POINTS, KUUDRA_TIERS_ORDER, SLAYER_BOSS_KEYS
from bot.errors import UserError
from bot.format import format_price
from bot.hypixel.leveling import calculate_slayer_level


@command("kuudra", usage="<ign> [profile]")
async def kuudra(cc: CommandContext) -> None:
    p = await cc.fetch_profile()
    nether_data = p.member.get("nether_island_player_data")
    if nether_data is None:
        return
    completed_tiers = nether_data.get("kuudra_completed_tiers")
    if not completed_tiers:
        raise UserError(f"No Kuudra completions recorded for {p.ign} in profile {p.profile_name}.")

    completions: list[str] = []
    total_score = 0
    for tier in KUUDRA_TIERS_ORDER:
        count = completed_tiers.get(tier, 0)
        tier_name = "basic" if tier == "none" else tier
        completions.append(f"{tier_name} {count}")
        total_score += count * KUUDRA_TIER_POINTS.get(tier, 0)

    await cc.reply(
        f"{p.ign}'s Kuudra completions in profile '{p.profile_name}': "
        f"{', '.join(completions)} | Score: {total_score:,}"
    )


@command("slayer", aliases=("slayers",), usage="<ign> [profile]")
async def slayer(cc: CommandContext) -> None:
    p = await cc.fetch_profile()
    slayer_bosses = p.member.get("slayer", {}).get("slayer_bosses", {})
    if not slayer_bosses:
        raise UserError(f"'{p.ign}' has no slayer data in profile '{p.profile_name}'.")

    total_xp = 0
    levels: list[str] = []
    for boss_key in SLAYER_BOSS_KEYS:
        xp = slayer_bosses.get(boss_key, {}).get("xp", 0)
        total_xp += xp
        level = calculate_slayer_level(cc.services.leveling, xp, boss_key)
        levels.append(f"{boss_key.capitalize()} {level} ({format_price(xp)} XP)")

    await cc.reply(
        f"{p.ign}'s Slayers (Profile: '{p.profile_name}'): "
        f"Total XP: {format_price(total_xp)} | {' | '.join(levels)}"
    )


@command("essence", usage="<ign> [profile]")
async def essence(cc: CommandContext) -> None:
    p = await cc.fetch_profile()
    all_essence = p.member.get("currencies", {}).get("essence", {})
    if not all_essence:
        raise UserError(f"No essence data found for '{p.ign}' in profile '{p.profile_name}'.")

    amounts = [
        f"{essence_type.capitalize()}: {format_price(all_essence.get(essence_type, {}).get('current', 0))}"
        for essence_type in ESSENCE_TYPES
    ]
    await cc.reply(f"{p.ign} (Profile: '{p.profile_name}'): {' | '.join(amounts)}")
