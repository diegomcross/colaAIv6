# cogs/bungie_cog.py
import discord
from discord import app_commands
from discord.ext import commands
import secrets
import datetime
import pytz  # Adicionado para corrigir o NameError
from urllib.parse import urlparse, parse_qs

import bungie_api
import database as db
from config import BUNGIE_CLIENT_ID

class BungieCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        if not hasattr(self.bot, 'pending_oauth_states'):
            self.bot.pending_oauth_states = {}

    @app_commands.command(name="vincular_bungie", description="Vincula sua conta Bungie.net à sua conta do Discord.")
    async def vincular_bungie(self, interaction: discord.Interaction):
        """Inicia o processo de vinculação OAuth2 da Bungie."""
        await interaction.response.send_message(
            "Iniciando o processo de vinculação... Por favor, verifique suas mensagens diretas (DMs).",
            ephemeral=True
        )
        state = secrets.token_urlsafe(16)
        self.bot.pending_oauth_states[state] = interaction.user.id

        oauth_url = f"https://www.bungie.net/en/OAuth/Authorize?client_id={BUNGIE_CLIENT_ID}&response_type=code&state={state}"
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Autorizar com Bungie.net", url=oauth_url))

        try:
            await interaction.user.send(
                "Para vincular sua conta, clique no botão abaixo. Após autorizar, copie a URL da página de erro e cole aqui.",
                view=view
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ **Não consegui te enviar uma DM!** Verifique suas configurações de privacidade.",
                ephemeral=True
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Escuta por DMs contendo a resposta do callback OAuth2."""
        if message.author.bot or not isinstance(message.channel, discord.DMChannel):
            return

        if 'code=' not in message.content or 'state=' not in message.content:
            return

        try:
            parsed_url = urlparse(message.content)
            query_params = parse_qs(parsed_url.query)

            auth_code = query_params.get('code', [None])[0]
            state = query_params.get('state', [None])[0]

            if not auth_code or not state:
                return

            original_user_id = self.bot.pending_oauth_states.pop(state, None)
            if original_user_id != message.author.id:
                await message.channel.send("❌ **Erro de segurança!** O estado da autorização é inválido ou expirou. Tente usar `/vincular_bungie` novamente.")
                return

            await message.channel.send("Processando sua autorização, um momento...")

            token_data = await bungie_api.exchange_code_for_token(auth_code)
            if not token_data:
                await message.channel.send("❌ Falha ao obter o token de acesso da Bungie. Tente novamente.")
                return

            access_token = token_data['access_token']
            refresh_token = token_data['refresh_token']
            expires_in = token_data['expires_in']
            token_expires_at = (datetime.datetime.now(pytz.utc) + datetime.timedelta(seconds=expires_in)).isoformat()

            profile_data = await bungie_api.get_bungie_memberships_for_current_user(access_token)
            if not profile_data:
                await message.channel.send("❌ Falha ao obter seu perfil da Bungie. Tente novamente.")
                return

            bnet_user_info = profile_data['Response']['bungieNetUser']
            destiny_membership = profile_data['Response']['destinyMemberships'][0]

            bungie_name = f"{bnet_user_info['uniqueName']}"
            bungie_membership_id = destiny_membership['membershipId']
            bungie_membership_type = destiny_membership['membershipType']

            db.db_save_bungie_profile(
                discord_id=original_user_id,
                bungie_membership_id=bungie_membership_id,
                bungie_membership_type=bungie_membership_type,
                bungie_name=bungie_name,
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=token_expires_at
            )

            await message.channel.send(f"✅ **Sucesso!** Sua conta do Discord foi vinculada ao perfil da Bungie: **{bungie_name}**.")

        except Exception as e:
            print(f"OAUTH_ERROR: Erro ao processar callback: {e}")
            await message.channel.send("Ocorreu um erro inesperado ao processar sua vinculação. Verifique os logs do bot.")


async def setup(bot: commands.Bot):
    await bot.add_cog(BungieCog(bot))