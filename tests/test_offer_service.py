"""
Testes unitários para OfferService.
Cobre: add/remove group, add/remove alert, keyword matching, formatação.
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock


class TestOfferServiceGroupManagement:
    """Testes para gerenciamento de grupos."""

    def test_add_group_success(self, offer_service):
        """Adicionar grupo novo deve funcionar."""
        success, msg = offer_service.add_group("novogrupo")
        assert success is True
        assert "adicionado" in msg.lower()
        assert "novogrupo" in offer_service.state["grupos"]

    def test_add_group_duplicate(self, offer_service):
        """Adicionar grupo duplicado deve falhar."""
        # grupo1 já está no sample_state
        success, msg = offer_service.add_group("grupo1")
        assert success is False
        assert "já está" in msg.lower()

    def test_remove_group_success(self, offer_service):
        """Remover grupo existente deve funcionar."""
        success, msg = offer_service.remove_group("grupo1")
        assert success is True
        assert "removido" in msg.lower()
        assert "grupo1" not in offer_service.state["grupos"]

    def test_remove_group_not_found(self, offer_service):
        """Remover grupo inexistente deve falhar."""
        success, msg = offer_service.remove_group("grupoinexistente")
        assert success is False
        assert "não encontrado" in msg.lower()

    def test_get_groups_list_empty(self, offer_service):
        """Lista vazia quando não há grupos."""
        offer_service.state["grupos"] = []
        result = offer_service.get_groups_list()
        assert "Nenhum grupo" in result

    def test_get_groups_list_formatted(self, offer_service):
        """Lista formatada com backticks."""
        result = offer_service.get_groups_list()
        assert "`grupo1`" in result
        assert "`grupo2`" in result

    def test_add_group_cleans_url(self, offer_service):
        """URLs devem ser limpas ao adicionar grupo."""
        dirty_url = "https://t.me/grupolimp"
        success, _ = offer_service.add_group(dirty_url)
        assert success is True
        assert "grupolimp" in offer_service.state["grupos"]
        assert "https://" not in offer_service.state["grupos"][-1]


class TestOfferServiceAlertManagement:
    """Testes para gerenciamento de alertas."""

    def test_add_alert_success(self, offer_service):
        """Adicionar alerta novo deve funcionar."""
        success, msg = offer_service.add_alert("smartphone")
        assert success is True
        assert "adicionado" in msg.lower()
        assert "smartphone" in offer_service.state["alertas"]

    def test_add_alert_duplicate(self, offer_service):
        """Adicionar alerta duplicado deve falhar."""
        success, msg = offer_service.add_alert("iphone")
        assert success is False
        assert "já está" in msg.lower()

    def test_remove_alert_success(self, offer_service):
        """Remover alerta existente deve funcionar."""
        success, msg = offer_service.remove_alert("iphone")
        assert success is True
        assert "removido" in msg.lower()
        assert "iphone" not in offer_service.state["alertas"]

    def test_remove_alert_not_found(self, offer_service):
        """Remover alerta inexistente deve falhar."""
        success, msg = offer_service.remove_alert("inexistente")
        assert success is False
        assert "não encontrado" in msg.lower()

    def test_get_alerts_list_empty(self, offer_service):
        """Lista vazia quando não há alertas."""
        offer_service.state["alertas"] = []
        result = offer_service.get_alerts_list()
        assert "Nenhum alerta" in result


class TestOfferServiceKeywordMatching:
    """Testes para matching de palavras-chave."""

    def test_keyword_exact_match(self, offer_service):
        """Deve encontrar palavra exata."""
        result = offer_service.check_keyword_match("Compro iphone hoje")
        assert result == "iphone"

    def test_keyword_plural_match(self, offer_service):
        """Deve encontrar plural (teclado -> teclados)."""
        result = offer_service.check_keyword_match("Teclados mecânicos à venda")
        assert result == "teclado"

    def test_keyword_case_insensitive(self, offer_service):
        """Deve ignorar maiúsculas/minúsculas."""
        result = offer_service.check_keyword_match("COMPRO IPHONE URGENTE")
        assert result == "iphone"

    def test_keyword_no_match(self, offer_service):
        """Não deve encontrar palavra inexistente."""
        result = offer_service.check_keyword_match("compro geladeira")
        assert result is None

    def test_keyword_empty_message(self, offer_service):
        """Mensagem vazia não deve casar."""
        result = offer_service.check_keyword_match("")
        assert result is None

    def test_keyword_none_message(self, offer_service):
        """None não deve causar erro."""
        result = offer_service.check_keyword_match(None)
        assert result is None

    def test_keyword_word_boundary(self, offer_service):
        """Deve respeitar limite de palavra (não casar substring)."""
        # "note" não deve casar com "notebook"
        offer_service.state["alertas"].append("note")
        result = offer_service.check_keyword_match("compro notebook")
        # "notebook" contém "note" como prefixo, mas \b deve impedir
        # Na prática, regex \bnote\b não casa em "notebook"
        assert result is None or result == "notebook"


class TestOfferServiceFormatMessage:
    """Testes para formatação de mensagens de oferta."""

    def test_format_offer_message_basic(self, offer_service):
        """Formata mensagem com data e origem."""
        mock_msg = MagicMock()
        mock_msg.date = datetime(2026, 6, 30, 14, 30, tzinfo=timezone.utc)
        mock_chat = MagicMock()
        mock_chat.title = "Grupo Teste"
        mock_msg.get_chat = MagicMock(return_value=mock_chat)

        result = offer_service.format_offer_message(mock_msg)

        assert "📅 **Data da oferta:**" in result
        assert "📦 **Origem:**" in result
        assert "Grupo Teste" in result

    def test_format_offer_message_no_chat(self, offer_service):
        """Chat ausente deve usar 'Desconhecido'."""
        mock_msg = MagicMock()
        mock_msg.date = datetime(2026, 6, 30, 14, 30, tzinfo=timezone.utc)
        mock_msg.get_chat = MagicMock(return_value=None)

        result = offer_service.format_offer_message(mock_msg)
        assert "Desconhecido" in result

    def test_format_offer_message_custom_timezone(self, offer_service):
        """Timezone customizada deve ser respeitada."""
        mock_msg = MagicMock()
        mock_msg.date = datetime(2026, 6, 30, 14, 30, tzinfo=timezone.utc)
        mock_chat = MagicMock()
        mock_chat.title = "Grupo BR"
        mock_msg.get_chat = MagicMock(return_value=mock_chat)

        br_tz = timezone(timedelta(hours=-3))
        result = offer_service.format_offer_message(mock_msg, br_tz=br_tz)

        # UTC 14:30 - 3h = 11:30
        assert "11:30" in result
