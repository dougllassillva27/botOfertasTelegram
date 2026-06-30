# 🤖 Bot de Ofertas Telegram (Garimpo Automático)

![Status](https://img.shields.io/badge/status-active-success)
![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.10+-blue)
![Telethon](https://img.shields.io/badge/telethon-1.33.1-orange)

**Userbot inteligente para monitoramento de ofertas em canais do Telegram com alertas personalizáveis e busca retroativa.**

---

## 🔗 Demo

O bot roda localmente no seu computador como serviço Windows, acessando sua conta pessoal do Telegram via API MTProto.

---

## 📋 Visão Geral Técnica

Bot de Ofertas é um **userbot avançado** construído com Telethon que atua como "garimpeiro" pessoal. Ele monitora dezenas de canais de ofertas simultaneamente em tempo real, filtra mensagens por palavras-chave configuráveis e encaminha apenas as promoções relevantes para uma Central de Comando (seu grupo privado). Além disso, permite buscas retroativas em histórico de 7 dias consolidado em todos os grupos monitorados.

A arquitetura segue princípios de **Clean Architecture** e **Separation of Concerns**, com handlers modulares, serviço dedicado para lógica de negócio e persistência JSON local.

---

## ⚙️ Highlights Técnicos

- **Monitoramento passivo 24h**: Escuta grupos continuamente via Telethon API MTProto
- **Busca ativa retroativa (`/buscar`)**: Pesquisa últimos 7 dias em todos os grupos cadastrados
- **Central de comando unificada**: Controle total via grupo privado sem tocar em código
- **Rastreabilidade inteligente**: Encaminha mensagem original preservando links, fotos e botões
- **Execução autônoma (Daemon)**: Roda silenciosamente como serviço Windows via NSSM
- **Arquitetura modular**: Handlers separados (command, message, callback), OfferService dedicado
- **Testes automatizados**: 22 testes unitários com pytest-cov (77% cobertura)
- **Persistência leve**: Estado em JSON local com encoding UTF-8 garantido

---

## 🏗️ Arquitetura

```
Navegador / App Telegram
   │
   ▼
Userbot Telethon (API MTProto)
   │
   ├── CommandHandler (comandos administrativos)
   ├── MessageHandler (mensagens recebidas)
   ├── CallbackHandler (callbacks inline - placeholder)
   └── OfferService (lógica de grupos, alertas, busca, formatação)
   │
   ▼
Persistência Local (data/data.json)
   │
   ▼
Serviço Windows (NSSM) - execução 24/7
```

---

## 📁 Estrutura do Projeto

```
botOfertas/
├── app/
│   ├── __init__.py
│   ├── main.py              # Entry point, inicializa client e handlers
│   ├── config.py            # Variáveis de ambiente (.env)
│   ├── storage.py           # Persistência JSON local
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── command_handler.py    # /addgroup, /removegroup, /addalert, etc.
│   │   ├── message_handler.py    # Handler de mensagens recebidas
│   │   └── callback_handler.py   # Callbacks inline (placeholder)
│   └── services/
│       ├── __init__.py
│       └── offer_service.py      # Lógica principal: grupos, alertas, busca, formatação
├── tests/
│   ├── conftest.py          # Fixtures pytest
│   └── test_offer_service.py  # 22 testes unitários
├── scripts/
│   └── import_grupos.py     # Importação em massa de grupos
├── data/
│   └── data.json            # Estado persistente (grupos, alertas)
├── NSSM/                    # Non-Sucking Service Manager (Windows)
├── .env.example             # Referência de configuração
├── requirements.txt         # Dependências Python
└── resumo-de-trabalho.md    # Diário de bordo do desenvolvimento
```

---

## 🎯 Responsabilidades por Pasta/Módulo

### `app/main.py`
Entry point da aplicação. Inicializa cliente Telethon, carrega estado, registra handlers e inicia loop de escuta. Wrapper UTF-8 para terminal Windows.

### `app/config.py`
Carregamento de variáveis de ambiente via `.env` usando python-dotenv. Validação de credenciais API_ID/API_HASH.

### `app/storage.py`
Camada de persistência JSON. Load/save de estado (grupos, alertas) com encoding UTF-8 explícito.

### `app/handlers/command_handler.py`
Registro e processamento de comandos administrativos: `/addgroup`, `/removegroup`, `/addalert`, `/removealert`, `/status`, `/search`, `/getid`.

### `app/handlers/message_handler.py`
Filtro de mensagens recebidas dos grupos monitorados. Casamento de palavras-chave e encaminhamento para Central de Comando.

### `app/handlers/callback_handler.py`
Placeholder reservado para expansão futura com botões inline e interações via CallbackQuery.

### `app/services/offer_service.py`
Coração da lógica de negócio: gerenciamento de grupos, alertas, busca retroativa, formatação de mensagens e consolidação de resultados.

### `tests/test_offer_service.py`
Suite de 22 testes unitários cobrindo operações CRUD de grupos/alertas, busca retroativa e formatação. Fixtures em `conftest.py`.

### `scripts/import_grupos.py`
Utilitário para importação em massa de grupos a partir de lista predefinida.

---

## 🔄 Fluxo Principal da Aplicação

```
1. Usuário inicia o bot (python -m app.main ou serviço Windows)
2. Cliente Telethon conecta com credenciais do .env
3. Estado é carregado de data/data.json (grupos, alertas)
4. Handlers são registrados (command, message, callback)
5. Loop de escuta inicia - bot monitora grupos 24h
6. Mensagem chega em grupo monitorado → MessageHandler filtra
7. Palavra-chave casada? → Encaminha para Central de Comando com metadata
8. Usuário digita comando no grupo → CommandHandler processa e responde
9. Alterações persistidas em data/data.json
10. Serviço roda continuamente via NSSM (background Windows)
```

---

## 💾 Persistência

- **Tipo**: JSON local (`data/data.json`)
- **Encoding**: UTF-8 garantido em todas as operações de I/O
- **Estrutura**: Objeto com arrays de grupos monitorados e alertas configurados
- **Backup**: Arquivo `data/data.json.bak` criado automaticamente antes de migrações
- **Fallback**: Memória (state) durante execução, sincronizado com disco a cada alteração

---

## 🔒 Segurança e Privacidade

- **Credenciais**: Armazenadas em `.env` (não versionado pelo git). API_ID e API_HASH obtidos em my.telegram.org
- **Autenticação**: Login via código SMS enviado pelo Telegram na primeira execução (sessão persistida em `.session`)
- **2FA**: Suporte a senha de duas etapas se configurada na conta
- **Escopo**: Bot vinculado à conta pessoal do usuário. Se grupo banir a conta, bot perde acesso às ofertas
- **Dados sensíveis**: `.env` e arquivos `.session` excluídos do git via `.gitignore`

---

## 🎮 Sistema de Comandos

Todos os comandos são executados no **Grupo de Controle** (configurado via `FORWARD_TO` no `.env`). Somente o dono da conta (usuário "me") pode acioná-los:

| Comando        | Função                                                                      | Exemplo                        |
| :------------- | :-------------------------------------------------------------------------- | :----------------------------- |
| `/comandos`    | Lista painel de ajuda completo                                             | `/comandos`                    |
| `/buscar`      | Varredura retroativa nos últimos 7 dias                                    | `/buscar notebook`             |
| `/grupos`      | Lista grupos vigiados                                                       | `/grupos`                      |
| `/grupos add`  | Adiciona grupo à vigilância                                                | `/grupos add @nomedocanal`     |
| `/grupos rm`   | Remove grupo da vigilância                                                 | `/grupos rm nomedocanal`       |
| `/alertas`     | Lista palavras-chave ativas                                                | `/alertas`                     |
| `/alertas add` | Adiciona palavra-chave                                                     | `/alertas add tv 4k`           |
| `/alertas rm`  | Remove palavra-chave                                                       | `/alertas rm shampoo`          |
| `/getid`       | Revela ID numérico do chat atual (útil para configurar FORWARD_TO)         | `/getid`                       |

---

## 🚀 Como Rodar Localmente

### Pré-requisitos

1. **Python 3.10+** instalado
2. **Conta ativa no Telegram** (para gerar credenciais de desenvolvedor)
3. **Grupo privado no Telegram** (servirá como Central de Comando)

### Passo 1: Obter Credenciais do Telegram

1. Acesse [my.telegram.org](https://my.telegram.org) e faça login com seu número
2. Clique em **"API development tools"**
3. Preencha formulário (título arbitrário, plataforma "Desktop" ou "Other")
4. Anote **`App api_id`** (número) e **`App api_hash`** (texto longo)

### Passo 2: Configurar Ambiente

```bash
# Clonar ou baixar projeto
cd botOfertas

# Criar ambiente virtual (opcional, mas recomendado)
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Instalar dependências
pip install -r requirements.txt

# Criar .env baseado no exemplo
cp .env.example .env

# Editar .env com suas credenciais
# API_ID=12345678
# API_HASH=seu_hash_gigante_aqui
# SESSION_NAME=meu_userbot
# FORWARD_TO=-1001234567890  # ID do seu grupo privado
```

### Passo 3: Primeiro Login (Gerar Sessão)

```bash
python -m app.main
```

O terminal pedirá:
1. Número de telefone (com DDI +55 e DDD)
2. Código de verificação enviado pelo Telegram
3. Senha 2FA (se configurada)

Após login bem-sucedido, bot inicia escuta e mensagem de sucesso aparece.

### Passo 4: Executar como Serviço Windows (24/7)

Para rodar em background sem manter terminal aberto:

1. Baixe **NSSM** (já incluso na pasta `NSSM/`)
2. Execute `reiniciar_bot.bat` como Administrador
3. Bot inicia como serviço Windows (inicia automaticamente com sistema)

Para gerenciar serviço:
- Iniciar: `nssm start botOfertas`
- Parar: `nssm stop botOfertas`
- Reiniciar: `reiniciar_bot.bat`

---

## 🧪 Testes

```bash
# Rodar suite completa
pytest tests/ -v

# Com cobertura de código
pytest tests/ --cov=app.services.offer_service --cov-report=term-missing
```

**Resultado atual**: 22 testes passando, 77% de cobertura em `OfferService`.

---

## 🛠️ Stack Tecnológica

| Tecnologia        | Versão   | Responsabilidade                        |
| ----------------- | -------- | --------------------------------------- |
| Python            | 3.10+    | Linguagem principal                     |
| Telethon          | 1.33.1   | API MTProto do Telegram (userbot)       |
| python-dotenv     | latest   | Carregamento de variáveis de ambiente   |
| pytest            | latest   | Framework de testes unitários           |
| pytest-cov        | latest   | Cobertura de código                     |
| Ruff              | latest   | Linting e formatação de código          |
| NSSM              | 2.24     | Gerenciador de serviço Windows          |

---

## 📦 Versionamento

Commits seguem padrão **Conventional Commits** com prefixos semânticos:
- `feat:` nova funcionalidade
- `fix:` correção de bug
- `refactor:` refatoração sem mudança comportamental
- `docs:` documentação
- `test:` testes automatizados
- `chore:` manutenção

Histórico completo em `resumo-de-trabalho.md` com IDs únicos rastreáveis.

---

## 💡 Decisões Técnicas

- **SPA monolítico → Modular**: `main.py` de 232 linhas refatorado em handlers dedicados e OfferService
- **Persistência JSON**: Leve, rápida e sem dependência de banco de dados externo
- **Telethon sobre python-telegram-bot**: Acesso via API MTProto contorna limites de bots normais (lê mensagens de qualquer grupo)
- **Local-first**: Dados persistem em JSON local, sem necessidade de cloud ou serviços externos
- **NSSM para serviço Windows**: Solução robusta e gratuita para execução 24/7 sem manter terminal aberto
- **UTF-8 forçado**: Wrapper em sys.stdout/stderr garante encoding correto no terminal Windows (CP1252 → UTF-8)
- **Limite de 30 resultados em `/buscar`**: Travas de segurança contra FloodWait (spam detection do Telegram)

---

## ⚠️ Solução de Problemas

**"Meus comandos não respondem no grupo"**
- Provável causa: ID errado em `FORWARD_TO` no `.env`
- Grupos privados começam com `-100` (ex: `-1003637074849`)
- Use `/getid` no grupo desejado para descobrir ID correto
- Atualize `.env` e reinicie bot

**"Bot não encaminha mensagens filtradas"**
- Verifique se bot foi adicionado ao grupo origem
- Confirme alertas configurados via `/alertas`
- Cheque logs de erro (NSSM grava em `C:\error.log` por padrão)

**"Minha conta foi banida de grupo"**
- Bot é vinculado à conta pessoal. Se grupo banir você, bot perde acesso
- Solicite desban ou use conta secundária

---

## 📄 Licença

MIT License

---

## 👤 Autoria

Desenvolvido por **Douglas Silva** como projeto pessoal de automação Telegram.

Base original adaptada, expandida e personalizada mantendo licença MIT conforme projeto fonte.
