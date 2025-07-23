## Twitch Bot for Hypixel Skyblock Streams

The Bot automatically joins all Minecraft Streams with "Hypixel SkyBlock" in Title  

Feel free to contact me on Discord "Iceshadow_" if u have any questions

## Getting Started

Self-Hosting with Docker
The easiest way to run this bot is using Docker.

Create a docker-compose.yml file with the following content:


    services:
        twitchbot:
        container_name: TwitchBot
        network_mode: bridge
        environment:
          # Required Twitch Authentication and Bot Configuration
          - TWITCH_OAUTH_TOKEN=oauth:YOUR_OAUTH_TOKEN_HERE
          - TWITCH_NICKNAME=YOUR_BOT_TWITCH_NAME # The Twitch username of your bot account
          - TWITCH_CHANNELS=channel1,channel2,channel3 # Comma-separated list of channels the bot should always join
        
          # Required Twitch Developer Application Credentials
          - TWITCH_CLIENT_ID=YOUR_TWITCH_CLIENT_ID
          - TWITCH_CLIENT_SECRET=YOUR_TWITCH_CLIENT_SECRET
        
          # Required Hypixel API Key
          - HYPIXEL_API_KEY=YOUR_HYPIXEL_API_KEY # Obtain from Hypixel developer dashboard
        
          # Optional Configuration
          - TZ=Europe/Berlin # Set your desired timezone (e.g., America/New_York)
        
          # Optional: Command Prefix
          # - prefix=# # Uncomment and change if you prefer a different command prefix (default is '#')
        volumes:
          - ./config:/config:rw # Persists configuration files and data
        image: ghcr.io/iceshadow1404/hypixelskyblock:latest