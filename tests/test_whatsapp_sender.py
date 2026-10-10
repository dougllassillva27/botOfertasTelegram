"""
Testes unitários para o whatsapp_sender.
Cobre: montagem do texto (com/sem link, sem texto) e envio (mock da ponte).
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import app.services.whatsapp_sender as ws


class TestBuildOfferText:
    """Testes para a montagem do texto da oferta."""

    def test_contains_original_text(self):
        """Texto original deve aparecer na mensagem."""
        msg_date = datetime(2026, 10, 9, 14, 30, tzinfo=timezone.utc)
        text = ws.build_offer_text("iPhone por R$ 1500 https://loja.com/x", "promotop", msg_date)
        assert "iPhone por R$ 1500" in text
        assert "https://loja.com/x" in text

    def test_contains_origin_and_date(self):
        """Origem e data (horário de Brasília) devem aparecer."""
        msg_date = datetime(2026, 10, 9, 14, 30, tzinfo=timezone.utc)
        text = ws.build_offer_text("oferta", "promotop", msg_date)
        assert "promotop" in text
        assert "09/10/2026 às 11:30" in text  # UTC-3

    def test_handles_empty_text(self):
        """Mensagem sem texto não deve quebrar."""
        msg_date = datetime(2026, 10, 9, 14, 30, tzinfo=timezone.utc)
        text = ws.build_offer_text("", "promotop", msg_date)
        assert "(sem texto)" in text

    def test_text_carries_mention_handle(self):
        """O @número PRECISA estar no corpo do texto.

        Regressão: o campo `mentions` sozinho não renderiza nem notifica —
        o WhatsApp só cria a menção quando o @número aparece no texto
        (validado em teste real em 09/10/2026).
        """
        msg_date = datetime(2026, 10, 9, 14, 30, tzinfo=timezone.utc)
        text = ws.build_offer_text("oferta", "promotop", msg_date)
        expected_handle = "@" + ws.WHATSAPP_MENTION_JID.split("@")[0]
        assert expected_handle in text


class TestSendOfferToWhatsapp:
    """Testes para o envio (ponte mockada)."""

    def _mock_response(self, body):
        resp = MagicMock()
        resp.read.return_value = json.dumps(body).encode("utf-8")
        resp.__enter__ = lambda s: resp
        resp.__exit__ = lambda s, *a: False
        return resp

    def test_posts_payload_with_mentions(self):
        """POST deve incluir grupo, texto e menção nativa."""
        msg_date = datetime(2026, 10, 9, 14, 30, tzinfo=timezone.utc)
        with patch.object(
            ws.urllib.request,
            "urlopen",
            return_value=self._mock_response({"success": True, "messageId": "abc"}),
        ) as mock_open:
            ok = ws.send_offer_to_whatsapp("oferta", "promotop", msg_date)

        assert ok is True
        request = mock_open.call_args[0][0]
        assert request.full_url == f"{ws.BRIDGE_URL}/send"
        payload = json.loads(request.data)
        assert payload["chatId"] == ws.WHATSAPP_GROUP_ID
        assert payload["mentions"] == [ws.WHATSAPP_MENTION_JID]
        assert "oferta" in payload["message"]

    def test_returns_false_on_bridge_error(self):
        """Erro de rede não deve propagar — retorna False (extra opcional)."""
        msg_date = datetime(2026, 10, 9, 14, 30, tzinfo=timezone.utc)
        with patch.object(
            ws.urllib.request, "urlopen", side_effect=ConnectionRefusedError("down")
        ):
            ok = ws.send_offer_to_whatsapp("oferta", "promotop", msg_date)
        assert ok is False

    def test_returns_false_when_bridge_rejects(self):
        """success=false na resposta deve retornar False."""
        msg_date = datetime(2026, 10, 9, 14, 30, tzinfo=timezone.utc)
        with patch.object(
            ws.urllib.request,
            "urlopen",
            return_value=self._mock_response({"success": False, "error": "Not connected"}),
        ):
            ok = ws.send_offer_to_whatsapp("oferta", "promotop", msg_date)
        assert ok is False
