import asyncio
import logging
import functools
import random

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

_COLORS = (0xFFCA1F, 0x198BCC, 0xFF2020)
_SUCCESS_GREEN = 0x28A745
_ALERT_AMBER = 0xFFBF00


def embed_neutral(desc, color=discord.Embed.Empty):
    return discord.Embed(description=str(desc), color=color)


def embed_success(desc):
    return discord.Embed(description=str(desc), color=_SUCCESS_GREEN)


def embed_alert(desc):
    return discord.Embed(description=str(desc), color=_ALERT_AMBER)


def attach_image(embed, img_file):
    embed.set_image(url=f'attachment://{img_file.filename}')


def color_embed(**kwargs):
    return discord.Embed(**kwargs, color=random.choice(_COLORS))


def set_author_footer(embed, user):
    embed.set_footer(text=f'Requested by {user}', icon_url=user.avatar_url)


def time_format(seconds):
    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return days, hours, minutes, seconds


def pretty_time_format(
        seconds,
        *,
        shorten=False,
        only_most_significant=False,
        always_seconds=False):
    days, hours, minutes, seconds = time_format(seconds)
    timespec = [
        (days, 'day', 'days'),
        (hours, 'hour', 'hours'),
        (minutes, 'minute', 'minutes'),
    ]
    timeprint = [(cnt, singular, plural)
                 for cnt, singular, plural in timespec if cnt]
    if not timeprint or always_seconds:
        timeprint.append((seconds, 'second', 'seconds'))
    if only_most_significant:
        timeprint = [timeprint[0]]

    def format_(triple):
        cnt, singular, plural = triple
        return f'{cnt}{singular[0]}' if shorten \
            else f'{cnt} {singular if cnt == 1 else plural}'

    return ' '.join(map(format_, timeprint))


def send_error_if(*error_cls):
    """Decorator for `cog_command_error` methods.
    Decorated methods send the error in an alert embed
    when the error is an instance of one of the specified errors,
    otherwise the wrapped function is invoked.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(cog, ctx, error):
            if isinstance(error, error_cls):
                await ctx.send(embed=embed_alert(error))
                error.handled = True
            else:
                await func(cog, ctx, error)
        return wrapper
    return decorator


def once(func):
    """Decorator that wraps the given async function
    such that it is executed only once."""
    first = True

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        nonlocal first
        if first:
            first = False
            await func(*args, **kwargs)

    return wrapper


def on_ready_event_once(bot):
    """Decorator that uses bot.event to set the given function
    as the bot's on_ready event handler,
    but does not execute it more than once.
    """
    def register_on_ready(func):
        @bot.event
        @once
        async def on_ready():
            await func()

    return register_on_ready


async def bot_error_handler(ctx, exception):
    if getattr(exception, 'handled', False):
        # Errors already handled in cogs should have .handled = True
        return

    exc_info = type(exception), exception, exception.__traceback__
    logger.exception(
        'Ignoring exception in command {}:'.format(
            ctx.command), exc_info=exc_info)


async def presence(bot):
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name='clist.by'))
