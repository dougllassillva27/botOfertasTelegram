"""
Handler de callbacks — botões inline de confirmação WhatsApp.

Botões enviados pelo /alertas add:
  wa_sim:<keyword>  → marca o alerta pra também ir pro WhatsApp
  wa_nao:<keyword>  → mantém só no Telegram (comportamento padrão)
"""

import logging
import re
from telethon import events

logger = logging.getLogger(__name__)

CALLBACK_SIM = "wa_sim"
CALLBACK_NAO = "wa_nao"


class CallbackHandler:
    """Registra handlers para callbacks de botões inline."""

    def __init__(self, client, offer_service):
        self.client = client
        self.offer_service = offer_service

    def register(self):
        """Registra todos os handlers de callback."""
        self._register_whatsapp_confirm()

    def _register_whatsapp_confirm(self):
        pattern = re.compile(rf"^({CALLBACK_SIM}|{CALLBACK_NAO})")

        @self.client.on(events.CallbackQuery(data=pattern))
        async def handle_whatsapp_confirm(event):
            data = event.data.decode("utf-8")
            action, keyword = data.split(":", 1)

            if action == CALLBACK_SIM:
                success, msg = self.offer_service.set_whatsapp_flag(keyword, True)
            else:
                success, msg = self.offer_service.set_whatsapp_flag(keyword, False)

            # Edit remove os botões e mostra o resultado — evita cliques repetidos
            await event.edit(msg, buttons=None)
            logger.info(
                f"Callback WhatsApp [{action}] keyword='{keyword}' "
                f"success={success} by={event.sender_id}"
            )
            raise events.StopPropagation
