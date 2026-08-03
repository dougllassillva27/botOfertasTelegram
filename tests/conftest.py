"""
Fixtures reutilizáveis para testes do bot.
"""

import pytest
from unittest.mock import MagicMock

from app.services.offer_service import OfferService
from app.services.deduplication import OfferDeduplicator


@pytest.fixture(autouse=True)
def isolate_storage(monkeypatch):
    """Impede que testes escrevam nos arquivos reais de data/."""
    monkeypatch.setattr("app.services.offer_service.save_data", MagicMock())


@pytest.fixture
def sample_state():
    """Estado inicial de exemplo para testes."""
    return {
        "grupos": ["grupo1", "grupo2"],
        "alertas": ["iphone", "notebook", "teclado"],
        "forward_to": 123456789,
    }


@pytest.fixture
def offer_service(sample_state):
    """Instância do OfferService com estado de teste."""
    return OfferService(sample_state)


@pytest.fixture
def dedup(tmp_path):
    """Deduplicador isolado em diretório temporário."""
    return OfferDeduplicator(
        data_file=str(tmp_path / "offers_sent.json"),
        log_file=str(tmp_path / "Logs.txt"),
    )
