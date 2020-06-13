import asyncio
import logging
import functools
import random

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

_CF_COLORS = (0xFFCA1F, 0x198BCC, 0xFF2020)
_SUCCESS_GREEN = 0x28A745
_ALERT_AMBER = 0xFFBF00


def embed_neutral(desc, color=discord.Embed.Empty):
    return discord.Embed(description=str(desc), color=color)


def embed_success(desc):
    return discord.Embed(description=str(desc), color=_SUCCESS_GREEN)


def embed_alert(desc):
    return discord.Embed(description=str(desc), color=_ALERT_AMBER)


def cf_color_embed(**kwargs):
    return discord.Embed(**kwargs, color=random.choice(_CF_COLORS))


def attach_image(embed, img_file):
    embed.set_image(url=f'attachment://{img_file.filename}')


def set_author_footer(embed, user):
    embed.set_footer(text=f'Requested by {user}', icon_url=user.avatar_url)


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
