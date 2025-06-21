# config.py
import os
from dotenv import load_dotenv

# Carrega as variáveis do ficheiro .env para o ambiente
load_dotenv()

# Carrega o token de autenticação do bot
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not DISCORD_BOT_TOKEN:
    raise ValueError("Erro: O token do bot (DISCORD_BOT_TOKEN) não foi encontrado. Verifique o seu ficheiro .env ou os 'Secrets' do Replit.")

# Carrega a chave da API da Bungie
BUNGIE_API_KEY = os.getenv("BUNGIE_API_KEY")
if not BUNGIE_API_KEY:
    print("AVISO: A chave da API da Bungie (BUNGIE_API_KEY) não foi encontrada. As funcionalidades de integração com a API não irão funcionar.")

# Carrega o ID do Clã da Bungie
BUNGIE_CLAN_ID = os.getenv("BUNGIE_CLAN_ID")
if not BUNGIE_CLAN_ID:
    print("AVISO: O ID do Clã da Bungie (BUNGIE_CLAN_ID) não foi encontrado. As funcionalidades de gestão de clã não irão funcionar.")

# Carrega as credenciais OAuth da Bungie
BUNGIE_CLIENT_ID = os.getenv("BUNGIE_CLIENT_ID")
BUNGIE_CLIENT_SECRET = os.getenv("BUNGIE_CLIENT_SECRET")
if not BUNGIE_CLIENT_ID or not BUNGIE_CLIENT_SECRET:
    print("AVISO: As credenciais OAuth (BUNGIE_CLIENT_ID, BUNGIE_CLIENT_SECRET) não foram encontradas. A vinculação de contas não irá funcionar.")

# Carrega o ID do servidor de desenvolvimento/teste (opcional, mas recomendado)
GUILD_ID = os.getenv("GUILD_ID")
if GUILD_ID:
    try:
        GUILD_ID = int(GUILD_ID)
    except ValueError:
        raise ValueError("Erro: GUILD_ID no ficheiro .env não é um número válido.")
else:
    # Se GUILD_ID não estiver definido, os comandos podem demorar mais a sincronizar globalmente.
    print("AVISO: GUILD_ID não definido no .env. Os comandos slash serão registados globalmente.")