# twitch.py
from datetime import datetime
from typing import TypeAlias

from twitchio.ext import commands

from hypixelbot import constants
from hypixelbot import utils
from hypixelbot.commands.kuudra import KuudraCommand
from hypixelbot.commands.classaverage import ClassAverageCommand
from hypixelbot.commands.mayor import MayorCommand
from hypixelbot.commands.bank import BankCommand
from hypixelbot.commands.nucleus import NucleusCommand
from hypixelbot.commands.hotm import HotmCommand
from hypixelbot.commands.essence import EssenceCommand
from hypixelbot.commands.powder import PowderCommand
from hypixelbot.commands.slayer import SlayerCommand
from hypixelbot.commands.rtca import RtcaCommand
from hypixelbot.commands.currdungeon import CurrDungeonCommand
from hypixelbot.commands.runstillcata import RunsTillCataCommand
from hypixelbot.commands_cog import CommandsCog
from hypixelbot.commands.link import LinkCommand
from hypixelbot.commands.networth import NetworthCommand
from hypixelbot.commands.guild import GuildCommand
from hypixelbot.commands.whatdoing import WhatdoingCommand
from hypixelbot.commands.rtcl import RtclCommand
from hypixelbot.commands.hypixelstatus import hypixelStatus
from hypixelbot.commands.coinflip import coinflip
from hypixelbot.commands.roll import roll
from hypixelbot.commands.skills import SkillsCommand
from hypixelbot.commands.overflow_skills import OverflowSkillCommand
from hypixelbot.commands.cata import DungeonCommand
from hypixelbot.commands.sblvl import SblvlCommand
from hypixelbot.commands.auction_house import AuctionsCommand
from hypixelbot.commands.secrets import SecretsCommand
from hypixelbot.commands.skill_level import SkillLevelCommand
from hypixelbot.bot_messaging import MessagingMixin
from hypixelbot.bot_profile import ProfileMixin
from hypixelbot.bot_streams import StreamMonitorMixin
from hypixelbot.bot_events import EventsMixin


class Bot(EventsMixin, StreamMonitorMixin, ProfileMixin, MessagingMixin, commands.Bot):
    # Twitch Bot for interacting with Hypixel SkyBlock API and providing commands.

    def __init__(self, token: str, prefix: str, nickname: str, initial_channels: list[str],
                 hypixel_api_key: str | None = None, local_mode: bool = False):
        # Initializes the Bot.
        self.start_time = datetime.now()
        self.hypixel_api_key = hypixel_api_key
        self.leveling_data = utils._load_leveling_data()
        self.constants = constants
        self.local_mode = local_mode

        # Initialize the SkyblockClient for caching
        self.session = None  # Will be initialized in event_ready
        self.skyblock_client = None  # Will be initialized in event_ready

        self.channel_join_attempts = {}
        self.blacklisted_channels = set()

        self._kuudra_command = KuudraCommand(self)
        self._classaverage_command = ClassAverageCommand(self)
        self._mayor_command = MayorCommand(self)
        self._bank_command = BankCommand(self)
        self._nucleus_command = NucleusCommand(self)
        self._hotm_command = HotmCommand(self)
        self._essence_command = EssenceCommand(self)
        self._powder_command = PowderCommand(self)
        self._slayer_command = SlayerCommand(self)
        self._rtca_command = RtcaCommand(self)
        self._currdungeon_command = CurrDungeonCommand(self)
        self._runstillcata_command = RunsTillCataCommand(self)
        self._link_command = LinkCommand(self)
        self._networth_command = NetworthCommand(self)
        self._guild_command = GuildCommand(self)
        self._whatdoing_command = WhatdoingCommand(self)
        self._rtcl_command = RtclCommand(self)
        self._hypixel_command = hypixelStatus(self)
        self._coinflip_command = coinflip(self)
        self._roll_command = roll(self)
        self._skills_command = SkillsCommand(self)
        self._oskill_command = OverflowSkillCommand(self)
        self._dungeon_command = DungeonCommand(self)
        self._sblvl_command = SblvlCommand(self)
        self._auctions_command = AuctionsCommand(self)
        self._secrets_command = SecretsCommand(self)
        self._skilllevel_command = SkillLevelCommand(self)

        # Store initial channels from .env to avoid leaving them
        self._initial_env_channels = [ch.lower() for ch in initial_channels]

        # Initialize bot with only channels from .env first
        super().__init__(token=token, prefix=prefix, nick=nickname, initial_channels=initial_channels)
        print(f"[INFO] Bot initialized, attempting to join initial channels from .env: {initial_channels}")

        # Register Cogs
        self.add_cog(CommandsCog(self))

IceBot: TypeAlias = Bot
