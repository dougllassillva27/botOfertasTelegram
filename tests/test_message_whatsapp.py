"""
Testes unitários para o disparo WhatsApp no MessageHandler.
Cobre: keyword marcada envia pra ponte; keyword sem marca não envia;
falha na ponte não derruba o fluxo do Telegram.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.handlers.message_handler import MessageHandler


def _make_event(text, chat_title="promotop", chat_username="promotop"):
    event = MagicMock()
    event.out = False
    event.message.message = text
    event.message.date = MagicMock()
    event.get_chat = AsyncMock(return_value=MagicMock(
        title=chat_title, username=chat_username, id=-100123,
    ))
    event.message.forward_to = AsyncMock(return_value=MagicMock())
    return event


@pytest.fixture
def handler(offer_service):
    client = MagicMock()
    client.send_message = AsyncMock()
    offer_service.state["grupos"] = ["promotop"]
    offer_service.state["alertas"] = ["iphone"]
    # Isola a deduplicação real (grava em arquivo) dos testes
    offer_service.deduplicator = MagicMock()
    offer_service.deduplicator.is_duplicate.return_value = (False, None, None)
    return MessageHandler(client, offer_service)


def _run(handler, event):
    import asyncio
    asyncio.run(handler.handle_message(event))


class TestWhatsappDispatch:
    """Testes para o envio condicional pro WhatsApp."""

    def test_flagged_keyword_reaches_bridge(self, handler, offer_service):
        """Keyword marcada deve chamar o sender do WhatsApp."""
        offer_service.set_whatsapp_flag("iphone", True)
        event = _make_event("iPhone por R$ 1500 https://loja.com/x")
        with patch(
            "app.handlers.message_handler.send_offer_to_whatsapp"
        ) as mock_send:
            _run(handler, event)
        mock_send.assert_called_once()

    def test_unflagged_keyword_skips_bridge(self, handler, offer_service):
        """Keyword sem marca não deve tocar na ponte."""
        event = _make_event("iPhone por R$ 1500 https://loja.com/x")
        with patch(
            "app.handlers.message_handler.send_offer_to_whatsapp"
        ) as mock_send:
            _run(handler, event)
        mock_send.assert_not_called()

    def test_bridge_failure_does_not_break_telegram_flow(self, handler):
        """Ponte fora do ar: Telegram segue normalmente, sem exceção."""
        offer_service = handler.offer_service
        offer_service.set_whatsapp_flag("iphone", True)
        event = _make_event("iPhone por R$ 1500 https://loja.com/x")
        with patch(
            "app.handlers.message_handler.send_offer_to_whatsapp",
            side_effect=ConnectionRefusedError("down"),
        ):
            _run(handler, event)  # não deve levantar exceção
        handler.client.send_message.assert_awaited_once()


class TestMultipleKeywords:
    """Oferta que bate mais de uma keyword (caso ORFEU Café de 11/10/2026)."""

    @pytest.fixture
    def cafe_e_orfeu(self, handler, offer_service):
        offer_service.state["alertas"] = ["café", "orfeu"]
        return offer_service

    def test_flagged_second_keyword_reaches_bridge(self, handler, cafe_e_orfeu):
        """`café` vem antes na lista, mas quem está marcada é `orfeu`:
        a oferta ainda assim tem que ir pro WhatsApp."""
        cafe_e_orfeu.set_whatsapp_flag("orfeu", True)
        event = _make_event(
            "TU PREFERE MOER TEUS GRÃOS?\nORFEU Café em Grãos Intenso 1 kg\n"
            "🔥 DE 169 | POR 105\nhttps://amzn.divulgador.link/bqzpZONp"
        )
        with patch(
            "app.handlers.message_handler.send_offer_to_whatsapp"
        ) as mock_send:
            _run(handler, event)
        mock_send.assert_called_once()

    def test_no_flagged_keyword_skips_bridge(self, handler, cafe_e_orfeu):
        """Duas keywords batendo, nenhuma marcada: não vai pro WhatsApp."""
        event = _make_event("ORFEU Café em Grãos Intenso 1 kg")
        with patch(
            "app.handlers.message_handler.send_offer_to_whatsapp"
        ) as mock_send:
            _run(handler, event)
        mock_send.assert_not_called()

    def test_alert_footer_lists_all_matches(self, handler, cafe_e_orfeu):
        """O aviso no Telegram mostra todas as keywords que bateram."""
        cafe_e_orfeu.set_whatsapp_flag("orfeu", True)
        event = _make_event("ORFEU Café em Grãos Intenso 1 kg")
        _run(handler, event)
        footer = handler.client.send_message.call_args[0][1]
        assert "`café`" in footer and "`orfeu`" in footer
