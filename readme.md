# Bot de Eventos e Gestão de Clã para Destiny 2

Este é um bot multifuncional para Discord, projetado para gerenciar eventos, atividades de membros e integração com a API da Bungie para clãs de Destiny 2.

## Funcionalidades Principais

### Gestão de Eventos
* **Criação de Eventos:** Crie eventos de forma rápida e detalhada através de um formulário (`/agendar`) ou de uma conversa interativa via DM (`/criar_evento`).
* **RSVP Inteligente:** Membros podem se inscrever, cancelar a inscrição ou marcar "talvez" através de botões intuitivos. O sistema gerencia automaticamente uma lista de espera se as vagas se esgotarem.
* **Canais e Cargos Temporários:** Para cada evento, uma thread de discussão e um cargo temporário são criados automaticamente, mantendo a organização e facilitando a comunicação. A thread é arquivada e o cargo é deletado após o evento.
* **Notificações e Lembretes:** O bot envia lembretes 1 hora e 15 minutos antes do evento, notifica os participantes sobre cancelamentos ou reagendamentos, e posta um resumo diário dos próximos eventos em um canal dedicado.

### Sistema de Atividade e Ranking
* **Monitoramento de Atividade:** O bot registra o tempo que cada membro passa em canais de voz e verifica automaticamente a presença em eventos agendados.
* **Ranking Semanal:** Com base no tempo de voz, os membros recebem cargos de ranking automaticamente todo sábado, desde "Turista da Torre" até "Mestre dos Confins". As promoções são anunciadas em um canal específico.
* **Leaderboard Diário:** Um leaderboard com os membros mais ativos da semana é postado e atualizado diariamente às 7h da manhã no canal de ranking.
* **Gestão de Inatividade:** O bot ajuda a manter a comunidade ativa, enviando avisos para membros inativos por 2 semanas e removendo-os automaticamente do Discord e do clã no jogo após 3 semanas de inatividade, com notificações para a moderação.

### Integração com a Bungie.net
* **Vinculação de Contas:** Membros podem vincular sua conta do Discord à sua conta da Bungie de forma segura através de um comando (`/vincular bungie`) e do processo oficial de autenticação OAuth2.
* **Gestão do Clã:** (Em desenvolvimento) Funcionalidades futuras incluem a remoção automática de membros inativos do clã no jogo e um sistema para gerenciar pedidos de entrada no clã diretamente pelo Discord.

## Comandos

### Comandos de Usuário
* `/agendar` - Abre um formulário para criar um novo evento.
* `/criar_evento` - Inicia uma conversa por DM para criar um novo evento.
* `/lista` - Mostra uma lista de todos os eventos futuros.
* `/vincular_bungie` - Inicia o processo para vincular sua conta do Discord à da Bungie.net.

### Comandos de Administração
* `/configurar canal_eventos` - Define os canais onde os anúncios de eventos podem ser postados.
* `/configurar canal_resumo` - Define o canal para o resumo diário de eventos.
* `/configurar ranking` - Configura o sistema de ranking, definindo o canal do leaderboard e criando/associando os cargos de atividade.
* `/configurar inatividade` - Define o canal de notificação dos moderadores e o cargo de penalidade.
* `/ver_configuracoes` - Mostra todas as configurações atuais do bot no servidor.
* `/permissoes` - Gerencia permissões granulares para quem pode criar, editar ou apagar eventos.

## Instalação e Configuração

1.  **Clone o Repositório:** `git clone [URL_DO_SEU_REPOSITORIO]`
2.  **Crie o arquivo `.env`:** Na raiz do projeto, crie um arquivo `.env` com as seguintes variáveis:
    ```
    DISCORD_BOT_TOKEN="SEU_TOKEN_DO_DISCORD"
    BUNGIE_API_KEY="SUA_CHAVE_DA_API_DA_BUNGIE"
    BUNGIE_CLAN_ID="ID_DO_SEU_CLÃ"
    BUNGIE_CLIENT_ID="SEU_OAUTH_CLIENT_ID"
    BUNGIE_CLIENT_SECRET="SEU_OAUTH_CLIENT_SECRET"
    GUILD_ID="ID_DO_SEU_SERVIDOR_DE_TESTES" # Opcional, para desenvolvimento
    ```
3.  **Instale as Dependências:** `pip install -r requirements.txt` (ou o comando do seu gestor de pacotes).
4.  **Execute o Bot:** `python main.py`