"""
Testes unitários para CommandHandler.
Cobre: parsing de itens em massa, formatação da resposta agrupada
(o que mudou, o que não mudou e o total) e a resposta real dos comandos.
"""

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock

from telethon import events

from app.handlers.command_handler import CommandHandler


class TestParseBulkItems:
    """Testes para o parser de operações em massa."""

    def test_split_and_strip(self):
        """Divide por vírgula e remove espaços das pontas."""
        assert CommandHandler.parse_bulk_items("a, b ,c") == ["a", "b", "c"]

    def test_discards_empty_items(self):
        """Itens vazios (vírgulas extras) são descartados em silêncio."""
        assert CommandHandler.parse_bulk_items("a,,b, ,") == ["a", "b"]

    def test_dedupes_preserving_order(self):
        """Duplicatas removidas preservando a ordem original."""
        assert CommandHandler.parse_bulk_items("a,b,a") == ["a", "b"]

    def test_preserves_inner_spaces(self):
        """Espaço interno permanece parte do nome (alerta multi-palavra)."""
        assert CommandHandler.parse_bulk_items("shampoo infantil, fralda") == [
            "shampoo infantil",
            "fralda",
        ]


class TestFormatBulkResponse:
    """Testes para a resposta agrupada por status."""

    def test_all_success(self):
        """Só bloco de sucesso quando tudo der certo."""
        results = [("a", True, "adicionado com sucesso"), ("b", True, "adicionado com sucesso")]
        response = CommandHandler.format_bulk_response(results)
        assert "✅" in response
        assert "`a`" in response and "`b`" in response
        assert "⚠️" not in response

    def test_mixed_success_and_failure(self):
        """Blocos separados para sucesso e falha com motivo."""
        results = [
            ("a", True, "adicionado com sucesso"),
            ("b", False, "já está na lista"),
        ]
        response = CommandHandler.format_bulk_response(results)
        assert "✅" in response and "`a`" in response
        assert "⚠️" in response and "`b`: já está na lista" in response


class TestWhatsappHint:
    """Testes para a dica de envio pro WhatsApp no /alertas add."""

    def test_single_added_hints_command(self):
        """Um alerta adicionado = dica com o comando da própria keyword."""
        results = [("teclado", True, "adicionado com sucesso")]
        hint = CommandHandler.whatsapp_hint(results)
        assert "`/alertas wa teclado`" in hint

    def test_multiword_keyword_in_hint(self):
        """Keyword com espaço vai inteira na dica."""
        results = [("teclado mecanico", True, "adicionado com sucesso")]
        hint = CommandHandler.whatsapp_hint(results)
        assert "`/alertas wa teclado mecanico`" in hint

    def test_bulk_add_uses_placeholder(self):
        """Mais de um alerta = placeholder, já que o comando é por keyword."""
        results = [
            ("a", True, "adicionado com sucesso"),
            ("b", True, "adicionado com sucesso"),
        ]
        assert "`/alertas wa <palavra>`" in CommandHandler.whatsapp_hint(results)

    def test_no_added_no_hint(self):
        """Nada adicionado (tudo duplicado) = sem dica."""
        results = [("a", False, "já está na lista")]
        assert CommandHandler.whatsapp_hint(results) == ""


class TestFormatBulkResponseBonito:
    """Resposta de add/rm com título, itens, motivo e total atual."""

    def test_single_add(self):
        resp = CommandHandler.format_bulk_response(
            [("orfeu", True, "adicionado com sucesso")],
            entidade="alerta",
            verbo="adicionado",
            total=14,
            rotulo_total="alertas ativos",
        )
        assert "✅ **Alerta adicionado**" in resp
        assert "• `orfeu`" in resp
        assert "📊 **14** alertas ativos" in resp
        assert "Sucesso" not in resp  # o "Sucesso:" genérico saiu

    def test_plural_remove(self):
        resp = CommandHandler.format_bulk_response(
            [("a", True, "removido"), ("b", True, "removido")],
            entidade="alerta",
            verbo="removido",
            total=13,
            rotulo_total="alertas ativos",
        )
        assert "🗑️ **2 alertas removidos**" in resp
        assert "📊 **13** alertas ativos" in resp

    def test_group_entity(self):
        resp = CommandHandler.format_bulk_response(
            [("canalzinho", True, "adicionado com sucesso")],
            entidade="grupo",
            verbo="adicionado",
            total=53,
            rotulo_total="grupos monitorados",
        )
        assert "✅ **Grupo adicionado**" in resp
        assert "📊 **53** grupos monitorados" in resp

    def test_only_failures_has_no_success_block(self):
        resp = CommandHandler.format_bulk_response(
            [("x", False, "não encontrado")],
            entidade="alerta",
            verbo="removido",
            total=13,
            rotulo_total="alertas ativos",
        )
        assert "⚠️ **1 sem alteração**" in resp
        assert "• `x`: não encontrado" in resp
        assert "🗑️" not in resp  # nada mudou, não anuncia remoção

    def test_no_total_when_not_informed(self):
        resp = CommandHandler.format_bulk_response([("a", True, "removido")])
        assert "📊" not in resp


def _padrao_do(builder):
    """Texto-fonte do pattern do Telethon.

    Telethon guarda a regex compilada e expõe `pattern` como o método
    `match` dela — o fonte fica em `__self__` (o `re.Pattern`).
    """
    for alvo in (getattr(builder, "_pattern", None), getattr(builder, "pattern", None)):
        if isinstance(alvo, str):
            return alvo
        regex = getattr(alvo, "__self__", alvo)
        texto = getattr(regex, "pattern", None)
        if isinstance(texto, str):
            return texto
    return ""


def _captura_handlers(offer_service):
    """Registra os handlers num client fake e devolve [(pattern, fn)]."""
    capturados = []
    client = MagicMock()

    def fake_on(builder):
        def deco(fn):
            capturados.append((_padrao_do(builder), fn))
            return fn

        return deco

    client.on = fake_on
    CommandHandler(client, offer_service).register(forward_to=123)
    return capturados


def _roda(handler, texto_comando):
    """Dispara o handler com o comando e devolve o que foi respondido.

    O StopPropagation só sobe nos comandos com argumento; a listagem
    (sem argumento) responde e dá `return`.
    """
    event = MagicMock()
    event.pattern_match.group = lambda _i: texto_comando
    event.respond = AsyncMock()
    try:
        asyncio.run(handler(event))
    except events.StopPropagation:
        pass
    return event.respond.call_args[0][0]


class TestRespostaRealDoComando:
    """O texto que chega pro Douglas no Telegram, comando a comando."""

    @pytest.fixture
    def alertas_handler(self, offer_service):
        capturados = _captura_handlers(offer_service)
        return next(fn for pat, fn in capturados if pat.endswith("/alertas(.*)"))

    @pytest.fixture
    def grupos_handler(self, offer_service):
        capturados = _captura_handlers(offer_service)
        return next(fn for pat, fn in capturados if pat.endswith("/grupos(.*)"))

    def test_add_mostra_total_e_dica_whatsapp(self, alertas_handler, offer_service):
        texto = _roda(alertas_handler, " add orfeu")
        assert "✅ **Alerta adicionado**" in texto
        assert "• `orfeu`" in texto
        assert "📊 **4** alertas ativos" in texto  # sample_state tem 3
        assert "`/alertas wa orfeu`" in texto

    def test_add_duplicado_lista_motivo_sem_dica(self, alertas_handler, offer_service):
        texto = _roda(alertas_handler, " add iphone")
        assert "⚠️ **1 sem alteração**" in texto
        assert "`iphone`: já está na lista" in texto
        assert "📊 **3** alertas ativos" in texto
        assert "/alertas wa" not in texto  # não ensina caminho pra quem não mudou nada

    def test_rm_avisa_quando_sai_do_whatsapp(self, alertas_handler, offer_service):
        offer_service.set_whatsapp_flag("iphone", True)
        texto = _roda(alertas_handler, " rm iphone")
        assert "🗑️ **Alerta removido**" in texto
        assert "📊 **2** alertas ativos" in texto
        assert "🔕 Também saiu do envio pro WhatsApp: `iphone`" in texto

    def test_rm_sem_whatsapp_nao_menciona_zap(self, alertas_handler, offer_service):
        texto = _roda(alertas_handler, " rm notebook")
        assert "🗑️ **Alerta removido**" in texto
        assert "WhatsApp" not in texto

    def test_lista_de_alertas_com_contagem_e_comandos(self, alertas_handler):
        texto = _roda(alertas_handler, "")
        assert "🔔 **Alertas ativos (3)**" in texto
        assert "• `iphone`" in texto
        assert "➕ `/alertas add palavra`" in texto
        assert "📲 `/alertas wa palavra`" in texto

    def test_lista_de_grupos_com_contagem(self, grupos_handler):
        texto = _roda(grupos_handler, "")
        assert "📦 **Grupos monitorados (2)**" in texto
        assert "• `grupo1`" in texto
        assert "💡 Em massa: `/grupos add grupo1, grupo2`" in texto

    def test_grupo_add_com_total(self, grupos_handler):
        texto = _roda(grupos_handler, " add canalnovo")
        assert "✅ **Grupo adicionado**" in texto
        assert "📊 **3** grupos monitorados" in texto
