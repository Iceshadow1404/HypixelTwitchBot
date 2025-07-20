import typing
import traceback
from twitchio.ext import commands


if typing.TYPE_CHECKING:
    from twitch import IceBot

async def secrets_command(ctx: commands.Context, ign: str | None = None, requested_profile_name: str | None = None):
    bot: IceBot = ctx.bot
    if not ign:
        ign = ctx.author.name

    print(ign, requested_profile_name)

    profile_data = await bot._get_player_profile_data(ctx, ign, requested_profile_name=None)
    if not profile_data:
        return  # Error message already sent by helper

    target_ign, player_uuid, selected_profile = profile_data
    profile_name = selected_profile.get('cute_name', 'Unknown')



    try:
        member_data = selected_profile.get('members', {}).get(player_uuid)
        secrets = member_data.get('dungeons', {}).get('secrets', 0)

        """with open("profile_data.json", 'w') as f:
            json.dump(member_data, f, indent=4)
            print("saved data")"""

        formatted_secrets = f"{secrets:,}".replace(",", ".")
        await bot.send_message(ctx, f"{target_ign} has {formatted_secrets} secrets")


    except Exception as e:
        print(f"[ERROR][SkillsCmd] Unexpected error calculating skills: {e}")
        traceback.print_exc()
        await bot.send_message(ctx, "An unexpected error occurred while calculating skill levels.")
