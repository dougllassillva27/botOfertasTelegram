"""
Testes unitários para a flag "whatsapp" dos alertas.
Cobre: ligar, desligar, verificar, limpeza automática no remove.
"""

import pytest
from unittest.mock import MagicMock


class TestWhatsAppFlag:
    """Testes para gerenciamento da marca whatsapp dos alertas."""

    def test_has_whatsapp_flag_false_by_default(self, offer_service):
        """Alerta sem marca não deve reportar flag."""
        assert offer_service.has_whatsapp_flag("iphone") is False

    def test_set_whatsapp_flag_success(self, offer_service):
        """Marcar alerta existente deve funcionar."""
        success, msg = offer_service.set_whatsapp_flag("iphone", True)
        assert success is True
        assert "whatsapp" in msg.lower()
        assert offer_service.has_whatsapp_flag("iphone") is True

    def test_set_whatsapp_flag_normalizes_keyword(self, offer_service):
        """Marca deve normalizar minúsculas/espaços igual aos alertas."""
        offer_service.state["alertas"].append("teclado mecanico")
        success, _ = offer_service.set_whatsapp_flag("  Teclado Mecanico ", True)
        assert success is True
        assert offer_service.has_whatsapp_flag("teclado mecanico") is True

    def test_set_whatsapp_flag_unmarks(self, offer_service):
        """Desligar a marca deve remover a flag."""
        offer_service.set_whatsapp_flag("iphone", True)
        success, msg = offer_service.set_whatsapp_flag("iphone", False)
        assert success is True
        assert offer_service.has_whatsapp_flag("iphone") is False

    def test_set_whatsapp_flag_unknown_alert(self, offer_service):
        """Marcar alerta inexistente deve falhar."""
        success, msg = offer_service.set_whatsapp_flag("naoexiste", True)
        assert success is False
        assert "não encontrado" in msg.lower()

    def test_remove_alert_clears_whatsapp_flag(self, offer_service):
        """Remover alerta deve limpar a marca whatsapp junto."""
        offer_service.set_whatsapp_flag("iphone", True)
        offer_service.remove_alert("iphone")
        assert offer_service.has_whatsapp_flag("iphone") is False

    def test_remove_alerts_bulk_clears_flags(self, offer_service):
        """Remove em massa também limpa as marcas."""
        offer_service.set_whatsapp_flag("iphone", True)
        offer_service.set_whatsapp_flag("notebook", True)
        offer_service.remove_alerts(["iphone", "notebook"])
        assert offer_service.has_whatsapp_flag("iphone") is False
        assert offer_service.has_whatsapp_flag("notebook") is False

    def test_legacy_state_without_whatsapp_key(self, offer_service):
        """Estado antigo sem a chave alertas_whatsapp não deve quebrar."""
        offer_service.state.pop("alertas_whatsapp", None)
        assert offer_service.has_whatsapp_flag("iphone") is False
        success, _ = offer_service.set_whatsapp_flag("iphone", True)
        assert success is True
