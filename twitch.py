# twitch.py
from datetime import datetime
from typing import TypeAlias

from twitchio.ext import commands

import constants
import utils
from commands.kuudra import KuudraCommand
from commands.classaverage import ClassAverageCommand
from commands.mayor import MayorCommand
from commands.bank import BankCommand
from commands.nucleus import NucleusCommand
from commands.hotm import HotmCommand
from commands.essence import EssenceCommand
from commands.powder import PowderCommand
from commands.slayer import SlayerCommand
from commands.rtca import RtcaCommand
from commands.currdungeon import CurrDungeonCommand
from commands.runstillcata import RunsTillCataCommand
from commands_cog import CommandsCog
from commands.link import LinkCommand
from commands.networth import NetworthCommand
from commands.guild import GuildCommand
from commands.whatdoing import WhatdoingCommand
from commands.rtcl import RtclCommand
from commands.hypixelstatus import hypixelStatus
from commands.coinflip import coinflip
from commands.roll import roll
from bot_messaging import MessagingMixin
from bot_profile import ProfileMixin
from bot_streams import StreamMonitorMixin
from bot_events import EventsMixin


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
        self._hypxiel_command = hypixelStatus(self)
        self._coinflip_command = coinflip(self)
        self._roll_command = roll(self)

        # Store initial channels from .env to avoid leaving them
        self._initial_env_channels = [ch.lower() for ch in initial_channels]

        # Initialize bot with only channels from .env first
        super().__init__(token=token, prefix=prefix, nick=nickname, initial_channels=initial_channels)
        print(f"[INFO] Bot initialized, attempting to join initial channels from .env: {initial_channels}")

        # Register Cogs
        self.add_cog(CommandsCog(self))

IceBot: TypeAlias = Bot
