# constants.py
import pytz
import datetime
import discord

# --- Timezone Configuration ---
BRAZIL_TZ_STR = 'America/Sao_Paulo'
BRAZIL_TZ = pytz.timezone(BRAZIL_TZ_STR)

# --- Database Configuration ---
DB_NAME = 'destiny_events.db'

# --- Date/Time Formatting Constants ---
DIAS_SEMANA_PT_FULL = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
DIAS_SEMANA_PT_SHORT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
MESES_PT = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

# --- Activity Dictionaries (em pt-BR) ---
RAID_INFO_PT = {
    "Queda do Rei": ["queda", "oryx", "queda do rei", "king's fall", "kings fall", "kf"],
    "O Fim de Crota": ["crota", "fim de crota", "crota's end", "crotas end", "ce"],
    "Câmara de Cristal": ["camara", "câmara", "vog", "camara de cristal", "câmara de cristal", "vault of glass"],
    "Último Desejo": ["riven", "ultimo desejo", "último desejo", "last wish", "lw"],
    "Jardim da Salvação": ["jardim", "jardim da salvação", "garden", "garden of salvation", "gos"],
    "Cripta da Pedra Profunda": ["cripta", "cripta da pedra", "dsc", "deep stone crypt"],
    "Voto do Discípulo": ["voto", "discípulo", "voto do discípulo", "disciple", "vod", "vow of the disciple"],
    "Raiz dos Pesadelos": ["raiz", "pesadelos", "raiz dos pesadelos", "ron", "root of nightmares"],
    "Limiar da Salvação": ["limiar", "salvação", "limiar da salvação", "edge", "salvation's edge", "salvations edge", "se"]
}
MASMORRA_INFO_PT = {
    "Profecia": ["profecia", "prophecy"],
    "Trono Estilhaçado": ["trono", "trono estilhaçado", "estilhaçado", "shattered throne", "st"],
    "Poço da Heresia": ["poço", "heresia", "poco", "poço da heresia", "pit of heresy", "pit", "poh"],
    "Dualidade": ["dualidade", "duality"],
    "Pináculo da Sentinela": ["pinaculo", "pináculo", "sentinela", "pináculo da sentinela", "spire", "spire of the watcher", "sotw"],
    "Fantasmas das Profundezas": ["fantasmas", "profundezas", "fantasmas das profundezas", "ghosts", "ghosts of the deep", "gotd"],
    "Ruína da Senhora da Guerra": ["ruina", "ruína", "senhora da guerra", "ruína da senhora da guerra", "warlord's ruin", "warlords ruin", "wr"],
    "Domínio de Vésper": ["vesper", "domínio de vesper", "dominio de vesper"],
    "Doutrina Apartada": ["doutrina", "apartada", "doutrina apartada", "severance"]
}
PVP_ACTIVITY_INFO_PT = {
    "Desafios de Osíris": ["osiris", "desafios", "trials", "desafios de osíris", "trials of osiris"]
}

# --- Aggregate Lists ---
ACTIVITY_SUBTYPES_RAID = [keyword for keywords_list in RAID_INFO_PT.values() for keyword in keywords_list]
ACTIVITY_SUBTYPES_DUNGEON = [keyword for keywords_list in MASMORRA_INFO_PT.values() for keyword in keywords_list]
ACTIVITY_SUBTYPES_PVP = [keyword for keywords_list in PVP_ACTIVITY_INFO_PT.values() for keyword in keywords_list]
ACTIVITY_SUBTYPES_GAMBIT = ["gambit"]
ACTIVITY_SUBTYPES_NIGHTFALL = ["anoitecer", "gm", "grandmaster", "mestre", "lendário", "legend", "nightfall"]
ACTIVITY_SUBTYPES_EXOTIC = ["exotica", "exótica", "missão exótica", "missao exotica", "exotic mission", "exotic"]
ACTIVITY_SUBTYPES_SEASONAL = ["sazonal", "historia", "história", "sobrecarga", "invasão", "brecha"]
ACTIVITY_SUBTYPES_OTHER = ["patrulha", "campanha", "qualquer", "ajuda", "outro"]

ALL_ACTIVITIES_PT = {**RAID_INFO_PT, **MASMORRA_INFO_PT, **PVP_ACTIVITY_INFO_PT}
SIMILARITY_THRESHOLD = 0.8

# --- Event Embed Colors ---
DEFAULT_EVENT_COLOR = discord.Color.blue()
EVENT_TYPE_COLORS = {
    "Raid": discord.Color.purple(),
    "Dungeon": discord.Color.orange(),
    "PvP": discord.Color.red(),
    "Gambit": discord.Color.green(),
    "Anoitecer": discord.Color.teal(),
    "Exótica": discord.Color.gold(),
    "Sazonal": discord.Color.teal(), # Correção: Trocado cyan() por teal()
    "Outro": discord.Color.light_grey()
}

# --- Horários para a Tarefa de Resumo Diário ---
DIGEST_TIMES_BRT = [
    datetime.time(hour=8, minute=0, tzinfo=BRAZIL_TZ),
    datetime.time(hour=16, minute=0, tzinfo=BRAZIL_TZ)
]