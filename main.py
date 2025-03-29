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
        # Read comma-separated channels instead of a single channel
        'twitch_channels_str': os.getenv('TWITCH_CHANNELS'), 
        'prefix': '#', # Setzt das Prefix fest
        'hypixel_api_key': os.getenv('HYPIXEL_API_KEY') 
    }

    if not config['token'] or not config['token'].startswith('oauth:'):
        print("Fehler: TWITCH_OAUTH_TOKEN fehlt, ist ungültig oder beginnt nicht mit 'oauth:' in deiner .env Datei.")
        print("Du kannst einen Token hier generieren: https://twitchapps.com/tmi/")
        return None

    if not config['nickname']:
        print("Fehler: TWITCH_NICKNAME fehlt in deiner .env Datei.")
        return None

    # Validate and process the list of channels
    if not config['twitch_channels_str']:
        print("Fehler: TWITCH_CHANNELS fehlt in deiner .env Datei.")
        return None
    
    # Split the string into a list, remove whitespace, and convert to lowercase
    initial_channels = [ch.strip().lower() for ch in config['twitch_channels_str'].split(',') if ch.strip()]
    if not initial_channels:
        print("Fehler: TWITCH_CHANNELS enthält keine gültigen Kanalnamen.")
        return None
    config['initial_channels'] = initial_channels # Store the list
    del config['twitch_channels_str'] # Remove the original string

    if not config['hypixel_api_key']:  
        print("Fehler: HYPIXEL_API_KEY fehlt in deiner .env Datei.")
        print("Du kannst einen Schlüssel hier beantragen: https://developer.hypixel.net/")
        print("Warnung: Bot startet ohne Hypixel API Funktionalität.")  

    # Ensure nickname is lowercase
    config['nickname'] = config['nickname'].lower()

    return config

# --- Hauptausführung ---
if __name__ == "__main__":
    config = load_config()

    if config:
        print(f"Konfiguration geladen. Bot wird versuchen, Kanälen beizutreten: {config['initial_channels']}")
        print("Starte Bot...")
        # Pass the list of channels to the Bot constructor
        bot = Bot(
            token=config['token'],
            prefix=config['prefix'],
            nickname=config['nickname'],
            initial_channels=config['initial_channels'], # Changed from initial_channel
            hypixel_api_key=config['hypixel_api_key'] 
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