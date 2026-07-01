"""Pin the CONFIG_DIR contract.

The config paths used to be hard-coded absolute (/config/...). They are now
env-driven so local dev uses a relative ./config while production keeps the
mounted /config volume. These tests make sure:
- the default stays relative (local usability), and
- setting CONFIG_DIR=/config reproduces the exact previous production paths,
so the Docker volume mapping can never silently break.
"""
import importlib
import os


def test_config_dir_defaults_to_relative(monkeypatch):
    monkeypatch.delenv("CONFIG_DIR", raising=False)
    import constants
    importlib.reload(constants)
    try:
        assert constants.LINKS_FILE == os.path.join("config", "user_links.json")
        assert constants.DEBUG_LOG == os.path.join("config", "debug_log.txt")
    finally:
        importlib.reload(constants)


def test_config_dir_env_reproduces_docker_paths(monkeypatch):
    monkeypatch.setenv("CONFIG_DIR", "/config")
    import constants
    importlib.reload(constants)
    try:
        # Byte-identical to the previous hard-coded production paths.
        assert constants.LINKS_FILE == "/config/user_links.json"
        assert constants.DEBUG_LOG == "/config/debug_log.txt"
    finally:
        monkeypatch.delenv("CONFIG_DIR", raising=False)
        importlib.reload(constants)
