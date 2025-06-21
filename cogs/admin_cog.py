# cogs/admin_cog.py
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List, Dict

import database as db
import utils
from constants import EVENT_TYPE_COLORS

RANKING_ROLES_CONFIG = {
    1: {"name": "Turista da Torre", "color": discord.Color.light_grey()},
    2: {"name": "Arauto do Destino", "color": discord.Color.green()},
    3: {"name": "Guardião do Limiar", "color": discord.Color.blue()},
    4: {"name": "Mestre dos Confins", "color": discord.Color.gold()}
}

class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Alteração: Removido default_permissions para tornar os comandos visíveis a todos,
    # com a verificação de permissão feita dentro de cada comando.
    admin_group = app_commands.Group(name="configurar", description="Comandos de configuração para administradores.", guild_only=True)

    def is_owner_or_admin(self, interaction: discord.Interaction) -> bool:
        """Verifica se o usuário é o dono do servidor ou um administrador."""
        return interaction.user.id == interaction.guild.owner_id or interaction.user.guild_permissions.administrator

    @admin_group.command(name="canal_eventos", description="Adiciona ou remove um canal para postagem de eventos.")
    @app_commands.describe(canal="O canal onde os eventos serão postados.", acao="Adicionar ou remover o canal.")
    @app_commands.choices(acao=[
        app_commands.Choice(name="Adicionar", value="add"),
        app_commands.Choice(name="Remover", value="remove")
    ])
    async def configurar_canal_eventos(self, interaction: discord.Interaction, canal: discord.TextChannel, acao: app_commands.Choice[str]):
        if not self.is_owner_or_admin(interaction):
            await interaction.response.send_message("Este comando é restrito ao dono do servidor ou administradores.", ephemeral=True)
            return
        if not interaction.guild_id: return

        if acao.value == "add":
            db.db_add_designated_event_channel(interaction.guild_id, canal.id)
            await interaction.response.send_message(f"✅ O canal {canal.mention} foi adicionado à lista de canais permitidos.", ephemeral=True)
        elif acao.value == "remove":
            db.db_remove_designated_event_channel(interaction.guild_id, canal.id)
            await interaction.response.send_message(f"🗑️ O canal {canal.mention} foi removido da lista.", ephemeral=True)

    @admin_group.command(name="canal_resumo", description="Define ou remove o canal para o resumo diário de eventos.")
    @app_commands.describe(canal="O canal para enviar o resumo diário. Não especifique para remover.")
    async def configurar_canal_resumo(self, interaction: discord.Interaction, canal: Optional[discord.TextChannel] = None):
        if not self.is_owner_or_admin(interaction):
            await interaction.response.send_message("Este comando é restrito ao dono do servidor ou administradores.", ephemeral=True)
            return
        if not interaction.guild_id: return

        if canal:
            db.db_set_server_config(interaction.guild_id, digest_channel_id=canal.id)
            await interaction.response.send_message(f"✅ O resumo diário de eventos será enviado em {canal.mention}.", ephemeral=True)
        else:
            db.db_set_server_config(interaction.guild_id, digest_channel_id=None)
            await interaction.response.send_message("🗑️ O canal de resumo diário foi removido.", ephemeral=True)

    @admin_group.command(name="ranking", description="Configura o sistema de ranking de atividade por voz.")
    @app_commands.describe(canal_ranking="O canal onde a tabela de classificação será postada.")
    async def configurar_ranking(self, interaction: discord.Interaction, canal_ranking: discord.TextChannel):
        if not self.is_owner_or_admin(interaction):
            await interaction.response.send_message("Este comando é restrito ao dono do servidor ou administradores.", ephemeral=True)
            return
        if not interaction.guild or not interaction.guild_id: return
        await interaction.response.defer(ephemeral=True)

        db.db_set_server_config(interaction.guild_id, ranking_channel_id=canal_ranking.id)

        created_roles_log = []
        existing_roles_log = []
        role_ids_to_db: Dict[int, int] = {}

        current_roles_in_guild = {role.name: role for role in interaction.guild.roles}

        for tier, config in RANKING_ROLES_CONFIG.items():
            role_name = config["name"]
            if role_name in current_roles_in_guild:
                role = current_roles_in_guild[role_name]
                existing_roles_log.append(role.mention)
                role_ids_to_db[tier] = role.id
            else:
                try:
                    new_role = await interaction.guild.create_role(
                        name=role_name,
                        color=config["color"],
                        reason=f"Criação automática de cargo para o sistema de ranking do bot."
                    )
                    created_roles_log.append(new_role.mention)
                    role_ids_to_db[tier] = new_role.id
                except discord.Forbidden:
                    await interaction.followup.send(f"⚠️ Permissão negada para criar o cargo '{role_name}'.", ephemeral=True)
                    return
                except Exception as e:
                    await interaction.followup.send(f"❌ Erro ao criar o cargo '{role_name}': {e}", ephemeral=True)
                    return

        db.db_set_ranking_roles(interaction.guild_id, role_ids_to_db)

        msg = f"✅ **Sistema de Ranking Configurado!**\n\n"
        msg += f"📰 Canal da classificação: {canal_ranking.mention}\n"
        if created_roles_log:
            msg += f"✨ Cargos criados: {' '.join(created_roles_log)}\n"
        if existing_roles_log:
            msg += f"🔍 Cargos associados: {' '.join(existing_roles_log)}\n"

        await interaction.followup.send(msg, ephemeral=True)

    @admin_group.command(name="inatividade", description="Configura o sistema de gestão de inatividade.")
    @app_commands.describe(canal_moderadores="Canal para notificar sobre remoções.", cargo_penalidade="Cargo a ser aplicado para faltas (opcional).")
    async def configurar_inatividade(self, interaction: discord.Interaction, canal_moderadores: discord.TextChannel, cargo_penalidade: Optional[discord.Role] = None):
        if not self.is_owner_or_admin(interaction):
            await interaction.response.send_message("Este comando é restrito ao dono do servidor ou administradores.", ephemeral=True)
            return
        if not interaction.guild_id: return

        penalty_id = cargo_penalidade.id if cargo_penalidade else None
        db.db_set_server_config(interaction.guild_id, mod_notification_channel_id=canal_moderadores.id, penalty_role_id=penalty_id)

        msg = f"✅ Canal de notificação de moderadores definido para {canal_moderadores.mention}.\n"
        if cargo_penalidade:
            msg += f"✅ Cargo de penalidade definido como {cargo_penalidade.mention}."
        else:
            msg += "ℹ️ Nenhum cargo de penalidade foi definido."

        await interaction.response.send_message(msg, ephemeral=True)

    @admin_group.command(name="admin_cla", description="Define um administrador para executar ações na API da Bungie.")
    @app_commands.describe(admin="O membro que será o administrador do clã para o bot.")
    async def configurar_admin_cla(self, interaction: discord.Interaction, admin: discord.Member):
        if not self.is_owner_or_admin(interaction):
            await interaction.response.send_message("Este comando é restrito ao dono do servidor ou administradores.", ephemeral=True)
            return
        if not interaction.guild_id: return

        await interaction.response.defer(ephemeral=True)

        bungie_profile = db.db_get_bungie_profile(admin.id)
        if not bungie_profile:
            await interaction.followup.send(f"❌ O usuário {admin.mention} não possui uma conta Bungie vinculada. Peça para ele usar `/vincular_bungie`.", ephemeral=True)
            return

        db.db_set_server_config(interaction.guild_id, clan_admin_discord_id=admin.id)
        await interaction.followup.send(f"✅ {admin.mention} foi definido como o Administrador do Clã para as ações da API.", ephemeral=True)

    @admin_group.command(name="cargo_cla", description="Define o cargo que será atribuído aos membros do clã.")
    @app_commands.describe(cargo="O cargo para os membros do clã.")
    async def configurar_cargo_cla(self, interaction: discord.Interaction, cargo: discord.Role):
        if not self.is_owner_or_admin(interaction):
            await interaction.response.send_message("Este comando é restrito ao dono do servidor ou administradores.", ephemeral=True)
            return
        if not interaction.guild_id: return

        db.db_set_server_config(interaction.guild_id, clan_role_id=cargo.id)
        await interaction.response.send_message(f"✅ O cargo {cargo.mention} foi definido como o cargo oficial do clã.", ephemeral=True)

    @app_commands.command(name="ver_configuracoes", description="Mostra as configurações atuais do bot neste servidor.")
    @app_commands.guild_only()
    async def ver_configuracoes(self, interaction: discord.Interaction):
        if not self.is_owner_or_admin(interaction):
            await interaction.response.send_message("Este comando é restrito ao dono do servidor ou administradores.", ephemeral=True)
            return
        if not interaction.guild or not interaction.guild_id: return
        await interaction.response.defer(ephemeral=True)

        configs = db.db_get_server_configs(interaction.guild_id)
        ranking_roles_data = db.db_get_ranking_roles(interaction.guild_id)

        embed = discord.Embed(title=f"Configurações do Bot para {interaction.guild.name}", color=discord.Color.blurple())

        digest_ch = f"<#{configs['digest_channel_id']}>" if configs and configs.get('digest_channel_id') else "Não definido"
        ranking_ch = f"<#{configs['ranking_channel_id']}>" if configs and configs.get('ranking_channel_id') else "Não definido"
        mod_ch = f"<#{configs['mod_notification_channel_id']}>" if configs and configs.get('mod_notification_channel_id') else "Não definido"
        embed.add_field(name="Canais Configurados", value=f"**Resumo Diário:** {digest_ch}\n**Ranking:** {ranking_ch}\n**Notificações Mod:** {mod_ch}", inline=False)

        penalty_role = f"<@&{configs['penalty_role_id']}>" if configs and configs.get('penalty_role_id') else "Não definido"
        clan_role_mention = f"<@&{configs['clan_role_id']}>" if configs and configs.get('clan_role_id') else "Não definido"
        embed.add_field(name="Cargos Especiais", value=f"**Cargo do Clã:** {clan_role_mention}\n**Penalidade Ausência:** {penalty_role}", inline=False)

        admin_cla_mention = "Não definido"
        if configs and configs.get('clan_admin_discord_id'):
            admin_cla_id = configs['clan_admin_discord_id']
            admin_cla_mention = f"<@{admin_cla_id}>"
        embed.add_field(name="👑 Administrador do Clã (API)", value=admin_cla_mention, inline=False)

        ranking_text = ""
        if ranking_roles_data:
            for i in range(1, 5):
                role_id = ranking_roles_data[f'role_tier_{i}_id']
                role_mention = f"<@&{role_id}>" if role_id else "Não definido"
                ranking_text += f"**Nível {i}:** {role_mention}\n"
        else:
            ranking_text = "Não configurado. Use `/configurar ranking`."
        embed.add_field(name="Cargos de Ranking", value=ranking_text, inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))