import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    token: str
    nickname: str
    initial_channels: tuple[str, ...]
    prefix: str
    hypixel_api_key: str
    twitch_client_id: str | None
    twitch_client_secret: str | None
    local_mode: bool
    log_level: str
    data_dir: Path
    node_service_url: str


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def load_settings() -> Settings:
    load_dotenv()

    channels = tuple(ch.strip().lower() for ch in _require("TWITCH_CHANNELS").split(",") if ch.strip())
    if not channels:
        raise SystemExit("TWITCH_CHANNELS contains no valid channel names.")

    local_mode = os.getenv("LOCAL_MODE", "false").strip().lower() == "true"
    client_id = os.getenv("TWITCH_CLIENT_ID")
    client_secret = os.getenv("TWITCH_CLIENT_SECRET")
    if not local_mode and (not client_id or not client_secret):
        raise SystemExit("TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET are required unless LOCAL_MODE=true.")

    data_dir = Path(os.getenv("DATA_DIR", "./data"))
    data_dir.mkdir(parents=True, exist_ok=True)

    return Settings(
        token=_require("TWITCH_OAUTH_TOKEN"),
        nickname=_require("TWITCH_NICKNAME").lower(),
        initial_channels=channels,
        # legacy deployments use lowercase "prefix"
        prefix=os.getenv("PREFIX") or os.getenv("prefix") or "#",
        hypixel_api_key=_require("HYPIXEL_API_KEY"),
        twitch_client_id=client_id,
        twitch_client_secret=client_secret,
        local_mode=local_mode,
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        data_dir=data_dir,
        node_service_url=os.getenv("NODE_SERVICE_URL", "http://localhost:3000"),
    )
