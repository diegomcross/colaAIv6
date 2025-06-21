# cogs/tasks_cog.py
import discord
from discord.ext import commands, tasks
import asyncio 
import datetime
import pytz
import database as db
import utils 
import role_utils 
import bungie_api
from constants import BRAZIL_TZ, DIGEST_TIMES_BRT
from utils import ConfirmAttendanceView, ClanInviteView
from cogs.event_cog import PersistentRsvpView 

RANKING_HOURS_TIERS = {
    4: 36,
    3: 20,
    2: 10,
    1: 0
}

class TasksCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cleanup_completed_events_task.start()
        self.delete_event_messages_task.start()
        self.event_reminder_task.start() 
        self.confirmation_reminder_task.start() 
        self.daily_event_digest_task.start()
        self.attendance_check_task.start()
        self.manage_event_voice_channels_task.start()
        self.update_leaderboard_task.start()
        self.update_ranking_roles_task.start()
        self.inactivity_check_task.start()
        self.clan_role_sync_task.start()
        self.clan_invite_check_task.start()

    def cog_unload(self):
        self.cleanup_completed_events_task.cancel()
        self.delete_event_messages_task.cancel()
        self.event_reminder_task.cancel()
        self.confirmation_reminder_task.cancel()
        self.daily_event_digest_task.cancel()
        self.attendance_check_task.cancel()
        self.manage_event_voice_channels_task.cancel()
        self.update_leaderboard_task.cancel()
        self.update_ranking_roles_task.cancel()
        self.inactivity_check_task.cancel()
        self.clan_role_sync_task.cancel()
        self.clan_invite_check_task.cancel()

    @tasks.loop(minutes=15)
    async def clan_invite_check_task(self):
        db.db_prune_expired_invites() 

        for guild in self.bot.guilds:
            configs = db.db_get_server_configs(guild.id)
            if not configs: continue

            admin_cla_id = configs.get('clan_admin_discord_id')
            mod_channel_id = configs.get('mod_notification_channel_id')

            if not admin_cla_id or not mod_channel_id:
                continue

            mod_channel = guild.get_channel(mod_channel_id)
            if not mod_channel or not isinstance(mod_channel, discord.TextChannel):
                continue

            try:
                pending_invites = await bungie_api.get_pending_invitations(admin_cla_id)
                for invite_info in pending_invites:
                    bnet_id = invite_info['membership_id']
                    if not db.db_is_invite_tracked(bnet_id):
                        embed = discord.Embed(
                            title="📥 Pedido de Entrada no Clã",
                            description=f"O jogador **{invite_info['bungie_name']}** solicitou entrada no clã.",
                            color=discord.Color.blue()
                        )
                        embed.add_field(name="ID Bungie", value=f"`{bnet_id}`", inline=False)
                        embed.set_footer(text="Aja usando os botões abaixo.")

                        view = ClanInviteView(applicant_info=invite_info)
                        message = await mod_channel.send(embed=embed, view=view)

                        db.db_track_pending_invite(bnet_id, guild.id, message.id)
                        await asyncio.sleep(2)

            except Exception as e:
                print(f"CLAN_INVITE_CHECK_ERROR: Ocorreu um erro ao verificar convites para {guild.name}: {e}")

    @tasks.loop(hours=1.0)
    async def clan_role_sync_task(self):
        for guild in self.bot.guilds:
            configs = db.db_get_server_configs(guild.id)
            if not configs: continue

            clan_role_id = configs.get('clan_role_id')
            admin_cla_id = configs.get('clan_admin_discord_id')

            if not clan_role_id or not admin_cla_id:
                continue

            clan_role = guild.get_role(clan_role_id)
            if not clan_role:
                continue

            try:
                clan_member_bnet_ids = await bungie_api.get_clan_members(admin_cla_id)
                if not clan_member_bnet_ids:
                    continue

                all_linked_profiles = db.db_get_all_linked_profiles()
                bnet_id_to_discord_id = {
                    profile['bungie_membership_id']: profile['discord_id'] for profile in all_linked_profiles
                }

                discord_ids_in_clan = set()
                for bnet_id in clan_member_bnet_ids:
                    if bnet_id in bnet_id_to_discord_id:
                        discord_ids_in_clan.add(bnet_id_to_discord_id[bnet_id])

                for member in guild.members:
                    if member.bot: continue

                    has_role = clan_role in member.roles
                    should_have_role = member.id in discord_ids_in_clan

                    if should_have_role and not has_role:
                        await member.add_roles(clan_role, reason="Sincronização automática de membro do clã.")
                    elif not should_have_role and has_role:
                        await member.remove_roles(clan_role, reason="Sincronização automática - membro não está mais no clã.")

            except Exception as e:
                print(f"CLAN_ROLE_SYNC_ERROR: Ocorreu um erro durante a sincronização em {guild.name}: {e}")

    @tasks.loop(time=datetime.time(hour=7, minute=0, tzinfo=BRAZIL_TZ))
    async def update_leaderboard_task(self):
        for guild in self.bot.guilds:
            configs = db.db_get_server_configs(guild.id)
            if not configs or not configs.get('ranking_channel_id'):
                continue

            ranking_channel = guild.get_channel(configs['ranking_channel_id'])
            if not ranking_channel or not isinstance(ranking_channel, discord.TextChannel):
                continue

            user_times = db.db_get_all_users_weekly_voice_time(guild.id)
            embed = discord.Embed(title="🏆 Ranking de Atividade Semanal", description="Top membros por tempo em canais de voz nos últimos 7 dias.", color=discord.Color.gold())

            leaderboard_text = ""
            if not user_times:
                leaderboard_text = "Nenhuma atividade de voz registrada na última semana."
            else:
                for i, (user_id, total_seconds) in enumerate(user_times[:20]):
                    member = guild.get_member(user_id)
                    if member:
                        hours = total_seconds / 3600
                        leaderboard_text += f"{i+1}. {member.mention} - **{hours:.1f} horas**\n"

            embed.add_field(name="Classificação", value=leaderboard_text or "Ninguém esteve ativo.", inline=False)
            embed.set_footer(text=f"Atualizado em: {utils.get_brazil_now().strftime('%d/%m/%Y %H:%M')}")

            try:
                history = [msg async for msg in ranking_channel.history(limit=50)]
                bot_message = next((msg for msg in history if msg.author == self.bot.user and msg.embeds and msg.embeds[0].title == embed.title), None)
                if bot_message:
                    await bot_message.edit(embed=embed)
                else:
                    await ranking_channel.send(embed=embed)
            except Exception as e:
                print(f"ERRO_TASK: Falha ao enviar/editar leaderboard para {guild.name}: {e}")

    @tasks.loop(hours=24) 
    async def update_ranking_roles_task(self):
        now_brt = utils.get_brazil_now()
        if now_brt.weekday() != 5:
            return 

        for guild in self.bot.guilds:
            ranking_roles_data = db.db_get_ranking_roles(guild.id)
            configs = db.db_get_server_configs(guild.id)
            if not ranking_roles_data or not configs or not configs.get('ranking_channel_id'):
                continue

            ranking_roles = {
                1: guild.get_role(ranking_roles_data['role_tier_1_id']),
                2: guild.get_role(ranking_roles_data['role_tier_2_id']),
                3: guild.get_role(ranking_roles_data['role_tier_3_id']),
                4: guild.get_role(ranking_roles_data['role_tier_4_id'])
            }
            all_ranking_role_ids = {r.id for r in ranking_roles.values() if r}
            if len(all_ranking_role_ids) != 4: continue

            promoted_members = []

            for member in guild.members:
                if member.bot: continue

                weekly_hours = db.db_get_user_weekly_voice_time(guild.id, member.id) / 3600

                correct_tier = 1
                for tier, required_hours in sorted(RANKING_HOURS_TIERS.items(), reverse=True):
                    if weekly_hours >= required_hours:
                        correct_tier = tier
                        break

                correct_role = ranking_roles.get(correct_tier)
                if not correct_role: continue

                current_ranking_roles = [r for r in member.roles if r.id in all_ranking_role_ids]

                if correct_role not in member.roles:
                    if current_ranking_roles:
                        await member.remove_roles(*current_ranking_roles, reason="Atualização de cargo de ranking.")
                    await member.add_roles(correct_role, reason="Promoção de cargo de ranking.")

                    if correct_tier > 1 and not any(r.id == correct_role.id for r in current_ranking_roles):
                         promoted_members.append(f"👑 {member.mention} alcançou o cargo {correct_role.mention}!")

            if promoted_members:
                ranking_channel_id = configs.get('ranking_channel_id')
                if ranking_channel_id:
                    ranking_channel = guild.get_channel(ranking_channel_id)
                    if ranking_channel and isinstance(ranking_channel, discord.TextChannel):
                        announcement_embed = discord.Embed(title="🎉 Promoções do Ranking Semanal!", description="\n".join(promoted_members), color=discord.Color.green())
                        await ranking_channel.send(embed=announcement_embed)

    @tasks.loop(hours=24)
    async def inactivity_check_task(self):
        for guild in self.bot.guilds:
            configs = db.db_get_server_configs(guild.id)
            if not configs or not configs.get('mod_notification_channel_id'):
                continue

            mod_channel = guild.get_channel(configs['mod_notification_channel_id'])
            if not mod_channel or not isinstance(mod_channel, discord.TextChannel): continue

            clan_member_ids = set()
            admin_cla_id = configs.get('clan_admin_discord_id')
            if admin_cla_id:
                clan_member_ids = await bungie_api.get_clan_members(admin_cla_id)

            inactive_3_weeks = db.db_get_inactive_members(guild.id, 3)
            for user_id in inactive_3_weeks:
                member = guild.get_member(user_id)
                if not member: continue

                try:
                    await member.send(f"Olá. Devido a um período de inatividade superior a 3 semanas, seu acesso ao servidor {guild.name} foi revogado.")
                    await asyncio.sleep(1) 
                except discord.Forbidden:
                    pass
                except Exception as e:
                    print(f"INACTIVITY_LOG: Erro ao enviar DM para membro inativo {user_id}: {e}")

                bungie_kick_success = False
                member_bnet_profile = db.db_get_bungie_profile(user_id)

                if admin_cla_id and member_bnet_profile and member_bnet_profile['bungie_membership_id'] in clan_member_ids:
                    kick_result = await bungie_api.kick_clan_member(
                        admin_discord_id=admin_cla_id,
                        member_to_kick_bnet_id=member_bnet_profile['bungie_membership_id'],
                        member_to_kick_membership_type=member_bnet_profile['bungie_membership_type']
                    )
                    if kick_result:
                        await mod_channel.send(f"🌐 O membro {member.mention} (`{member.id}`) foi removido do clã na Bungie.net.")
                        bungie_kick_success = True
                    else:
                        await mod_channel.send(f"⚠️ Falha ao remover o membro {member.mention} do clã na Bungie.net.")

                try:
                    kick_reason = "Remoção por inatividade (3 semanas)." + (" Removido também do clã Bungie." if bungie_kick_success else "")
                    await member.kick(reason=kick_reason)
                    await mod_channel.send(f"🚨 O membro {member.mention} (`{member.id}`) foi removido do Discord por inatividade.")
                except discord.Forbidden:
                    await mod_channel.send(f"⚠️ Falha ao remover o membro {member.mention} (`{member.id}`) do Discord.")
                except Exception as e:
                    await mod_channel.send(f"❌ Erro ao remover o membro {member.mention} do Discord: {e}")

            await asyncio.sleep(5)

            inactive_2_weeks = db.db_get_inactive_members(guild.id, 2)
            for user_id in inactive_2_weeks:
                if user_id in inactive_3_weeks: continue
                member = guild.get_member(user_id)
                if member:
                    try:
                        await member.send(f"👋 Lembrete de atividade do servidor **{guild.name}**. Notamos que você não participa de um evento há mais de 2 semanas.")
                        await asyncio.sleep(1)
                    except discord.Forbidden:
                         pass
                    except Exception as e:
                        print(f"INACTIVITY_LOG: Erro ao enviar DM de aviso para {user_id}: {e}")

    @tasks.loop(minutes=1.0)
    async def manage_event_voice_channels_task(self):
        events_for_vc_creation = db.db_get_events_for_vc_creation()
        for event in events_for_vc_creation:
            guild = self.bot.get_guild(event['guild_id'])
            if not guild: continue
            event_text_channel = guild.get_channel(event['channel_id'])
            category = event_text_channel.category if event_text_channel else None
            vc_name = f"{event['activity_type']} {event['title']}"
            try:
                new_vc = await guild.create_voice_channel(name=vc_name, category=category, reason=f"Canal para evento ID: {event['event_id']}")
                db.db_update_event_details(event['event_id'], voice_channel_id=new_vc.id)
            except Exception as e: print(f"ERRO_TASK_VC: Falha ao criar VC para evento {event['event_id']}: {e}")

        events_for_vc_deletion = db.db_get_events_for_vc_deletion()
        for event in events_for_vc_deletion:
            guild = self.bot.get_guild(event['guild_id'])
            if not guild or not event['voice_channel_id']: continue
            channel = guild.get_channel(event['voice_channel_id'])
            if isinstance(channel, discord.VoiceChannel) and not channel.members:
                try:
                    await channel.delete(reason="Evento concluído.")
                    db.db_update_event_details(event['event_id'], voice_channel_id=None)
                except Exception as e: print(f"ERRO_TASK_VC: Falha ao apagar VC {channel.id}: {e}")
            elif channel is None:
                db.db_update_event_details(event['event_id'], voice_channel_id=None)

    @tasks.loop(minutes=5.0)
    async def attendance_check_task(self):
        events_to_check = db.db_get_events_for_attendance_check()
        if not events_to_check: return
        for event in events_to_check:
            guild = self.bot.get_guild(event['guild_id'])
            if not guild:
                db.db_mark_attendance_checked(event['event_id']); continue
            event_vc_id = event['voice_channel_id']
            event_vc = guild.get_channel(event_vc_id) if event_vc_id else None
            if not isinstance(event_vc, discord.VoiceChannel):
                creator = guild.get_member(event['creator_id'])
                if creator and creator.voice and creator.voice.channel:
                    event_vc = creator.voice.channel
            if not isinstance(event_vc, discord.VoiceChannel):
                db.db_mark_attendance_checked(event['event_id']); continue
            members_in_vc_ids = {m.id for m in event_vc.members}
            rsvps = db.db_get_rsvps_for_event(event['event_id'])
            confirmed_ids = set(rsvps.get('vou', []))
            for user_id in confirmed_ids:
                status = 'compareceu' if user_id in members_in_vc_ids else 'ausente'
                db.db_update_rsvp_attendance(event['event_id'], user_id, status)
            db.db_mark_attendance_checked(event['event_id'])

    @tasks.loop(minutes=5.0)
    async def delete_event_messages_task(self):
        events_to_process = db.db_get_events_to_delete_message()
        if not events_to_process: return
        for row in events_to_process:
            try:
                channel = self.bot.get_channel(row['channel_id'])
                if channel and isinstance(channel, discord.TextChannel):
                    msg = await channel.fetch_message(row['message_id'])
                    await msg.delete()
                db.db_clear_message_id_and_update_status_after_delete(row['event_id'], row['status'])
            except (discord.NotFound, discord.Forbidden):
                db.db_clear_message_id_and_update_status_after_delete(row['event_id'], row['status'])
            except Exception as e:
                print(f"Erro ao deletar msg do evento {row['event_id']}: {e}")

    @tasks.loop(minutes=1.0)
    async def event_reminder_task(self):
        events = db.db_get_upcoming_events_for_reminder()
        for event in events:
            guild = self.bot.get_guild(event['guild_id'])
            if not guild: continue
            link = f"https://discord.com/channels/{guild.id}/{event['channel_id']}/{event['message_id']}"
            msg = f"🔔 **Lembrete:** O evento **'{event['title']}'** começa em aproximadamente 15 minutos!\n{link}"
            if event['voice_channel_id']:
                vc = guild.get_channel(event['voice_channel_id'])
                if vc: msg += f"\nCanal de Voz: {vc.mention}"

            attendees = db.db_get_rsvps_for_event(event['event_id']).get('vou', [])
            for user_id in attendees:
                try:
                    user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
                    await user.send(msg)
                    await asyncio.sleep(2)
                except Exception: pass
            db.db_mark_reminder_sent(event['event_id'])

    @tasks.loop(minutes=1.0)
    async def confirmation_reminder_task(self):
        events = db.db_get_events_for_confirmation_reminder()
        for event in events:
            guild = self.bot.get_guild(event['guild_id'])
            if not guild: continue
            attendees = db.db_get_rsvps_for_event(event['event_id']).get('vou', [])
            creator_id = event['creator_id']
            for user_id in attendees:
                if user_id == creator_id: continue
                member = guild.get_member(user_id)
                if not member: continue
                try:
                    view = ConfirmAttendanceView(user_id, event['event_id'], self.bot)
                    msg = await member.send(f"⏳ Lembrete: Evento **'{event['title']}'** em ~1 hora. Ainda pretende comparecer?", view=view)
                    view.message = msg
                    await asyncio.sleep(2)
                except Exception: pass
            db.db_mark_reminder_sent(event['event_id'], "confirmation")

    # Correção: O decorador @tasks.loop agora usa a lista de tempos de constants.py
    @tasks.loop(time=DIGEST_TIMES_BRT)
    async def daily_event_digest_task(self):
        for guild in self.bot.guilds:
            configs = db.db_get_server_configs(guild.id)
            if configs and configs['digest_channel_id']:
                channel = guild.get_channel(configs['digest_channel_id'])
                if channel and isinstance(channel, discord.TextChannel):
                    content = await utils.generate_event_list_message_content(guild.id, 3, self.bot)
                    if "Nenhum evento" not in content:
                        await channel.send(f"**Eventos Agendados:**\n{content}")

    @tasks.loop(hours=1.0)
    async def cleanup_completed_events_task(self):
        events = db.db_get_events_for_cleanup()
        for event in events:
            view = PersistentRsvpView(self.bot)
            await view._update_event_message_embed(event['event_id'], event['channel_id'], event['message_id'])
            guild = self.bot.get_guild(event['guild_id'])
            if guild and event['temp_role_id']:
                await role_utils.delete_event_role(guild, event['temp_role_id'], f"Evento {event['event_id']} concluído.")
            delete_at = datetime.datetime.now(pytz.utc) + datetime.timedelta(hours=24)
            db.db_update_event_status(event['event_id'], 'concluido', delete_after_utc=delete_at.isoformat())
            db.db_update_event_details(event_id=event['event_id'], temp_role_id=None)

    @clan_invite_check_task.before_loop
    @update_leaderboard_task.before_loop
    @update_ranking_roles_task.before_loop
    @inactivity_check_task.before_loop
    @delete_event_messages_task.before_loop
    @event_reminder_task.before_loop
    @confirmation_reminder_task.before_loop
    @daily_event_digest_task.before_loop
    @cleanup_completed_events_task.before_loop
    @attendance_check_task.before_loop
    @manage_event_voice_channels_task.before_loop
    @clan_role_sync_task.before_loop
    async def before_task(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(TasksCog(bot))