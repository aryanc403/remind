import os
import asyncio
import discord
import logging
from logging.handlers import TimedRotatingFileHandler
from os import environ
from remind import constants

from discord.ext import commands
from dotenv import load_dotenv
from pathlib import Path
from remind.util import discord_common


def setup():
    # Make required directories.
    for path in constants.ALL_DIRS:
        os.makedirs(path, exist_ok=True)

    # logging to console and file on daily interval
    logging.basicConfig(
        format='{asctime}:{levelname}:{name}:{message}',
        style='{',
        datefmt='%d-%m-%Y %H:%M:%S',
        level=logging.INFO,
        handlers=[
            logging.StreamHandler(),
            TimedRotatingFileHandler(
                constants.LOG_FILE_PATH,
                when='D',
                backupCount=3,
                utc=True)])


def main():
    load_dotenv()
    token = os.getenv('BOT_TOKEN_REMIND')
    GUILD = os.getenv('GUILD_ID')
    CHANNEL = int(os.getenv('CHANNEL_ID'))

    if not token:
        logging.error('Token required')
        return

    setup()

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
