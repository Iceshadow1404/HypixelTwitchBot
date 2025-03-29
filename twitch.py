# twitch.py
import asyncio
from twitchio.ext import commands
import json
import os
import aiohttp
import traceback
import time
# No longer need SimpleNamespace if using handle_commands
# from types import SimpleNamespace

# --- Konstanten ---
# (Constants remain the same)
CUSTOM_COMMANDS_FILE = 'custom_commands.json'
MOJANG_API_URL = "https://api.mojang.com/users/profiles/minecraft/{username}"
HYPIXEL_API_URL = "https://api.hypixel.net/v2/skyblock/profiles"
AVERAGE_SKILLS_LIST = [
    'farming', 'mining', 'combat', 'foraging', 'fishing',
    'enchanting', 'alchemy', 'taming', 'carpentry'
]

class Bot(commands.Bot):
    # __init__, start/close_http_session, _load_custom_commands, API helpers,
    # calculate_average_skill_level, find_latest_profile
    # remain the same as the previous version with enhanced logging.
    # Add them back here or ensure they are present in your file.

    # --- PASTE PREVIOUS METHODS HERE ---
    def __init__(self, token: str, prefix: str, nickname: str, initial_channel: str, hypixel_api_key: str | None):
        self.target_channel_name = initial_channel.lower()
        self.target_channel_obj = None
        self.hypixel_api_key = hypixel_api_key
        self.http_session = None
        self.leveling_data = self._load_leveling_data()

        super().__init__(
            token=token,
            prefix=prefix,
            nick=nickname,
            initial_channels=[self.target_channel_name]
        )
        print(f"Bot initialisiert für Nick: {nickname}, Channel: #{self.target_channel_name}, Prefix: '{prefix}'")

    async def start_http_session(self):
        if self.http_session is None or self.http_session.closed:
            self.http_session = aiohttp.ClientSession()
            print("aiohttp Session gestartet.")

    async def close_http_session(self):
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()
            print("aiohttp Session geschlossen.")
            self.http_session = None

    def _load_custom_commands(self):
        if not os.path.exists(CUSTOM_COMMANDS_FILE):
             print(f"Warnung: Datei für benutzerdefinierte Befehle '{CUSTOM_COMMANDS_FILE}' nicht gefunden. Erstelle eine leere Datei.")
             try:
                 with open(CUSTOM_COMMANDS_FILE, 'w', encoding='utf-8') as f:
                     json.dump({}, f)
             except IOError as e:
                 print(f"Fehler beim Erstellen der Datei '{CUSTOM_COMMANDS_FILE}': {e}")
             return

        try:
            with open(CUSTOM_COMMANDS_FILE, 'r', encoding='utf-8') as f:
                loaded_commands = json.load(f)
                self.custom_commands = {k.lower(): v for k, v in loaded_commands.items()}
                print(f"{len(self.custom_commands)} benutzerdefinierte Befehle aus '{CUSTOM_COMMANDS_FILE}' geladen.")
        except json.JSONDecodeError as e:
            print(f"Fehler beim Parsen der JSON-Datei '{CUSTOM_COMMANDS_FILE}': {e}")
            print("Bitte überprüfe die Syntax der Datei. Benutzerdefinierte Befehle werden nicht geladen.")
        except IOError as e:
            print(f"Fehler beim Lesen der Datei '{CUSTOM_COMMANDS_FILE}': {e}")
            return

    def _load_leveling_data(self) -> dict:
        """Lädt die Leveling-Daten aus der leveling.json Datei."""
        try:
            with open('leveling.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {
                    'xp_table': data.get('leveling_xp', []),
                    'level_caps': data.get('leveling_caps', {})
                }
        except Exception as e:
            print(f"[Log][Error] Fehler beim Laden der leveling.json: {e}")
            return {'xp_table': [], 'level_caps': {}}

    def calculate_skill_level(self, xp: float, skill_name: str, member_data: dict | None = None) -> float:
        """Berechnet das Level eines Skills basierend auf der XP und den Leveling-Daten."""
        if not self.leveling_data['xp_table']:
            return 0.0
            
        max_level = self.leveling_data['level_caps'].get(skill_name, 50)
        xp_table = self.leveling_data['xp_table']
        
        # Berechne die Gesamt-XP für das maximale Level
        total_xp = sum(xp_table)
        
        # Wenn die XP höher als die maximale XP in der Tabelle ist, return max_level
        if xp >= total_xp:
            # Spezielle Behandlung für Taming basierend auf Pet-Sacrifices
            if skill_name == 'taming' and member_data:
                pets_data = member_data.get('pets_data', {})
                pet_care = pets_data.get('pet_care', {})
                sacrificed_pets = pet_care.get('pet_types_sacrificed', [])
                
                # Berechne das maximale Level basierend auf den Pet-Sacrifices (0-10)
                # Jedes Level zwischen 50 und 60 ist möglich
                if len(sacrificed_pets) >= 10:
                    max_level = 60
                elif len(sacrificed_pets) >= 1:
                    # Für 1-9 Pets: Level 50 + Anzahl der Pets
                    max_level = 50 + len(sacrificed_pets)
                else:
                    max_level = 50
            # Spezielle Behandlung für Farming basierend auf Jacobs Contest Perks
            elif skill_name == 'farming' and member_data:
                jacobs_contest = member_data.get('jacobs_contest', {})
                perks = jacobs_contest.get('perks', {})
                farming_level_cap = perks.get('farming_level_cap', 0)  # Standard ist 0, da es ein Bonus ist
                max_level = 50 + farming_level_cap  # Basis-Level 50 + Bonus
                    
            return max_level
            
        # Finde das Level basierend auf der XP
        total_xp_required = 0
        level = 0
        
        for required_xp in xp_table:
            total_xp_required += required_xp
            if xp >= total_xp_required:
                level += 1
            else:
                break
                
        # Spezielle Behandlung für Taming basierend auf Pet-Sacrifices
        if skill_name == 'taming' and member_data:
            pets_data = member_data.get('pets_data', {})
            pet_care = pets_data.get('pet_care', {})
            sacrificed_pets = pet_care.get('pet_types_sacrificed', [])
            
            # Berechne das maximale Level basierend auf den Pet-Sacrifices (0-10)
            if len(sacrificed_pets) >= 10:
                max_level = 60
            elif len(sacrificed_pets) >= 1:
                # Für 1-9 Pets: Level 50 + Anzahl der Pets
                max_level = 50 + len(sacrificed_pets)
            else:
                max_level = 50
        # Spezielle Behandlung für Farming basierend auf Jacobs Contest Perks
        elif skill_name == 'farming' and member_data:
            jacobs_contest = member_data.get('jacobs_contest', {})
            perks = jacobs_contest.get('perks', {})
            farming_level_cap = perks.get('farming_level_cap', 0)  # Standard ist 0, da es ein Bonus ist
            max_level = 50 + farming_level_cap  # Basis-Level 50 + Bonus
                
            # Verwende das niedrigere Level zwischen XP-basiertem Level und Farming Level Cap
            level = min(level, max_level)
                
        return level

    def calculate_average_skill_level(self, profile: dict, player_uuid: str) -> float | None:
        profile_id = profile.get('profile_id', 'UNKNOWN_PROFILE_ID')
        print(f"[Log][Calc] Berechne Skill Average für Profil {profile_id}")
        
        if not profile or player_uuid not in profile.get('members', {}):
            print(f"[Log][Calc] Profil ungültig oder Spieler nicht Mitglied im Profil.")
            return None
            
        member_data = profile['members'][player_uuid]
        player_data = member_data.get('player_data', {})
        experience_data = player_data.get('experience', {})
        
        total_level_estimate = 0
        skills_counted = 0
        
        print("\n[Log][Calc] Skill-Level Übersicht:")
        print("-" * 40)
        
        for skill_name in AVERAGE_SKILLS_LIST:
            xp_field = f'SKILL_{skill_name.upper()}'
            skill_xp = experience_data.get(xp_field)
            
            if skill_xp is not None:
                if skill_xp > 0:
                    level = self.calculate_skill_level(skill_xp, skill_name, member_data)
                    total_level_estimate += level
                    skills_counted += 1
                    print(f"{skill_name.capitalize():<10} Level: {level:>3.1f} | XP: {skill_xp:,.0f}")
                else:
                    total_level_estimate += 0
                    skills_counted += 1
                    print(f"{skill_name.capitalize():<10} Level: {0:>3.1f} | XP: 0")
            else:
                total_level_estimate += 0
                skills_counted += 1
                print(f"{skill_name.capitalize():<10} Level: {0:>3.1f} | XP: Nicht verfügbar")
        
        print("-" * 40)
                
        if skills_counted > 0:
            average = total_level_estimate / skills_counted
            print(f"[Log][Calc] Skill Average berechnet: {average:.2f}")
            return average
        else:
            print(f"[Log][Calc] Keine Skills gefunden.")
            return 0.0

    def find_latest_profile(self, profiles: list, player_uuid: str) -> dict | None:
         print(f"[Log][Profile] Suche Profil für UUID {player_uuid} aus {len(profiles)} Profilen.")
         
         if not profiles:
             print("[Log][Profile] Keine Profile zum Durchsuchen vorhanden.")
             return None
             
         # Zuerst nach ausgewähltem Profil suchen
         for profile in profiles:
             profile_id = profile.get('profile_id', 'UNKNOWN_ID')
             cute_name = profile.get('cute_name', 'UNKNOWN_NAME')
             is_selected = profile.get('selected', False)
             member_data = profile.get('members', {}).get(player_uuid)
             
             if member_data and is_selected:
                 print(f"[Log][Profile] Ausgewähltes Profil gefunden: '{cute_name}'")
                 return profile
             elif member_data:
                 print(f"[Log][Profile] Profil '{cute_name}' ist nicht ausgewählt.")
             else:
                 print(f"[Log][Profile] Profil '{cute_name}': Spieler ist kein Mitglied.")
         
         # Wenn kein ausgewähltes Profil gefunden wurde, suche nach dem neuesten Profil
         print("[Log][Profile] Kein ausgewähltes Profil gefunden, suche nach dem neuesten Profil...")
         latest_profile = None
         latest_timestamp = 0
         
         for profile in profiles:
             cute_name = profile.get('cute_name', 'UNKNOWN_NAME')
             member_data = profile.get('members', {}).get(player_uuid)
             
             if member_data:
                 first_join = member_data.get('profile', {}).get('first_join', 0)
                 if first_join > latest_timestamp:
                     latest_timestamp = first_join
                     latest_profile = profile
                     print(f"[Log][Profile] Neueres Profil gefunden: '{cute_name}'")
         
         if latest_profile:
             print(f"[Log][Profile] Neuestes Profil ausgewählt: '{latest_profile.get('cute_name')}'")
             return latest_profile
         
         print(f"[Log][Profile] Kein passendes Profil gefunden.")
         return None

    async def get_uuid_from_ign(self, username: str) -> str | None:
        if not self.http_session or self.http_session.closed:
            print("[Log][API] Fehler: aiohttp Session nicht verfügbar für Mojang API Anfrage.")
            return None
        url = MOJANG_API_URL.format(username=username)
        print(f"[Log][API] Mojang Anfrage für '{username}'...")
        try:
            async with self.http_session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    uuid = data.get('id')
                    if not uuid:
                        print(f"[Log][API] Mojang API: Keine UUID für '{username}' gefunden.")
                    return uuid
                elif response.status == 204:
                    print(f"[Log][API] Mojang API: Benutzer '{username}' nicht gefunden.")
                    return None
                else:
                    print(f"[Log][API] Mojang API Fehler: Status {response.status}")
                    return None
        except aiohttp.ClientError as e:
            print(f"[Log][API] Netzwerkfehler bei Mojang API Anfrage: {e}")
            return None
        except Exception as e:
            print(f"[Log][API] Unerwarteter Fehler bei Mojang API Anfrage: {e}")
            traceback.print_exc()
            return None

    async def get_skyblock_data(self, uuid: str) -> list | None:
        if not self.hypixel_api_key:
            print("[Log][API] Fehler: Hypixel API Key nicht konfiguriert.")
            return None
        if not self.http_session or self.http_session.closed:
            print("[Log][API] Fehler: aiohttp Session nicht verfügbar für Hypixel API Anfrage.")
            return None
        params = {"key": self.hypixel_api_key, "uuid": uuid}
        print(f"[Log][API] Hypixel Anfrage für UUID '{uuid}'...")
        try:
            async with self.http_session.get(HYPIXEL_API_URL, params=params) as response:
                print(f"[Log][API] Hypixel Antwort Status: {response.status}")
                response_text = await response.text()
                if response.status == 200:
                    try:
                        data = json.loads(response_text)
                        # Speichere die komplette Antwort in einer JSON-Datei
                        debug_file = f"hypixel_response_{uuid}.json"
                        with open(debug_file, 'w', encoding='utf-8') as f:
                            json.dump(data, f, indent=4)
                        print(f"[Log][API] Hypixel Antwort wurde in '{debug_file}' gespeichert.")
                        
                        if data.get("success"):
                            profiles = data.get('profiles')
                            if profiles is None:
                                 print(f"[Log][API] Hypixel API Erfolg, aber 'profiles' Feld fehlt oder ist null.")
                                 return None
                            if not isinstance(profiles, list):
                                print(f"[Log][API] Hypixel API Erfolg, aber 'profiles' ist keine Liste.")
                                return None
                            return profiles
                        else:
                            reason = data.get('cause', 'Unbekannter Grund')
                            print(f"[Log][API] Hypixel API Fehler: {reason}")
                            return None
                    except json.JSONDecodeError as json_e:
                        print(f"[Log][API][Error] Fehler beim Parsen der Hypixel JSON Antwort: {json_e}")
                        return None
                else:
                    print(f"[Log][API] Fehler bei Hypixel API Anfrage: Status {response.status}")
                    return None
        except aiohttp.ClientError as e:
            print(f"[Log][API][Error] Netzwerkfehler bei Hypixel API Anfrage: {e}")
            return None
        except Exception as e:
            print(f"[Log][API][Error] Unerwarteter Fehler bei Hypixel API Anfrage: {e}")
            traceback.print_exc()
            return None

    async def get_auctions_data(self, uuid: str) -> list | None:
        """Fetches auction data for a player."""
        if not self.hypixel_api_key:
            print("[Log][API] Error: Hypixel API Key not configured.")
            return None
        if not self.http_session or self.http_session.closed:
            print("[Log][API] Error: aiohttp session not available for Hypixel API request.")
            return None
            
        url = "https://api.hypixel.net/v2/skyblock/auction"
        params = {
            "key": self.hypixel_api_key,
            "player": uuid
        }
        print(f"[Log][API] Hypixel Auctions request for UUID '{uuid}'...")
        
        try:
            async with self.http_session.get(url, params=params) as response:
                print(f"[Log][API] Hypixel response status: {response.status}")
                if response.status == 200:
                    try:
                        data = await response.json()
                        if data.get("success"):
                            return data.get('auctions', [])
                        else:
                            reason = data.get('cause', 'Unknown reason')
                            print(f"[Log][API] Hypixel API Error: {reason}")
                            return None
                    except json.JSONDecodeError as json_e:
                        print(f"[Log][API][Error] Error parsing Hypixel JSON response: {json_e}")
                        return None
                else:
                    print(f"[Log][API] Error in Hypixel API request: Status {response.status}")
                    return None
        except aiohttp.ClientError as e:
            print(f"[Log][API][Error] Network error in Hypixel API request: {e}")
            return None
        except Exception as e:
            print(f"[Log][API][Error] Unexpected error in Hypixel API request: {e}")
            traceback.print_exc()
            return None

    def format_price(self, price: int) -> str:
        """Formatiert einen Preis in eine kürzere Form (z.B. 1.3m statt 1,300,000)."""
        if price >= 1_000_000_000:
            return f"{price/1_000_000_000:.1f}b"
        elif price >= 1_000_000:
            return f"{price/1_000_000:.1f}m"
        elif price >= 1_000:
            return f"{price/1_000:.1f}k"
        else:
            return str(price)

    # --- ENDE PASTE PREVIOUS METHODS ---

    # --- Bot Events ---
    async def event_ready(self):
        """Wird aufgerufen, sobald der Bot erfolgreich mit Twitch verbunden ist."""
        try:
            print("[Log][EventReady] Entering event_ready...")
            await self.start_http_session()
            print("[Log][EventReady] aiohttp session started.")

            print("[Log][EventReady] Printing login info...")
            print(f'------')
            print(f'Login erfolgreich als: {self.nick}')
            print(f'Verbunden mit Channel: #{self.target_channel_name}')
            print(f'User ID: {self.user_id}')
            print(f'------')
            print("[Log][EventReady] Login info printed.")

            print(f"[Log][EventReady] Attempting to get channel object for: #{self.target_channel_name}...")
            self.target_channel_obj = self.get_channel(self.target_channel_name)
            print(f"[Log][EventReady] get_channel call completed. Result: {self.target_channel_obj}")

            if self.target_channel_obj:
                print(f"[Log][EventReady] Channel object found: {self.target_channel_obj.name}")
                print("Bot ist bereit!")
                print("Verfügbare Befehle:")
                print(f"- {self._prefix}ping")
                print(f"- {self._prefix}skills [spielername]")
                print(f"- {self._prefix}reload")
            else:
                print(f"FEHLER: Konnte das Channel-Objekt für #{self.target_channel_name} nicht abrufen nach der Verbindung.")
                print("Mögliche Ursachen: Tippfehler im Channelnamen (.env)?, Bot nicht im Channel?, Twitch-Verzögerung?")
                print("[Log][EventReady] Closing bot due to missing channel object...")
                await self.close()

            print("[Log][EventReady] Exiting event_ready normally.")

        except Exception as e:
            print(f"[Log][EventReady][FATAL ERROR] Exception occurred in event_ready: {e}")
            traceback.print_exc()
            print("[Log][EventReady] Closing bot due to fatal error in event_ready...")
            await self.close()

    async def event_message(self, message):
        """Verarbeitet eingehende Twitch-Nachrichten."""
        if message.echo:
            return  # Ignoriere Echo-Nachrichten (Nachrichten vom Bot selbst)

        # Prüfe, ob die Nachricht von einem echten Twitch-Channel kommt
        if not hasattr(message.channel, 'name') or message.channel.name != self.target_channel_name:
            return  # Ignoriere Nachrichten von anderen Channels

        # Prüfe, ob die Nachricht von einem echten Twitch-User kommt
        if not hasattr(message.author, 'name') or not message.author.name:
            return  # Ignoriere Nachrichten ohne echten Autor

        # Verarbeite Befehle
        await self.handle_commands(message)

    # --- Commands ---
    @commands.command(name='ping')
    async def ping_command(self, ctx: commands.Context):
        """Antwortet auf den Befehl #ping mit pong."""
        print(f"[Log][Cmd] Befehl '{self._prefix}ping' von {ctx.author.name} in #{ctx.channel.name} empfangen.")
        await ctx.send(f'pong, {ctx.author.name}!')

    @commands.command(name='skills')
    async def skills_command(self, ctx: commands.Context, *, ign: str | None = None):
        """Shows the average SkyBlock skill level for a player."""
        if not self.hypixel_api_key:
            await ctx.send("Hypixel API is not configured. Please check the .env file.")
            return

        if not self.http_session or self.http_session.closed:
            await ctx.send("Error connecting to external APIs. Please try again later.")
            return

        target_ign = ign if ign else ctx.author.name
        target_ign = target_ign.lstrip('@')
        await ctx.send(f"Searching SkyBlock Skill Average for '{target_ign}'...")
        
        try:
            player_uuid = await self.get_uuid_from_ign(target_ign)
            if not player_uuid:
                await ctx.send(f"Could not find Minecraft account for '{target_ign}'. Please check the username.")
                return

            profiles = await self.get_skyblock_data(player_uuid)
            if profiles is None:
                await ctx.send(f"Could not fetch SkyBlock profiles for '{target_ign}'. Player might be offline or has no profiles.")
                return
            if not profiles:
                await ctx.send(f"'{target_ign}' seems to have no SkyBlock profiles yet.")
                return

            latest_profile = self.find_latest_profile(profiles, player_uuid)
            if not latest_profile:
                await ctx.send(f"Could not find an active profile for '{target_ign}'. Player must be a member of at least one profile.")
                return

            profile_name = latest_profile.get('cute_name', 'Unknown')
            average_level = self.calculate_average_skill_level(latest_profile, player_uuid)
            if average_level is not None:
                await ctx.send(f"{target_ign}'s Skill Average in profile '{profile_name}' is approximately {average_level:.2f}.")
            else:
                await ctx.send(f"Could not calculate skill level for '{target_ign}' in profile '{profile_name}'. Skill data might be missing.")

        except Exception as e:
            await ctx.send(f"An unexpected error occurred. Please try again later.")

    @commands.command(name='kuudra')
    async def kuudra_command(self, ctx: commands.Context, *, ign: str | None = None):
        """Shows Kuudra completions for different tiers."""
        if not self.hypixel_api_key:
            await ctx.send("Hypixel API is not configured. Please check the .env file.")
            return

        if not self.http_session or self.http_session.closed:
            await ctx.send("Error connecting to external APIs. Please try again later.")
            return

        target_ign = ign if ign else ctx.author.name
        target_ign = target_ign.lstrip('@')
        await ctx.send(f"Searching Kuudra completions for '{target_ign}'...")
        
        try:
            player_uuid = await self.get_uuid_from_ign(target_ign)
            if not player_uuid:
                await ctx.send(f"Could not find Minecraft account for '{target_ign}'. Please check the username.")
                return

            profiles = await self.get_skyblock_data(player_uuid)
            if profiles is None:
                await ctx.send(f"Could not fetch SkyBlock profiles for '{target_ign}'. Player might be offline or has no profiles.")
                return
            if not profiles:
                await ctx.send(f"'{target_ign}' seems to have no SkyBlock profiles yet.")
                return

            latest_profile = self.find_latest_profile(profiles, player_uuid)
            if not latest_profile:
                await ctx.send(f"Could not find an active profile for '{target_ign}'. Player must be a member of at least one profile.")
                return

            profile_name = latest_profile.get('cute_name', 'Unknown')
            member_data = latest_profile.get('members', {}).get(player_uuid, {})
            nether_island_data = member_data.get('nether_island_player_data', {})
            kuudra_completed_tiers = nether_island_data.get('kuudra_completed_tiers', {})
            
            if not kuudra_completed_tiers:
                await ctx.send(f"'{target_ign}' has no Kuudra completions in profile '{profile_name}'.")
                return
                
            # Format output - only the 5 main entries
            main_tiers = ['none', 'hot', 'burning', 'fiery', 'infernal']
            completions = []
            total_score = 0
            
            # Point system for different tiers
            tier_points = {
                'none': 1,
                'hot': 2,
                'burning': 3,
                'fiery': 4,
                'infernal': 5
            }
            
            for tier in main_tiers:
                count = kuudra_completed_tiers.get(tier, 0)
                # Rename 'none' to 'basic'
                tier_name = 'basic' if tier == 'none' else tier
                completions.append(f"{tier_name} {count}")
                # Calculate score for this tier
                total_score += count * tier_points[tier]
                
            await ctx.send(f"{target_ign}'s Kuudra completions in profile '{profile_name}': {', '.join(completions)} | Score: {total_score:,}")

        except Exception as e:
            await ctx.send(f"An unexpected error occurred. Please try again later.")

    @commands.command(name='auctions')
    async def auctions_command(self, ctx: commands.Context, *, ign: str | None = None):
        """Shows active auctions for a player."""
        if not self.hypixel_api_key:
            await ctx.send("Hypixel API is not configured. Please check the .env file.")
            return

        if not self.http_session or self.http_session.closed:
            await ctx.send("Error connecting to external APIs. Please try again later.")
            return

        target_ign = ign if ign else ctx.author.name
        target_ign = target_ign.lstrip('@')
        await ctx.send(f"Searching active auctions for '{target_ign}'...")
        
        try:
            player_uuid = await self.get_uuid_from_ign(target_ign)
            if not player_uuid:
                await ctx.send(f"Could not find Minecraft account for '{target_ign}'. Please check the username.")
                return

            auctions = await self.get_auctions_data(player_uuid)
            if auctions is None:
                await ctx.send(f"Could not fetch auction data for '{target_ign}'. Please try again later.")
                return
                
            if not auctions:
                await ctx.send(f"'{target_ign}' has no active auctions.")
                return
                
            # Count unique items
            unique_items = set()
            for auction in auctions:
                item_name = auction.get('item_name', 'Unknown Item')
                unique_items.add(item_name)
            
            # Format output with 480 character limit
            message = f"{target_ign}'s Auctions: "
            auction_list = []
            shown_items = set()
            
            for auction in auctions:
                item_name = auction.get('item_name', 'Unknown Item')
                highest_bid = auction.get('highest_bid_amount', 0)
                if highest_bid == 0:
                    highest_bid = auction.get('starting_bid', 0)
                
                # Format price
                price_str = self.format_price(highest_bid)
                
                # Create auction string
                auction_str = f"{item_name} {price_str}"
                
                # Check if new string fits in message
                if len(auction_list) > 0:
                    test_message = message + ' | '.join(auction_list + [auction_str])
                else:
                    test_message = message + auction_str
                
                if len(test_message) <= 480:
                    auction_list.append(auction_str)
                    shown_items.add(item_name)
            
            # Add auctions to message
            if auction_list:
                message += ' | '.join(auction_list)
                hidden_items = len(unique_items) - len(shown_items)
                if hidden_items > 0:
                    message += f" (+{hidden_items} Auctions)"
                
                await ctx.send(message)

        except Exception as e:
            await ctx.send(f"An unexpected error occurred. Please try again later.")

    # --- Cleanup ---
    async def close(self):
        print("[Log] Bot wird heruntergefahren...")
        await self.close_http_session()
        await super().close()
        print("[Log] Bot-Verbindung geschlossen.")