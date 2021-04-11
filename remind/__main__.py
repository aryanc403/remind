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
from remind.util import clist_api


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

    token = os.environ['DISCORD_TOKEN']
    if not token:
        logging.error('Token required')
        return

    super_users_str = os.getenv('SUPER_USERS')
    if not super_users_str:
        logging.error('Superusers required')
        return
    constants.SUPER_USERS = list(map(int, super_users_str.split(",")))

    remind_moderator_role = os.getenv('REMIND_MODERATOR_ROLE')
    if remind_moderator_role:
        constants.REMIND_MODERATOR_ROLE = remind_moderator_role

    setup()

    intents = discord.Intents.default()
    intents.members = True
    bot = commands.Bot(
        command_prefix=commands.when_mentioned_or('t;'),
        intents=intents)

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

    @discord_common.on_ready_event_once(bot)
    async def init():
        clist_api.cache()
        asyncio.create_task(discord_common.presence(bot))

    bot.add_listener(discord_common.bot_error_handler, name='on_command_error')
    bot.run(token)


if __name__ == '__main__':
    main()
