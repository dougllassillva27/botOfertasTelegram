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

    @staticmethod
    def parse_bulk_items(text):
        """Converte texto em lista de itens para operações em massa.

        Divide por vírgula, remove espaços das pontas, descarta vazios
        e elimina duplicatas preservando a ordem original.
        """
        items = []
        for part in text.split(","):
            item = part.strip()
            if item and item not in items:
                items.append(item)
        return items

    @staticmethod
    def format_bulk_response(
        results,
        entidade="alerta",
        verbo="adicionado",
        total=None,
        rotulo_total="alertas ativos",
    ):
        """Monta a resposta de add/rm: o que mudou, o que não mudou e o total.

        - `entidade`/`verbo` dão o título no singular ("Alerta adicionado") ou
          no plural ("2 alertas adicionados")
        - `total` + `rotulo_total` fecham com o estado atual ("📊 14 alertas
          ativos") — quem executa o comando sai sabendo onde parou
        - itens que não mudaram vêm com o motivo, um por linha
        """
        ok_items = [item for item, ok, _ in results if ok]
        fail_items = [(item, msg) for item, ok, msg in results if not ok]

        blocks = []

        if ok_items:
            emoji = "🗑️" if verbo.startswith("remov") else "✅"
            if len(ok_items) == 1:
                titulo = f"{entidade.capitalize()} {verbo}"
            else:
                titulo = f"{len(ok_items)} {entidade}s {verbo}s"
            linhas = "\n".join(f"• `{item}`" for item in ok_items)
            blocks.append(f"{emoji} **{titulo}**\n\n{linhas}")

        if fail_items:
            linhas = "\n".join(f"• `{item}`: {msg}" for item, msg in fail_items)
            blocks.append(f"⚠️ **{len(fail_items)} sem alteração**\n\n{linhas}")

        if total is not None:
            blocks.append(f"📊 **{total}** {rotulo_total}")

        return "\n\n".join(blocks)

    def register(self, forward_to):
        """Registra todos os handlers de comando no cliente Telegram."""
        self._register_getid()
        self._register_comandos(forward_to)
        self._register_buscar(forward_to)
        self._register_grupos(forward_to)
        self._register_alertas(forward_to)

    @staticmethod
    def whatsapp_hint(results):
        """Dica de envio pro WhatsApp após adicionar alertas.

        Os botões inline não funcionam em userbot: o Telegram descarta o
        reply_markup quando o remetente é conta pessoal (não Bot API).
        Ver rotinas/troubleshooting/whatsapp-botao-inline-nao-funciona.md
        """
        added = [item for item, ok, _ in results if ok]
        if not added:
            return ""
        kw = added[0] if len(added) == 1 else "<palavra>"
        return (
            "\n\n📲 **Pra enviar também no WhatsApp:** `/alertas wa " + kw + "`"
            " (liga/desliga a qualquer momento)"
        )

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
                "➖ `/grupos rm nomedogrupo`\n"
                "💡 Em massa: `/grupos add grupo1, grupo2`\n\n"
                "🔔 `/alertas`\n"
                "Gerencia as palavras-chave monitoradas.\n"
                "➕ `/alertas add teclado`\n"
                "➖ `/alertas rm teclado`\n"
                "📲 `/alertas wa teclado` — liga/desliga o envio pro WhatsApp\n"
                "💡 Em massa: `/alertas add iphone, caixa de som`\n\n"
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
                grupos = self.offer_service.state["grupos"]
                grupos_list = self.offer_service.get_groups_list()
                msg = (
                    f"📦 **Grupos monitorados ({len(grupos)})**\n\n"
                    f"{grupos_list}\n\n"
                    "⚙️ **Como gerenciar**\n"
                    "➕ `/grupos add nomedogrupo`\n"
                    "➖ `/grupos rm nomedogrupo`\n"
                    "💡 Em massa: `/grupos add grupo1, grupo2`"
                )
                await event.respond(msg)
                return

            cmd = args[0].lower()
            item = " ".join(args[1:])
            items = self.parse_bulk_items(item)

            if cmd == "add":
                if not items:
                    await event.respond(
                        "⚠️ **Uso correto:** `/grupos add grupo1, grupo2, grupo3`"
                    )
                else:
                    results, _ = self.offer_service.add_groups(items)
                    await event.respond(
                        self.format_bulk_response(
                            results,
                            entidade="grupo",
                            verbo="adicionado",
                            total=len(self.offer_service.state["grupos"]),
                            rotulo_total="grupos monitorados",
                        )
                    )
            elif cmd in ["rm", "del", "remove"]:
                if not items:
                    await event.respond(
                        "⚠️ **Uso correto:** `/grupos rm grupo1, grupo2`"
                    )
                else:
                    results, _ = self.offer_service.remove_groups(items)
                    await event.respond(
                        self.format_bulk_response(
                            results,
                            entidade="grupo",
                            verbo="removido",
                            total=len(self.offer_service.state["grupos"]),
                            rotulo_total="grupos monitorados",
                        )
                    )

            raise events.StopPropagation

    def _register_alertas(self, forward_to):
        @self.client.on(
            events.NewMessage(chats=forward_to, pattern=r"(?i)^/alertas(.*)")
        )
        async def handle_alertas(event):
            args_text = event.pattern_match.group(1).strip()
            args = args_text.split() if args_text else []

            if not args:
                alertas = self.offer_service.state["alertas"]
                alerts_list = self.offer_service.get_alerts_list()
                msg = (
                    f"🔔 **Alertas ativos ({len(alertas)})**\n\n"
                    f"{alerts_list}\n\n"
                    "⚙️ **Como gerenciar**\n"
                    "➕ `/alertas add palavra`\n"
                    "➖ `/alertas rm palavra`\n"
                    "📲 `/alertas wa palavra` — vai pro WhatsApp também"
                )
                await event.respond(msg)
                return

            cmd = args[0].lower()
            item = " ".join(args[1:])
            items = self.parse_bulk_items(item)

            if cmd == "add":
                if not items:
                    await event.respond(
                        "⚠️ **Uso correto:** `/alertas add iphone, teclado mecanico`"
                    )
                else:
                    results, _ = self.offer_service.add_alerts(items)
                    await event.respond(
                        self.format_bulk_response(
                            results,
                            entidade="alerta",
                            verbo="adicionado",
                            total=len(self.offer_service.state["alertas"]),
                            rotulo_total="alertas ativos",
                        )
                        + self.whatsapp_hint(results)
                    )
            elif cmd == "wa":
                if not items:
                    await event.respond(
                        "⚠️ **Uso correto:** `/alertas wa iphone`\n"
                        "Liga/desliga o envio pro WhatsApp daquele alerta."
                    )
                else:
                    for kw in items:
                        current = self.offer_service.has_whatsapp_flag(kw)
                        _, msg = self.offer_service.set_whatsapp_flag(kw, not current)
                        await event.respond(msg)
            elif cmd in ["rm", "del", "remove"]:
                if not items:
                    await event.respond(
                        "⚠️ **Uso correto:** `/alertas rm iphone, shampoo`"
                    )
                else:
                    # Pega as marcas WhatsApp ANTES da remoção (o remove limpa junto)
                    wa_removidos = [
                        kw
                        for kw in items
                        if self.offer_service.has_whatsapp_flag(kw)
                    ]
                    results, _ = self.offer_service.remove_alerts(items)
                    msg = self.format_bulk_response(
                        results,
                        entidade="alerta",
                        verbo="removido",
                        total=len(self.offer_service.state["alertas"]),
                        rotulo_total="alertas ativos",
                    )
                    if wa_removidos:
                        msg += (
                            "\n\n🔕 Também saiu do envio pro WhatsApp: "
                            + ", ".join(f"`{kw}`" for kw in wa_removidos)
                        )
                    await event.respond(msg)

            raise events.StopPropagation
