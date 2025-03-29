# twitch_auth.py
import os
from dotenv import load_dotenv

def load_twitch_config():
    """Lädt Twitch-spezifische Konfiguration aus der .env Datei und validiert sie."""
    load_dotenv() # Ensure .env is loaded
    config = {
        'token': os.getenv('TWITCH_OAUTH_TOKEN'),
        'nickname': os.getenv('TWITCH_NICKNAME'),
        'target_channel': os.getenv('TARGET_CHANNEL'),
        'prefix': '#', # Setzt das Prefix fest
    }

    valid = True
    if not config['token'] or not config['token'].startswith('oauth:'):
        print("Fehler: TWITCH_OAUTH_TOKEN fehlt, ist ungültig oder beginnt nicht mit 'oauth:' in deiner .env Datei.")
        print("Du kannst einen Token hier generieren: https://twitchapps.com/tmi/")
        valid = False

    if not config['nickname']:
        print("Fehler: TWITCH_NICKNAME fehlt in deiner .env Datei.")
        valid = False
    else:
        # Stelle sicher, dass der Nickname klein geschrieben ist (wichtig für twitchio)
        config['nickname'] = config['nickname'].lower()


    if not config['target_channel']:
        print("Fehler: TARGET_CHANNEL fehlt in deiner .env Datei.")
        valid = False
    else:
         # Stelle sicher, dass der Channelname klein geschrieben ist
        config['target_channel'] = config['target_channel'].lower()

    if not valid:
        return None # Return None if config is invalid

    print("Twitch-Konfiguration erfolgreich geladen.")
    return config

def load_hypixel_key():
    """Lädt den Hypixel API Key aus der .env Datei."""
    load_dotenv() # Ensure .env is loaded again or rely on previous load
    api_key = os.getenv('HYPIXEL_API_KEY')
    if not api_key:
        print("Fehler: HYPIXEL_API_KEY fehlt in deiner .env Datei.")
        print("Du kannst einen Schlüssel hier beantragen: https://developer.hypixel.net/")
        print("Warnung: Bot startet ohne Hypixel API Funktionalität.")
        return None
    print("Hypixel API Key geladen.")
    return api_key