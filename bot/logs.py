import logging

from aiohttp import ClientConnectionResetError


class JoinChannelResetFilter(logging.Filter):
    """Drops asyncio's noise about twitchio JOIN tasks that died during a reconnect.

    twitchio fires JOINs as unawaited tasks, so the error cannot be caught at the call site.
    Harmless — the stream monitor rejoins on its next pass. Other connection resets (e.g. a
    failed PRIVMSG) still get logged.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        exception = record.exc_info[1] if record.exc_info else None
        return not (
            isinstance(exception, ClientConnectionResetError) and "_join_channel" in record.getMessage()
        )


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # twitchio logs every raw IRC line on DEBUG; keep it at INFO
    logging.getLogger("twitchio").setLevel(logging.INFO)
    logging.getLogger("asyncio").addFilter(JoinChannelResetFilter())
