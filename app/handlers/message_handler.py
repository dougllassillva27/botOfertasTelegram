"""
Handler de mensagens — monitora grupos e encaminha ofertas com alertas.
"""

import logging
from datetime import timezone, timedelta

logger = logging.getLogger(__name__)


class MessageHandler:
    """Handler responsável por processar mensagens dos grupos monitorados."""

    def __init__(self, client, offer_service):
        self.client = client
        self.offer_service = offer_service

    async def handle_message(self, event):
        """Processa uma mensagem recebida e verifica se há keywords de alerta."""
        # Ignora mensagens enviadas pelo próprio bot que sejam comandos
        if (
            event.out
            and event.message.message
            and event.message.message.startswith("/")
        ):
            return

        chat = await event.get_chat()
        if not chat:
            return

        chat_username = getattr(chat, "username", "") or ""
        chat_id = str(chat.id)

        # Verifica se o chat está na lista de grupos monitorados
        is_monitored = any(
            g.lower() in [chat_username.lower(), chat_id]
            for g in self.offer_service.state["grupos"]
        )

        if not is_monitored:
            return

        message_text = event.message.message if event.message.message else ""
        matched_keyword = self.offer_service.check_keyword_match(message_text)

        if matched_keyword:
            chat_title = getattr(chat, "title", "Desconhecido")
            logger.info(
                f"Keyword '{matched_keyword}' found in chat '{chat_title}'! Forwarding..."
            )

            fw_msg = await event.message.forward_to(
                self.offer_service.state["forward_to"]
            )

            br_tz = timezone(timedelta(hours=-3))
            msg_date = event.message.date.astimezone(br_tz).strftime(
                "%d/%m/%Y às %H:%M"
            )

            await self.client.send_message(
                self.offer_service.state["forward_to"],
                f"🔔 **Alerta:** `{matched_keyword}`\n📅 **Data:** {msg_date}\n📦 **Origem:** {chat_title}",
                reply_to=fw_msg,
                silent=True,
            )
