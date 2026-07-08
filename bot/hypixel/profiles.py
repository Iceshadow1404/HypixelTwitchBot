from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from bot.errors import UserError
from bot.hypixel.client import HypixelClient
from bot.hypixel.mojang import MojangClient

if TYPE_CHECKING:
    # imported lazily to avoid a circular import via bot.services
    from bot.services.links import LinkStore

logger = logging.getLogger(__name__)

Json = dict[str, Any]


@dataclass(frozen=True)
class PlayerProfile:
    ign: str
    uuid: str
    profile: Json
    member: Json

    @property
    def profile_name(self) -> str:
        return self.profile.get("cute_name", "Unknown")

    @property
    def profile_id(self) -> str | None:
        return self.profile.get("profile_id")


def select_profile(profiles: list[Json], player_uuid: str, requested_name: str | None) -> Json | None:
    """Picks the requested profile by cute_name, else the selected/most recent one."""
    if requested_name:
        requested_lower = requested_name.lower()
        for profile in profiles:
            cute_name = profile.get("cute_name")
            if cute_name and cute_name.lower() == requested_lower:
                if player_uuid in profile.get("members", {}):
                    return profile
                logger.warning(
                    "profile %r matches request but player %s is not a member", cute_name, player_uuid
                )
        logger.info("requested profile %r not found, falling back to latest", requested_name)

    for profile in profiles:
        if profile.get("selected", False) and player_uuid in profile.get("members", {}):
            return profile

    latest_profile: Json | None = None
    latest_save = 0
    for profile in profiles:
        member_data = profile.get("members", {}).get(player_uuid)
        if member_data:
            last_save = member_data.get("last_save", 0)
            if last_save > latest_save:
                latest_save = last_save
                latest_profile = profile
    return latest_profile


class ProfileService:
    """Resolves a chat request (ign + optional profile name) to a full player profile."""

    def __init__(self, mojang: MojangClient, hypixel: HypixelClient, links: LinkStore) -> None:
        self._mojang = mojang
        self._hypixel = hypixel
        self._links = links

    def resolve_ign(self, ign_arg: str | None, author_name: str) -> str:
        """The IGN to look up: explicit argument, else the author's linked IGN, else their name."""
        if not ign_arg or not ign_arg.strip() or ign_arg == author_name:
            linked = self._links.get(author_name)
            if linked:
                return linked
            return author_name
        return ign_arg.strip().lstrip("@")

    async def fetch(
        self,
        ign_arg: str | None,
        profile_arg: str | None,
        author_name: str,
        use_cache: bool = True,
    ) -> PlayerProfile:
        target_ign = self.resolve_ign(ign_arg, author_name)

        uuid = await self._mojang.get_uuid(target_ign)
        if not uuid:
            raise UserError(
                f"Could not find Minecraft account for '{target_ign}'. Please check the username. "
                f"You can use #link IGN to link your Twitch account to your Minecraft IGN"
            )

        profiles = await self._hypixel.get_profiles(uuid, use_cache=use_cache)
        if profiles is None:
            raise UserError(f"Could not fetch SkyBlock profiles for '{target_ign}'. An API error occurred.")
        if not profiles:
            raise UserError(f"'{target_ign}' seems to have no SkyBlock profiles yet.")

        profile = select_profile(profiles, uuid, profile_arg)
        if not profile:
            profile_msg = f"the requested profile '{profile_arg}' or" if profile_arg else "an active"
            raise UserError(
                f"Could not find {profile_msg} profile for '{target_ign}'. "
                f"Player must be a member of at least one profile."
            )

        member = profile.get("members", {}).get(uuid, {})
        return PlayerProfile(ign=target_ign, uuid=uuid, profile=profile, member=member)
