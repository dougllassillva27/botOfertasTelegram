"""
Testes unitários para o CallbackHandler (botões inline WhatsApp).
Cobre: clique em "sim" liga a flag, clique em "não" desliga, registro no client.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from telethon import events

from app.handlers.callback_handler import CallbackHandler


@pytest.fixture
def callback_handler(offer_service):
    client = MagicMock()
    return CallbackHandler(client, offer_service)


def _make_event(data: bytes):
    event = MagicMock()
    event.data = data
    event.sender_id = 123
    event.edit = AsyncMock()
    return event


def _extract_handler(callback_handler):
    """Registra e extrai o handler interno para teste direto."""
    registered = {}

    def fake_on(event_builder):
        def decorator(fn):
            registered["fn"] = fn
            return fn

        return decorator

    callback_handler.client.on = fake_on
    callback_handler.register()
    return registered["fn"]


def _run_handler(handler, event):
    """Executa o handler e absorve o StopPropagation do final."""
    try:
        asyncio.run(handler(event))
    except events.StopPropagation:
        pass


class TestWhatsAppConfirmCallback:
    """Testes para o callback de confirmação WhatsApp."""

    def test_sim_ligates_flag(self, callback_handler, offer_service):
        """Clique em 'sim' deve ligar a flag do alerta."""
        handler = _extract_handler(callback_handler)
        event = _make_event(b"wa_sim:iphone")
        _run_handler(handler, event)
        assert offer_service.has_whatsapp_flag("iphone") is True
        event.edit.assert_awaited_once()

    def test_nao_keeps_default(self, callback_handler, offer_service):
        """Clique em 'não' não deve ligar nada."""
        handler = _extract_handler(callback_handler)
        event = _make_event(b"wa_nao:iphone")
        _run_handler(handler, event)
        assert offer_service.has_whatsapp_flag("iphone") is False
        event.edit.assert_awaited_once()

    def test_sim_removes_buttons_after_click(self, callback_handler):
        """Após o clique, os botões devem ser removidos da mensagem."""
        handler = _extract_handler(callback_handler)
        event = _make_event(b"wa_sim:iphone")
        _run_handler(handler, event)
        _, kwargs = event.edit.await_args
        assert kwargs.get("buttons") is None

    def test_register_installs_handler(self, callback_handler):
        """register() deve instalar o handler no client."""
        callback_handler.register()
        callback_handler.client.on.assert_called_once()
