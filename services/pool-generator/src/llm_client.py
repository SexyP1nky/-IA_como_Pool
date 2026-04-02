"""LLM client with circuit breaker for synchronous Celery tasks.

Supports Gemini, Groq, and a static mock fallback.
"""

import json
import logging
import random
import time
import uuid
from datetime import datetime, timezone

from src.config import config

logger = logging.getLogger(__name__)


class LLMError(Exception):
    pass


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: int = 120,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.is_open = False

    def record_success(self) -> None:
        self.failure_count = 0
        self.is_open = False

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.is_open = True
            logger.warning("Circuit breaker OPEN after %d failures", self.failure_count)

    def allow_request(self) -> bool:
        if not self.is_open:
            return True
        elapsed = time.time() - (self.last_failure_time or 0)
        if elapsed >= self.recovery_timeout:
            logger.info("Circuit breaker half-open, allowing probe request")
            return True
        return False


circuit_breaker = CircuitBreaker(
    failure_threshold=config.CB_FAILURE_THRESHOLD,
    recovery_timeout=config.CB_RECOVERY_TIMEOUT_S,
)


# ---------------------------------------------------------------------------
# Prompt template shared across providers
# ---------------------------------------------------------------------------

_PROMPT_TEMPLATE = """Gere um desafio de programação no formato JSON.

Tipo: {challenge_type}
Nível: {level}

Responda APENAS com JSON válido (sem markdown, sem explicações):

{{
    "title": "Título do desafio",
    "description": "Descrição clara do problema",
    "example_input": "entrada de exemplo",
    "example_output": "saída esperada"
}}

Requisitos:
- title: máximo 50 caracteres
- description: máximo 200 caracteres
- Exemplos concretos e funcionais
- Válido para nível {level}
- JSON válido e parseável
"""

_CHALLENGE_TYPES = ["algorithm", "string_manipulation", "math"]
_LEVELS = ["easy", "medium", "hard"]


def _parse_llm_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    data = json.loads(text.strip())
    for key in ("title", "description", "example_input", "example_output"):
        if key not in data:
            raise LLMError(f"Missing required field: {key}")
    return data


# ---------------------------------------------------------------------------
# Provider implementations (synchronous for Celery)
# ---------------------------------------------------------------------------


def _generate_gemini(challenge_type: str, level: str) -> dict:
    from google import genai

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    prompt = _PROMPT_TEMPLATE.format(challenge_type=challenge_type, level=level)
    response = client.models.generate_content(
        model=config.GEMINI_MODEL, contents=prompt
    )
    text = getattr(response, "text", None)
    if not text:
        raise LLMError("Gemini returned empty response")
    return _parse_llm_response(text)


def _generate_groq(challenge_type: str, level: str) -> dict:
    from groq import Groq

    client = Groq(api_key=config.GROQ_API_KEY)
    prompt = _PROMPT_TEMPLATE.format(challenge_type=challenge_type, level=level)
    completion = client.chat.completions.create(
        model=config.GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": "Você gera apenas JSON válido e sem markdown.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )
    content = completion.choices[0].message.content if completion.choices else None
    if not content:
        raise LLMError("Groq returned empty response")
    return _parse_llm_response(content)


_STATIC_POOL = [
    {
        "title": "Sum of Two Numbers",
        "description": "Dado uma lista de inteiros e um alvo, encontre dois números que somam o alvo.",
        "example_input": "[2, 7, 11, 15], target=9",
        "example_output": "[0, 1]",
        "type": "algorithm",
        "level": "easy",
    },
    {
        "title": "Fibonacci Sequence",
        "description": "Retorne o n-ésimo número da sequência de Fibonacci.",
        "example_input": "n=6",
        "example_output": "8",
        "type": "algorithm",
        "level": "medium",
    },
    {
        "title": "Reverse String",
        "description": "Inverta uma string sem usar built-in reverse.",
        "example_input": "hello",
        "example_output": "olleh",
        "type": "string_manipulation",
        "level": "easy",
    },
    {
        "title": "Palindrome Check",
        "description": "Verifique se uma string é um palíndromo ignorando espaços e maiúsculas.",
        "example_input": "A man a plan a canal Panama",
        "example_output": "true",
        "type": "string_manipulation",
        "level": "medium",
    },
    {
        "title": "Merge Sorted Arrays",
        "description": "Mescle dois arrays ordenados sem usar espaço extra.",
        "example_input": "[1,2,3], [2,5,6]",
        "example_output": "[1,2,2,3,5,6]",
        "type": "algorithm",
        "level": "hard",
    },
    {
        "title": "Prime Number Check",
        "description": "Determine se um número é primo.",
        "example_input": "17",
        "example_output": "true",
        "type": "math",
        "level": "easy",
    },
    {
        "title": "Greatest Common Divisor",
        "description": "Calcule o MDC de dois números sem usar biblioteca.",
        "example_input": "48, 18",
        "example_output": "6",
        "type": "math",
        "level": "medium",
    },
    {
        "title": "Longest Substring Without Repeating",
        "description": "Encontre o comprimento da maior substring sem caracteres repetidos.",
        "example_input": "abcabcbb",
        "example_output": "3",
        "type": "string_manipulation",
        "level": "hard",
    },
]


def _generate_mock(challenge_type: str, level: str) -> dict:
    candidates = [
        c for c in _STATIC_POOL if c["type"] == challenge_type and c["level"] == level
    ]
    if not candidates:
        candidates = [c for c in _STATIC_POOL if c["type"] == challenge_type]
    if not candidates:
        candidates = _STATIC_POOL
    chosen = random.choice(candidates)
    return {
        "title": chosen["title"],
        "description": chosen["description"],
        "example_input": chosen["example_input"],
        "example_output": chosen["example_output"],
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _select_provider():
    """Return (generate_fn, provider_name) based on config."""
    if not config.ENABLE_LLM:
        return _generate_mock, "mock"
    if config.LLM_PROVIDER == "groq" and config.GROQ_API_KEY:
        return _generate_groq, "groq"
    if config.GEMINI_API_KEY:
        return _generate_gemini, "gemini"
    logger.warning("No LLM API key configured, falling back to mock")
    return _generate_mock, "mock"


def generate_challenge(
    challenge_type: str | None = None,
    level: str | None = None,
) -> dict:
    """Generate a single challenge dict ready for Redis.

    Uses the configured LLM provider with circuit-breaker protection.
    Falls back to the static pool on failure.
    """
    if challenge_type is None:
        challenge_type = random.choice(_CHALLENGE_TYPES)
    if level is None:
        level = random.choice(_LEVELS)

    generate_fn, provider_name = _select_provider()

    source = provider_name
    if _circuit_breaker_allows(provider_name):
        try:
            data = generate_fn(challenge_type, level)
            circuit_breaker.record_success()
        except Exception as exc:
            logger.warning(
                "[CIRCUIT BREAKER] %s call failed: %s — falling back to mock",
                provider_name,
                exc,
            )
            circuit_breaker.record_failure()
            data = _generate_mock(challenge_type, level)
            source = "mock_fallback"
    else:
        logger.warning(
            "[CIRCUIT BREAKER] OPEN — skipping %s, using mock fallback",
            provider_name,
        )
        data = _generate_mock(challenge_type, level)
        source = "mock_fallback" if provider_name != "mock" else "mock"

    return {
        "id": str(uuid.uuid4()),
        "type": challenge_type,
        "level": level,
        "title": data["title"],
        "description": data["description"],
        "example_input": data["example_input"],
        "example_output": data["example_output"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "generator_version": "2.0",
            "source": source,
        },
    }


def _circuit_breaker_allows(provider_name: str) -> bool:
    if provider_name == "mock":
        return True
    return circuit_breaker.allow_request()
