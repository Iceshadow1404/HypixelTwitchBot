import pytest

from bot.hypixel.leveling import LevelingData, load_leveling_data


@pytest.fixture(scope="session")
def leveling() -> LevelingData:
    return load_leveling_data()
