import logging
import asyncio
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient, events
from app.config import API_ID, API_HASH, SESSION_NAME, FORWARD_TO
from app.storage import load_data, save_data

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load state in memory for fast checking
state = load_data()

async def main():
    if not API_ID or not API_HASH:
        logger.error("API_ID and API_HASH must be set in the .env file. Please check your configurations.")
        return

    logger.info("Initializing Telegram Client...")
    async with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
        logger.info("Client created successfully. Setting up event handler...")
        logger.info(f"Commands will be monitored in chat ID: {FORWARD_TO}")

        # --- DEBUG COMMAND: /getid ---
        @client.on(events.NewMessage(pattern=r'/getid', from_users='me'))
        async def handle_getid(event):
            chat_id = event.chat_id
            await event.respond(f"ℹ️ **Chat ID:** `{chat_id}`")
            # Stop processing this event with other handlers
            raise events.StopPropagation

        # --- COMMAND HANDLER: /comandos ---
        @client.on(events.NewMessage(chats=FORWARD_TO, pattern=r'(?i)^/comandos(.*)', from_users='me'))
        async def handle_comandos(event):
            msg = (
                "🤖 **Central de Controle - Comandos Disponíveis:**\n\n"
                "🔍 `/buscar <produto>`\n"
                "Busca ofertas retroativas nos últimos 7 dias em todos os grupos.\n"
                "Ex: `/buscar iphone`\n\n"
                "📦 `/grupos`\n"
                "Gerencia os canais monitorados.\n"
                "➕ `/grupos add nomedogrupo`\n"
                "➖ `/grupos rm nomedogrupo`\n\n"
                "🔔 `/alertas`\n"
                "Gerencia as palavras-chave monitoradas.\n"
                "➕ `/alertas add teclado`\n"
                "➖ `/alertas rm teclado`\n\n"
                "ℹ️ `/getid`\n"
                "Mostra o ID do chat atual para configurações."
            )
            await event.respond(msg)
            raise events.StopPropagation

                # --- COMMAND HANDLER: /buscar ---
        @client.on(events.NewMessage(chats=FORWARD_TO, pattern=r'(?i)^/buscar(.*)', from_users='me'))
        async def handle_buscar(event):
            args_text = event.pattern_match.group(1).strip()
            
            if not args_text:
                await event.respond("⚠️ **Uso correto:** `/buscar <produto>`\nExemplo: `/buscar notebook`")
                raise events.StopPropagation

            query = args_text.lower()
            await event.respond(f"🔍 **Buscando por:** `{query}` nos últimos 7 dias...\nIsso pode levar alguns segundos.")
            
            seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
            found_messages = []
            max_results = 30 # Limite de segurança para não floodar o grupo
            
            for group in state["grupos"]:
                try:
                    # iter_messages traz as mensagens da mais nova para a mais velha
                    async for message in client.iter_messages(group, search=query):
                        if message.date < seven_days_ago:
                            break # Passou de 7 dias, vai pro próximo grupo
                        
                        found_messages.append(message)
                except Exception as e:
                    logger.warning(f"Erro ao buscar no grupo {group}: {e}")
                    continue
                    
            # Ordena todas as mensagens coletadas globalmente (da mais recente para a mais antiga)
            found_messages.sort(key=lambda msg: msg.date, reverse=True)
            
            # Limita aos top X resultados para evitar spam
            messages_to_forward = found_messages[:max_results]
            
            for msg in messages_to_forward:
                fw_msg = await msg.forward_to(FORWARD_TO)
                
                # Coleta data e origem
                br_tz = timezone(timedelta(hours=-3))
                msg_date = msg.date.astimezone(br_tz).strftime("%d/%m/%Y às %H:%M")
                chat = await msg.get_chat()
                chat_title = getattr(chat, 'title', 'Desconhecido')
                
                # Responde à mensagem com a etiqueta (silenciosamente)
                await client.send_message(
                    FORWARD_TO,
                    f"📅 **Data da oferta:** {msg_date}\n📦 **Origem:** {chat_title}",
                    reply_to=fw_msg,
                    silent=True
                )
                
                await asyncio.sleep(0.5) # Pausa para evitar limites anti-spam (FloodWait)
                
            total_found = len(found_messages)
            forwarded_count = len(messages_to_forward)
            
            if total_found > max_results:
                await event.respond(f"✅ **Busca concluída!**\nEncontramos **{total_found}** ofertas de `{query}`.\nLimitado às **{forwarded_count}** mais recentes para evitar flood.")
            else:
                await event.respond(f"✅ **Busca concluída!**\nEncontramos **{total_found}** ofertas de `{query}`.")
            raise events.StopPropagation


        # --- COMMAND HANDLER: /grupos ---
        @client.on(events.NewMessage(chats=FORWARD_TO, pattern=r'(?i)^/grupos(.*)', from_users='me'))
        async def handle_grupos(event):
            args_text = event.pattern_match.group(1).strip()
            args = args_text.split() if args_text else []
            
            if not args:
                msg = "**📦 Grupos Monitorados:**\n" + "\n".join([f"- `{g}`" for g in state["grupos"]])
                msg += "\n\n**⚙️ Como gerenciar:**"
                msg += "\n➕ Para adicionar: `/grupos add nomedogrupo`"
                msg += "\n➖ Para remover: `/grupos rm nomedogrupo`"
                await event.respond(msg)
                return
            
            cmd = args[0].lower()
            item = " ".join(args[1:]).replace('https://web.telegram.org/k/#@', '').replace('https://t.me/', '').replace('@', '').strip()
            
            if cmd == 'add' and item:
                if item not in state["grupos"]:
                    state["grupos"].append(item)
                    save_data(state)
                    await event.respond(f"✅ Grupo `{item}` adicionado com sucesso!")
                else:
                    await event.respond("⚠️ Este grupo já está na lista.")
            elif cmd in ['rm', 'del', 'remove'] and item:
                if item in state["grupos"]:
                    state["grupos"].remove(item)
                    save_data(state)
                    await event.respond(f"🗑️ Grupo `{item}` removido.")
                else:
                    await event.respond("⚠️ Grupo não encontrado.")
            raise events.StopPropagation

        # --- COMMAND HANDLER: /alertas ---
        @client.on(events.NewMessage(chats=FORWARD_TO, pattern=r'(?i)^/alertas(.*)', from_users='me'))
        async def handle_alertas(event):
            args_text = event.pattern_match.group(1).strip()
            args = args_text.split() if args_text else []
            
            if not args:
                msg = "**🔔 Alertas Ativos:**\n" + "\n".join([f"- `{a}`" for a in state["alertas"]])
                msg += "\n\n**⚙️ Como gerenciar:**"
                msg += "\n➕ Para adicionar: `/alertas add iphone`"
                msg += "\n➖ Para remover: `/alertas rm shampoo`"
                await event.respond(msg)
                return
            
            cmd = args[0].lower()
            item = " ".join(args[1:]).lower().strip()
            
            if cmd == 'add' and item:
                if item not in state["alertas"]:
                    state["alertas"].append(item)
                    save_data(state)
                    await event.respond(f"✅ Alerta para `{item}` adicionado com sucesso!")
                else:
                    await event.respond("⚠️ Este alerta já está na lista.")
            elif cmd in ['rm', 'del', 'remove'] and item:
                if item in state["alertas"]:
                    state["alertas"].remove(item)
                    save_data(state)
                    await event.respond(f"🗑️ Alerta para `{item}` removido.")
                else:
                    await event.respond("⚠️ Alerta não encontrado.")
            raise events.StopPropagation

        # --- MAIN LISTENER (Dynamic Groups) ---
        @client.on(events.NewMessage())
        async def handler(event):
            # This check is now implicitly handled by StopPropagation in command handlers,
            # but we keep it as a safeguard for any other command you might send.
            if event.out and event.message.message and event.message.message.startswith('/'):
                return

            chat = await event.get_chat()
            if not chat:
                return
                
            chat_username = getattr(chat, 'username', '') or ''
            chat_id = str(chat.id)

            # Verifica se o chat está na nossa lista dinâmica de grupos
            is_monitored = any(g.lower() in [chat_username.lower(), chat_id] for g in state["grupos"])
            
            if is_monitored:
                message_text = event.message.message.lower() if event.message.message else ""
                for keyword in state["alertas"]:
                    if keyword.lower() in message_text:
                        chat_title = getattr(chat, 'title', 'Desconhecido')
                        logger.info(f"Keyword '{keyword}' found in chat '{chat_title}'! Forwarding...")
                        
                        fw_msg = await event.message.forward_to(FORWARD_TO)
                        
                        br_tz = timezone(timedelta(hours=-3))
                        msg_date = event.message.date.astimezone(br_tz).strftime("%d/%m/%Y às %H:%M")
                        
                        await client.send_message(
                            FORWARD_TO,
                            f"🔔 **Alerta:** `{keyword}`\n📅 **Data:** {msg_date}\n📦 **Origem:** {chat_title}",
                            reply_to=fw_msg,
                            silent=True
                        )
                        break

        logger.info("Bot is running and listening for offers! Press Ctrl+C to stop.")
        await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())