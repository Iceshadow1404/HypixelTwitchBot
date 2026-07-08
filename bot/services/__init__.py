from dataclasses import dataclass

import aiohttp

from bot.config import Settings
from bot.gamedata import load_area_names
from bot.hypixel.client import HypixelClient
from bot.hypixel.leveling import LevelingData, load_leveling_data
from bot.hypixel.mojang import MojangClient
from bot.hypixel.profiles import ProfileService
from bot.services.links import LinkStore
from bot.services.networth import NetworthClient


@dataclass(frozen=True)
class Services:
    settings: Settings
    session: aiohttp.ClientSession
    mojang: MojangClient
    hypixel: HypixelClient
    profiles: ProfileService
    links: LinkStore
    networth: NetworthClient
    leveling: LevelingData
    area_names: dict[str, str]


def build_services(settings: Settings, session: aiohttp.ClientSession) -> Services:
    mojang = MojangClient(session)
    hypixel = HypixelClient(settings.hypixel_api_key, session)
    links = LinkStore(settings.data_dir)
    return Services(
        settings=settings,
        session=session,
        mojang=mojang,
        hypixel=hypixel,
        profiles=ProfileService(mojang, hypixel, links),
        links=links,
        networth=NetworthClient(settings.node_service_url, session),
        leveling=load_leveling_data(settings.data_dir),
        area_names=load_area_names(settings.data_dir),
    )
