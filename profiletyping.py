from typing import TypedDict, Optional


class Profile(TypedDict):
    cute_name: str
    selected: bool
    game_mode: str
    profile_id: str
    members: dict[str, 'ProfileMember']

class ProfileMember(TypedDict):
    player_data: Optional['PlayerData']

class PlayerData(TypedDict):
    experience: Optional[dict[str, float]]
