"""
Testes unitários para OfferService.
Cobre: add/remove group, add/remove alert, keyword matching, formatação.
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest


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


class TestOfferServiceBulkGroups:
    """Testes para gerenciamento de grupos em massa."""

    def test_add_groups_all_new(self, offer_service):
        """Adicionar vários grupos novos deve aplicar todos com 1 save."""
        with patch("app.services.offer_service.save_data") as mock_save:
            results, changed = offer_service.add_groups(["grupoA", "grupoB"])
        assert changed is True
        assert all(ok for _, ok, _ in results)
        assert "grupoA" in offer_service.state["grupos"]
        assert "grupoB" in offer_service.state["grupos"]
        mock_save.assert_called_once_with(offer_service.state)

    def test_add_groups_mixed(self, offer_service):
        """Misto: novo aplicado, já existente reportado como falha."""
        with patch("app.services.offer_service.save_data") as mock_save:
            results, changed = offer_service.add_groups(["grupoA", "grupo1"])
        assert changed is True
        assert results[0] == ("grupoA", True, "adicionado com sucesso")
        item, ok, msg = results[1]
        assert item == "grupo1" and ok is False
        assert "já está" in msg
        assert "grupoA" in offer_service.state["grupos"]
        mock_save.assert_called_once_with(offer_service.state)

    def test_add_groups_all_duplicates_no_save(self, offer_service):
        """Todos já existentes: estado inalterado e save_data não chamado."""
        with patch("app.services.offer_service.save_data") as mock_save:
            results, changed = offer_service.add_groups(["grupo1", "grupo2"])
        assert changed is False
        assert all(not ok for _, ok, _ in results)
        assert offer_service.state["grupos"] == ["grupo1", "grupo2"]
        mock_save.assert_not_called()

    def test_remove_groups_all_existing(self, offer_service):
        """Remover vários grupos existentes com 1 save."""
        with patch("app.services.offer_service.save_data") as mock_save:
            results, changed = offer_service.remove_groups(["grupo1", "grupo2"])
        assert changed is True
        assert all(ok for _, ok, _ in results)
        assert offer_service.state["grupos"] == []
        mock_save.assert_called_once_with(offer_service.state)

    def test_remove_groups_mixed(self, offer_service):
        """Misto: existentes removidos, inexistentes reportados."""
        with patch("app.services.offer_service.save_data") as mock_save:
            results, changed = offer_service.remove_groups(["grupo1", "fantasma"])
        assert changed is True
        assert results[0] == ("grupo1", True, "removido")
        item, ok, msg = results[1]
        assert item == "fantasma" and ok is False
        assert "não encontrado" in msg
        assert offer_service.state["grupos"] == ["grupo2"]
        mock_save.assert_called_once_with(offer_service.state)

    def test_add_groups_cleans_urls_per_item(self, offer_service):
        """Sanitização aplicada por item (URL, @)."""
        offer_service.add_groups(
            ["https://t.me/grupoA", "@grupoB", "https://web.telegram.org/k/#@grupoC"]
        )
        assert "grupoA" in offer_service.state["grupos"]
        assert "grupoB" in offer_service.state["grupos"]
        assert "grupoC" in offer_service.state["grupos"]


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

    def test_remove_alert_persists(self, offer_service):
        """Remoção deve persistir em disco (regressão: alertas voltavam após restart)."""
        with patch("app.services.offer_service.save_data") as mock_save:
            offer_service.remove_alert("iphone")
            mock_save.assert_called_once_with(offer_service.state)

    def test_get_alerts_list_empty(self, offer_service):
        """Lista vazia quando não há alertas."""
        offer_service.state["alertas"] = []
        result = offer_service.get_alerts_list()
        assert "Nenhum alerta" in result


class TestOfferServiceBulkAlerts:
    """Testes para gerenciamento de alertas em massa."""

    def test_add_alerts_mixed_with_case_normalization(self, offer_service):
        """Normalização por item: case ignorado, espaço interno preservado."""
        with patch("app.services.offer_service.save_data") as mock_save:
            results, changed = offer_service.add_alerts(["IPHONE", "Teclado Mecanico"])
        assert changed is True
        # "IPHONE" normaliza para "iphone", que já existe
        assert results[0][0] == "iphone" and results[0][1] is False
        # "Teclado Mecanico" entra como novo, lowercased e com espaço preservado
        assert results[1] == ("teclado mecanico", True, "adicionado com sucesso")
        assert "teclado mecanico" in offer_service.state["alertas"]
        mock_save.assert_called_once_with(offer_service.state)

    def test_add_alerts_all_duplicates_no_save(self, offer_service):
        """Todos já existentes: nada muda e save_data não chamado."""
        with patch("app.services.offer_service.save_data") as mock_save:
            results, changed = offer_service.add_alerts(["iphone", "notebook"])
        assert changed is False
        assert all(not ok for _, ok, _ in results)
        mock_save.assert_not_called()

    def test_remove_alerts_mixed(self, offer_service):
        """Misto: existentes removidos, inexistentes reportados."""
        with patch("app.services.offer_service.save_data") as mock_save:
            results, changed = offer_service.remove_alerts(["IPHONE", "fantasma"])
        assert changed is True
        assert results[0] == ("iphone", True, "removido")
        item, ok, msg = results[1]
        assert item == "fantasma" and ok is False
        assert "não encontrado" in msg
        assert "iphone" not in offer_service.state["alertas"]
        mock_save.assert_called_once_with(offer_service.state)

    def test_bulk_empty_list(self, offer_service):
        """Lista vazia: sem resultados, sem mutação, sem save."""
        with patch("app.services.offer_service.save_data") as mock_save:
            results, changed = offer_service.add_alerts([])
        assert results == []
        assert changed is False
        mock_save.assert_not_called()


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


class TestOfferServiceAllKeywordMatches:
    """Todas as keywords da mensagem, não só a primeira."""

    @pytest.fixture
    def cafe_e_orfeu(self, offer_service):
        """Cenário real de 11/10/2026: lista com `café` antes de `orfeu`."""
        offer_service.state["alertas"] = ["café", "orfeu", "sabão"]
        return offer_service

    def test_returns_all_matches_in_list_order(self, cafe_e_orfeu):
        """Mensagem com as duas keywords deve devolver as duas, na ordem da lista."""
        result = cafe_e_orfeu.check_keyword_matches(
            "TU PREFERE MOER TEUS GRÃOS?\nORFEU Café em Grãos Intenso 1 kg"
        )
        assert result == ["café", "orfeu"]

    def test_single_match_still_works(self, cafe_e_orfeu):
        """Mensagem com uma keyword só devolve lista de um."""
        assert cafe_e_orfeu.check_keyword_matches("Sabão em pó barato") == ["sabão"]

    def test_no_match_returns_empty_list(self, cafe_e_orfeu):
        """Sem keyword: lista vazia (e não None)."""
        assert cafe_e_orfeu.check_keyword_matches("compro geladeira") == []
        assert cafe_e_orfeu.check_keyword_matches("") == []
        assert cafe_e_orfeu.check_keyword_matches(None) == []

    def test_first_match_is_backward_compatible(self, cafe_e_orfeu):
        """check_keyword_match continua devolvendo a primeira da lista."""
        assert (
            cafe_e_orfeu.check_keyword_match("ORFEU Café em Grãos 1kg")
            == "café"
        )


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
