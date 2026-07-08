import logging

from bot.commands.base import CommandContext, command
from bot.errors import UserError

logger = logging.getLogger(__name__)


@command("link", usage="<minecraft_ign>")
async def link(cc: CommandContext) -> None:
    links = cc.services.links
    if not cc.raw_args:
        current = links.get(cc.author_name)
        if current:
            raise UserError(f"You are currently linked to Minecraft IGN: {current}")
        raise UserError(f"You are not currently linked to any Minecraft IGN. Use {cc.usage} to set your IGN.")

    minecraft_ign = cc.raw_args.strip()
    if not await cc.services.mojang.get_uuid(minecraft_ign):
        raise UserError(f"'{minecraft_ign}' does not appear to be a valid Minecraft username.")

    if links.set(cc.author_name, minecraft_ign):
        await cc.reply(f"Successfully linked to Minecraft IGN: {minecraft_ign}")
    else:
        raise UserError("Failed to save your link. Please try again later.")


@command("unlink")
async def unlink(cc: CommandContext) -> None:
    if cc.services.links.get(cc.author_name) is None:
        raise UserError("You are not currently linked to any Minecraft IGN.")
    previous = cc.services.links.remove(cc.author_name)
    if previous is None:
        raise UserError("Failed to remove your link. Please try again later.")
    await cc.reply(f"Successfully unlinked from Minecraft IGN: {previous}")


@command("guild", aliases=("g", "guildof"), usage="<ign>")
async def guild(cc: CommandContext) -> None:
    ign_arg, _ = cc.parse_ign_profile()
    target_ign = cc.services.profiles.resolve_ign(ign_arg, cc.author_name)

    uuid = await cc.services.mojang.get_uuid(target_ign)
    if not uuid:
        raise UserError(f"Could not find a Minecraft account for '{target_ign}'. Please check the name.")

    response = await cc.services.hypixel.get_guild_by_player(uuid)
    if response is None:
        raise UserError(
            f"Could not fetch guild information for '{target_ign}'. An API or network error occurred."
        )
    guild_data = response.get("guild")
    if guild_data is None:
        raise UserError(f"'{target_ign}' is not currently in a Hypixel guild.")
    await cc.reply(f"'{target_ign}' is in the guild: {guild_data.get('name', 'Unknown Guild Name')}")


@command("whatdoing", aliases=("wd",), usage="[username]")
async def whatdoing(cc: CommandContext) -> None:
    ign_arg = cc.raw_args.split()[0] if cc.raw_args else None
    target_ign = cc.services.profiles.resolve_ign(ign_arg, cc.author_name)

    uuid = await cc.services.mojang.get_uuid(target_ign)
    if not uuid:
        raise UserError(
            f"Could not find a Minecraft account for '{target_ign}'. "
            f"You can use #link <IGN> to link your Twitch account."
        )

    status = await cc.services.hypixel.get_player_status(uuid)
    if status is None:
        raise UserError(f"Could not retrieve status for {target_ign}.")

    session_data = status.get("session")
    if not session_data or not session_data.get("online"):
        raise UserError(f"{target_ign} is currently offline or not on Hypixel.")

    game_type = session_data.get("gameType", "Unknown")
    mode = session_data.get("mode", "Unknown")
    readable_island = cc.services.area_names.get(mode, mode)
    await cc.reply(f"{target_ign} is currently playing {game_type}, ({readable_island}).")
