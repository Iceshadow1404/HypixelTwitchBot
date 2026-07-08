import logging
import time

from bot.commands.base import CommandContext, command
from bot.constants import MAX_MESSAGE_LENGTH
from bot.errors import UserError
from bot.format import format_number, format_price

logger = logging.getLogger(__name__)

TWO_WEEKS_SECONDS = 14 * 24 * 3600


@command("bank", aliases=("purse", "money"), usage="<ign> [profile]")
async def bank(cc: CommandContext) -> None:
    p = await cc.fetch_profile()
    bank_balance = p.profile.get("banking", {}).get("balance", 0.0)
    purse_balance = p.member.get("currencies", {}).get("coin_purse", 0.0)
    personal_bank = p.member.get("profile", {}).get("bank_account")

    parts = [f"{p.ign}'s Bank: {bank_balance:,.0f}", f"Purse: {purse_balance:,.0f}"]
    if personal_bank is not None:
        parts.append(f"Personal Bank: {personal_bank:,.0f}")
    parts.append(f"(Profile: '{p.profile_name}')")
    await cc.reply(", ".join(parts))


@command("networth", aliases=("nw",), usage="<ign> [profile]")
async def networth(cc: CommandContext) -> None:
    p = await cc.fetch_profile()
    inventory_api_off = "inventory" not in p.member

    if not p.profile_id:
        logger.error("no profile ID found for %s", p.ign)
        raise UserError(f"Couldn't calculate networth for {p.ign}: Missing profile ID")

    museum = await cc.services.hypixel.get_museum(p.uuid, p.profile_id)
    museum_member = museum.get("members", {}).get(p.uuid) if museum else None

    bank_balance = p.profile.get("banking", {}).get("balance", 0)
    result = await cc.services.networth.calculate(p.uuid, p.profile, museum_member, bank_balance)
    if not result or not result.get("success"):
        error_msg = result.get("error", "Unknown error") if result else "Failed to calculate networth"
        raise UserError(f"Couldn't calculate networth for {p.ign}: {error_msg}")

    response = f"Networth for {p.ign} ({p.profile_name}): {format_number(result.get('networth', 0))}"

    extras: list[str] = []
    purse = result.get("purse", 0)
    bank_value = result.get("bank", 0)
    non_cosmetic = result.get("nonCosmeticNetworth", 0)
    if purse > 0:
        extras.append(f"Purse: {format_number(purse)}")
    if bank_value > 0:
        extras.append(f"Bank: {format_number(bank_value)}")
    if non_cosmetic > 0:
        extras.append(f"Non-Cosmetic: {format_number(non_cosmetic)}")
    if inventory_api_off:
        extras.append("Inv API disabled")
    if extras:
        response += f" | {', '.join(extras)}"

    categories = result.get("categories", {})
    top_categories = sorted(
        ((name, value) for name, value in categories.items() if isinstance(value, int | float) and value > 0),
        key=lambda item: item[1],
        reverse=True,
    )[:3]
    if top_categories:
        response += (
            f" | Top: {', '.join(f'{name}: {format_number(value)}' for name, value in top_categories)}"
        )

    await cc.reply(response)


@command("auctions", aliases=("ah",), usage="<ign>")
async def auctions(cc: CommandContext) -> None:
    ign_arg = cc.raw_args.split()[0] if cc.raw_args else None
    target_ign = cc.services.profiles.resolve_ign(ign_arg, cc.author_name)

    uuid = await cc.services.mojang.get_uuid(target_ign)
    if not uuid:
        raise UserError(f"Could not find Minecraft account for '{target_ign}'.")

    all_auctions = await cc.services.hypixel.get_player_auctions(uuid)
    if all_auctions is None:
        raise UserError("Failed to fetch auction data (API error).")
    if not all_auctions:
        raise UserError(f"'{target_ign}' has no active auctions.")

    two_weeks_ago = time.time() - TWO_WEEKS_SECONDS
    recent = [
        auction
        for auction in all_auctions
        if not auction.get("claimed", False)
        and (not auction.get("start") or auction["start"] / 1000 >= two_weeks_ago)
    ]
    if not recent:
        raise UserError(f"'{target_ign}' has no active auctions less than 2 weeks old.")

    total_unique_items = len({auction.get("item_name", "Unknown Item") for auction in recent})

    message_prefix = f"{target_ign}'s Auctions: "
    shown: list[str] = []
    current_length = len(message_prefix)
    for auction in recent:
        item_name = auction.get("item_name", "Unknown Item").replace("§.", "")
        highest_bid = auction.get("highest_bid_amount", 0) or auction.get("starting_bid", 0)
        auction_str = f"{item_name} {format_price(highest_bid)}"
        separator_length = 3 if shown else 0
        if current_length + separator_length + len(auction_str) > MAX_MESSAGE_LENGTH:
            break
        shown.append(auction_str)
        current_length += separator_length + len(auction_str)

    if not shown:
        raise UserError(f"Could not format any auctions for '{target_ign}' within the character limit.")

    message = message_prefix + " | ".join(shown)
    hidden_items = total_unique_items - len(shown)
    if hidden_items > 0 and len(message) + len(f" (+{hidden_items} more)") <= MAX_MESSAGE_LENGTH:
        message += f" (+{hidden_items} more)"
    await cc.reply(message)
