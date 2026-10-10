"""
Handler de callbacks — reservado para interações assíncronas.

Atualmente vazio: os botões inline de confirmação WhatsApp foram removidos
porque o Telegram descarta o reply_markup quando o remetente é conta pessoal
(userbot via MTProto) — só contas Bot API podem enviar inline keyboards.
A alternativa adotada é o comando `/alertas wa <palavra>`.

Ver rotinas/troubleshooting/whatsapp-botao-inline-nao-funciona.md no vault.
"""

import logging

logger = logging.getLogger(__name__)


class CallbackHandler:
    """Registra handlers para callbacks de botões inline."""

    def __init__(self, client, offer_service):
        self.client = client
        self.offer_service = offer_service

    def register(self):
        """Registra todos os handlers de callback."""
        # Placeholder: registrar @client.on(events.CallbackQuery()) aqui
