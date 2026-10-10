"""
Testes unitários para CommandHandler.
Cobre: parsing de itens em massa e formatação da resposta agrupada.
"""

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
