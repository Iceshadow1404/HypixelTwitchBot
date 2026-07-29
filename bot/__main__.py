import logging
import signal

from bot.config import load_settings
from bot.logs import setup_logging
from bot.twitch.bot import SkyBot


def main() -> None:
    settings = load_settings()
    setup_logging(settings.log_level)
    logger = logging.getLogger("bot")
    logger.info("starting bot for channels: %s", list(settings.initial_channels))
    # twitchio's run() only cleans up on KeyboardInterrupt; docker stop sends SIGTERM, which
    # would kill the process mid-write without ever closing the connection
    signal.signal(signal.SIGTERM, signal.default_int_handler)
    SkyBot(settings).run()


if __name__ == "__main__":
    main()
