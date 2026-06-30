"""
Handler de callbacks — botões inline e interações assíncronas.

Atualmente vazio, reservado para expansão futura com botões
e interações via InlineKeyboard.
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
        pass
