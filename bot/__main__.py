import logging

from bot.config import load_settings
from bot.logs import setup_logging
from bot.twitch.bot import SkyBot


def main() -> None:
    settings = load_settings()
    setup_logging(settings.log_level)
    logger = logging.getLogger("bot")
    logger.info("starting bot for channels: %s", list(settings.initial_channels))
    SkyBot(settings).run()


if __name__ == "__main__":
    main()
