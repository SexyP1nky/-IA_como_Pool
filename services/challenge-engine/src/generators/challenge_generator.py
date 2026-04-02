"""
Challenge Generator Module

Módulo responsável por gerar desafios de programação.
Implementa diferentes tipos de desafios e mantém a geração modular e extensível.
Suporta geração via LLM (Gemini, Mock) com fallback para pool pré-definido.
"""

import logging
import uuid
import os
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime

from src.llm.provider import LLMProvider, CircuitBreaker, LLMError

logger = logging.getLogger(__name__)


class ChallengeLevel(str, Enum):
    """Níveis de dificuldade dos desafios."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class ChallengeType(str, Enum):
    """Tipos de desafios disponíveis."""

    ALGORITHM = "algorithm"
    STRING_MANIPULATION = "string_manipulation"
    MATH = "math"


@dataclass
class ChallengeRecord:
    """Linha da tabela PostgreSQL `challenges` (fallback estático).

    Coluna `challenge`: mesma string que o Redis — JSON de `Challenge.to_dict()`.
    """

    id: int | None
    challenge: str


@dataclass
class Challenge:
    """Representação de um desafio."""

    id: str
    type: ChallengeType
    level: ChallengeLevel
    title: str
    description: str
    example_input: str
    example_output: str
    created_at: str
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converte o desafio para dicionário."""
        data = asdict(self)
        data["type"] = self.type.value
        data["level"] = self.level.value
        return data


class ChallengeGenerationError(Exception):
    """Erro na geração de desafios."""

    pass


class ChallengeGenerator:
    """Gerador de desafios de programação."""

    CHALLENGE_POOL = {
        ChallengeType.ALGORITHM: [
            {
                "title": "Sum of Two Numbers",
                "description": "Dado uma lista de números inteiros e um alvo, encontre dois números que somam o alvo.",
                "example_input": "[2, 7, 11, 15], target=9",
                "example_output": "[0, 1]",
                "level": ChallengeLevel.EASY,
            },
            {
                "title": "Fibonacci Sequence",
                "description": "Retorne o n-ésimo número da sequência de Fibonacci.",
                "example_input": "n=6",
                "example_output": "8",
                "level": ChallengeLevel.MEDIUM,
            },
            {
                "title": "Merge Sorted Arrays",
                "description": "Mescle dois arrays ordenados sem usar espaço extra.",
                "example_input": "[1,2,3], [2,5,6]",
                "example_output": "[1,2,2,3,5,6]",
                "level": ChallengeLevel.HARD,
            },
        ],
        ChallengeType.STRING_MANIPULATION: [
            {
                "title": "Reverse String",
                "description": "Inverta uma string sem usar built-in reverse.",
                "example_input": "hello",
                "example_output": "olleh",
                "level": ChallengeLevel.EASY,
            },
            {
                "title": "Palindrome Check",
                "description": "Verifique se uma string é um palíndromo ignorando espaços e maiúsculas.",
                "example_input": "A man a plan a canal Panama",
                "example_output": "true",
                "level": ChallengeLevel.MEDIUM,
            },
            {
                "title": "Longest Substring Without Repeating",
                "description": "Encontre o comprimento da maior substring sem caracteres repetidos.",
                "example_input": "abcabcbb",
                "example_output": "3",
                "level": ChallengeLevel.HARD,
            },
        ],
        ChallengeType.MATH: [
            {
                "title": "Prime Number Check",
                "description": "Determine se um número é primo.",
                "example_input": "17",
                "example_output": "true",
                "level": ChallengeLevel.EASY,
            },
            {
                "title": "Greatest Common Divisor",
                "description": "Calcule o MDC de dois números sem usar biblioteca.",
                "example_input": "48, 18",
                "example_output": "6",
                "level": ChallengeLevel.MEDIUM,
            },
        ],
    }

    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        enable_llm: bool = True,
    ):
        """
        Inicializa o gerador de desafios.

        Args:
            llm_provider: Provedor LLM (ou detecta automaticamente)
            enable_llm: Se deve usar LLM em vez de pool pré-definido
        """
        self.logger = logging.getLogger(__name__)
        self.enable_llm = enable_llm

        if enable_llm and os.getenv("ENABLE_LLM", "true").lower() == "true":
            if llm_provider:
                self.llm_provider = llm_provider
            else:
                try:
                    provider_name = os.getenv("LLM_PROVIDER", "gemini").strip().lower()

                    if provider_name == "groq":
                        from src.llm.groq_provider import GroqLLMProvider

                        self.llm_provider = GroqLLMProvider()
                        self.logger.info("LLM: Groq inicializado")
                    else:
                        from src.llm.gemini_provider import GeminiLLMProvider

                        self.llm_provider = GeminiLLMProvider()
                        self.logger.info("LLM: Google Gemini inicializado")
                except (LLMError, ImportError) as e:
                    self.logger.warning(f"LLM indisponível ({str(e)}), usando Mock")
                    from src.llm.mock_provider import MockLLMProvider

                    self.llm_provider = MockLLMProvider()

            from src.llm.mock_provider import MockLLMProvider

            self.fallback_provider = MockLLMProvider()
            self.circuit_breaker = CircuitBreaker(failure_threshold=3)
        else:
            self.llm_provider = None
            self.fallback_provider = None
            self.circuit_breaker = None
            self.enable_llm = False

        self.logger.info("ChallengeGenerator initialized")

    async def generate(
        self,
        challenge_type: Optional[ChallengeType] = None,
        level: Optional[ChallengeLevel] = None,
    ) -> Challenge:
        """
        Gera um novo desafio usando LLM se disponível, senão pool pré-definido.

        Args:
            challenge_type: Tipo de desafio (ou aleatório se None)
            level: Nível de dificuldade (ou aleatório se None)

        Returns:
            Challenge: Desafio gerado

        Raises:
            ChallengeGenerationError: Erro durante a geração
        """
        try:
            if challenge_type is None:
                challenge_type = self._random_type()

            if level is None:
                level = self._random_level()

            if self.enable_llm and self.circuit_breaker and self.llm_provider:
                try:
                    challenge_data = await self.circuit_breaker.call_with_fallback(
                        self.llm_provider.generate_challenge,
                        self.fallback_provider.generate_challenge,
                        challenge_type.value,
                        level.value,
                    )
                    source = challenge_data.pop("_llm_source", "llm")

                    challenge = Challenge(
                        id=str(uuid.uuid4()),
                        type=challenge_type,
                        level=level,
                        title=challenge_data["title"],
                        description=challenge_data["description"],
                        example_input=challenge_data["example_input"],
                        example_output=challenge_data["example_output"],
                        created_at=datetime.utcnow().isoformat(),
                        metadata={
                            "generator_version": "2.0",
                            "source": source,
                        },
                    )

                    self.logger.info(
                        f"Challenge generated: id={challenge.id}, type={challenge.type}, "
                        f"level={challenge.level}, source={challenge.metadata['source']}"
                    )
                    return challenge

                except Exception as e:
                    self.logger.warning(
                        f"LLM generation failed: {str(e)}, falling back to pool"
                    )

            if challenge_type not in self.CHALLENGE_POOL:
                raise ChallengeGenerationError(
                    f"Challenge type '{challenge_type}' not available"
                )

            challenges = self.CHALLENGE_POOL[challenge_type]

            challenges = [c for c in challenges if c["level"] == level]
            if not challenges:
                raise ChallengeGenerationError(
                    f"No challenge available for type={challenge_type}, level={level}"
                )

            import random

            challenge_data = random.choice(challenges)

            challenge = Challenge(
                id=str(uuid.uuid4()),
                type=challenge_type,
                level=challenge_data["level"],
                title=challenge_data["title"],
                description=challenge_data["description"],
                example_input=challenge_data["example_input"],
                example_output=challenge_data["example_output"],
                created_at=datetime.utcnow().isoformat(),
                metadata={
                    "generator_version": "2.0",
                    "source": "pool",
                },
            )

            self.logger.info(
                f"Challenge generated (fallback): id={challenge.id}, type={challenge.type}, level={challenge.level}"
            )
            return challenge

        except ChallengeGenerationError:
            raise
        except Exception as e:
            error_msg = f"Failed to generate challenge: {str(e)}"
            self.logger.error(error_msg)
            raise ChallengeGenerationError(error_msg) from e

    async def generate_batch(
        self, count: int = 10, challenge_type: Optional[ChallengeType] = None
    ) -> list[Challenge]:
        """
        Gera múltiplos desafios em lote.

        Args:
            count: Quantidade de desafios a gerar
            challenge_type: Tipo de desafio (ou aleatório se None)

        Returns:
            list[Challenge]: Lista de desafios gerados

        Raises:
            ChallengeGenerationError: Erro durante a geração
        """
        if count <= 0:
            raise ChallengeGenerationError("Count must be greater than 0")

        if count > 1000:
            raise ChallengeGenerationError("Count cannot exceed 1000")

        try:
            challenges = []
            for _ in range(count):
                challenge = await self.generate(challenge_type=challenge_type)
                challenges.append(challenge)

            self.logger.info(f"Generated batch of {count} challenges")
            return challenges

        except ChallengeGenerationError:
            raise
        except Exception as e:
            error_msg = f"Failed to generate batch: {str(e)}"
            self.logger.error(error_msg)
            raise ChallengeGenerationError(error_msg) from e

    @staticmethod
    def _random_type() -> ChallengeType:
        """Seleciona um tipo aleatório de desafio."""
        import random

        return random.choice(list(ChallengeType))

    @staticmethod
    def _random_level() -> ChallengeLevel:
        """Seleciona um nível aleatório de dificuldade."""
        import random

        return random.choice(list(ChallengeLevel))

    @staticmethod
    def get_available_types() -> list[str]:
        """Retorna os tipos de desafios disponíveis."""
        return [ct.value for ct in ChallengeType]

    @staticmethod
    def get_available_levels() -> list[str]:
        """Retorna os níveis de dificuldade disponíveis."""
        return [cl.value for cl in ChallengeLevel]
