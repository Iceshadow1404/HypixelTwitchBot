import logging
import re
from xml.etree.ElementTree import ParseError

import aiohttp
from defusedxml import ElementTree as ET

from bot.commands.base import CommandContext, command
from bot.constants import HYPIXEL_STATUS_RSS_URL
from bot.errors import UserError

logger = logging.getLogger(__name__)


@command("mayor")
async def mayor(cc: CommandContext) -> None:
    election = await cc.services.hypixel.get_election()
    if election is None:
        raise UserError("API request failed. Could not fetch election data.")
    mayor_data = election.get("mayor")
    if not mayor_data:
        raise UserError("Could not find current mayor data in the API response.")

    mayor_name = mayor_data.get("name", "Unknown")
    perk_names = [p.get("name", "") for p in mayor_data.get("perks", []) if p.get("name")]
    perks_str = " | ".join(perk_names) if perk_names else "No Perks"

    minister_str = ""
    minister_data = mayor_data.get("minister")
    if minister_data:
        minister_name = minister_data.get("name", "Unknown")
        minister_perk = minister_data.get("perk", {}).get("name", "Unknown Perk")
        minister_str = f" | Minister: {minister_name} ({minister_perk})"

    await cc.reply(f"Current Mayor: {len(perk_names)} perk {mayor_name} ({perks_str}){minister_str}")


@command("status")
async def hypixel_status(cc: CommandContext) -> None:
    try:
        async with cc.services.session.get(HYPIXEL_STATUS_RSS_URL) as response:
            response.raise_for_status()
            rss_content = await response.text()
    except aiohttp.ClientError as e:
        logger.warning("failed to fetch Hypixel status RSS: %s", e)
        raise UserError("Could not retrieve the latest Hypixel status") from None

    try:
        root = ET.fromstring(rss_content)
        latest_item = root.find(".//item")
        if latest_item is None:
            raise UserError("Could not retrieve the latest Hypixel status")
        title = latest_item.findtext("title", "").strip()
        description_html = latest_item.findtext("description", "")
        description = re.sub(r"<.*?>", "", description_html).strip()
    except ParseError as e:
        logger.warning("failed to parse Hypixel status RSS: %s", e)
        raise UserError("Could not retrieve the latest Hypixel status") from None

    if not title or not description:
        raise UserError("Could not retrieve the latest Hypixel status")
    await cc.reply(f"Latest Hypixel Status Incident: {title}, {description}")
