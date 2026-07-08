from bot.commands.base import CommandContext, command
from bot.constants import NUCLEUS_CRYSTALS
from bot.hypixel.leveling import calculate_hotm_level


@command("hotm", usage="<ign> [profile]")
async def hotm(cc: CommandContext) -> None:
    p = await cc.fetch_profile()
    hotm_xp = p.member.get("mining_core", {}).get("experience", 0.0)
    level = calculate_hotm_level(cc.services.leveling, hotm_xp)
    await cc.reply(f"{p.ign}'s HotM level is {level:.2f} (XP: {hotm_xp:,.0f}) (Profile: '{p.profile_name}')")


@command("powder", usage="<ign> [profile]")
async def powder(cc: CommandContext) -> None:
    p = await cc.fetch_profile()
    mining_core = p.member.get("mining_core", {})

    parts: list[str] = []
    for powder_type in ("mithril", "gemstone", "glacite"):
        current = mining_core.get(f"powder_{powder_type}", 0)
        total = current + mining_core.get(f"powder_spent_{powder_type}", 0)
        parts.append(f"{powder_type} powder: {current:,.0f} (total: {total:,.0f})")

    await cc.reply(f"{p.ign}'s powder ({p.profile_name}): {' | '.join(parts)}")


@command("nucleus", usage="<ign> [profile]")
async def nucleus(cc: CommandContext) -> None:
    p = await cc.fetch_profile()
    crystals = p.member.get("mining_core", {}).get("crystals", {})
    total_placed = sum(crystals.get(key, {}).get("total_placed", 0) for key in NUCLEUS_CRYSTALS)
    await cc.reply(f"{p.ign}'s nucleus runs: {total_placed // 5} (Profile: '{p.profile_name}')")
