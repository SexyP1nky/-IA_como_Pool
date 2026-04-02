"""
Configuração do pytest para o projeto.

Define fixtures globais e configurações de asyncio.
"""
import pytest

pytest_plugins = ["pytest_asyncio"]

def pytest_configure(config):
    config.addinivalue_line(
        "markers", "asyncio: marks tests as asynchronous"
    )

