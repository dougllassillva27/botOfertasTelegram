"""
Handler de comandos — /comandos, /buscar, /grupos, /alertas.
"""

import asyncio
from telethon import events


class CommandHandler:
    """Registra e processa todos os comandos do bot."""

    def __init__(self, client, offer_service):
        self.client = client
        self.offer_service = offer_service

    def register(self, forward_to):
        """Registra todos os handlers de comando no cliente Telegram."""
        self._register_getid()
        self._register_comandos(forward_to)
        self._register_buscar(forward_to)
        self._register_grupos(forward_to)
        self._register_alertas(forward_to)

    def _register_getid(self):
        @self.client.on(events.NewMessage(pattern=r"/getid", from_users="me"))
        async def handle_getid(event):
            chat_id = event.chat_id
            await event.respond(f"ℹ️ **Chat ID:** `{chat_id}`")
            raise events.StopPropagation

    def _register_comandos(self, forward_to):
        @self.client.on(
            events.NewMessage(chats=forward_to, pattern=r"(?i)^/comandos(.*)")
        )
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

    def _register_buscar(self, forward_to):
        @self.client.on(
            events.NewMessage(chats=forward_to, pattern=r"(?i)^/buscar(.*)")
        )
        async def handle_buscar(event):
            args_text = event.pattern_match.group(1).strip()

            if not args_text:
                await event.respond(
                    "⚠️ **Uso correto:** `/buscar <produto>`\nExemplo: `/buscar notebook`"
                )
                raise events.StopPropagation

            query = args_text.lower()
            await event.respond(
                f"🔍 **Buscando por:** `{query}` nos últimos 7 dias...\nIsso pode levar alguns segundos."
            )

            (
                found_messages,
                messages_to_forward,
            ) = await self.offer_service.search_offers(self.client, query)

            for msg in messages_to_forward:
                fw_msg = await msg.forward_to(forward_to)
                label = self.offer_service.format_offer_message(msg)

                await self.client.send_message(
                    forward_to, label, reply_to=fw_msg, silent=True
                )
                await asyncio.sleep(0.5)

            total_found = len(found_messages)
            forwarded_count = len(messages_to_forward)

            if total_found > forwarded_count:
                await event.respond(
                    f"✅ **Busca concluída!**\nEncontramos **{total_found}** ofertas de `{query}`.\n"
                    f"Limitado às **{forwarded_count}** mais recentes para evitar flood."
                )
            else:
                await event.respond(
                    f"✅ **Busca concluída!**\nEncontramos **{total_found}** ofertas de `{query}`."
                )

            raise events.StopPropagation

    def _register_grupos(self, forward_to):
        @self.client.on(
            events.NewMessage(chats=forward_to, pattern=r"(?i)^/grupos(.*)")
        )
        async def handle_grupos(event):
            args_text = event.pattern_match.group(1).strip()
            args = args_text.split() if args_text else []

            if not args:
                groups_list = self.offer_service.get_groups_list()
                msg = (
                    "**📦 Grupos Monitorados:**\n"
                    + groups_list
                    + "\n\n**⚙️ Como gerenciar:**"
                    + "\n➕ Para adicionar: `/grupos add nomedogrupo`"
                    + "\n➖ Para remover: `/grupos rm nomedogrupo`"
                )
                await event.respond(msg)
                return

            cmd = args[0].lower()
            item = " ".join(args[1:])

            if cmd == "add" and item:
                success, response_msg = self.offer_service.add_group(item)
                await event.respond(response_msg)
            elif cmd in ["rm", "del", "remove"] and item:
                success, response_msg = self.offer_service.remove_group(item)
                await event.respond(response_msg)

            raise events.StopPropagation

    def _register_alertas(self, forward_to):
        @self.client.on(
            events.NewMessage(chats=forward_to, pattern=r"(?i)^/alertas(.*)")
        )
        async def handle_alertas(event):
            args_text = event.pattern_match.group(1).strip()
            args = args_text.split() if args_text else []

            if not args:
                alerts_list = self.offer_service.get_alerts_list()
                msg = (
                    "**🔔 Alertas Ativos:**\n"
                    + alerts_list
                    + "\n\n**⚙️ Como gerenciar:**"
                    + "\n➕ Para adicionar: `/alertas add iphone`"
                    + "\n➖ Para remover: `/alertas rm shampoo`"
                )
                await event.respond(msg)
                return

            cmd = args[0].lower()
            item = " ".join(args[1:])

            if cmd == "add" and item:
                success, response_msg = self.offer_service.add_alert(item)
                await event.respond(response_msg)
            elif cmd in ["rm", "del", "remove"] and item:
                success, response_msg = self.offer_service.remove_alert(item)
                await event.respond(response_msg)

            raise events.StopPropagation
