"""
Interface abstrata para provedores de LLM.

Permite implementar múltiplos provedores (OpenAI, Gemini, Ollama, etc).
"""

import time
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Erro ao chamar LLM."""

    pass


class LLMProvider(ABC):
    """Interface para provedores de LLM."""

    @abstractmethod
    async def generate_challenge(
        self,
        challenge_type: str,
        level: str,
    ) -> dict:
        """
        Gera um desafio usando LLM.

        Args:
            challenge_type: Tipo do desafio (algorithm, string_manipulation, math)
            level: Nível (easy, medium, hard)

        Returns:
            dict contendo:
                - title: str
                - description: str
                - example_input: str
                - example_output: str

        Raises:
            LLMError: Erro na geração
        """
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Verifica se o provedor está disponível."""
        pass


class CircuitBreaker:
    """Implementa Circuit Breaker pattern para LLM."""

    def __init__(self, failure_threshold: int = 3, timeout: int = 300):
        """
        Args:
            failure_threshold: Número de falhas antes de abrir o circuito
            timeout: Segundos para tentar reconectar
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.is_open = False

    async def call_with_fallback(
        self,
        llm_func,
        fallback_func,
        *args,
        **kwargs,
    ):
        """
        Executa função com fallback automático.

        Args:
            llm_func: Função LLM principal
            fallback_func: Função de fallback
            *args, **kwargs: Argumentos para llm_func

        Returns:
            Resultado de llm_func ou fallback_func
        """
        if self.is_open:
            elapsed = time.time() - self.last_failure_time
            if elapsed > self.timeout:
                logger.info("Circuit breaker: tentando novamente")
                self.is_open = False
                self.failure_count = 0
            else:
                logger.warning("Circuit breaker aberto, usando fallback")
                fallback_result = await fallback_func(*args, **kwargs)
                if isinstance(fallback_result, dict):
                    fallback_result.setdefault("_llm_source", "mock")
                return fallback_result

        try:
            result = await llm_func(*args, **kwargs)
            self.failure_count = 0
            if isinstance(result, dict):
                result.setdefault("_llm_source", "llm")
            return result
        except LLMError as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            logger.error(
                f"LLM failed ({self.failure_count}/{self.failure_threshold}): {str(e)}"
            )

            if self.failure_count >= self.failure_threshold:
                self.is_open = True
                logger.error(
                    f"Circuit breaker aberto. Failover para {fallback_func.__name__}"
                )

            fallback_result = await fallback_func(*args, **kwargs)
            if isinstance(fallback_result, dict):
                fallback_result.setdefault("_llm_source", "mock")
            return fallback_result
