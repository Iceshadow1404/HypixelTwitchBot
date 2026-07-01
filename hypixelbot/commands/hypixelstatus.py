from twitchio.ext import commands
import xml.etree.ElementTree as ET
import re
import requests

class hypixelStatus:
    def __init__(self, bot):
        self.bot = bot

    async def status_command(self, ctx: commands.Context, *, args: str | None = None):
        bot = ctx.bot
        def get_latest_hypixel_status_from_url(url):
            try:
                response = requests.get(url)
                response.raise_for_status()
                rss_content = response.text

                root = ET.fromstring(rss_content)

                items = root.findall('.//item')

                if not items:
                    return None, None

                latest_item = items[0]

                title = latest_item.find('title').text
                description_html = latest_item.find('description').text

                clean_description = re.sub(r'<.*?>', '', description_html).strip()

                return title, clean_description

            except requests.exceptions.RequestException as e:
                print(f"Error fetching URL: {e}")
                return None, None
            except ET.ParseError as e:
                print(f"Error parsing XML: {e}")
                return None, None
            except AttributeError as e:
                print(f"Error accessing element text: {e}")
                return None, None

        rss_feed_url = "https://status.hypixel.net/history.rss"
        latest_title, latest_description = get_latest_hypixel_status_from_url(rss_feed_url)

        if latest_title and latest_description:
            await bot.send_message(ctx, f"Latest Hypixel Status Incident: {latest_title}, {latest_description}")
        else:
            await bot.send_message(ctx, f"Could not retrieve the latest Hypixel status")




