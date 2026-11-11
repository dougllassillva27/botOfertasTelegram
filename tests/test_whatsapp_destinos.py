"""
Testes unitários para whatsapp_destinos.

Cobre: normalização do número em JID (a ponte aceita qualquer string e devolve
success mesmo para JID inválido), CRUD dos destinos e o recorte por keyword.
"""

import pytest

from app.services import whatsapp_destinos as wd


class TestNormalizeJid:
    """O número digitado de qualquer jeito deve virar JID utilizável."""

    def test_plain_number_with_ddi(self):
        assert wd.normalize_jid("5551999999999") == "5551999999999@s.whatsapp.net"

    def test_formatted_number_is_cleaned(self):
        assert wd.normalize_jid("+55 (51) 99999-9999") == "5551999999999@s.whatsapp.net"

    def test_national_number_gets_ddi(self):
        """DDD + celular (11 dígitos) recebe o 55 na frente."""
        assert wd.normalize_jid("51999999999") == "5551999999999@s.whatsapp.net"

    def test_short_subscriber_is_preserved_as_typed(self):
        """Número com 8 dígitos após o DDD NÃO ganha o nono dígito.

        Regressão de 11/11/2026: o destinatário real era `555194694630` e o
        normalizador "consertava" para `5551994694630` — JID inexistente que a
        ponte aceita com `success: true` e o WhatsApp descarta em silêncio.
        """
        assert wd.normalize_jid("+55 51 9469-4630") == "555194694630@s.whatsapp.net"

    def test_full_mobile_with_ninth_digit_is_preserved(self):
        """Quem informa com o nono dígito também não é alterado."""
        assert wd.normalize_jid("+55 51 99469-4630") == "5551994694630@s.whatsapp.net"

    def test_jid_roundtrip(self):
        jid = "5551999999999@s.whatsapp.net"
        assert wd.normalize_jid(jid) == jid

    @pytest.mark.parametrize("invalido", ["", None, "abc", "123", "5551999999999123"])
    def test_rejects_garbage(self, invalido):
        assert wd.normalize_jid(invalido) == ""

    @pytest.mark.parametrize("alvo", ["120363428867776994@g.us", "194523464482903@lid"])
    def test_rejects_group_and_lid(self, alvo):
        """Grupo tem fluxo próprio e LID não serve para iniciar conversa."""
        assert wd.normalize_jid(alvo) == ""


class TestAddDestino:
    def test_adds_and_persists(self, offer_service):
        ok, msg = wd.add_destino(
            offer_service.state, "Amigo", "5551999999999", ["iphone"]
        )
        assert ok is True
        assert "cadastrado" in msg
        assert "`iphone`" in msg
        destinos = wd.load_destinos(offer_service.state)
        assert destinos[0]["jid"] == "5551999999999@s.whatsapp.net"
        assert destinos[0]["keywords"] == ["iphone"]

    def test_warns_when_destino_has_no_keywords(self, offer_service):
        ok, msg = wd.add_destino(offer_service.state, "Amigo", "5551999999999")
        assert ok is True
        assert "não recebe nada" in msg

    def test_rejects_duplicate_number(self, offer_service):
        wd.add_destino(offer_service.state, "Amigo", "5551999999999")
        ok, msg = wd.add_destino(offer_service.state, "Outro", "5551999999999")
        assert ok is False
        assert "já está cadastrado" in msg

    def test_rejects_duplicate_name(self, offer_service):
        wd.add_destino(offer_service.state, "Amigo", "5551999999999")
        ok, msg = wd.add_destino(offer_service.state, "amigo", "5551888888888")
        assert ok is False
        assert "chamado" in msg

    def test_rejects_invalid_number(self, offer_service):
        ok, msg = wd.add_destino(offer_service.state, "Amigo", "123")
        assert ok is False
        assert "inválido" in msg

    def test_rejects_name_with_space(self, offer_service):
        ok, msg = wd.add_destino(offer_service.state, "Meu Amigo", "5551999999999")
        assert ok is False
        assert "sem espaços" in msg

    def test_ignores_keyword_that_is_not_alert(self, offer_service):
        """Keyword fora de `alertas` seria filtro que nunca dispara."""
        ok, msg = wd.add_destino(
            offer_service.state, "Amigo", "5551999999999", ["inexistente"]
        )
        assert ok is True
        assert "não são alertas ativos" in msg
        assert wd.load_destinos(offer_service.state)[0]["keywords"] == []


class TestSetKeywords:
    def test_replaces_keywords(self, offer_service):
        wd.add_destino(offer_service.state, "Amigo", "5551999999999", ["iphone"])
        ok, msg = wd.set_keywords(offer_service.state, "amigo", ["notebook", "teclado"])
        assert ok is True
        assert "`notebook`" in msg and "`teclado`" in msg
        assert wd.load_destinos(offer_service.state)[0]["keywords"] == [
            "notebook",
            "teclado",
        ]

    def test_empty_list_stops_delivery(self, offer_service):
        wd.add_destino(offer_service.state, "Amigo", "5551999999999", ["iphone"])
        ok, msg = wd.set_keywords(offer_service.state, "Amigo", [])
        assert ok is True
        assert "não recebe mais nada" in msg
        assert wd.load_destinos(offer_service.state)[0]["keywords"] == []

    def test_unknown_destino(self, offer_service):
        ok, msg = wd.set_keywords(offer_service.state, "Ninguem", ["iphone"])
        assert ok is False
        assert "não encontrado" in msg


class TestRemoveDestino:
    def test_removes(self, offer_service):
        wd.add_destino(offer_service.state, "Amigo", "5551999999999", ["iphone"])
        ok, msg = wd.remove_destino(offer_service.state, "Amigo")
        assert ok is True
        assert "removido" in msg
        assert wd.load_destinos(offer_service.state) == []

    def test_unknown(self, offer_service):
        ok, msg = wd.remove_destino(offer_service.state, "Ninguem")
        assert ok is False
        assert "não encontrado" in msg


class TestDestinosFor:
    @pytest.fixture
    def com_dois_destinos(self, offer_service):
        wd.add_destino(offer_service.state, "Amigo", "5551999999999", ["iphone"])
        wd.add_destino(offer_service.state, "Outro", "5551888888888", ["notebook"])
        return offer_service.state

    def test_matches_by_keyword(self, com_dois_destinos):
        destinos = wd.destinos_for(com_dois_destinos, ["iphone"])
        assert [d["nome"] for d in destinos] == ["Amigo"]

    def test_dedupe_when_two_keywords_match(self, offer_service):
        """Oferta que bate duas keywords do mesmo destino sai uma vez só."""
        wd.add_destino(
            offer_service.state, "Amigo", "5551999999999", ["iphone", "notebook"]
        )
        destinos = wd.destinos_for(offer_service.state, ["iphone", "notebook"])
        assert len(destinos) == 1

    def test_no_match(self, com_dois_destinos):
        assert wd.destinos_for(com_dois_destinos, ["shampoo"]) == []

    def test_empty_keywords(self, com_dois_destinos):
        assert wd.destinos_for(com_dois_destinos, []) == []


class TestEstadoAntigo:
    def test_missing_key(self):
        """Estado gravado antes dessa funcionalidade não pode quebrar."""
        state = {"grupos": [], "alertas": []}
        assert wd.load_destinos(state) == []

    def test_ignores_malformed_entries(self):
        state = {
            "alertas": ["orfeu"],
            "whatsapp_destinos": [
                "lixo",
                {"nome": "Sem número"},
                {"nome": "Bom", "jid": "5551999999999", "keywords": ["orfeu"]},
            ],
        }
        destinos = wd.load_destinos(state)
        assert [d["nome"] for d in destinos] == ["Bom"]

    def test_list_text_for_empty_state(self):
        texto = wd.list_destinos({"alertas": []})
        assert "Nenhum destino extra" in texto
        assert "/wa add" in texto
