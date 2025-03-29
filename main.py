# main.py
import os
import asyncio
from dotenv import load_dotenv
from twitch import Bot # Importiert die Bot-Klasse aus twitch.py

# --- Konfiguration laden ---
def load_config():
    """Lädt Konfiguration aus der .env Datei und validiert sie."""
    load_dotenv()
    config = {
        'token': os.getenv('TWITCH_OAUTH_TOKEN'),
        'nickname': os.getenv('TWITCH_NICKNAME'),
        'target_channel': os.getenv('TARGET_CHANNEL'),
        'prefix': '#', # Setzt das Prefix fest
        'hypixel_api_key': os.getenv('HYPIXEL_API_KEY') # NEU
    }

    if not config['token'] or not config['token'].startswith('oauth:'):
        print("Fehler: TWITCH_OAUTH_TOKEN fehlt, ist ungültig oder beginnt nicht mit 'oauth:' in deiner .env Datei.")
        print("Du kannst einen Token hier generieren: https://twitchapps.com/tmi/")
        return None

    if not config['nickname']:
        print("Fehler: TWITCH_NICKNAME fehlt in deiner .env Datei.")
        return None

    if not config['target_channel']:
        print("Fehler: TARGET_CHANNEL fehlt in deiner .env Datei.")
        return None

    if not config['hypixel_api_key']:  # NEU: Validierung für Hypixel Key
        print("Fehler: HYPIXEL_API_KEY fehlt in deiner .env Datei.")
        print("Du kannst einen Schlüssel hier beantragen: https://developer.hypixel.net/")
        # Optional: Entscheide, ob der Bot ohne Key starten soll oder nicht
        # return None # Bot nicht starten
        print("Warnung: Bot startet ohne Hypixel API Funktionalität.")  # Bot starten, aber Befehle fehlschlagen lassen

    # Stelle sicher, dass der Nickname klein geschrieben ist (wichtig für twitchio)
    config['nickname'] = config['nickname'].lower()
    # Stelle sicher, dass der Channelname klein geschrieben ist
    config['target_channel'] = config['target_channel'].lower()

    return config

# --- Hauptausführung ---
if __name__ == "__main__":
    config = load_config()

    if config:
        print("Konfiguration geladen. Starte Bot...")
        # Übergebe den API Key an den Bot Konstruktor
        bot = Bot(
            token=config['token'],
            prefix=config['prefix'],
            nickname=config['nickname'],
            initial_channel=config['target_channel'],
            hypixel_api_key=config['hypixel_api_key'] # NEU
        )
        try:
            bot.run()
        except Exception as e:
            print(f"Ein Fehler ist beim Starten oder während des Betriebs des Bots aufgetreten: {e}")
            if "Authentication failed" in str(e):
                 print("-> Überprüfe dein TWITCH_OAUTH_TOKEN in der .env Datei.")
    else:
        print("Bot konnte aufgrund fehlender oder fehlerhafter Konfiguration nicht gestartet werden.")
        exit(1)