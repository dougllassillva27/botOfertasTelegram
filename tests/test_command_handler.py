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


class TestWhatsappConfirmButtons:
    """Testes para os botões de confirmação WhatsApp."""

    def test_single_added_shows_buttons(self):
        """Um alerta adicionado = botões de confirmação."""
        results = [("teclado", True, "adicionado com sucesso")]
        buttons = CommandHandler.whatsapp_confirm_buttons(["teclado"], results)
        assert buttons is not None
        row = buttons[0]
        assert row[0].data == b"wa_sim:teclado"
        assert row[1].data == b"wa_nao:teclado"

    def test_multiword_keyword_in_data(self):
        """Keyword com espaço deve ir inteira no data do botão."""
        results = [("teclado mecanico", True, "adicionado com sucesso")]
        buttons = CommandHandler.whatsapp_confirm_buttons(["teclado mecanico"], results)
        assert buttons[0][0].data == b"wa_sim:teclado mecanico"

    def test_bulk_add_no_buttons(self):
        """Mais de um alerta = sem botões (usar /alertas wa depois)."""
        results = [
            ("a", True, "adicionado com sucesso"),
            ("b", True, "adicionado com sucesso"),
        ]
        assert CommandHandler.whatsapp_confirm_buttons(["a", "b"], results) is None

    def test_all_duplicates_no_buttons(self):
        """Nada adicionado = sem botões."""
        results = [("a", False, "já está na lista")]
        assert CommandHandler.whatsapp_confirm_buttons(["a"], results) is None
