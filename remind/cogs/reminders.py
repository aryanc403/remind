import asyncio
import functools
import json
import logging
import time
import datetime as dt
from pathlib import Path
import pytz

from collections import defaultdict

import discord
from discord.ext import commands
import os

from remind.util import codeforces_common as cf_common
from remind.util.rounds import Rounds
from remind.util import discord_common
from remind.util import paginator
from remind import constants
from remind.util import clist_api as clist

_CONTESTS_PER_PAGE = 5
_CONTEST_PAGINATE_WAIT_TIME = 5 * 60
_FINISHED_CONTESTS_LIMIT = 5
localtimezone = pytz.timezone("Asia/Kolkata")
# (Channel ID, Role ID, [List of Minutes])
_REMINDER_SETTINGS = (
    '53',
    '66',
    '[180, 60, 10]')
_CONTEST_REFRESH_PERIOD = 3 * 60 * 60  # seconds
_CODEFORCES_WEBSITE = 'codeforces.com'


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


def _get_embed_fields_from_contests(contests):
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


async def _send_reminder_at(channel, role, contests, before_secs, send_time):
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
    for name, value in _get_embed_fields_from_contests(contests):
        embed.add_field(name=name, value=value)
    await channel.send(role.mention, embed=embed)


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

        self.member_converter = commands.MemberConverter()
        self.role_converter = commands.RoleConverter()

        self.logger = logging.getLogger(self.__class__.__name__)

    @commands.Cog.listener()
    async def on_ready(self):
        if self.running:
            return
        # To avoid re-creating tasks if discord is reconnected.
        self.running = True
        global _REMINDER_SETTINGS
        _REMINDER_SETTINGS = (int(os.getenv('REMIND_CHANNEL_ID')), int(
            os.getenv('REMIND_ROLE_ID')), _REMINDER_SETTINGS[2])
        asyncio.create_task(self._update_task())

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
        clist.cache(forced=False)
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
        try:
            # settings = cf_common.user_db.get_reminder_settings(guild_id)
            settings = _REMINDER_SETTINGS
        except db.DatabaseDisabledError:
            return
        if settings is None:
            return
        channel_id, role_id, before = settings
        channel_id, role_id, before = int(
            channel_id), int(role_id), json.loads(before)
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
                        before_secs)
                )
                self.task_map[guild_id].append(task)
        self.logger.info(
            f'{len(self.task_map[guild_id])} \
                tasks scheduled for guild {guild_id}')

    @ staticmethod
    def _make_contest_pages(contests, title):
        pages = []
        chunks = paginator.chunkify(contests, _CONTESTS_PER_PAGE)
        for chunk in chunks:
            embed = discord_common.cf_color_embed()
            for name, value in _get_embed_fields_from_contests(chunk):
                embed.add_field(name=name, value=value, inline=False)
            pages.append((title, embed))
        return pages

    async def _send_contest_list(self, ctx, contests, *, title, empty_msg):
        if contests is None:
            raise RemindersCogError('Contest list not present')
        if len(contests) == 0:
            await ctx.send(embed=discord_common.embed_neutral(empty_msg))
            return
        pages = self._make_contest_pages(contests, title)
        paginator.paginate(
            self.bot,
            ctx.channel,
            pages,
            wait_time=_CONTEST_PAGINATE_WAIT_TIME,
            set_pagenum_footers=True
        )

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
