"""
Configuração do pytest para o projeto.

Define fixtures globais e configurações de asyncio.
"""
import pytest

# Habilita modo automático do pytest-asyncio
pytest_plugins = ["pytest_asyncio"]

# Configuração do asyncio_mode
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "asyncio: marks tests as asynchronous"
    )

