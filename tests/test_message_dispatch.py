"""
Testes do despacho não-bloqueante e do novo fluxo do MessageHandler.

Cobre: o handler não segura o loop de updates (processa em task), mensagem
sem keyword nem chega na deduplicação, duplicata não é encaminhada, o envio
pro WhatsApp sai por thread (não trava o event loop) e o atraso é registrado.
"""

import asyncio
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.handlers.message_handler import MessageHandler

BR_TZ = timezone(timedelta(hours=-3))


def _make_event(text, chat_title="promotop", chat_username="promotop", date=None):
    event = MagicMock()
    event.out = False
    event.message.message = text
    event.message.id = 42
    event.message.date = date or datetime.now(timezone.utc)
    event.get_chat = AsyncMock(
        return_value=MagicMock(title=chat_title, username=chat_username, id=-100123)
    )
    event.message.forward_to = AsyncMock(return_value=MagicMock())
    return event


@pytest.fixture
def handler(offer_service):
    client = MagicMock()
    client.send_message = AsyncMock()
    offer_service.state["grupos"] = ["promotop"]
    offer_service.state["alertas"] = ["iphone"]
    offer_service.deduplicator = MagicMock()
    offer_service.deduplicator.is_duplicate.return_value = (False, None, None)
    return MessageHandler(client, offer_service)


class TestDispatch:
    def test_dispatch_does_not_block_the_update_loop(self, handler):
        """O Telethon aguarda o handler; ele precisa retornar na hora."""
        event = _make_event("iPhone por R$ 1500 https://loja.com/x")

        async def slow_forward(*_args, **_kwargs):
            await asyncio.sleep(0.3)
            return MagicMock()

        event.message.forward_to = AsyncMock(side_effect=slow_forward)

        async def scenario():
            started = time.perf_counter()
            task = handler.dispatch(event)
            elapsed = time.perf_counter() - started
            await task
            return elapsed

        assert asyncio.run(scenario()) < 0.1

    def test_dispatch_logs_handler_failure_without_propagating(self, handler, caplog):
        event = _make_event("iPhone por R$ 1500 https://loja.com/x")
        event.get_chat = AsyncMock(side_effect=RuntimeError("boom"))

        async def scenario():
            await handler.dispatch(event)

        with caplog.at_level(logging.ERROR):
            asyncio.run(scenario())

        assert "Falha ao processar mensagem recebida" in caplog.text


class TestFlow:
    def test_message_without_keyword_skips_dedup(self, handler, offer_service):
        """Mensagem sem alerta não paga a comparação fuzzy."""
        event = _make_event("Panela de pressão 4,5L por R$ 99")

        asyncio.run(handler.handle_message(event))

        offer_service.deduplicator.is_duplicate.assert_not_called()
        event.message.forward_to.assert_not_awaited()

    def test_monitored_message_is_marked_even_without_keyword(self, handler):
        """Métrica do catch-up: tudo que o push viu fica marcado como visto."""
        event = _make_event("Panela de pressão 4,5L por R$ 99")

        asyncio.run(handler.handle_message(event))

        assert handler.was_processed("-100123", 42)

    def test_duplicate_is_not_forwarded(self, handler, offer_service):
        offer_service.deduplicator.is_duplicate.return_value = (
            True,
            "similaridade_95%",
            "abc",
        )
        event = _make_event("iPhone por R$ 1500 https://loja.com/x")

        asyncio.run(handler.handle_message(event))

        event.message.forward_to.assert_not_awaited()
        handler.client.send_message.assert_not_awaited()

    def test_offer_is_registered_before_forwarding(self, handler, offer_service):
        """Registro sob lock: duas entregas simultâneas não passam as duas."""
        event = _make_event("iPhone por R$ 1500 https://loja.com/x")

        asyncio.run(handler.handle_message(event))

        offer_service.deduplicator.register_offer.assert_called_once()

    def test_whatsapp_send_runs_off_the_event_loop(self, handler, offer_service):
        """A ponte é HTTP síncrono: precisa sair da thread do event loop."""
        offer_service.set_whatsapp_flag("iphone", True)
        event = _make_event("iPhone por R$ 1500 https://loja.com/x")
        seen = {}

        def fake_send(text, title, msg_date, destinos=None, group=True):
            seen["send_thread"] = threading.current_thread()
            seen["destinos"] = destinos
            return True

        async def scenario():
            seen["loop_thread"] = threading.current_thread()
            await handler.handle_message(event)

        with patch(
            "app.handlers.message_handler.send_offer_to_whatsapp",
            side_effect=fake_send,
        ) as mock_send:
            asyncio.run(scenario())

        mock_send.assert_called_once()
        assert seen["send_thread"] is not seen["loop_thread"]


class TestLagLogging:
    def test_delayed_offer_is_logged_as_warning(self, handler, caplog):
        """Oferta que chega 11 min depois (caso BUG 17:20 -> 17:31)."""
        late = datetime.now(timezone.utc) - timedelta(minutes=11)
        event = _make_event("iPhone por R$ 1500 https://loja.com/x", date=late)

        with caplog.at_level(logging.WARNING):
            asyncio.run(handler.handle_message(event))

        assert "atrasada" in caplog.text
        assert "660s" in caplog.text

    def test_fresh_offer_is_not_warned(self, handler, caplog):
        event = _make_event("iPhone por R$ 1500 https://loja.com/x")

        with caplog.at_level(logging.WARNING):
            asyncio.run(handler.handle_message(event))

        assert "atrasada" not in caplog.text


class TestSeenIds:
    def test_mark_and_check(self, handler):
        handler._mark_processed("-100123", 42)
        assert handler.was_processed("-100123", 42)
        assert not handler.was_processed("-100123", 43)

    def test_mark_is_idempotent_and_bounded(self, handler):
        from app.handlers.message_handler import SEEN_IDS_MAX

        for i in range(SEEN_IDS_MAX + 10):
            handler._mark_processed("-100123", i)
            handler._mark_processed("-100123", i)

        assert len(handler._seen) == SEEN_IDS_MAX
        assert len(handler._seen_set) == SEEN_IDS_MAX
        assert not handler.was_processed("-100123", 0)
        assert handler.was_processed("-100123", SEEN_IDS_MAX + 9)
