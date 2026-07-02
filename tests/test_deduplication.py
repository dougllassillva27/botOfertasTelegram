"""
Testes para o módulo OfferDeduplicator.
"""

import pytest
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from app.services.deduplication import OfferDeduplicator


class TestOfferDeduplicatorNormalization:
    """Testes de normalização de texto."""

    def test_normalize_text_lowercase(self):
        dedup = OfferDeduplicator()
        result = dedup._normalize_text("OFERTA ESPECIAL")
        assert result == "oferta especial"

    def test_normalize_text_remove_extra_spaces(self):
        dedup = OfferDeduplicator()
        result = dedup._normalize_text("  Oferta   com   espaços  ")
        assert result == "oferta com espaços"

    def test_normalize_text_remove_urls(self):
        dedup = OfferDeduplicator()
        result = dedup._normalize_text("Oferta https://exemplo.com/produto mais texto")
        assert "https://exemplo.com/produto" not in result
        assert "oferta mais texto" in result

    def test_normalize_text_remove_special_chars(self):
        dedup = OfferDeduplicator()
        result = dedup._normalize_text("Oferta! @#R$100%")
        assert result == "oferta r100"


class TestOfferDeduplicatorHashGeneration:
    """Testes de geração de hash."""

    def test_generate_hash_consistent(self):
        dedup = OfferDeduplicator()
        h1 = dedup.generate_hash("Oferta A", "Descrição A", "https://a.com")
        h2 = dedup.generate_hash("Oferta A", "Descrição A", "https://a.com")
        assert h1 == h2

    def test_generate_hash_different_inputs(self):
        dedup = OfferDeduplicator()
        h1 = dedup.generate_hash("Oferta A", "Desc A", "https://a.com")
        h2 = dedup.generate_hash("Oferta B", "Desc B", "https://b.com")
        assert h1 != h2

    def test_generate_hash_case_insensitive(self):
        dedup = OfferDeduplicator()
        h1 = dedup.generate_hash("Oferta A", "Descrição A", None)
        h2 = dedup.generate_hash("oferta a", "descrição a", None)
        assert h1 == h2


class TestOfferDeduplicatorSimilarity:
    """Testes de similaridade fuzzy."""

    def test_similarity_identical_texts(self):
        dedup = OfferDeduplicator()
        sim = dedup.calculate_similarity("Oferta XYZ", "Oferta XYZ")
        assert sim == 100

    def test_similarity_different_texts(self):
        dedup = OfferDeduplicator()
        sim = dedup.calculate_similarity("Notebook Dell", "Tênis Nike")
        assert sim < 50

    def test_similarity_similar_texts(self):
        dedup = OfferDeduplicator()
        sim = dedup.calculate_similarity(
            "Notebook Dell i7 16GB",
            "Notebook Dell Core i7 16GB RAM"
        )
        assert sim >= 80


class TestOfferDeduplicatorDuplicateDetection:
    """Testes de detecção de duplicatas."""

    def setup_method(self):
        self.dedup = OfferDeduplicator()
        self.dedup.offers = {}  # Limpa para testes isolados

    def test_is_duplicate_exact_match(self):
        # Registra primeira oferta
        self.dedup.register_offer("Oferta A", "Desc A", "https://a.com")

        # Verifica segunda idêntica
        is_dup, reason, _ = self.dedup.is_duplicate("Oferta A", "Desc A", "https://a.com")

        assert is_dup is True
        assert reason == "hash_exato"

    def test_is_duplicate_fuzzy_match(self):
        # Registra oferta original
        self.dedup.register_offer("Notebook Dell i7", "16GB RAM SSD", "https://dell.com/xyz")

        # Verifica oferta similar (mesmo produto, descrição ligeiramente diferente)
        is_dup, reason, _ = self.dedup.is_duplicate(
            "Notebook Dell Core i7", "16GB RAM SSD 512GB", "https://dell.com/xyz"
        )

        assert is_dup is True
        assert "similaridade" in reason

    def test_is_not_duplicate_new_offer(self):
        is_dup, reason, _ = self.dedup.is_duplicate("iPhone 15", "128GB", "https://apple.com/iphone")

        assert is_dup is False
        assert reason is None

    def test_register_and_detect_cycle(self):
        # Primeira oferta (ainda não registrada)
        is_dup1, reason1, _ = self.dedup.is_duplicate("Produto X", "Desc X", "https://x.com")
        assert is_dup1 is False  # Não é duplicata ainda

        # Registra
        self.dedup.register_offer("Produto X", "Desc X", "https://x.com")

        # Segunda oferta idêntica
        is_dup2, reason2, _ = self.dedup.is_duplicate("Produto X", "Desc X", "https://x.com")
        assert is_dup2 is True
        assert reason2 == "hash_exato"


class TestOfferDeduplicatorExpiration:
    """Testes de expiração de registros."""

    def test_cleanup_expired_offers(self):
        dedup = OfferDeduplicator()
        dedup.offers = {}

        # Adiciona oferta antiga (49h atrás)
        old_time = (datetime.now(timezone.utc) - timedelta(hours=49)).isoformat()
        dedup.offers["old_hash"] = {
            "title": "Old Offer",
            "description": "Old Desc",
            "url": "https://old.com",
            "sent_at": old_time,
            "groups_sent": []
        }

        # Adiciona oferta recente (1h atrás)
        recent_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        dedup.offers["recent_hash"] = {
            "title": "Recent Offer",
            "description": "Recent Desc",
            "url": "https://recent.com",
            "sent_at": recent_time,
            "groups_sent": []
        }

        # Executa cleanup
        dedup._cleanup_expired(hours=48)

        # Verifica que só a antiga foi removida
        assert "old_hash" not in dedup.offers
        assert "recent_hash" in dedup.offers


class TestOfferDeduplicatorPersistence:
    """Testes de persistência em JSON."""

    def test_save_and_load_data(self, tmp_path):
        data_file = tmp_path / "test_offers.json"
        dedup = OfferDeduplicator(data_file=str(data_file))

        # Registra oferta
        dedup.register_offer("Test Offer", "Test Desc", "https://test.com")

        # Cria nova instância (deve carregar dados salvos)
        dedup2 = OfferDeduplicator(data_file=str(data_file))

        assert len(dedup2.offers) == 1
        assert any("Test Offer" in data["title"] for data in dedup2.offers.values())


class TestOfferDeduplicatorLogging:
    """Testes de log de ofertas puladas."""

    def test_log_skipped_creates_file(self, tmp_path):
        log_file = tmp_path / "Logs.txt"
        dedup = OfferDeduplicator(log_file=str(log_file))

        dedup.log_skipped("Oferta Teste", "Desc Teste", "https://teste.com", "hash_exato")

        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8")
        assert "[PULADA]" in content
        assert "Oferta Teste" in content
        assert "hash_exato" in content
