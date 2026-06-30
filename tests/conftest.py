"""
Fixtures reutilizáveis para testes do bot.
"""

import pytest
from app.services.offer_service import OfferService


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
