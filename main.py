# main.py
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import sys
import traceback
import datetime

# --- Carregar Variáveis de Ambiente ---
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID_STR = os.getenv("GUILD_ID")
GUILD_ID = int(GUILD_ID_STR) if GUILD_ID_STR and GUILD_ID_STR.isdigit() else None

# --- Importações de Módulos do Projeto ---
import database as db
from constants import DB_NAME
from cogs.event_cog import PersistentRsvpView

if not DISCORD_TOKEN:
    print("ERRO CRÍTICO: O DISCORD_BOT_TOKEN não foi encontrado no arquivo .env.", file=sys.stderr)
    sys.exit(1)

class ColaAIBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.voice_states = True
        super().__init__(command_prefix="!", intents=intents)

        self.persistent_views_added = False
        self.initial_cogs = [
            'cogs.admin_cog',
            'cogs.event_cog',
            'cogs.listeners_cog',
            'cogs.permissions_cog',
            'cogs.tasks_cog',
            'cogs.bungie_cog'
        ]

    async def setup_hook(self):
        db.init_db()
        print(f"DEBUG: Banco de dados '{DB_NAME}' inicializado/verificado.")

        for cog in self.initial_cogs:
            try:
                await self.load_extension(cog)
                print(f"  -> Cog '{cog}' carregado com sucesso.")
            except Exception as e:
                print(f"  /!\\ Falha ao carregar o cog '{cog}': {e}", file=sys.stderr)
                traceback.print_exc()

        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            print(f"DEBUG: Comandos slash registados para a guild: {GUILD_ID}")
        else:
            print("AVISO: GUILD_ID não definido no .env. Comandos podem levar tempo para aparecer globalmente.")

    async def on_ready(self):
        if not self.persistent_views_added:
            self.add_view(PersistentRsvpView(self))
            self.persistent_views_added = True

        print("------------------------------")
        print(f"Logado como {self.user} (ID: {self.user.id})")
        print("------------------------------")

if __name__ == "__main__":
    bot = ColaAIBot()
    bot.run(DISCORD_TOKEN)