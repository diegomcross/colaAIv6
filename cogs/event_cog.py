# cogs/event_cog.py
import discord
from discord import app_commands, ui
from discord.ext import commands
import asyncio
import datetime
import sqlite3
import pytz
import re
from typing import Literal, Optional, List, Dict, Any

import dateparser

# Imports customizados
import database as db
import utils 
import role_utils 
from constants import (
    BRAZIL_TZ, BRAZIL_TZ_STR,
    DIAS_SEMANA_PT_FULL, DIAS_SEMANA_PT_SHORT, MESES_PT
)
from utils import SelectChannelView, SelectActivityDetailsView, ConfirmActivityView


# --- Modals ---
# Refatorado de EditEventModal para um EventModal mais genérico
class EventModal(discord.ui.Modal, title="✏️ Agendar / Editar Evento"):
    def __init__(self, bot_instance: commands.Bot, parent_view_instance, event_details: Optional[Dict[str, Any]] = None):
        super().__init__(timeout=None)
        self.bot = bot_instance
        self.parent_view_instance = parent_view_instance
        self.is_edit = event_details is not None
        self.event_id = event_details.get('event_id') if self.is_edit else None

        # Define os valores padrão com base em se é uma edição ou criação
        title_default = event_details.get('title', '') if self.is_edit else ''
        description_default = event_details.get('description') if self.is_edit and event_details.get('description') else ''
        time_default = ""
        if self.is_edit and event_details.get('event_time_utc'):
            dt_utc = datetime.datetime.fromisoformat(event_details['event_time_utc'].replace('Z', '+00:00'))
            dt_brt = dt_utc.astimezone(BRAZIL_TZ)
            time_default = dt_brt.strftime('%d/%m %H:%M')

        self.event_title_input = ui.TextInput(label="Título do Evento", default=title_default, required=True, max_length=200)
        self.event_description_input = ui.TextInput(label="Descrição (ou 'x' para remover)", style=discord.TextStyle.paragraph, default=description_default, required=False, max_length=1000)
        self.event_datetime_input = ui.TextInput(label="Data e Hora", placeholder="Ex: 25/12 19:30, amanhã 21h", default=time_default, required=True)
        self.max_attendees_input = ui.TextInput(label="Nº de Vagas", default=str(event_details.get('max_attendees', 6)) if self.is_edit else '6', required=True)

        self.add_item(self.event_title_input)
        self.add_item(self.event_description_input)
        self.add_item(self.event_datetime_input)
        self.add_item(self.max_attendees_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        parser_settings = {'TIMEZONE': BRAZIL_TZ_STR, 'RETURN_AS_TIMEZONE_AWARE': True, 'PREFER_DATES_FROM': 'future'}
        parsed_dt_brt = dateparser.parse(self.event_datetime_input.value.strip(), languages=['pt'], settings=parser_settings)

        if not parsed_dt_brt or parsed_dt_brt < utils.get_brazil_now():
            await interaction.followup.send("Data/hora inválida ou no passado. Use formatos como '25/12 21:00' ou 'amanhã às 22h'.", ephemeral=True)
            return

        try:
            max_attendees = int(self.max_attendees_input.value)
            if not 1 <= max_attendees <= 100: raise ValueError()
        except ValueError:
            await interaction.followup.send("Número de vagas inválido. Use um número de 1 a 100.", ephemeral=True)
            return

        desc_value = self.event_description_input.value.strip()
        final_description = None if desc_value.lower() == 'x' else (desc_value or (None if self.is_edit else None))

        event_data = {
            "title": self.event_title_input.value,
            "description": final_description,
            "event_time_utc": parsed_dt_brt.astimezone(pytz.utc).isoformat(),
            "max_attendees": max_attendees,
            "activity_type": utils.detect_activity_type(self.event_title_input.value, final_description or "")
        }

        if self.is_edit and self.event_id:
            db.db_update_event_details(self.event_id, **event_data)
            await interaction.followup.send("✅ Evento atualizado com sucesso!", ephemeral=True)
            original_event = db.db_get_event_details(self.event_id)
            if original_event and original_event['message_id']:
                await self.parent_view_instance._update_event_message_embed(self.event_id, original_event['channel_id'], original_event['message_id'])
        else:
            event_id = db.db_create_event(
                guild_id=interaction.guild_id, channel_id=interaction.channel_id,
                creator_id=interaction.user.id, created_at_utc=datetime.datetime.now(pytz.utc).isoformat(),
                **event_data
            )
            if event_id:
                await interaction.followup.send(f"✅ Evento `{event_id}` criado com sucesso!", ephemeral=True)
                target_channel = self.bot.get_channel(interaction.channel_id)
                if isinstance(target_channel, discord.TextChannel):
                    await self.parent_view_instance.send_initial_message(target_channel, event_id)
            else:
                await interaction.followup.send("❌ Erro ao salvar o evento no banco de dados.", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        print(f"Erro no EventModal: {error}"); import traceback; traceback.print_exc()
        msg = "Ocorreu um erro crítico. Verifique o console."
        if interaction.response.is_done(): await interaction.followup.send(msg, ephemeral=True)
        else: await interaction.response.send_message(msg, ephemeral=True)


class EditOptionsView(discord.ui.View):
    def __init__(self, bot_instance: commands.Bot, event_id: int, original_interaction: discord.Interaction, parent_view_instance):
        super().__init__(timeout=180.0)
        self.bot = bot_instance
        self.event_id = event_id
        self.original_interaction = original_interaction
        self.message_with_options: Optional[discord.Message] = None
        self.parent_view_instance = parent_view_instance

    async def disable_all_buttons(self, interaction_to_edit: Optional[discord.Interaction] = None, content: Optional[str] = None):
        for item in self.children:
            if isinstance(item, discord.ui.Button): item.disabled = True
        final_content = content or "Opções desabilitadas."
        if interaction_to_edit and not interaction_to_edit.response.is_done():
            await interaction_to_edit.response.edit_message(content=final_content, view=self)
        elif self.message_with_options:
            try: await self.message_with_options.edit(content=final_content, view=self)
            except: pass
        self.stop()

    @discord.ui.button(label="Título/Desc/Data/Hora", style=discord.ButtonStyle.green, custom_id="edit_basic_details_opt", emoji="📝")
    async def edit_basic_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        event_details = db.db_get_event_details(self.event_id)
        if not event_details:
            await interaction.response.send_message("Evento não encontrado.", ephemeral=True)
            await self.disable_all_buttons(interaction, "Erro: Evento não encontrado."); return
        # AQUI USAMOS O NOVO EventModal PARA EDIÇÃO
        modal = EventModal(self.bot, self.parent_view_instance, event_details=dict(event_details))
        await interaction.response.send_modal(modal)
        if self.message_with_options:
            try: await self.message_with_options.edit(content="Modal de edição aberto.", view=None)
            except: pass
        self.stop()

    @discord.ui.button(label="Tipo/Vagas", style=discord.ButtonStyle.primary, custom_id="edit_type_spots_opt", emoji="⚙️")
    async def edit_type_spots_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        user = interaction.user
        dm_channel = await user.create_dm()
        event_details = db.db_get_event_details(self.event_id)
        if not event_details:
            await dm_channel.send("Erro: Evento não encontrado."); self.stop(); return
        await interaction.followup.send("Edição de Tipo/Vagas continuará na sua DM.", ephemeral=True)
        if self.message_with_options:
            try: await self.message_with_options.edit(content="Edição movida para DM.", view=None)
            except: pass
        await dm_channel.send(f"Editando Tipo/Vagas para: **{event_details['title']}**\nTipo: `{event_details['activity_type']}`, Vagas: `{event_details['max_attendees']}`")
        type_details_view = utils.SelectActivityDetailsView(self.bot, interaction)
        type_details_msg_dm = await dm_channel.send("Selecione o novo tipo de atividade:", view=type_details_view)
        type_details_view.message = type_details_msg_dm
        await type_details_view.wait()
        if type_details_view.selected_activity_type and type_details_view.selected_max_attendees is not None:
            new_activity_type = type_details_view.selected_activity_type
            new_max_attendees = type_details_view.selected_max_attendees
            if new_activity_type != event_details['activity_type'] or new_max_attendees != event_details['max_attendees']:
                db.db_update_event_details(event_id=self.event_id, activity_type=new_activity_type, max_attendees=new_max_attendees)
                await dm_channel.send(f"Tipo/Vagas atualizados para '{new_activity_type}' ({new_max_attendees} vagas).")
                if self.parent_view_instance and event_details['channel_id'] and event_details['message_id']:
                    await self.parent_view_instance._update_event_message_embed(self.event_id, event_details['channel_id'], event_details['message_id'])
            else:
                await dm_channel.send("Tipo/Vagas mantidos como os atuais.")
        else:
            await dm_channel.send("Edição de tipo/vagas cancelada ou tempo esgotado.")
        self.stop()

    @discord.ui.button(label="Cancelar Edição", style=discord.ButtonStyle.grey, custom_id="cancel_edit_flow_opt", emoji="↩️")
    async def cancel_edit_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.message_with_options: await self.message_with_options.edit(content="Edição cancelada.", view=None)
        self.stop()

    async def on_timeout(self):
        await self.disable_all_buttons(None, "Tempo esgotado para escolher opção de edição.")
        self.stop()

class ConfirmDeleteView(discord.ui.View):
    def __init__(self, bot_instance: commands.Bot, event_id: int, original_button_interaction: discord.Interaction, parent_view_instance):
        super().__init__(timeout=60.0)
        self.bot = bot_instance; self.event_id = event_id
        self.original_button_interaction = original_button_interaction
        self.message_sent_for_confirmation: Optional[discord.Message] = None
        self.parent_view_instance = parent_view_instance

    async def disable_all_buttons(self, content: Optional[str] = None):
        for item in self.children:
            if isinstance(item, discord.ui.Button): item.disabled = True
        if self.message_sent_for_confirmation:
            try: await self.message_sent_for_confirmation.edit(content=content or "Ação processada.", view=self)
            except: pass
        self.stop()

    @discord.ui.button(label="Sim, Apagar Evento", style=discord.ButtonStyle.danger, custom_id="confirm_delete_event_yes")
    async def confirm_yes_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer() 
        event_details = db.db_get_event_details(self.event_id)
        if not event_details:
            await self.disable_all_buttons("Erro: Evento não encontrado.");
            await self.original_button_interaction.followup.send("Erro: Evento não encontrado ao apagar.", ephemeral=True); return

        attendees_to_notify = db.db_get_rsvps_for_event(self.event_id).get('vou', [])
        notification_message = f"ℹ️ O evento **'{event_details['title']}'** para o qual você estava inscrito(a) foi cancelado."
        for user_id_notify in attendees_to_notify:
            try:
                member_to_notify = await self.bot.fetch_user(user_id_notify)
                if not member_to_notify.bot:
                    await member_to_notify.send(notification_message)
                    await asyncio.sleep(1)
            except Exception as e_dm_cancel:
                print(f"WARN: Não foi possível enviar DM de cancelamento para {user_id_notify}: {e_dm_cancel}")

        delete_time = datetime.datetime.now(pytz.utc) + datetime.timedelta(hours=1)
        db.db_update_event_status(self.event_id, 'cancelado', delete_time.isoformat())
        db.db_update_event_details(event_id=self.event_id, temp_role_id=None)

        if event_details['message_id'] and event_details['channel_id'] and self.parent_view_instance:
            await self.parent_view_instance._update_event_message_embed(self.event_id, event_details['channel_id'], event_details['message_id'])

        final_msg = f"Evento '{event_details['title']}' cancelado. Mensagem será apagada em 1h."
        await self.disable_all_buttons(final_msg)
        await self.original_button_interaction.followup.send(final_msg, ephemeral=True)
        self.stop()

    @discord.ui.button(label="Não, Manter Evento", style=discord.ButtonStyle.secondary, custom_id="confirm_delete_event_no")
    async def confirm_no_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(); await self.disable_all_buttons("Operação de apagar cancelada.")
        await self.original_button_interaction.followup.send("Cancelamento abortado.", ephemeral=True); self.stop()

    async def on_timeout(self):
        await self.disable_all_buttons("Tempo esgotado. Apagar cancelado.")
        self.stop()

class PersistentRsvpView(discord.ui.View):
    def __init__(self, bot_instance: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot_instance

    async def _extract_event_id_from_interaction(self, interaction: discord.Interaction) -> int | None:
        if not interaction.message or not interaction.message.embeds or not interaction.message.embeds[0].footer: return None
        footer = interaction.message.embeds[0].footer.text
        match = re.search(r"ID do Evento:\s*(\d+)", footer)
        if not match: return None
        return int(match.group(1))

    async def _handle_rsvp_logic(self, interaction: discord.Interaction, new_status: str, event_id: int):
        await interaction.response.defer(ephemeral=True)
        event_details = db.db_get_event_details(event_id)
        if not event_details: return
        db.db_add_or_update_rsvp(event_id, interaction.user.id, new_status)
        await self._update_event_message_embed(event_id, event_details['channel_id'], event_details['message_id'])
        await interaction.followup.send(f"Sua resposta foi atualizada para '{new_status}'.", ephemeral=True)

    async def _update_event_message_embed(self, event_id: int, channel_id: int, message_id: int | None):
        if message_id is None: return
        try:
            target_channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
            if not isinstance(target_channel, discord.TextChannel): return
            message_to_edit = await target_channel.fetch_message(message_id)
            event_details = db.db_get_event_details(event_id)
            if not event_details: return
            if event_details['status'] in ['cancelado', 'concluido']:
                embed = message_to_edit.embeds[0]
                embed.title = f"[{event_details['status'].upper()}] {embed.title}"
                embed.color = discord.Color.dark_grey()
                await message_to_edit.edit(embed=embed, view=None)
                return
            rsvps_data = db.db_get_rsvps_for_event(event_id)
            embed = await utils.build_event_embed(event_details, rsvps_data, self.bot)
            await message_to_edit.edit(embed=embed, view=self)
        except Exception as e:
            print(f"ERRO em _update_event_message_embed: {e}")

    async def send_initial_message(self, channel: discord.TextChannel, event_id: int):
        event_details = db.db_get_event_details(event_id)
        if not event_details: return
        rsvps_data = db.db_get_rsvps_for_event(event_id)
        embed = await utils.build_event_embed(event_details, rsvps_data, self.bot)
        message = await channel.send(embed=embed, view=self)
        db.db_update_event_message_id(event_id, message.id)

    @discord.ui.button(label=None, emoji="✅", style=discord.ButtonStyle.secondary, custom_id="persistent_rsvp_vou")
    async def vou_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        event_id = await self._extract_event_id_from_interaction(interaction)
        if event_id is not None: await self._handle_rsvp_logic(interaction, "vou", event_id)

    @discord.ui.button(label=None, emoji="❌", style=discord.ButtonStyle.secondary, custom_id="persistent_rsvp_nao_vou")
    async def nao_vou_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        event_id = await self._extract_event_id_from_interaction(interaction)
        if event_id is not None: await self._handle_rsvp_logic(interaction, "nao_vou", event_id)

    @discord.ui.button(label=None, emoji="🔷", style=discord.ButtonStyle.secondary, custom_id="persistent_rsvp_talvez")
    async def talvez_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        event_id = await self._extract_event_id_from_interaction(interaction)
        if event_id is not None: await self._handle_rsvp_logic(interaction, "talvez", event_id)

    @discord.ui.button(label="Editar", emoji="📝", style=discord.ButtonStyle.secondary, custom_id="persistent_event_edit")
    async def edit_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        event_id = await self._extract_event_id_from_interaction(interaction)
        if event_id is None: return
        event_details = db.db_get_event_details(event_id)
        if not await utils.is_user_event_manager(interaction, event_details['creator_id'], 'editar_qualquer_evento'):
            return await interaction.response.send_message("Você não tem permissão para editar este evento.", ephemeral=True)
        edit_view = EditOptionsView(self.bot, event_id, interaction, self)
        msg = await interaction.response.send_message("O que você deseja editar?", view=edit_view, ephemeral=True)
        edit_view.message_with_options = await interaction.original_response()

    @discord.ui.button(label="Apagar", emoji="🗑️", style=discord.ButtonStyle.danger, custom_id="persistent_event_delete")
    async def delete_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        event_id = await self._extract_event_id_from_interaction(interaction)
        if event_id is None: return
        event_details = db.db_get_event_details(event_id)
        if not await utils.is_user_event_manager(interaction, event_details['creator_id'], 'apagar_qualquer_evento'):
            return await interaction.response.send_message("Você não tem permissão para apagar este evento.", ephemeral=True)
        confirm_view = ConfirmDeleteView(self.bot, event_id, interaction, self)
        msg = await interaction.response.send_message(f"Tem certeza que deseja apagar o evento '{event_details['title']}'?", view=confirm_view, ephemeral=True)
        confirm_view.message_sent_for_confirmation = await interaction.original_response()

class EventCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.persistent_view = PersistentRsvpView(self.bot)
        self.bot.add_view(self.persistent_view)

    @app_commands.command(name="agendar", description="Cria um novo evento usando um formulário rápido.")
    @app_commands.guild_only()
    async def agendar(self, interaction: discord.Interaction):
        if not await utils.check_event_permission(interaction, 'criar_eventos'):
            return await interaction.response.send_message("Você não tem permissão para criar eventos.", ephemeral=True)
        allowed_channels = db.db_get_designated_event_channels(interaction.guild.id)
        if allowed_channels and interaction.channel.id not in allowed_channels:
            mentions = " ".join([f"<#{cid}>" for cid in allowed_channels])
            return await interaction.response.send_message(f"Eventos só podem ser criados em: {mentions}", ephemeral=True)
        modal = EventModal(self.bot, self.persistent_view, event_details=None)
        await interaction.response.send_modal(modal)

    @app_commands.command(name="criar_evento", description="Cria um novo evento de Destiny 2 (via DM).")
    @app_commands.guild_only()
    async def criar_evento(self, interaction: discord.Interaction):
        if not await utils.check_event_permission(interaction, 'criar_eventos'):
            await interaction.response.send_message("Você não tem permissão para criar eventos.", ephemeral=True)
            return

        user = interaction.user
        event_data = { "guild_id": interaction.guild_id, "creator_id": user.id, "created_at_utc": datetime.datetime.now(pytz.utc).isoformat() }
        try:
            await interaction.response.send_message("✅ DM enviada! Vamos continuar a criação do evento por lá.", ephemeral=True)
            dm_channel = await user.create_dm()
        except discord.Forbidden:
            await interaction.followup.send("Não consegui te enviar uma DM.", ephemeral=True); return
        except Exception as e:
            await interaction.followup.send(f"Ocorreu um erro: {e}", ephemeral=True); return

        # ... O resto do seu fluxo de criação por DM continua aqui, inalterado...
        title = await utils.ask_question_with_format(user, self.bot, "Qual será o nome do seu evento?")
        # ... etc.

    @app_commands.command(name="lista", description="Lista os eventos dos próximos 3 dias.")
    @app_commands.guild_only()
    async def lista_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        content = await utils.generate_event_list_message_content(interaction.guild_id, 3, self.bot)
        await interaction.followup.send(f"**Eventos Agendados:**\n{content}", ephemeral=True)

    @app_commands.command(name="gerenciar_rsvp", description="Adiciona, remove ou altera o status de RSVP de um usuário.")
    @app_commands.guild_only()
    @app_commands.describe(id_do_evento="ID do evento.", acao="Ação a ser realizada.", usuario="Usuário para gerenciar.")
    @app_commands.choices(acao=[
        app_commands.Choice(name="Definir 'Vou'", value="vou"),
        app_commands.Choice(name="Definir 'Lista de Espera'", value="lista_espera"),
        app_commands.Choice(name="Definir 'Talvez'", value="talvez"),
        app_commands.Choice(name="Definir 'Não Vou'", value="nao_vou"),
        app_commands.Choice(name="Remover RSVP", value="remover")
    ])
    async def gerenciar_rsvp(self, interaction: discord.Interaction, id_do_evento: int, acao: Literal['vou', 'lista_espera', 'talvez', 'nao_vou', 'remover'], usuario: discord.Member):
        await interaction.response.defer(ephemeral=True)
        event_details = db.db_get_event_details(id_do_evento)
        if not event_details:
            return await interaction.followup.send(f"Evento com ID {id_do_evento} não encontrado.", ephemeral=True)
        if not await utils.is_user_event_manager(interaction, event_details['creator_id'], 'gerir_rsvp_qualquer_evento'):
            return await interaction.followup.send("Você não tem permissão para gerenciar os RSVPs deste evento.", ephemeral=True)
        if acao == 'remover':
            db.db_remove_rsvp(id_do_evento, usuario.id)
            action_desc = "RSVP removido"
        else:
            db.db_add_or_update_rsvp(id_do_evento, usuario.id, acao)
            action_desc = f"status definido para '{acao}'"

        await self.persistent_view._update_event_message_embed(id_do_evento, event_details['channel_id'], event_details['message_id'])
        await interaction.followup.send(f"✅ {action_desc} para o usuário {usuario.mention} no evento ID {id_do_evento}.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(EventCog(bot))