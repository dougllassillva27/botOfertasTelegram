# Bot de Ofertas — Garimpo Automático de Promoções (Telegram + WhatsApp)

![Status](https://img.shields.io/badge/status-active-success)
![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.11-blue)
![Telethon](https://img.shields.io/badge/telethon-1.33.1-orange)

**Userbot MTProto que monitora dezenas de canais de ofertas em tempo real, filtra por palavras-chave configuráveis e encaminha apenas as promoções relevantes — com rota extra opcional para WhatsApp (menção nativa) nas ofertas prioritárias.**

---

## Descrição

O Bot de Ofertas atua como garimpeiro pessoal. Ele escuta continuamente os grupos monitorados, aplica as keywords de alerta cadastradas e encaminha cada oferta capturada para a Central de Comando (grupo privado no Telegram). Keywords marcadas como prioritárias também são entregues num grupo do WhatsApp, com menção nativa no dono.

Também oferece busca retroativa de 7 dias em todos os grupos cadastrados e deduplicação automática (hash exato + similaridade fuzzy).

---

## Visão Geral Técnica

Construído sobre **Telethon** (API MTProto), o bot opera como userbot — ou seja, acessa a conta pessoal do Telegram, o que permite ler mensagens de qualquer grupo ao qual a conta pertence (algo impossível para bots normais da Bot API).

A arquitetura isola quatro responsabilidades:

- **Handlers** — recepção e roteamento de eventos (comandos, mensagens, callbacks)
- **OfferService** — lógica de negócio (grupos, alertas, busca, formatação)
- **OfferDeduplicator** — detecção de duplicatas por hash e fuzzy
- **whatsapp_sender** — entrega opcional via ponte local do WhatsApp

A persistência é JSON local (sem banco de dados externo), e a execução contínua é garantida por um watchdog que encerra o processo quando a conexão trava — o `restart: unless-stopped` do Docker o religa.

---

## Highlights Técnicos

- **Monitoramento contínuo 24h** — escuta passiva via MTProto em todos os grupos cadastrados
- **Alertas por palavra-chave** — casamento por regex com plural tolerante (`\bkw(s?)\b`)
- **Rota WhatsApp opcional** — keyword marcada vai para Telegram **e** WhatsApp, com menção nativa
- **Busca retroativa (`/buscar`)** — varredura dos últimos 7 dias em todos os grupos, limitada a 30 resultados contra FloodWait
- **Deduplicação em duas camadas** — hash exato (título+descrição+URL normalizados) e similaridade fuzzy (thefuzz, threshold 80%)
- **Persistência temporal** — registro de ofertas enviadas expira em 48h
- **Auditoria** — ofertas puladas registradas em `logs/Logs.txt` com timestamp e motivo
- **Watchdog** — mata o processo se ficar sem atividade; o Docker o reinicia
- **Arquitetura modular** — handlers separados, serviços dedicados, sem monólito
- **98 testes unitários** — pytest, cobrindo serviços, handlers, deduplicação, watchdog e envio WhatsApp

---

## Arquitetura

```
Grupos monitorados (Telegram)
        |
        v
Userbot Telethon (MTProto)
        |
        +-- CommandHandler   /comandos /buscar /grupos /alertas /getid
        |
        +-- MessageHandler   filtra por keyword + dedup
        |        |
        |        +---> Telegram: encaminha para Central de Comando
        |        |
        |        +---> WhatsApp: se keyword marcada, envia para o grupo
        |                     do Sol com mencao nativa (via ponte :3001)
        |
        +-- CallbackHandler  (vazio, reservado)
        |
        +-- OfferService     grupos, alertas, flags whatsapp, busca
        +-- OfferDeduplicator  hash exato + fuzzy, expira em 48h
        |
        v
Persistencia JSON (data/data.json, data/offers_sent.json)
```

**Canal WhatsApp:** o envio não usa a Bot API do WhatsApp. O `whatsapp_sender` faz um POST direto na ponte local (`127.0.0.1:3001`) que roda no host e detém a sessão WhatsApp. Por isso o container precisa de `network_mode: host`.

---

## Estrutura do Projeto

```
botOfertas/
|-- app/
|   |-- main.py                  # Entry point: client, handlers, watchdog
|   |-- config.py                # Variaveis de ambiente (.env)
|   |-- storage.py               # Persistencia JSON
|   |-- handlers/
|   |   |-- command_handler.py    # Comandos + dica de envio WhatsApp
|   |   |-- message_handler.py    # Filtro de keyword + rota WhatsApp
|   |   +-- callback_handler.py   # Vazio, reservado
|   +-- services/
|       |-- offer_service.py      # Grupos, alertas, flags, busca
|       |-- deduplication.py      # Hash exato + fuzzy, expiracao 48h
|       +-- whatsapp_sender.py    # POST na ponte do WhatsApp com mencao
|-- tests/                       # 95 testes unitarios (pytest)
|-- data/                        # Estado + sessao (gitignored)
|-- logs/                        # Logs.txt unificado (gitignored)
|-- docs/                        # Documentacao de design
|-- Dockerfile
|-- docker-compose.yml           # Compose do projeto (secundario)
+-- requirements.txt
```

---

## Responsabilidades por Módulo

### `app/main.py`
Entry point. Inicializa o client Telethon, carrega o estado, registra os handlers (comandos, callbacks, mensagens), sobe o watchdog e mantém o loop de escuta. Aplica wrapper UTF-8 em stdout/stderr.

### `app/config.py`
Lê `API_ID`, `API_HASH`, `SESSION_NAME`, `FORWARD_TO` e os timeouts do watchdog a partir do `.env` (python-dotenv). Resolve o caminho absoluto da sessão dentro de `data/`.

### `app/storage.py`
Camada de persistência. `load_data` cria o `data.json` com estado padrão na primeira execução; `save_data` grava com indentação e UTF-8.

### `app/handlers/command_handler.py`
Registra e processa os comandos do grupo de controle. O `add` de alerta anexa uma dica de como ligar o envio WhatsApp; `/alertas wa` liga/desliga a marca de uma keyword.

### `app/handlers/message_handler.py`
Filtra mensagens dos grupos monitorados, aplica deduplicação, casa **todas** as keywords de alerta presentes na mensagem e encaminha para o Telegram (o aviso lista cada keyword que bateu). Se **qualquer uma** delas estiver marcada como prioritária, também dispara o envio para o WhatsApp (falha na ponte não interrompe o fluxo do Telegram).

### `app/handlers/callback_handler.py`
Vazio, reservado. Foi ocupado por botões inline de confirmação WhatsApp, mas o Telegram descarta o `reply_markup` quando o remetente é conta pessoal (userbot MTProto) — só contas Bot API podem enviar inline keyboards. A alternativa adotada é `/alertas wa <palavra>`.

### `app/services/offer_service.py`
Núcleo da lógica de negócio: CRUD de grupos e alertas, flags de prioridade WhatsApp, busca retroativa de 7 dias e formatação das mensagens. Delega deduplicação ao `OfferDeduplicator`.

### `app/services/deduplication.py`
Gera hash a partir de título + descrição + URL normalizados. Detecta duplicatas por hash exato ou similaridade fuzzy (threshold 80%). Mantém o registro por 48h e loga ofertas puladas.

### `app/services/whatsapp_sender.py`
Único módulo que conhece a API da ponte do WhatsApp. Monta o texto da oferta (com o handle de menção no corpo — obrigatório para a menção renderizar) e faz o POST `/send` com o campo `mentions`.

### `tests/`
98 testes unitários: `offer_service` (37), `deduplication` (17), `command_handler` (10), `whatsapp_flag` (8), `watchdog` (8), `whatsapp_sender` (7), `message_whatsapp` (6), `storage_backup` (5).

---

## Fluxo Principal

```
1. Bot inicia e conecta via MTProto com as credenciais do .env
2. Estado carregado de data/data.json (grupos, alertas, flags WhatsApp)
3. Registro de ofertas enviadas carregado (expira em 48h)
4. Handlers registrados; loop de escuta inicia
5. Mensagem chega em grupo monitorado
6. Deduplicacao verifica hash exato + fuzzy
7. Keyword casou? Encaminha para o Telegram com metadata de origem
8. Keyword marcada como prioritaria? Envia tambem para o WhatsApp
   com mencao nativa (via ponte local)
9. Comando digitado no grupo de controle? CommandHandler responde
10. Alteracoes persistidas em data/data.json
```

---

## Tecnologias

| Tecnologia      | Versão   | Responsabilidade                            |
| --------------- | -------- | ------------------------------------------- |
| Python          | 3.11     | Linguagem principal (imagem do Docker)      |
| Telethon        | 1.33.1   | API MTProto do Telegram (userbot)           |
| python-dotenv   | 1.0.1    | Carregamento de variáveis de ambiente       |
| thefuzz         | 0.22.1   | Similaridade fuzzy para deduplicação        |
| pytest          | latest   | Framework de testes unitários               |
| Ruff            | latest   | Linting e análise estática                  |
| Docker          | compose  | Empacotamento e execução contínua           |

`pytest` e `ruff` são dependências de desenvolvimento — não estão no `requirements.txt` (que contém apenas o runtime).

---

## Variáveis de Ambiente

Definidas em `.env` (não versionado; `!.env.example` é o template).

| Variável        | Obrigatória | Descrição                                                        |
| --------------- | ----------- | ---------------------------------------------------------------- |
| `API_ID`        | Sim         | App api_id de my.telegram.org                                     |
| `API_HASH`      | Sim         | App api_hash de my.telegram.org                                  |
| `SESSION_NAME`  | Não         | Nome da sessão Telethon (padrão: `userbot_session`)              |
| `FORWARD_TO`    | Não         | Destino das ofertas: `me`, ID numérico ou `@username` (padrão `me`) |
| `WATCHDOG_TIMEOUT_MIN`      | Não | Minutos sem atividade antes de matar o processo (padrão 40) |
| `WATCHDOG_CHECK_INTERVAL_MIN` | Não | Intervalo de checagem do watchdog (padrão 5)          |

Para a rota WhatsApp, o `whatsapp_sender` aceita override por env (`WHATSAPP_BRIDGE_URL`, `WHATSAPP_GROUP_ID`, `WHATSAPP_MENTION_JID`, `WHATSAPP_BRIDGE_TIMEOUT`); os valores padrão já apontam para a ponte local e o grupo do Sol.

---

## Como Rodar Localmente

### Pré-requisitos

1. Python 3.11+
2. Conta ativa no Telegram (para gerar credenciais de desenvolvedor)
3. Um grupo privado no Telegram (servirá como Central de Comando)

### 1. Obter credenciais

Acesse [my.telegram.org](https://my.telegram.org), faça login com seu número, abra **API development tools** e anote `App api_id` e `App api_hash`.

### 2. Configurar ambiente

```bash
cd botOfertas

python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

pip install -r requirements.txt
pip install pytest               # apenas para rodar os testes

cp .env.example .env
# edite .env com API_ID, API_HASH e FORWARD_TO
```

### 3. Primeiro login (gerar sessão)

```bash
python -m app.main
```

O terminal pede telefone (com DDI e DDD), código de verificação e senha 2FA se configurada. A sessão fica salva em `data/`.

> A ponte do WhatsApp não é necessária para o funcionamento base — sem ela, o bot opera apenas no Telegram.

---

## Deploy (Docker)

### Fonte canônica de deploy

O serviço de produção é gerenciado pelo **compose mestre** (`/root/dodo/docker-compose.yml`), que define o `bot-ofertas` com healthcheck e limites de recursos. O `docker-compose.yml` deste diretório é secundário (útil para subir isolado).

```bash
# deploy real (compose mestre)
cd /root/dodo && docker compose up -d --no-build bot-ofertas

# subir isolado a partir deste repositorio
cd botOfertas && docker compose up -d --build
```

### `network_mode: host` é obrigatório para a rota WhatsApp

A ponte do WhatsApp escuta em `127.0.0.1:3001` (somente localhost). Um container em rede bridge não a alcança. Por isso o serviço declara `network_mode: host` — o bot apenas faz conexões de saída, não expõe portas, então o ganho de superfície é nulo e a integração passa a funcionar.

Sem esse modo, o bot continua funcionando normalmente no Telegram; apenas a rota WhatsApp falha (e falha como "extra": loga e segue).

### Autenticação da sessão em servidor

- **Migração**: copie a pasta `data/` local (contendo o `.session`) para `data/` da VPS
- **Novo login**: `docker compose run --rm bot-ofertas` e autentique interativamente; a sessão persiste no volume

### Comandos úteis

```bash
docker compose logs -f        # logs em tempo real
docker compose restart        # reiniciar
docker compose down           # parar
git pull && docker compose up -d --build   # atualizar
```

---

## Testes

```bash
cd botOfertas
.venv/bin/python -m pytest tests/ -q        # suite completa (91 testes)
.venv/bin/python -m pytest tests/ -v        # verboso
```

Cobertura: `offer_service`, `deduplication`, `command_handler`, `watchdog`, `whatsapp_flag`, `whatsapp_sender`, `storage_backup`, `message_whatsapp`.

Para cobertura de código, instale `pytest-cov` e use `--cov=app`.

---

## Sistema de Comandos

Todos os comandos rodam no **Grupo de Controle** (configurado via `FORWARD_TO`). Somente o dono da conta pode acioná-los.

| Comando            | Função                                                     | Exemplo                |
| ------------------ | ---------------------------------------------------------- | ---------------------- |
| `/comandos`        | Painel de ajuda                                            | `/comandos`            |
| `/buscar`          | Busca retroativa (7 dias, máx. 30 resultados)              | `/buscar notebook`     |
| `/grupos`          | Lista grupos monitorados                                   | `/grupos`              |
| `/grupos add`      | Adiciona grupo(s), aceita vírgula para massa               | `/grupos add grupoa, grupob` |
| `/grupos rm`       | Remove grupo(s)                                            | `/grupos rm grupoa`    |
| `/alertas`         | Lista palavras-chave ativas                                | `/alertas`             |
| `/alertas add`     | Adiciona keyword; sugere o comando de envio WhatsApp       | `/alertas add teclado` |
| `/alertas rm`      | Remove keyword (limpa a flag WhatsApp junto)               | `/alertas rm teclado`  |
| `/alertas wa`      | Liga/desliga o envio WhatsApp de uma keyword               | `/alertas wa teclado`  |
| `/getid`           | Revela o ID numérico do chat atual                         | `/getid`               |

---

## Integração WhatsApp (Ofertas Prioritárias)

Uma keyword pode ser marcada como prioritária, recebendo entrega dupla: Telegram (como sempre) e um grupo do WhatsApp com **menção nativa** no dono.

### Marcar uma keyword

Depois de `/alertas add teclado`, o bot responde com a dica:

```
✅ **Sucesso:** `teclado`

📲 **Pra enviar também no WhatsApp:** `/alertas wa teclado` (liga/desliga a qualquer momento)
```

`/alertas wa teclado` alterna a marca a qualquer momento. Sem marca, o comportamento é o padrão: só Telegram.

> **Por que não há botão?** Botões inline exigem conta Bot API. O bot é userbot (conta pessoal via MTProto), e o Telegram remove o `reply_markup` de contas de usuário — validado ao vivo, não é configuração que mude.

### Como a entrega funciona

O `message_handler`, ao encaminhar uma oferta de keyword marcada, chama o `whatsapp_sender`, que monta o texto (mensagem original + origem + data) e faz `POST /send` na ponte do WhatsApp, com o campo `mentions`.

**Detalhe crítico de implementação:** o campo `mentions` sozinho não gera a menção. O WhatsApp/Baileys só renderiza (e notifica) quando o handle `@numero` aparece **no corpo do texto**. O `whatsapp_sender` injeta esse handle na primeira linha. Um `success: true` da ponte não prova que a menção formou — a verificação é visual.

### Comportamento em falha

Se a ponte estiver fora do ar, a oferta **não se perde**: já foi encaminhada para o Telegram antes. A falha é logada em `logs/Logs.txt` e o bot segue. Não há retry.

### Decisões de design

O registro completo (contexto, alternativas descartadas, consequências) está em `docs/design-integracao-whatsapp.md`.

---

## Persistência

- **Estado** (`data/data.json`): grupos monitorados, alertas e flags WhatsApp
- **Backup automático**: `save_data` grava `data.json.bak-<timestamp>` antes de cada escrita, mantendo os 10 mais recentes (`BACKUP_KEEP`) — blindagem contra sobrescrita acidental
- **Registro de ofertas** (`data/offers_sent.json`): hash das ofertas enviadas, expira em 48h
- **Sessão** (`data/*.session`): credencial Telethon persistida após o primeiro login
- **Encoding**: UTF-8 explícito em todas as operações de I/O
- Todo o diretório `data/` é gitignored

---

## Segurança e Privacidade

- **Credenciais** em `.env`, fora do versionamento (`.env.example` é o único commitado)
- **Sessão** `.session` também gitignored — quem tiver acesso a ele tem acesso à conta
- **Vinculação à conta pessoal**: é um userbot. Se um grupo banir sua conta, o bot perde acesso às ofertas daquele grupo
- **2FA suportada**: pedida no primeiro login se configurada na conta
- **Ponte do WhatsApp** roda no host e escuta apenas em `localhost` — não é exposta

---

## Solução de Problemas

**Comandos não respondem no grupo**
- `FORWARD_TO` incorreto no `.env`. Grupos privados começam com `-100`
- Use `/getid` no grupo desejado para descobrir o ID e ajuste o `.env`

**Bot não encaminha ofertas**
- Confirme se a conta foi adicionada ao grupo de origem
- Verifique as keywords via `/alertas`
- Confira `logs/Logs.txt` (ofertas puladas por dedup também aparecem lá)

**Oferta chega no Telegram mas não no WhatsApp**
- A keyword pode não estar marcada — verifique com `/alertas wa <kw>`
- A ponte do WhatsApp pode estar fora: `curl http://127.0.0.1:3001/health` deve retornar `connected`
- Se o container estiver em rede bridge, a ponte é inalcançável — `network_mode: host` é obrigatório

**Mensagem chega no WhatsApp sem notificação**
- A menção não formou. O handle `@numero` precisa estar no texto (o `whatsapp_sender` faz isso automaticamente); se você customizou o texto, mantenha o handle

**Conta banida de um grupo**
- O bot usa sua conta pessoal. Se o grupo banir você, o bot perde acesso. Solicite desban ou use conta secundária

---

## Decisões Técnicas

- **Telethon sobre python-telegram-bot**: A API MTProto permite ler mensagens de qualquer grupo — a Bot API não oferece isso
- **Persistência JSON**: Sem dependência de banco externo; o volume de dados é pequeno e o acesso é simples
- **Entrega WhatsApp direta na ponte**: Evita custo de LLM por alerta e latência de um agente; a menção nativa exige o campo `mentions` + handle no texto, que o webhook `deliver_only` do Hermes não envia
- **`network_mode: host`**: Requerido para alcançar a ponte em localhost; o bot só faz saída, então não abre superfície
- **Falha do WhatsApp é não-bloqueante**: A rota WhatsApp é um extra — o Telegram é o destino garantido
- **Watchdog + `restart: unless-stopped`**: Em vez de supervisionar a conexão, mata o processo travado e deixa o Docker religar
- **Limite de 30 em `/buscar`**: Proteção contra FloodWait (anti-spam do Telegram)
- **Marcação por keyword, não por oferta**: Configura uma vez e vale para todas as ofertas daquela keyword — mais prático que marcar oferta a oferta

---

## Licença

MIT License

---

## Autoria

Desenvolvido por **Douglas Silva** como projeto pessoal de automação.

Base original adaptada, expandida e personalizada, mantendo licença MIT conforme o projeto fonte.
