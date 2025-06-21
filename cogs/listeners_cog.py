# cogs/listeners_cog.py
import discord
from discord.ext import commands
import datetime
import pytz
import database as db
from constants import BRAZIL_TZ

class ListenersCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_sessions = {}  # user_id -> session_start_time

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot:
            return

        user_id = member.id
        now_utc = datetime.datetime.now(pytz.utc)

        # User joins a voice channel or moves between channels
        if after.channel is not None:
            # If user was not in a voice channel before, start a new session
            if before.channel is None:
                self.voice_sessions[user_id] = now_utc

        # User leaves a voice channel
        elif before.channel is not None and after.channel is None:
            if user_id in self.voice_sessions:
                session_start = self.voice_sessions.pop(user_id)
                duration = now_utc - session_start
                duration_seconds = int(duration.total_seconds())

                if duration_seconds > 10:  # Log sessions longer than 10 seconds
                    db.db_log_voice_session(
                        user_id=user_id,
                        guild_id=member.guild.id,
                        session_start_utc=session_start.isoformat(),
                        session_end_utc=now_utc.isoformat(),
                        duration_seconds=duration_seconds
                    )

# Função setup para carregar o Cog
async def setup(bot: commands.Bot):
    await bot.add_cog(ListenersCog(bot))