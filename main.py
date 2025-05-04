# main.py
import os
import asyncio
from dotenv import load_dotenv
from twitch import Bot

# --- Load Configuration ---
def load_config():
    """Loads configuration from the .env file and validates it."""
    load_dotenv()
    config = {
        'token': os.getenv('TWITCH_OAUTH_TOKEN'),
        'nickname': os.getenv('TWITCH_NICKNAME'),
        'twitch_channels_str': os.getenv('TWITCH_CHANNELS'),
        'prefix': os.getenv('prefix', '#'),
        'hypixel_api_key': os.getenv('HYPIXEL_API_KEY'),
        'local': os.getenv('LOCAL_MODE', 'false').lower() == 'true'
    }

    # Split the string into a list, remove whitespace, and convert to lowercase
    initial_channels = [ch.strip().lower() for ch in config['twitch_channels_str'].split(',') if ch.strip()]
    if not initial_channels:
        print("Error: TWITCH_CHANNELS contains no valid channel names.")
        return None
    config['initial_channels'] = initial_channels

    # Ensure nickname is lowercase
    config['nickname'] = config['nickname'].lower()

    return config

# --- Main Execution ---
if __name__ == "__main__":
    config = load_config()

    if config:
        print(f"Configuration loaded. Bot will attempt to join channels: {config['initial_channels']}")
        print("Starting Bot...")
        bot = Bot(
            token=config['token'],
            prefix=config['prefix'],
            nickname=config['nickname'],
            initial_channels=config['initial_channels'],
            hypixel_api_key=config['hypixel_api_key'],
            local_mode=config['local']
        )
        try:
            bot.run()
        except Exception as e:
            print(f"An error occurred while starting or running the bot: {e}")
            if "Authentication failed" in str(e):
                 print("-> Check your TWITCH_OAUTH_TOKEN in the .env file.")
    else:
        print("Bot could not be started due to missing or faulty configuration.")
        exit(1)