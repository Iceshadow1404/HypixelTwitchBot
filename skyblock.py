# skyblock.py
import aiohttp
import json
import traceback
from typing import Optional, Dict, List, Any

# --- Konstanten ---
MOJANG_API_URL = "https://api.mojang.com/users/profiles/minecraft/{username}"
HYPIXEL_API_URL = "https://api.hypixel.net/v2/skyblock/profiles"
AVERAGE_SKILLS_LIST = [
    'farming', 'mining', 'combat', 'foraging', 'fishing',
    'enchanting', 'alchemy', 'taming', 'carpentry'
]

class SkyblockClient:
    """Handles interactions with Mojang and Hypixel APIs for SkyBlock data."""

    def __init__(self, api_key: Optional[str], session: aiohttp.ClientSession):
        self.api_key = api_key
        self.session = session
        if not api_key:
            print("[SkyblockClient] Warnung: Initialisiert ohne Hypixel API Key.")
        else:
            print("[SkyblockClient] Initialisiert mit Hypixel API Key.")

    async def get_uuid_from_ign(self, username: str) -> Optional[str]:
        """Fetches the Minecraft UUID for a given In-Game Name using Mojang API."""
        if not self.session or self.session.closed:
            print("[SkyblockClient][API] Fehler: aiohttp Session nicht verfügbar für Mojang API Anfrage.")
            return None
        url = MOJANG_API_URL.format(username=username)
        print(f"[SkyblockClient][API] Mojang Anfrage für '{username}' an: {url}")
        try:
            async with self.session.get(url) as response:
                print(f"[SkyblockClient][API] Mojang Antwort für '{username}': Status {response.status}")
                if response.status == 200:
                    data = await response.json()
                    # print(f"[SkyblockClient][API] Mojang Antwort JSON: {data}") # Optional: Debugging
                    uuid = data.get('id')
                    if not uuid:
                         print(f"[SkyblockClient][API] Mojang Antwort JSON enthält keine 'id' für '{username}'.")
                    return uuid
                elif response.status == 204:
                     print(f"[SkyblockClient][API] Mojang API: Benutzer '{username}' nicht gefunden (Status 204).")
                     return None
                else:
                    error_text = await response.text()
                    print(f"[SkyblockClient][API] Fehler bei Mojang API Anfrage für '{username}': Status {response.status}, Body: {error_text}")
                    return None
        except aiohttp.ClientError as e:
            print(f"[SkyblockClient][API][Error] Netzwerkfehler bei Mojang API Anfrage für '{username}': {e}")
            return None
        except Exception as e:
            print(f"[SkyblockClient][API][Error] Unerwarteter Fehler bei Mojang API Anfrage für '{username}': {e}")
            traceback.print_exc()
            return None

    async def get_skyblock_data(self, uuid: str) -> Optional[List[Dict[str, Any]]]:
        """Fetches SkyBlock profile data for a given UUID using Hypixel API."""
        if not self.api_key:
            print("[SkyblockClient][API] Fehler: Hypixel API Key nicht konfiguriert.")
            return None
        if not self.session or self.session.closed:
            print("[SkyblockClient][API] Fehler: aiohttp Session nicht verfügbar für Hypixel API Anfrage.")
            return None

        params = {"key": self.api_key, "uuid": uuid}
        print(f"[SkyblockClient][API] Hypixel Anfrage für UUID '{uuid}' an: {HYPIXEL_API_URL} mit Parametern: key=HIDDEN, uuid={uuid}")
        try:
            async with (self.session.get(HYPIXEL_API_URL, params=params) as response):
                print(f"[SkyblockClient][API] Hypixel Antwort für UUID '{uuid}': Status {response.status}")
                response_text = await response.text() # Read text first for better error logging
                if response.status == 200:
                    try:
                        data = json.loads(response_text)
                        with open("data.json", 'w') as f:
                            json.dump(data, f, indent=4)
                        # print(f"[SkyblockClient][API] Hypixel Antwort JSON (UUID: {uuid}): {json.dumps(data, indent=2)}") # Optional: Debugging
                        if data.get("success"):
                            profiles = data.get('profiles')
                            if profiles is None:
                                 print(f"[SkyblockClient][API] Hypixel API Erfolg, aber 'profiles' Feld fehlt oder ist null für UUID '{uuid}'.")
                                 return None # Explicitly return None if profiles key is missing or null
                            if not isinstance(profiles, list):
                                print(f"[SkyblockClient][API] Hypixel API Erfolg, aber 'profiles' ist keine Liste für UUID '{uuid}'. Typ: {type(profiles)}")
                                return None # API contract violation
                            return profiles
                        else:
                            reason = data.get('cause', 'Unbekannter Grund')
                            print(f"[SkyblockClient][API] Hypixel API Fehler für UUID '{uuid}': Success=False, Grund: {reason}")
                            return None
                    except json.JSONDecodeError as json_e:
                        print(f"[SkyblockClient][API][Error] Fehler beim Parsen der Hypixel JSON Antwort für UUID '{uuid}': {json_e}")
                        print(f"[SkyblockClient][API] Hypixel Rohantwort-Text (erste 500 Zeichen): {response_text[:500]}")
                        return None
                else:
                    print(f"[SkyblockClient][API] Fehler bei Hypixel API Anfrage für UUID '{uuid}': Status {response.status}, Body (erste 500 Zeichen): {response_text[:500]}")
                    return None
        except aiohttp.ClientError as e:
            print(f"[SkyblockClient][API][Error] Netzwerkfehler bei Hypixel API Anfrage für UUID '{uuid}': {e}")
            return None
        except Exception as e:
            print(f"[SkyblockClient][API][Error] Unerwarteter Fehler bei Hypixel API Anfrage für UUID '{uuid}': {e}")
            traceback.print_exc()
            return None

    def calculate_average_skill_level(self, profile: Dict[str, Any], player_uuid: str) -> Optional[float]:
        """Calculates the estimated average skill level for a player in a specific profile."""
        profile_id = profile.get('profile_id', 'UNKNOWN_PROFILE_ID')
        print(f"[SkyblockClient][Calc] Berechne Skill Average für UUID {player_uuid} im Profil {profile_id}")
        if not profile or player_uuid not in profile.get('members', {}):
            print(f"[SkyblockClient][Calc] Profil ungültig oder Spieler {player_uuid} nicht Mitglied im Profil {profile_id}.")
            return None

        member_data = profile['members'][player_uuid]
        # print(f"[SkyblockClient][Calc] Member Data für {player_uuid} (Auszug): { {k: v for k, v in member_data.items() if 'experience_skill' in k or 'level' in k} }") # Optional Debugging

        total_level_estimate = 0
        skills_counted = 0

        for skill_name in AVERAGE_SKILLS_LIST:
            xp_field = f'experience_skill_{skill_name}'
            skill_xp = member_data.get(xp_field)

            # Hypixel doesn't always include the field if XP is 0
            if skill_xp is not None and skill_xp > 0:
                # print(f"[SkyblockClient][Calc] Skill '{skill_name}': XP = {skill_xp}") # Optional Debugging
                # Basic approximation - real formula is more complex (uses level caps, specific XP tables)
                # This is just a rough estimate based on common community approximations
                # Note: This formula is VERY rough and inaccurate for higher levels.
                # A better approach uses XP tables, but is much more complex.
                level_approx = (skill_xp / 100)**0.5 # Simplistic non-linear scaling estimate
                # print(f"[SkyblockClient][Calc] Skill '{skill_name}': Geschätztes Level = {level_approx:.2f}") # Optional Debugging
                total_level_estimate += level_approx
                skills_counted += 1
            else:
                # Treat missing skill or 0 XP skill as level 0 for average calculation
                # print(f"[SkyblockClient][Calc] Skill '{skill_name}': Kein XP Feld ('{xp_field}') oder XP <= 0. Level = 0") # Optional Debugging
                total_level_estimate += 0
                skills_counted += 1 # Count it as a skill to average over

        if skills_counted > 0:
            average = total_level_estimate / skills_counted
            print(f"[SkyblockClient][Calc] Berechnung abgeschlossen: Total Level Estimate={total_level_estimate:.2f}, Skills Counted={skills_counted}, Average={average:.2f}")
            return average
        else:
            print(f"[SkyblockClient][Calc] Berechnung nicht möglich: Keine Skills gezählt.")
            # Return 0.0 if no skills found, consistent with treating missing as 0
            return 0.0

    def find_latest_profile(self, profiles: List[Dict[str, Any]], player_uuid: str) -> Optional[Dict[str, Any]]:
        """Finds the profile with the most recent 'last_save' for the given player."""
        print(f"[SkyblockClient][Profile] Suche aktuellstes Profil für UUID {player_uuid} aus {len(profiles)} Profilen.")
        # profile_summary = [ { 'id': p.get('profile_id'), 'cute_name': p.get('cute_name'), 'game_mode': p.get('game_mode') } for p in profiles]
        # print(f"[SkyblockClient][Profile] Erhaltene Profile (Zusammenfassung): {json.dumps(profile_summary, indent=2)}") # Optional Debugging

        latest_profile = None
        last_save = -1 # Use -1 to ensure any profile with 0 last_save is picked if it's the only one

        if not profiles:
            print("[SkyblockClient][Profile] Keine Profile zum Durchsuchen vorhanden.")
            return None

        for profile in profiles:
            profile_id = profile.get('profile_id', 'UNKNOWN_ID')
            cute_name = profile.get('cute_name', 'UNKNOWN_NAME')
            member_data = profile.get('members', {}).get(player_uuid)

            if member_data:
                profile_last_save = member_data.get('last_save', 0) # Default to 0 if missing
                # print(f"[SkyblockClient][Profile] Prüfe Profil '{cute_name}' (ID: {profile_id}): Last Save = {profile_last_save}") # Optional Debugging
                if profile_last_save > last_save:
                    # print(f"[SkyblockClient][Profile] -> Neuer letzter Speicherpunkt gefunden ({profile_last_save} > {last_save}). Wähle Profil '{cute_name}'.") # Optional Debugging
                    last_save = profile_last_save
                    latest_profile = profile
                # else:
                    # print(f"[SkyblockClient][Profile] -> Nicht aktueller als bisheriges Maximum ({last_save}).") # Optional Debugging
            # else:
                # print(f"[SkyblockClient][Profile] Prüfe Profil '{cute_name}' (ID: {profile_id}): Spieler {player_uuid} ist KEIN Mitglied.") # Optional Debugging

        if latest_profile:
              print(f"[SkyblockClient][Profile] Aktuellstes Profil ausgewählt: '{latest_profile.get('cute_name')}' (ID: {latest_profile.get('profile_id')}) mit last_save {last_save}")
        else:
              print(f"[SkyblockClient][Profile] Kein Profil gefunden, in dem Spieler {player_uuid} Mitglied ist und einen last_save Zeitstempel hat.")

        return latest_profile

    async def get_skill_average(self, ign: str) -> Optional[Dict[str, Any]]:
        """High-level function to get skill average result for an IGN."""
        print(f"[SkyblockClient] Hole Skill Average für IGN: '{ign}'")
        player_uuid = await self.get_uuid_from_ign(ign)
        if not player_uuid:
            return {"success": False, "reason": f"Minecraft-Konto für '{ign}' nicht gefunden."}

        print(f"[SkyblockClient] UUID für '{ign}' gefunden: {player_uuid}. Rufe Profildaten ab...")
        profiles = await self.get_skyblock_data(player_uuid)

        if profiles is None:
             # Specific error logged in get_skyblock_data
             return {"success": False, "reason": f"Fehler beim Abrufen der Hypixel-Daten für '{ign}'."}
        if not profiles: # Empty list means no profiles found
             print(f"[SkyblockClient] Leere Profilliste für UUID {player_uuid} erhalten.")
             return {"success": False, "reason": f"'{ign}' hat anscheinend noch keine SkyBlock-Profile."}

        print(f"[SkyblockClient] {len(profiles)} Profile für '{ign}' gefunden. Suche aktuellstes...")
        latest_profile = self.find_latest_profile(profiles, player_uuid)

        if not latest_profile:
             print(f"[SkyblockClient] Kein aktives Profil für '{ign}' gefunden.")
             return {"success": False, "reason": f"Konnte kein aktives Profil für '{ign}' finden, in dem der Spieler Mitglied ist."}

        profile_name = latest_profile.get('cute_name', 'Unbekannt')
        profile_id_log = latest_profile.get('profile_id', 'N/A')
        print(f"[SkyblockClient] Aktuellstes Profil: '{profile_name}' (ID: {profile_id_log}). Berechne Durchschnitt...")

        average_level = self.calculate_average_skill_level(latest_profile, player_uuid)

        if average_level is not None:
            print(f"[SkyblockClient] Durchschnittliches Level für '{ign}' in '{profile_name}': {average_level:.2f}")
            return {
                "success": True,
                "ign": ign,
                "profile_name": profile_name,
                "average_level": average_level,
                "skill_count": len(AVERAGE_SKILLS_LIST)
            }
        else:
            # Should technically not happen if calculate_average_skill_level returns 0.0 on failure
            print(f"[SkyblockClient][Error] Unerwarteter Fehler bei der Durchschnittsberechnung für '{ign}' in '{profile_name}'.")
            return {"success": False, "reason": f"Konnte Skill-Level für '{ign}' im Profil '{profile_name}' nicht berechnen."}