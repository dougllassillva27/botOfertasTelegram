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


class TestDestinosEmDm:
    """Envio extra em conversa individual (além do grupo com menção)."""

    MSG_DATE = datetime(2026, 10, 9, 14, 30, tzinfo=timezone.utc)

    def _payloads(self, mock_open):
        return [json.loads(chamada[0][0].data) for chamada in mock_open.call_args_list]

    def test_text_without_mention_has_no_handle(self):
        """Em DM não existe menção: o @número seria texto solto."""
        text = ws.build_offer_text("oferta", "promotop", self.MSG_DATE, mention=False)
        assert "@" + ws.WHATSAPP_MENTION_JID.split("@")[0] not in text
        assert "Nova oferta" in text
        assert "promotop" in text

    def test_sends_group_then_each_destino(self):
        destinos = [
            {"nome": "Amigo", "jid": "5551999999999@s.whatsapp.net", "keywords": ["orfeu"]},
            {"nome": "Outro", "jid": "5551888888888@s.whatsapp.net", "keywords": ["bug"]},
        ]
        with patch.object(
            ws.urllib.request,
            "urlopen",
            return_value=MagicMock(
                read=lambda: json.dumps({"success": True, "messageId": "x"}).encode(),
                __enter__=lambda s: s,
                __exit__=lambda s, *a: False,
            ),
        ) as mock_open:
            ok = ws.send_offer_to_whatsapp("oferta", "promotop", self.MSG_DATE, destinos)

        assert ok is True
        payloads = self._payloads(mock_open)
        assert len(payloads) == 3  # grupo + 2 DMs
        assert payloads[0]["chatId"] == ws.WHATSAPP_GROUP_ID
        assert payloads[0]["mentions"] == [ws.WHATSAPP_MENTION_JID]
        assert [p["chatId"] for p in payloads[1:]] == [d["jid"] for d in destinos]
        for dm in payloads[1:]:
            assert "mentions" not in dm
            assert "@555195782073" not in dm["message"]

    def test_failing_destino_does_not_block_the_rest(self):
        """Falha num DM não impede o outro nem muda o resultado do grupo."""
        destinos = [
            {"nome": "Amigo", "jid": "5551999999999@s.whatsapp.net", "keywords": ["orfeu"]},
            {"nome": "Outro", "jid": "5551888888888@s.whatsapp.net", "keywords": ["bug"]},
        ]
        calls = []

        def fake_urlopen(request, timeout=None):
            payload = json.loads(request.data)
            calls.append(payload["chatId"])
            if payload["chatId"] == "5551999999999@s.whatsapp.net":
                raise ConnectionRefusedError("down")
            return MagicMock(
                read=lambda: json.dumps({"success": True}).encode(),
                __enter__=lambda s: s,
                __exit__=lambda s, *a: False,
            )

        with patch.object(ws.urllib.request, "urlopen", side_effect=fake_urlopen):
            ok = ws.send_offer_to_whatsapp("oferta", "promotop", self.MSG_DATE, destinos)

        assert ok is True
        assert "5551888888888@s.whatsapp.net" in calls  # segundo destino tentado
        assert calls[0] == ws.WHATSAPP_GROUP_ID

    def test_destino_payload_error_is_contained(self):
        """Destino malformado (sem jid) não derruba o envio já feito ao grupo."""
        with patch.object(
            ws.urllib.request,
            "urlopen",
            return_value=MagicMock(
                read=lambda: json.dumps({"success": True}).encode(),
                __enter__=lambda s: s,
                __exit__=lambda s, *a: False,
            ),
        ):
            ok = ws.send_offer_to_whatsapp(
                "oferta", "promotop", self.MSG_DATE, [{"nome": "Quebrado"}]
            )
        assert ok is True

    def test_group_false_skips_group_post(self):
        """Keyword que só interessa a um destino não vai pro grupo do dono."""
        destino = {
            "nome": "Amigo",
            "jid": "5551999999999@s.whatsapp.net",
            "keywords": ["moedor"],
        }
        with patch.object(
            ws.urllib.request,
            "urlopen",
            return_value=MagicMock(
                read=lambda: json.dumps({"success": True}).encode(),
                __enter__=lambda s: s,
                __exit__=lambda s, *a: False,
            ),
        ) as mock_open:
            ok = ws.send_offer_to_whatsapp(
                "oferta", "promotop", self.MSG_DATE, [destino], False
            )

        assert ok is True
        payloads = self._payloads(mock_open)
        assert len(payloads) == 1
        assert payloads[0]["chatId"] == destino["jid"]
        assert "mentions" not in payloads[0]
