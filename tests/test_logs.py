import logging

from aiohttp import ClientConnectionResetError

from bot.logs import JoinChannelResetFilter

JOIN_MESSAGE = (
    "Task exception was never retrieved\n"
    "future: <Task finished coro=<WSConnection._join_channel() done> "
    "exception=ClientConnectionResetError('Cannot write to closing transport')>"
)


def _record(message: str, exception: BaseException) -> logging.LogRecord:
    return logging.LogRecord(
        name="asyncio",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=(type(exception), exception, None),
    )


def test_join_channel_reset_is_dropped() -> None:
    record = _record(JOIN_MESSAGE, ClientConnectionResetError("Cannot write to closing transport"))
    assert JoinChannelResetFilter().filter(record) is False


def test_reset_from_other_coro_is_kept() -> None:
    message = JOIN_MESSAGE.replace("_join_channel", "_send_privmsg")
    record = _record(message, ClientConnectionResetError("Cannot write to closing transport"))
    assert JoinChannelResetFilter().filter(record) is True


def test_other_exception_in_join_channel_is_kept() -> None:
    record = _record(JOIN_MESSAGE, RuntimeError("boom"))
    assert JoinChannelResetFilter().filter(record) is True
