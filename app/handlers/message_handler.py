"""
Handler de mensagens — monitora grupos e encaminha ofertas com alertas.
"""

import logging
from datetime import timezone, timedelta
from app.services.whatsapp_sender import send_offer_to_whatsapp

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

        # Extrai info da oferta para verificar duplicidade
        title, description, url = self.offer_service.extract_offer_info(message_text)

        # Verifica se deve enviar (não é duplicata)
        should_send, reason = self.offer_service.should_send_offer(title, description, url)

        if not should_send:
            return

        matched_keywords = self.offer_service.check_keyword_matches(message_text)

        if matched_keywords:
            chat_title = getattr(chat, "title", "Desconhecido")
            logger.info(
                f"Keyword(s) {matched_keywords} found in chat '{chat_title}'!"
                " Forwarding..."
            )

            fw_msg = await event.message.forward_to(
                self.offer_service.state["forward_to"]
            )

            br_tz = timezone(timedelta(hours=-3))
            msg_date = event.message.date.astimezone(br_tz).strftime(
                "%d/%m/%Y às %H:%M"
            )

            # Registra oferta como enviada e atualiza grupo de destino
            title, description, url = self.offer_service.extract_offer_info(message_text)
            if title:
                self.offer_service.register_sent_offer(title, description, url, [chat_title])

            alert_label = ", ".join(f"`{kw}`" for kw in matched_keywords)
            await self.client.send_message(
                self.offer_service.state["forward_to"],
                f"🔔 **Alerta:** {alert_label}\n📅 **Data:** {msg_date}\n📦 **Origem:** {chat_title}",
                reply_to=fw_msg,
                silent=True,
            )

            # Destino extra: se QUALQUER keyword da mensagem estiver marcada,
            # a oferta vai pro WhatsApp (não só a primeira da lista — uma
            # oferta de café Orfeu bate `café` e `orfeu`).
            flagged = [
                kw
                for kw in matched_keywords
                if self.offer_service.has_whatsapp_flag(kw)
            ]
            if flagged:
                logger.info(f"Enviando oferta pro WhatsApp pelos alertas {flagged}")
                try:
                    send_offer_to_whatsapp(message_text, chat_title, event.message.date)
                except Exception as e:
                    logger.warning(f"Falha ao enviar oferta pro WhatsApp: {e}")
