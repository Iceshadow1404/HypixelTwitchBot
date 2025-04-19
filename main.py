# main.py
import os
import asyncio
from dotenv import load_dotenv
from twitch import Bot # Import the Bot class from twitch.py

# --- Load Configuration ---
def load_config():
    """Loads configuration from the .env file and validates it."""
    load_dotenv()
    config = {
        'token': os.getenv('TWITCH_OAUTH_TOKEN'),
        'nickname': os.getenv('TWITCH_NICKNAME'),
        # Read comma-separated channels instead of a single channel
        'twitch_channels_str': os.getenv('TWITCH_CHANNELS'), 
        'prefix': '#', # Set the command prefix
        'hypixel_api_key': os.getenv('HYPIXEL_API_KEY') 
    }

    if not config['token'] or not config['token'].startswith('oauth:'):
        print("Error: TWITCH_OAUTH_TOKEN is missing, invalid, or does not start with 'oauth:' in your .env file.")
        print("You can generate a token here: https://twitchapps.com/tmi/")
        return None

    if not config['nickname']:
        print("Error: TWITCH_NICKNAME is missing in your .env file.")
        return None

    # Validate and process the list of channels
    if not config['twitch_channels_str']:
        print("Error: TWITCH_CHANNELS is missing in your .env file.")
        return None
    
    # Split the string into a list, remove whitespace, and convert to lowercase
    initial_channels = [ch.strip().lower() for ch in config['twitch_channels_str'].split(',') if ch.strip()]
    if not initial_channels:
        print("Error: TWITCH_CHANNELS contains no valid channel names.")
        return None
    config['initial_channels'] = initial_channels # Store the list
    del config['twitch_channels_str'] # Remove the original string

    if not config['hypixel_api_key']:  
        print("Error: HYPIXEL_API_KEY is missing in your .env file.")
        print("You can request a key here: https://developer.hypixel.net/")
        print("Warning: Bot starting without Hypixel API functionality.")
        print()

    # Ensure nickname is lowercase
    config['nickname'] = config['nickname'].lower()

    return config

# --- Main Execution ---
if __name__ == "__main__":
    config = load_config()

    if config:
        print(f"Configuration loaded. Bot will attempt to join channels: {config['initial_channels']}")
        print("Starting Bot...")
        # Pass the list of channels to the Bot constructor
        bot = Bot(
            token=config['token'],
            prefix=config['prefix'],
            nickname=config['nickname'],
            initial_channels=config['initial_channels'],
            hypixel_api_key=config['hypixel_api_key'] 
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