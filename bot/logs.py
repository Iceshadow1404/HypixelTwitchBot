import logging


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # twitchio logs every raw IRC line on DEBUG; keep it at INFO
    logging.getLogger("twitchio").setLevel(logging.INFO)
