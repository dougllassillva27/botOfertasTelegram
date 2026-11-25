"""
Handler de comandos  -  /comandos, /buscar, /grupos, /alertas.
"""

import asyncio

from telethon import events

from app.services.whatsapp_destinos import (
    add_destino,
    list_destinos,
    remove_destino,
    set_keywords,
)


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
          ativos")  -  quem executa o comando sai sabendo onde parou
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
        self._register_tags(forward_to)
        self._register_preco(forward_to)
        self._register_wa(forward_to)

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

    def _register_tags(self, forward_to):
        """Comandos `/tags`  -  tags de urgência/promoção boa, com marca WhatsApp."""

        @self.client.on(events.NewMessage(chats=forward_to, pattern=r"(?i)^/tags(.*)"))
        async def handle_tags(event):
            args_text = event.pattern_match.group(1).strip()
            args = args_text.split() if args_text else []
            state = self.offer_service.state

            if not args or args[0].lower() in ("", "list"):
                tags_list = self.offer_service.get_promo_tags_list()
                msg = (
                    f"🏷️ **Tags de promoção ({len(self.offer_service._get_promo_tags())})**\n\n"
                    f"{tags_list}\n\n"
                    "⚙️ **Como gerenciar**\n"
                    "➕ `/tags add bug, corre, urgente`\n"
                    "➖ `/tags rm bug`\n"
                    "📲 `/tags wa bug`  -  liga/desliga o envio pro WhatsApp\n\n"
                    "💡 Uma tag dispara o encaminhamento mesmo sem keyword de produto.\n"
                    "🔁 Variantes são toleradas (corre, corree, correeee)."
                )
                await event.respond(msg)
                raise events.StopPropagation

            cmd = args[0].lower()
            item = " ".join(args[1:])
            items = self.parse_bulk_items(item)

            if cmd == "add":
                if not items:
                    await event.respond(
                        "⚠️ **Uso correto:** `/tags add bug, corre, urgente`"
                    )
                else:
                    results, _ = self.offer_service.add_promo_tags(items)
                    await event.respond(
                        self.format_bulk_response(
                            results,
                            entidade="tag",
                            verbo="adicionada",
                            total=len(self.offer_service._get_promo_tags()),
                            rotulo_total="tags de promoção",
                        )
                        + self._tags_whatsapp_hint(results)
                    )
            elif cmd == "wa":
                if not items:
                    await event.respond(
                        "⚠️ **Uso correto:** `/tags wa bug`\n"
                        "Liga/desliga o envio pro WhatsApp daquela tag."
                    )
                else:
                    for tg in items:
                        current = self.offer_service.has_promo_tag_whatsapp_flag(tg)
                        _, msg = self.offer_service.set_promo_tag_whatsapp_flag(
                            tg, not current
                        )
                        await event.respond(msg)
            elif cmd in ("rm", "del", "remove"):
                if not items:
                    await event.respond("⚠️ **Uso correto:** `/tags rm bug`")
                else:
                    results, _ = self.offer_service.remove_promo_tags(items)
                    await event.respond(
                        self.format_bulk_response(
                            results,
                            entidade="tag",
                            verbo="removida",
                            total=len(self.offer_service._get_promo_tags()),
                            rotulo_total="tags de promoção",
                        )
                    )
            else:
                await event.respond(
                    "⚠️ **Comando não reconhecido.**\n\n"
                    "📋 `/tags`  -  lista as tags\n"
                    "➕ `/tags add bug, corre`\n"
                    "➖ `/tags rm bug`\n"
                    "📲 `/tags wa bug`"
                )

            raise events.StopPropagation

    @staticmethod
    def _tags_whatsapp_hint(results):
        added = [item for item, ok, _ in results if ok]
        if not added:
            return ""
        tg = added[0] if len(added) == 1 else "<tag>"
        return (
            "\n\n📲 **Pra enviar também no WhatsApp:** `/tags wa " + tg + "`"
            " (liga/desliga a qualquer momento)"
        )

    def _register_preco(self, forward_to):
        """Comandos `/preco` - regras de 'valor bom' por desconto/preço."""

        @self.client.on(events.NewMessage(chats=forward_to, pattern=r"(?i)^/preco(.*)"))
        async def handle_preco(event):
            args_text = event.pattern_match.group(1).strip()
            args = args_text.split() if args_text else []

            if not args:
                rules_text = (
                    "💰 **Regras de preço bom**\n\n"
                    "Desconto mínimo: {}%\n".format(self.offer_service.get_price_discount_min())
                    + "Teto de preço: R$ {}\n".format(self.offer_service.get_price_max())
                    + "WhatsApp: {}\n\n".format(
                        "ligado 📲" if self.offer_service.has_price_whatsapp_flag() else "desligado"
                    )
                    + "⚙️ **Como ajustar**\n"
                    + "/preco desconto 60\n"
                    + "/preco teto 20\n"
                    + "/preco wa   (liga/desliga WhatsApp)"
                )
                await event.respond(rules_text)
                raise events.StopPropagation

            cmd = args[0].lower()

            if cmd == "desconto":
                if len(args) < 2:
                    await event.respond("⚠️ Uso: /preco desconto 60")
                else:
                    ok, msg = self.offer_service.set_price_discount_min(args[1])
                    await event.respond(msg)
            elif cmd == "teto":
                if len(args) < 2:
                    await event.respond("⚠️ Uso: /preco teto 20")
                else:
                    ok, msg = self.offer_service.set_price_max(args[1])
                    await event.respond(msg)
            elif cmd == "wa":
                current = self.offer_service.has_price_whatsapp_flag()
                ok, msg = self.offer_service.set_price_whatsapp_flag(not current)
                await event.respond(msg)
            else:
                await event.respond(
                    "⚠️ Comando não reconhecido.\n\n"
                    "📋 /preco - mostra as regras\n"
                    "📉 /preco desconto 60\n"
                    "💵 /preco teto 20\n"
                    "📲 /preco wa"
                )

            raise events.StopPropagation

    def _register_wa(self, forward_to):
        """Comandos `/wa`  -  destinos extras em DM, com recorte de keywords."""

        @self.client.on(events.NewMessage(chats=forward_to, pattern=r"(?i)^/wa(.*)"))
        async def handle_wa(event):
            args_text = event.pattern_match.group(1).strip()
            args = args_text.split() if args_text else []
            cmd = args[0].lower() if args else ""
            state = self.offer_service.state

            if cmd in ("", "list"):
                await event.respond(list_destinos(state))
                raise events.StopPropagation

            if cmd == "add":
                if len(args) < 3:
                    await event.respond(
                        "⚠️ **Uso correto:** `/wa add Amigo 5551999999999`\n"
                        "📱 Número no formato DDI+DDD+número (só dígitos).\n"
                        "🔔 Depois escolha o que ele recebe: `/wa kw Amigo orfeu`"
                    )
                    raise events.StopPropagation
                keywords = self.parse_bulk_items(" ".join(args[3:]))
                _, msg = add_destino(state, args[1], args[2], keywords)
                await event.respond(msg)
                raise events.StopPropagation

            if cmd == "kw":
                if len(args) < 2:
                    await event.respond(
                        "⚠️ **Uso correto:** `/wa kw Amigo orfeu, bug`\n"
                        "🔕 Sem keywords: `/wa kw Amigo` (para de receber)"
                    )
                    raise events.StopPropagation
                keywords = self.parse_bulk_items(" ".join(args[2:]))
                _, msg = set_keywords(state, args[1], keywords)
                await event.respond(msg)
                raise events.StopPropagation

            if cmd in ("rm", "del", "remove"):
                if len(args) < 2:
                    await event.respond("⚠️ **Uso correto:** `/wa rm Amigo`")
                    raise events.StopPropagation
                _, msg = remove_destino(state, args[1])
                await event.respond(msg)
                raise events.StopPropagation

            await event.respond(
                "⚠️ **Comando não reconhecido.**\n\n"
                "📋 `/wa`  -  lista os destinos\n"
                "➕ `/wa add Amigo 5551999999999`\n"
                "🔔 `/wa kw Amigo orfeu, bug`\n"
                "➖ `/wa rm Amigo`"
            )
            raise events.StopPropagation

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
            msg = """🤖 Central de Controle - Comandos Disponíveis:

🔍 /buscar <produto>
Busca ofertas retroativas nos últimos 7 dias em todos os grupos.
Ex: /buscar iphone

📦 /grupos
Gerencia os canais monitorados.
➕ /grupos add nomedogrupo
➖ /grupos rm nomedogrupo
💡 Em massa: /grupos add grupo1, grupo2

🔔 /alertas
Gerencia as palavras-chave monitoradas.
➕ /alertas add teclado
➖ /alertas rm teclado
📲 /alertas wa teclado  -  liga/desliga o envio pro WhatsApp
💡 Em massa: /alertas add iphone, caixa de som

🏷️ /tags
Gerencia tags de promoção boa (bug, corre, urgente...).
➕ /tags add bug, corre
➖ /tags rm bug
📲 /tags wa bug  -  liga/desliga o envio pro WhatsApp

💰 /preco
Regras de 'valor bom' por desconto/preço.
📉 /preco desconto 60
💵 /preco teto 20
📲 /preco wa - liga/desliga o envio pro WhatsApp

📤 /wa
Gerencia quem mais recebe as ofertas no WhatsApp (DM).
➕ /wa add Amigo 5551999999999
🔔 /wa kw Amigo orfeu, bug  -  o que ele recebe
➖ /wa rm Amigo
⚠️ Só recebe palavras que já são alertas ativos (/alertas add).

ℹ️ /getid
Mostra o ID do chat atual para configurações."""
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
                    "📲 `/alertas wa palavra`  -  vai pro WhatsApp também"
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
