import os
import asyncio
import discord
import logging
from discord.ext import commands
from dotenv import load_dotenv
from pathlib import Path
from remind.util import discord_common

def main():
    load_dotenv()
    token = os.getenv('BOT_TOKEN_REMIND')
    GUILD = os.getenv('GUILD_ID')
    CHANNEL = int(os.getenv('CHANNEL_ID'))

    if not token:
        logging.error('Token required')
        return

    bot = commands.Bot(command_prefix=commands.when_mentioned_or('t;'))
    cogs = [file.stem for file in Path('remind', 'cogs').glob('*.py')]
    for extension in cogs:
        bot.load_extension(f'remind.cogs.{extension}')
    logging.info(f'Cogs loaded: {", ".join(bot.cogs)}')

    def no_dm_check(ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage('Private messages not permitted.')
        return True

    # Restrict bot usage to inside guild channels only.
    bot.add_check(no_dm_check)

    @bot.event
    async def on_ready():
        asyncio.create_task(discord_common.presence(bot))

    bot.add_listener(discord_common.bot_error_handler, name='on_command_error')
    bot.run(token)


if __name__ == '__main__':
    main()