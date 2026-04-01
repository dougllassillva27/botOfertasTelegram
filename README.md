# 🤖 Bot de Ofertas Telegram (Garimpo Automático)

Um **Userbot** avançado para o Telegram criado para atuar como o seu "garimpeiro" pessoal. Ele monitora dezenas de canais de ofertas simultaneamente e envia apenas as promoções que te interessam para uma Central de Controle (seu próprio grupo privado), além de permitir buscas retroativas em um vasto histórico de mensagens.

---

## ✨ Principais Funcionalidades

- **Monitoramento Passivo (Tempo Real):** Escuta grupos 24 horas por dia e filtra mensagens com base em palavras-chave (alertas como "iphone", "notebook").
- **Busca Ativa Retroativa (`/buscar`):** Pesquisa um produto específico nos últimos 7 dias em todos os grupos monitorados, consolidando os resultados de forma ordenada.
- **Central de Comando Unificada:** Você controla tudo de dentro do seu próprio grupo do Telegram (adiciona grupos, remove palavras-chave), sem precisar tocar em arquivos de código.
- **Rastreabilidade (UX Inteligente):** O bot encaminha a mensagem real (preservando links, fotos e botões) e responde silenciosamente com a Data da Oferta e a Origem (Grupo que postou).
- **Execução Autônoma (Daemon):** Preparado para rodar silenciosamente no background do Windows como um serviço.

---

## 🛠️ Stack Tecnológica

- **Linguagem:** Python 3.10+
- **Core/API:** Telethon 1.33.1 (Acesso via API MTProto, contornando os limites de bots normais)
- **Gerenciamento de Estado:** Persistência leve e rápida em arquivo `JSON`.
- **Infraestrutura:** NSSM (Non-Sucking Service Manager) para execução contínua.

---

## 📋 Pré-requisitos

Para rodar este projeto, você precisará de:

1. **Python instalado** em seu computador (versão 3.8 ou superior).
2. **Uma conta ativa no Telegram** (usaremos ela para ser o "Userbot").

---

## 🚀 Guia de Instalação Rápida (Passo a Passo)

### 1. Obtenha suas Credenciais do Telegram

Como este bot usa a sua conta de usuário para ler mensagens, o Telegram exige que você gere credenciais de desenvolvedor:

1. Acesse my.telegram.org e faça login com o seu número de telefone.
2. Clique em **"API development tools"**.
3. Preencha o formulário (qualquer título e nome curto bastam; a plataforma pode ser "Desktop" ou "Other").
4. Você receberá um **`App api_id`** (número) e um **`App api_hash`** (texto longo). Guarde-os, eles são suas senhas!

### 2. Configuração do Projeto

Clone ou baixe esta pasta no seu computador e abra o terminal (Prompt de Comando ou PowerShell) nela.

Crie um ambiente virtual e instale as dependências:

```bash
# Opcional, mas recomendado:
python -m venv venv
venv\Scripts\activate

# Instalação das bibliotecas necessárias
pip install -r requirements.txt
```

### 3. Configurando o Ambiente (.env)

Crie um arquivo chamado `.env` na raiz do projeto (mesmo local do `README.md`) e cole o seguinte conteúdo, substituindo com seus dados:

```env
# Suas credenciais geradas no passo 1
API_ID=12345678
API_HASH=seu_hash_gigante_aqui

# Nome do arquivo da sua sessão (ficará salvo na pasta /data)
SESSION_NAME=meu_userbot

# O ID do seu Grupo Privado que servirá como Central de Comando
# ATENÇÃO: Grupos privados começam com "-100". Use o comando /getid para descobrir.
FORWARD_TO=-1001234567890
```

### 4. O Primeiro Login (Gerando a Sessão)

A primeira execução deve **obrigatoriamente** ser manual pelo terminal, para que você possa inserir o código que o Telegram envia no seu aplicativo.

```bash
python -m app.main
```

_O terminal vai pedir seu número de telefone (com DDI +55 e DDD) e, em seguida, o código de login. Se você tiver senha de duas etapas (2FA), ele também pedirá. Após isso, uma mensagem de sucesso aparecerá e o bot já estará escutando as mensagens!_

---

## 🎮 Como Usar (Comandos)

Vá para o seu grupo do Telegram configurado no `FORWARD_TO` e digite os comandos. **Somente você** (dono da conta) pode acioná-los:

| Comando        | O que faz                                                                                          | Exemplo de Uso                                      |
| :------------- | :------------------------------------------------------------------------------------------------- | :-------------------------------------------------- |
| `/comandos`    | Lista o painel de ajuda e todos os comandos.                                                       | `/comandos`                                         |
| `/buscar`      | Faz uma varredura nos últimos 7 dias em todos os seus grupos cadastrados procurando por promoções. | `/buscar notebook`                                  |
| `/grupos`      | Mostra todos os canais/grupos que o bot está vigiando.                                             | `/grupos`                                           |
| `/grupos add`  | Adiciona um novo grupo para o bot vigiar.                                                          | `/grupos add @nomedocanal` ou apenas o nome ou URL. |
| `/grupos rm`   | Remove um grupo da vigilância.                                                                     | `/grupos rm nomedocanal`                            |
| `/alertas`     | Mostra todas as palavras-chave que você quer que o bot pesque.                                     | `/alertas`                                          |
| `/alertas add` | Adiciona uma nova palavra-chave (produto) na sua rede.                                             | `/alertas add tv 4k`                                |
| `/alertas rm`  | Remove uma palavra da sua rede de buscas.                                                          | `/alertas rm shampoo`                               |
| `/getid`       | Use em qualquer chat/grupo para que o bot te diga qual é o ID numérico exato dele.                 | `/getid`                                            |

---

## 🏗️ Arquitetura do Projeto

Para desenvolvedores, o projeto aplica princípios de _Clean Architecture_ e _Separation of Concerns_:

```text
botTelegram/
  ├── app/                  # Lógica de negócio e ouvintes (main.py, config.py)
  ├── data/                 # Estado e Banco de dados Local (data.json, *.session)
  ├── scripts/              # Ferramentas isoladas (import_grupos.py)
  ├── NSSM/                 # Gerenciador de Serviço para Windows
  ├── .env                  # Credenciais (não versionado)
  ├── reiniciar_bot.bat     # Atalho administrativo de controle
  └── resumo-de-trabalho.md # Diário de bordo do desenvolvimento
```

---

## 🔄 Rodando 24/7 (Background no Windows)

Para não precisar manter a tela preta (terminal) aberta o tempo todo, o bot foi configurado para rodar como um **Serviço do Windows** usando a ferramenta NSSM.

**Para reiniciar, pausar ou ligar o bot:**

1. Clique com o botão direito no arquivo `reiniciar_bot.bat`.
2. Escolha **"Executar como Administrador"**.
3. Pronto! Ele foi reiniciado silenciosamente na memória do seu PC.

_(Caso o bot trave, os logs de erro são gravados pelo NSSM na raiz do disco C:\, garantindo que o seu console não fique poluído)._

---

## 💡 Dicas e Soluções de Problemas

- **"Meus comandos não respondem no grupo":** Provavelmente o ID no arquivo `.env` (`FORWARD_TO`) está errado. Lembre-se que IDs de grupos privados são negativos e contém `100` no início (ex: `-1003637074849`). Chame o bot no privado (Mensagens Salvas) e use `/getid`, depois cole o número no `.env` e reinicie.
- **Limite de Busca (Spam):** O comando `/buscar` limita propositalmente a pesquisa a **30 resultados** (priorizando os mais recentes) e dá pausas de meio segundo. Isso é uma trava de segurança da arquitetura para evitar que o Telegram bloqueie sua conta por "FloodWait" (spam).
- **Lembre-se:** Este bot é vinculado à **sua conta pessoal**. Se o grupo origem banir a sua conta, o bot automaticamente perderá acesso àquelas ofertas.
