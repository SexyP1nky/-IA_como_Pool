"""
Mock do provedor LLM para testes e fallback.
"""

import logging
from src.llm.provider import LLMProvider, LLMError

logger = logging.getLogger(__name__)


class MockLLMProvider(LLMProvider):
    """Mock que simula LLM para testes."""

    MOCK_DATA = {
        ("algorithm", "easy"): {
            "title": "Sum of Two Numbers",
            "description": "Encontre dois números que somam o alvo",
            "example_input": "[2, 7, 11], target=9",
            "example_output": "[0, 1]",
        },
        ("algorithm", "medium"): {
            "title": "Fibonacci Sequence",
            "description": "Retorne o n-ésimo número de Fibonacci",
            "example_input": "n=6",
            "example_output": "8",
        },
        ("algorithm", "hard"): {
            "title": "Merge K Sorted Lists",
            "description": "Mescle K listas ordenadas",
            "example_input": "[[1,4,5],[1,3,4],[2,6]]",
            "example_output": "[1,1,2,3,4,4,5,6]",
        },
        ("string_manipulation", "easy"): {
            "title": "Reverse String",
            "description": "Inverta uma string sem usar reverse",
            "example_input": "hello",
            "example_output": "olleh",
        },
        ("string_manipulation", "medium"): {
            "title": "Palindrome Check",
            "description": "Verifique se é palíndromo ignorando espaços",
            "example_input": "A man a plan a canal Panama",
            "example_output": "true",
        },
        ("string_manipulation", "hard"): {
            "title": "Longest Substring Without Repeating",
            "description": "Encontre maior substring sem caracteres repetidos",
            "example_input": "abcabcbb",
            "example_output": "3",
        },
        ("math", "easy"): {
            "title": "Prime Number Check",
            "description": "Determine se um número é primo",
            "example_input": "17",
            "example_output": "true",
        },
        ("math", "medium"): {
            "title": "Greatest Common Divisor",
            "description": "Calcule o MDC de dois números",
            "example_input": "48, 18",
            "example_output": "6",
        },
        ("math", "hard"): {
            "title": "Modular Exponentiation",
            "description": "Calcule (base^exp) % mod",
            "example_input": "base=2, exp=10, mod=1000",
            "example_output": "24",
        },
    }

    async def generate_challenge(
        self,
        challenge_type: str,
        level: str,
    ) -> dict:
        """Mock: retorna dados pré-definidos."""
        key = (challenge_type, level)

        if key not in self.MOCK_DATA:
            raise LLMError(f"Nenhum mock para {challenge_type}/{level}")

        logger.info(f"Mock LLM: {challenge_type}/{level}")
        return dict(self.MOCK_DATA[key])

    async def is_available(self) -> bool:
        """Mock está sempre disponível."""
        return True
