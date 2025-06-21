# utils.py
import discord
from discord import app_commands
from discord.ext import commands
# Adicionado para corrigir o NameError e padronizar
from discord.ui import Button, View, Modal, TextInput
import asyncio
import datetime
import pytz
from typing import Optional, List, Tuple, Dict, Set, Any
import sqlite3
from difflib import SequenceMatcher
import re

from constants import (
    BRAZIL_TZ,
    ACTIVITY_SUBTYPES_RAID, ACTIVITY_SUBTYPES_DUNGEON,
    ACTIVITY_SUBTYPES_PVP, ACTIVITY_SUBTYPES_GAMBIT,
    ACTIVITY_SUBTYPES_NIGHTFALL, ACTIVITY_SUBTYPES_EXOTIC,
    ACTIVITY_SUBTYPES_SEASONAL, ACTIVITY_SUBTYPES_OTHER,
    DEFAULT_EVENT_COLOR, EVENT_TYPE_COLORS,
    ALL_ACTIVITIES_PT, RAID_INFO_PT, MASMORRA_INFO_PT, PVP_ACTIVITY_INFO_PT,
    SIMILARITY_THRESHOLD, DIAS_SEMANA_PT_SHORT
)
import database as db
import bungie_api

# --- Funções de Verificação de Permissão ---
async def check_event_permission(interaction: discord.Interaction, permission: str) -> bool:
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        return False
    if interaction.user.guild_permissions.administrator:
        return True
    user_roles_ids: Set[int] = {role.id for role in interaction.user.roles}
    return db.db_check_user_permission(interaction.guild.id, user_roles_ids, permission)

async def is_user_event_manager(interaction: discord.Interaction, event_creator_id: int, permission_to_check: str) -> bool:
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        return False
    member: discord.Member = interaction.user
    if member.id == event_creator_id:
        return True
    return await check_event_permission(interaction, permission_to_check)

# --- Funções Utilitárias ---
def get_brazil_now() -> datetime.datetime:
    return datetime.datetime.now(BRAZIL_TZ)

def parse_event_time(time_str: str) -> Optional[datetime.datetime]:
    now_brt = get_brazil_now()
    date_part_match = re.search(r'(\d{1,2})/(\d{1,2})', time_str)
    event_date = now_brt.date()
    if date_part_match:
        day, month = map(int, date_part_match.groups())
        try:
            event_date = datetime.datetime(now_brt.year, month, day).date()
            if event_date < now_brt.date():
                event_date = datetime.datetime(now_brt.year + 1, month, day).date()
        except ValueError:
            return None
        time_str = re.sub(r'\s*\d{1,2}/\d{1,2}\s*', '', time_str).strip()
    time_str = time_str.replace(":", "")
    if not time_str.isdigit() or not (3 <= len(time_str) <= 4):
        return None
    hour = int(time_str[:-2])
    minute = int(time_str[-2:])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    event_time = datetime.time(hour, minute)
    event_datetime = datetime.datetime.combine(event_date, event_time, tzinfo=BRAZIL_TZ)
    if event_datetime < now_brt and not date_part_match:
        event_datetime += datetime.timedelta(days=1)
    return event_datetime

def detect_activity_type(title: str, description: str) -> str:
    text_to_search = (title + " " + description).lower()
    subtype_map = {
        **{subtype: "Raid" for subtype in ACTIVITY_SUBTYPES_RAID},
        **{subtype: "Dungeon" for subtype in ACTIVITY_SUBTYPES_DUNGEON},
        **{subtype: "PvP" for subtype in ACTIVITY_SUBTYPES_PVP},
        **{subtype: "Gambit" for subtype in ACTIVITY_SUBTYPES_GAMBIT},
        **{subtype: "Anoitecer" for subtype in ACTIVITY_SUBTYPES_NIGHTFALL},
        **{subtype: "Exótica" for subtype in ACTIVITY_SUBTYPES_EXOTIC},
        **{subtype: "Sazonal" for subtype in ACTIVITY_SUBTYPES_SEASONAL},
        **{subtype: "Outro" for subtype in ACTIVITY_SUBTYPES_OTHER}
    }
    for keyword, activity_type in subtype_map.items():
        if re.search(r'\b' + re.escape(keyword) + r'\b', text_to_search, re.IGNORECASE):
            return activity_type
    return "Outro"

def get_event_color(activity_type: str) -> discord.Color:
    return EVENT_TYPE_COLORS.get(activity_type, DEFAULT_EVENT_COLOR)

def format_datetime_for_embed(dt_utc: datetime.datetime) -> tuple[str, str]:
    if dt_utc.tzinfo is None: dt_utc = pytz.utc.localize(dt_utc)
    unix_ts = int(dt_utc.timestamp())
    return f"<t:{unix_ts}:F>", f"<t:{unix_ts}:R>"

async def get_user_display_name_static(user_id: int, bot: commands.Bot, guild: Optional[discord.Guild]) -> str:
    member = guild.get_member(user_id) if guild else None
    if member and member.nick: return member.nick
    try:
        user_obj = bot.get_user(user_id) or await bot.fetch_user(user_id)
        return user_obj.global_name or user_obj.name
    except (discord.NotFound, discord.HTTPException):
        return f"Usuário ({user_id})"

def format_event_line_for_list(row: sqlite3.Row, vou_count: int, guild_id: int) -> str:
    dt_utc = datetime.datetime.fromisoformat(row['event_time_utc'].replace('Z', '+00:00'))
    dt_brt = dt_utc.astimezone(BRAZIL_TZ)
    date_str = f"{DIAS_SEMANA_PT_SHORT[dt_brt.weekday()]}. {dt_brt.strftime('%d/%m')}"
    vagas_disp = row['max_attendees'] - vou_count
    vagas_str = f"{vagas_disp} vagas"
    if vagas_disp <= 0:
        espera_count = len(db.db_get_rsvps_for_event(row['event_id']).get('lista_espera', []))
        vagas_str = f"Lotado (Espera: {espera_count})" if espera_count > 0 else "Lotado"
    elif vagas_disp == 1: vagas_str = "1 vaga"
    link = f"https://discord.com/channels/{guild_id}/{row['channel_id']}/{row['message_id']}"
    return f"[{row['title']} - {date_str} às {dt_brt.strftime('%H:%M')} - {vagas_str}]({link})"

def format_compact_event_line(row: sqlite3.Row) -> str:
    dt_utc = datetime.datetime.fromisoformat(row['event_time_utc'].replace('Z', '+00:00'))
    dt_brt = dt_utc.astimezone(BRAZIL_TZ)
    date_str = dt_brt.strftime('%d/%m')
    link = f"https://discord.com/channels/{row['guild_id']}/{row['channel_id']}/{row['message_id']}"
    return f"[{date_str} - {row['title']}]({link})"

async def generate_event_list_message_content(guild_id: int, days: int, bot: commands.Bot) -> str:
    now_brt = get_brazil_now()
    start_utc = now_brt.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.utc)
    end_utc_detailed = (now_brt + datetime.timedelta(days=days)).replace(hour=23, minute=59, second=59).astimezone(pytz.utc)
    detailed_events = db.db_get_events_for_digest_list(guild_id, start_utc, end_utc_detailed)
    far_future_events = db.db_get_far_future_events(guild_id, end_utc_detailed)
    if not detailed_events and not far_future_events:
        return "Nenhum evento agendado para o futuro."
    message_parts = []
    if detailed_events:
        message_parts.append(f"**Próximos {days} Dias:**")
        detailed_lines = [format_event_line_for_list(er, len(db.db_get_rsvps_for_event(er['event_id']).get('vou', [])), guild_id) for er in detailed_events]
        message_parts.append("\n".join(detailed_lines))
    if far_future_events:
        message_parts.append("\n**Eventos Futuros:**" if message_parts else "**Eventos Futuros:**")
        compact_lines = [format_compact_event_line(er) for er in far_future_events]
        message_parts.append("\n".join(compact_lines))
    return "\n".join(message_parts)

async def get_text_channels_for_select(guild: discord.Guild, bot_user: discord.ClientUser) -> list[discord.SelectOption]:
    options: List[discord.SelectOption] = []
    designated_ids = db.db_get_designated_event_channels(guild.id)
    if not designated_ids: return options
    bot_member = guild.get_member(bot_user.id)
    if not bot_member: return options
    for cid in designated_ids:
        ch = guild.get_channel(cid)
        if ch and isinstance(ch, discord.TextChannel) and ch.permissions_for(bot_member).send_messages:
            options.append(discord.SelectOption(label=f"#{ch.name}", value=str(ch.id)))
            if len(options) >= 25: break
    return options

def detect_activity_details(name_input: str) -> tuple[str, str | None, int | None]:
    name_lower = name_input.lower().strip()
    best_match, best_type, best_spots, highest_sim = name_input.strip(), None, None, 0.0
    for official, keywords in ALL_ACTIVITIES_PT.items():
        sim_off = SequenceMatcher(None, name_lower, official.lower()).ratio()
        if sim_off > highest_sim: highest_sim, best_match = sim_off, official
        for kw in keywords:
            sim_kw = SequenceMatcher(None, name_lower, kw.lower()).ratio()
            if sim_kw > highest_sim: highest_sim, best_match = sim_kw, official
        if highest_sim == 1.0 and best_match == official: break
    if highest_sim >= SIMILARITY_THRESHOLD:
        if best_match in RAID_INFO_PT: best_type, best_spots = "Raid", 6
        elif best_match in MASMORRA_INFO_PT: best_type, best_spots = "Dungeon", 3
        elif best_match in PVP_ACTIVITY_INFO_PT: best_type, best_spots = "PvP", 3
        return best_match, best_type, best_spots
    return name_input.strip(), None, None

def detect_and_format_event_subtype(title: str, description: Optional[str]) -> str:
    if not description: return title
    subtype_map = {'mestre': ' (Mestre)', 'escola': ' (Escola)', 'farm': ' (Farm)', 'triunfo': ' (Triunfo)', 'catalisador': ' (Catalisador)'}
    desc_lower = description.lower()
    for keyword, tag in subtype_map.items():
        if keyword in desc_lower and tag.lower() not in title.lower():
            return f"{title}{tag}"
    return title

async def create_event_embed(bot: commands.Bot, event_id: int) -> Optional[discord.Embed]:
    event_details = db.db_get_event_details(event_id)
    if not event_details: return None
    rsvps = db.db_get_rsvps_for_event(event_id)
    attendees = rsvps.get('vou', [])
    maybe = rsvps.get('talvez', [])
    waitlist = attendees[event_details['max_attendees']:]
    attendees = attendees[:event_details['max_attendees']]
    creator = await bot.fetch_user(event_details['creator_id'])
    event_time_utc = datetime.datetime.fromisoformat(event_details['event_time_utc'])
    color = get_event_color(event_details['activity_type'])
    embed = discord.Embed(title=f"**{event_details['title']}**", description=event_details['description'], color=color)
    embed.set_author(name=f"Criado por {creator.display_name}", icon_url=creator.avatar.url if creator.avatar else None)
    fmt_date, rel_time = format_datetime_for_embed(event_time_utc)
    embed.add_field(name="🗓️ Data e Hora", value=f"{fmt_date} ({rel_time})", inline=False)
    attendees_mentions = [f"<@{uid}>" for uid in attendees]
    maybe_mentions = [f"<@{uid}>" for uid in maybe]
    waitlist_mentions = [f"<@{uid}>" for uid in waitlist]
    embed.add_field(name=f"✅ Confirmados ({len(attendees)}/{event_details['max_attendees']})", value="\n".join(attendees_mentions) or "Ninguém.", inline=True)
    embed.add_field(name=f"🤔 Talvez ({len(maybe)})", value="\n".join(maybe_mentions) or "Ninguém.", inline=True)
    if waitlist: embed.add_field(name=f"⌛ Lista de Espera ({len(waitlist)})", value="\n".join(waitlist_mentions), inline=True)
    if event_details['status'] == 'cancelado':
        embed.color = discord.Color.dark_red(); embed.title = f"**[CANCELADO]** {event_details['title']}"
    elif event_details['status'] == 'concluido':
        embed.color = discord.Color.dark_grey(); embed.title = f"**[CONCLUÍDO]** {event_details['title']}"
    embed.set_footer(text=f"ID do Evento: {event_id} | Tipo: {event_details['activity_type']}")
    return embed

# --- Views ---
class EventModal(Modal):
    def __init__(self, bot: commands.Bot, event_details: Optional[Dict] = None):
        super().__init__(title="Agendar Novo Evento" if not event_details else "Editar Evento")
        self.bot = bot
        self.event_details = event_details
        self.title_input = TextInput(label="Título", placeholder="Ex: Raid A Última Testemunha (Mestre)", default=event_details.get('title', '') if event_details else '', max_length=100)
        self.description_input = TextInput(label="Descrição e Requisitos", style=discord.TextStyle.paragraph, placeholder="Ex: Farmar a exótica. Levar Gjallarhorn.", default=event_details.get('description', '') if event_details else '', max_length=1024)
        self.time_input = TextInput(label="Horário (HH:MM) e Data opcional (DD/MM)", placeholder="Ex: 21:30 ou 21:30 25/12", default=event_details.get('time_str', '') if event_details else '', max_length=20)
        self.max_attendees_input = TextInput(label="Máximo de Participantes (padrão: 6)", default=str(event_details.get('max_attendees', 6)) if event_details else '6', max_length=2)
        self.add_item(self.title_input); self.add_item(self.description_input); self.add_item(self.time_input); self.add_item(self.max_attendees_input)

class ConfirmActivityView(View):
    def __init__(self, original_interaction: discord.Interaction, detected_title: str, detected_type: Optional[str], detected_spots: Optional[int]):
        super().__init__(timeout=180.0)
        self.original_interaction = original_interaction; self.confirmed: Optional[bool] = None
        self.message: Optional[discord.Message] = None; self.detected_title = detected_title
        self.detected_type = detected_type; self.detected_spots = detected_spots
        self.confirmation_message_content = f"Entendi como: **{detected_title}**"
        if detected_type and detected_spots: self.confirmation_message_content += f" (Tipo: {detected_type}, Vagas: {detected_spots}p)."
        else: self.confirmation_message_content += "."
        self.confirmation_message_content += "\nIsso está correto?"
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.original_interaction.user.id:
            await interaction.response.send_message("Você não pode interagir.", ephemeral=True); return False
        return True
    async def disable_all_items(self):
        for item in self.children:
            if hasattr(item, 'disabled'): item.disabled = True
        if self.message: await self.message.edit(view=self)
    @discord.ui.button(label="Sim", style=discord.ButtonStyle.success)
    async def confirm_yes(self, i: discord.Interaction, b: Button): self.confirmed = True; await self.disable_all_items(); self.stop()
    @discord.ui.button(label="Não", style=discord.ButtonStyle.danger)
    async def confirm_no(self, i: discord.Interaction, b: Button): self.confirmed = False; await self.disable_all_items(); self.stop()
    async def on_timeout(self):
        self.confirmed = None; await self.disable_all_items()
        if self.message: await self.message.edit(content=self.confirmation_message_content + "\n*Tempo esgotado.*", view=self)
        self.stop()

class SelectActivityDetailsView(View):
    def __init__(self, bot: commands.Bot, original_interaction: discord.Interaction):
        super().__init__(timeout=180.0)
        self.bot = bot; self.original_interaction = original_interaction
        self.selected_activity_type: Optional[str] = None
        self.selected_max_attendees: Optional[int] = None
        self.message: Optional[discord.Message] = None
        self.activity_options = {"raid": ("Raid", 6), "dungeon": ("Dungeon", 3), "pvp": ("PvP", 3), "other": ("Outro", 6)}
        for key, (label, _) in self.activity_options.items():
            b = Button(label=label, custom_id=key, style=discord.ButtonStyle.primary)
            b.callback = self.button_callback; self.add_item(b)
    async def interaction_check(self, i: discord.Interaction) -> bool:
        if i.user.id != self.original_interaction.user.id: await i.response.send_message("Não é pra vc.", ephemeral=True); return False
        return True
    async def button_callback(self, interaction: discord.Interaction):
        custom_id = interaction.data["custom_id"]
        self.selected_activity_type, self.selected_max_attendees = self.activity_options[custom_id]
        for item in self.children: item.disabled = True
        await interaction.response.edit_message(content=f"Tipo selecionado: {self.selected_activity_type}", view=self)
        self.stop()

class SelectChannelView(View):
    def __init__(self, bot: commands.Bot, original_interaction: discord.Interaction, text_channels_options: list[discord.SelectOption]):
        super().__init__(timeout=180.0)
        self.bot = bot; self.original_interaction = original_interaction
        self.selected_channel_id: Optional[int] = None
        self.message: Optional[discord.Message] = None
        if not text_channels_options: self.add_item(Button(label="Nenhum canal configurado", disabled=True)); return
        self.channel_select = discord.ui.Select(placeholder="Selecione o canal...", options=text_channels_options)
        self.channel_select.callback = self.on_select; self.add_item(self.channel_select)
    async def interaction_check(self, i: discord.Interaction) -> bool:
        if i.user.id != self.original_interaction.user.id: await i.response.send_message("Não é pra vc.", ephemeral=True); return False
        return True
    async def on_select(self, interaction: discord.Interaction):
        self.selected_channel_id = int(self.channel_select.values[0])
        self.channel_select.disabled = True
        await interaction.response.edit_message(content=f"Canal selecionado: <#{self.selected_channel_id}>.", view=self)
        self.stop()

class ConfirmAttendanceView(View):
    def __init__(self, user_id: int, event_id: int, bot: commands.Bot):
        super().__init__(timeout=3600)
        self.user_id = user_id; self.event_id = event_id
        self.bot = bot; self.message: Optional[discord.Message] = None
    async def on_timeout(self):
        if self.message: await self.message.edit(content="Lembrete expirou.", view=None)
    @discord.ui.button(label="Sim, vou", style=discord.ButtonStyle.success)
    async def confirm(self, i: discord.Interaction, b: Button):
        if i.user.id != self.user_id: await i.response.send_message("Não é pra vc.", ephemeral=True); return
        await i.response.edit_message(content="Presença confirmada!", view=None)
    @discord.ui.button(label="Não vou", style=discord.ButtonStyle.danger)
    async def cancel(self, i: discord.Interaction, b: Button):
        if i.user.id != self.user_id: await i.response.send_message("Não é pra vc.", ephemeral=True); return
        db.db_add_or_update_rsvp(self.event_id, self.user_id, 'nao_vou')
        from cogs.event_cog import PersistentRsvpView
        rsvp_view = PersistentRsvpView(self.bot)
        event_details = db.db_get_event_details(self.event_id)
        if event_details and event_details['message_id']:
            await rsvp_view._update_event_message_embed(self.event_id, event_details['channel_id'], event_details['message_id'])
        await i.response.edit_message(content="RSVP atualizado para 'Não vou'.", view=None)

class ClanInviteView(View):
    def __init__(self, applicant_info: Dict[str, Any]):
        super().__init__(timeout=None) 
        self.applicant_info = applicant_info; self.membership_id = applicant_info['membership_id']
        self.membership_type = applicant_info['membership_type']; self.bungie_name = applicant_info['bungie_name']
        self.custom_id_prefix = f"clan_invite_view_{self.membership_id}"
        self.approve_button.custom_id = f"{self.custom_id_prefix}_approve"
        self.deny_button.custom_id = f"{self.custom_id_prefix}_deny"
    async def handle_interaction(self, interaction: discord.Interaction, action: str):
        await interaction.response.defer()
        if not interaction.guild or not interaction.guild_id: return
        configs = db.db_get_server_configs(interaction.guild_id)
        if not configs or not configs.get('clan_admin_discord_id'):
            await interaction.followup.send("Admin do Clã não configurado.", ephemeral=True); return
        admin_id = configs['clan_admin_discord_id']; success = False
        if action == "approve": success = await bungie_api.approve_pending_invitation(admin_id, self.membership_id, self.membership_type)
        elif action == "deny": success = await bungie_api.deny_pending_invitation(admin_id, self.membership_id, self.membership_type)
        if not interaction.message: return
        original_embed = interaction.message.embeds[0]
        if success:
            action_text = "aprovado" if action == "approve" else "recusado"
            original_embed.color = discord.Color.green() if action == "approve" else discord.Color.red()
            original_embed.set_footer(text=f"Pedido {action_text} por {interaction.user.display_name}")
            for item in self.children:
                if isinstance(item, Button): item.disabled = True
            await interaction.message.edit(embed=original_embed, view=self)
            db.db_untrack_pending_invite(self.membership_id)
            if action == "approve":
                role_msg = ""
                clan_role_id = configs.get('clan_role_id')
                if clan_role_id:
                    bungie_profile = db.db_get_bungie_profile_by_bnet_id(self.membership_id)
                    if bungie_profile and bungie_profile.get('discord_id'):
                        member = interaction.guild.get_member(bungie_profile['discord_id'])
                        clan_role = interaction.guild.get_role(clan_role_id)
                        if member and clan_role:
                            await member.add_roles(clan_role, reason=f"Aceito no clã por {interaction.user.display_name}")
                            role_msg = f" Cargo {clan_role.mention} atribuído a {member.mention}."
                        elif clan_role:
                            role_msg = f" Usuário vinculado (<@{bungie_profile['discord_id']}>) não encontrado."
                    else: role_msg = " Perfil do Discord não vinculado."
                await interaction.followup.send(f"✅ **{self.bungie_name}** foi aceito.{role_msg}", ephemeral=False)
            else: await interaction.followup.send(f"🗑️ Pedido de **{self.bungie_name}** recusado.", ephemeral=False)
        else: await interaction.followup.send(f"❌ Falha ao processar API. Verifique os logs.", ephemeral=True)
    @discord.ui.button(label="Aceitar", style=discord.ButtonStyle.success)
    async def approve_button(self, i: discord.Interaction, b: Button): await self.handle_interaction(i, "approve")
    @discord.ui.button(label="Recusar", style=discord.ButtonStyle.danger)
    async def deny_button(self, i: discord.Interaction, b: Button): await self.handle_interaction(i, "deny")