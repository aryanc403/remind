import asyncio
import random
import functools
import json
import pickle
import logging
import time
import datetime as dt
from pathlib import Path
from recordtype import recordtype
import pytz

from collections import defaultdict
from collections import namedtuple

import discord
from discord.ext import commands
import os

from remind.util import codeforces_common as cf_common
from remind.util.rounds import Rounds
from remind.util import discord_common
from remind.util import paginator
from remind import constants

_CONTESTS_PER_PAGE = 5
_CONTEST_PAGINATE_WAIT_TIME = 5 * 60
_FINISHED_CONTESTS_LIMIT = 5
# (Channel ID, Role ID, [List of Minutes])
_REMINDER_SETTINGS = (
    '53',
    '66',
    '[180, 60, 10]')
_CONTEST_REFRESH_PERIOD = 3 * 60 * 60  # seconds
_CODEFORCES_WEBSITE = 'codeforces.com'
_PYTZ_TIMEZONES_GIST_URL = ('https://gist.github.com/heyalexej/'
                            '8bf688fd67d7199be4a1682b3eec7568')


class RemindersCogError(commands.CommandError):
    pass


def _contest_start_time_format(contest, tz):
    start = contest.start_time.replace(tzinfo=dt.timezone.utc).astimezone(tz)
    return f'{start.strftime("%d %b %y, %H:%M")} {tz}'


def _contest_duration_format(contest):
    duration_days, duration_hrs, duration_mins, _ = cf_common.time_format(
        contest.duration.total_seconds())
    duration = f'{duration_hrs}h {duration_mins}m'
    if duration_days > 0:
        duration = f'{duration_days}d ' + duration
    return duration


def _get_formatted_contest_desc(
        id_str,
        start,
        duration,
        url,
        max_duration_len):
    em = '\N{EN SPACE}'
    sq = '\N{WHITE SQUARE WITH UPPER RIGHT QUADRANT}'
    desc = (f'`{em}{id_str}{em}|'
            f'{em}{start}{em}|'
            f'{em}{duration.rjust(max_duration_len, em)}{em}|'
            f'{em}`[`link {sq}`]({url} "Link to contest page")')
    return desc


def _get_embed_fields_from_contests(contests, localtimezone):
    infos = [(contest.name,
              str(contest.id),
              _contest_start_time_format(contest,
                                         localtimezone),
              _contest_duration_format(contest),
              contest.url) for contest in contests]
    max_duration_len = max(len(duration) for _, _, _, duration, _ in infos)

    fields = []
    for name, id_str, start, duration, url in infos:
        value = _get_formatted_contest_desc(
            id_str, start, duration, url, max_duration_len)
        fields.append((name, value))
    return fields


async def _send_reminder_at(channel, role, contests, before_secs, send_time,
                            localtimezone: pytz.timezone):
    delay = send_time - dt.datetime.utcnow().timestamp()
    if delay <= 0:
        return
    await asyncio.sleep(delay)
    values = cf_common.time_format(before_secs)

    def make(value, label):
        tmp = f'{value} {label}'
        return tmp if value == 1 else tmp + 's'

    labels = 'day hr min sec'.split()
    before_str = ' '.join(make(value, label)
                          for label, value in zip(labels, values) if value > 0)
    desc = f'About to start in {before_str}'
    embed = discord_common.cf_color_embed(description=desc)
    for name, value in _get_embed_fields_from_contests(
            contests, localtimezone):
        embed.add_field(name=name, value=value)
    await channel.send(role.mention, embed=embed)


GuildSettings = recordtype(
    'GuildSettings', [
        ('channel_id', None), ('role_id', None),
        ('before', None), ('localtimezone', pytz.timezone('UTC'))])


class Reminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.running = False
        self.future_contests = None
        self.contest_cache = None
        self.active_contests = None
        self.finished_contests = None
        self.start_time_map = defaultdict(list)
        self.task_map = defaultdict(list)
        # Maps guild_id to `GuildSettings`
        self.guild_map = defaultdict(GuildSettings)

        self.member_converter = commands.MemberConverter()
        self.role_converter = commands.RoleConverter()

        self.logger = logging.getLogger(self.__class__.__name__)

    @commands.Cog.listener()
    async def on_ready(self):
        if self.running:
            return
        # To avoid re-initializing if discord is reconnected.
        self.running = True
        guild_map_path = Path(constants.GUILD_SETTINGS_MAP_PATH)
        try:
            with guild_map_path.open('rb') as guild_map_file:
                self.guild_map = pickle.load(guild_map_file)
        except FileNotFoundError:
            pass
        asyncio.create_task(self._update_task())

    async def cog_after_invoke(self, ctx):
        self._serialize_guild_map()
        self._reschedule_tasks(ctx.guild.id)

    async def _update_task(self):
        self.logger.info(f'Updating reminder tasks.')
        self._generate_contest_cache()
        contest_cache = self.contest_cache
        current_time = dt.datetime.utcnow()

        self.future_contests = [
            contest for contest in contest_cache
            if contest.start_time > current_time
        ]
        self.finished_contests = [
            contest for contest in contest_cache
            if contest.start_time +
            contest.duration < current_time
        ]
        self.active_contests = [
            contest for contest in contest_cache
            if contest.start_time <= current_time <=
            contest.start_time + contest.duration
        ]

        self.active_contests.sort(key=lambda contest: contest.start_time)
        self.finished_contests.sort(
            key=lambda contest: contest.start_time +
            contest.duration,
            reverse=True
        )
        self.future_contests.sort(key=lambda contest: contest.start_time)
        # Keep most recent _FINISHED_LIMIT
        self.finished_contests = \
            self.finished_contests[:_FINISHED_CONTESTS_LIMIT]
        self.start_time_map.clear()
        for contest in self.future_contests:
            self.start_time_map[time.mktime(
                contest.start_time.timetuple())].append(contest)
        self._reschedule_all_tasks()
        await asyncio.sleep(_CONTEST_REFRESH_PERIOD)
        asyncio.create_task(self._update_task())

    def _generate_contest_cache(self):
        db_file = Path(constants.CONTESTS_DB_FILE_PATH)
        with db_file.open() as f:
            data = json.load(f)
        contests = [Rounds(contest) for contest in data['objects']]
        self.contest_cache = [
            contest for contest in contests
            if contest.is_rated()
        ]

    def _reschedule_all_tasks(self):
        for guild in self.bot.guilds:
            self._reschedule_tasks(guild.id)

    def _reschedule_tasks(self, guild_id):
        for task in self.task_map[guild_id]:
            task.cancel()
        self.task_map[guild_id].clear()
        self.logger.info(f'Tasks for guild {guild_id} cleared')
        if not self.start_time_map:
            return
        settings = self.guild_map[guild_id]
        if any(setting is None for setting in settings):
            return
        channel_id, role_id, before, localtimezone = settings

        guild = self.bot.get_guild(guild_id)
        channel, role = guild.get_channel(channel_id), guild.get_role(role_id)
        for start_time, contests in self.start_time_map.items():
            # Skip Codeforces reminders. Allow TLE to do this.
            if contests[0].website == _CODEFORCES_WEBSITE:
                continue

            for before_mins in before:
                before_secs = 60 * before_mins
                task = asyncio.create_task(
                    _send_reminder_at(
                        channel,
                        role,
                        contests,
                        before_secs,
                        start_time -
                        before_secs, localtimezone)
                )
                self.task_map[guild_id].append(task)
        self.logger.info(
            f'{len(self.task_map[guild_id])} '
            f'tasks scheduled for guild {guild_id}')

    @staticmethod
    def _make_contest_pages(contests, title, localtimezone):
        pages = []
        chunks = paginator.chunkify(contests, _CONTESTS_PER_PAGE)
        for chunk in chunks:
            embed = discord_common.cf_color_embed()
            for name, value in _get_embed_fields_from_contests(
                    chunk, localtimezone):
                embed.add_field(name=name, value=value, inline=False)
            pages.append((title, embed))
        return pages

    async def _send_contest_list(self, ctx, contests, *, title, empty_msg):
        if contests is None:
            raise RemindersCogError('Contest list not present')
        if len(contests) == 0:
            await ctx.send(embed=discord_common.embed_neutral(empty_msg))
            return
        pages = self._make_contest_pages(
            contests, title, self.guild_map[ctx.guild.id].localtimezone)
        paginator.paginate(
            self.bot,
            ctx.channel,
            pages,
            wait_time=_CONTEST_PAGINATE_WAIT_TIME,
            set_pagenum_footers=True
        )

    def _serialize_guild_map(self):
        out_path = Path(constants.GUILD_SETTINGS_MAP_PATH)
        with out_path.open(mode='wb') as out_file:
            pickle.dump(self.guild_map, out_file)

    @commands.group(brief='Commands for contest reminders',
                    invoke_without_command=True)
    async def remind(self, ctx):
        await ctx.send_help(ctx.command)

    @remind.command(brief='Set the reminders channel')
    @commands.has_role('Admin')
    async def here(self, ctx):
        """Sets reminder channel to current channel.
        """
        self.guild_map[ctx.guild.id].channel_id = ctx.channel.id
        await ctx.send(embed=discord_common.embed_success(
            f'Succesfully set the reminder channel to {ctx.channel.mention}'))

    @remind.command(brief='Set the reminder times',
                    usage='<reminder_times_in_minutes>')
    @commands.has_role('Admin')
    async def before(self, ctx, *reminder_times: int):
        """Sets a reminder `x` minutes before the contests
           for each `x` in `reminder_times`.
        """
        if not reminder_times or any(
                reminder_time <= 0 for reminder_time in reminder_times):
            raise RemindersCogError('Please provide valid `reminder_times`')
        reminder_times = list(reminder_times)
        reminder_times.sort(reverse=True)
        self.guild_map[ctx.guild.id].before = reminder_times
        await ctx.send(embed=discord_common.embed_success(
            'Succesfully set the reminder times to ' + f'{reminder_times}'))

    @remind.command(brief='Set the reminder role',
                    usage='<mentionable_role>')
    @commands.has_role('Admin')
    async def role(self, ctx, role: discord.Role):
        """Sets the reminder role to the given role.
        """
        if not role.mentionable:
            raise RemindersCogError(
                'The role for reminders must be mentionable')
        self.guild_map[ctx.guild.id].role_id = role.id
        await ctx.send(embed=discord_common.embed_success(
            f'Succesfully set the reminder role to {role.mention}'))

    @remind.command(brief='Show reminder settings')
    async def settings(self, ctx):
        """Shows the reminders role, channel, times, and timezone settings."""
        settings = self.guild_map[ctx.guild.id]
        channel_id, role_id, before, timezone = settings
        channel = ctx.guild.get_channel(channel_id)
        role = ctx.guild.get_role(role_id)
        if channel is None:
            raise RemindersCogError('No channel set for reminders')
        if role is None:
            raise RemindersCogError('No role set for reminders')
        before_str = ', '.join(str(before_mins) for before_mins in before)
        embed = discord_common.embed_success('Current reminder settings')
        embed.add_field(name='Channel', value=channel.mention)
        embed.add_field(name='Role', value=role.mention)
        embed.add_field(name='Before',
                        value=f'At {before_str} mins before contest')
        await ctx.send(embed=embed)

    @commands.command(brief='Set the server\'s timezone',
                      usage=' <timezone>')
    @commands.has_role('Admin')
    async def settz(self, ctx, timezone: str):
        """Sets the server's timezone to the given timezone.
        """
        if not (timezone in pytz.all_timezones):
            desc = ('The given timezone is invalid\n\n'
                    'Examples of valid timezones:\n\n')
            desc += '\n'.join(random.sample(pytz.all_timezones, 5))
            desc += '\n\nAll valid timezones can be found [here]'
            desc += f'({_PYTZ_TIMEZONES_GIST_URL})'
            raise RemindersCogError(desc)
        self.guild_map[ctx.guild.id].localtimezone = pytz.timezone(timezone)
        await ctx.send(embed=discord_common.embed_success(
            f'Succesfully set the server timezone to {timezone}'))

    @commands.group(brief='Commands for listing contests',
                    invoke_without_command=True)
    async def clist(self, ctx):
        await ctx.send_help(ctx.command)

    @clist.command(brief='List future contests')
    async def future(self, ctx):
        """List future contests on Codeforces."""
        await self._send_contest_list(ctx, self.future_contests,
                                      title='Future contests',
                                      empty_msg='No future contests scheduled'
                                      )

    @clist.command(brief='List active contests')
    async def active(self, ctx):
        """List active contests."""
        await self._send_contest_list(ctx, self.active_contests,
                                      title='Active contests on Codeforces',
                                      empty_msg='No contests currently active'
                                      )

    @clist.command(brief='List recent finished contests')
    async def finished(self, ctx):
        """List recently concluded contests."""
        await self._send_contest_list(ctx, self.finished_contests,
                                      title='Recently finished contests',
                                      empty_msg='No finished contests found'
                                      )

    @discord_common.send_error_if(RemindersCogError)
    async def cog_command_error(self, ctx, error):
        pass


def setup(bot):
    bot.add_cog(Reminders(bot))
