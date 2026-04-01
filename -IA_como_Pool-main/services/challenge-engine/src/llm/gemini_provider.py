"""
Provedor de LLM usando Google Gemini.
"""
import os
import json
import logging
from typing import Optional

from src.llm.provider import LLMProvider, LLMError

logger = logging.getLogger(__name__)

try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning(
        "google-genai não instalado. Instale com: pip install -q -U google-genai"
    )


class GeminiLLMProvider(LLMProvider):
    """Provedor usando Google Gemini."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Inicializa provedor Gemini.

        Args:
            api_key: chave da API (ou usar GEMINI_API_KEY do .env)

        Raises:
            LLMError: Se API key não configurada ou biblioteca não instalada
        """
        if not GEMINI_AVAILABLE:
            raise LLMError("google-genai não está instalado")

        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise LLMError(
                "GEMINI_API_KEY não configurada. "
                "Defina a variável de ambiente ou passe api_key="
            )

        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.client = genai.Client(api_key=self.api_key)
        self.logger = logging.getLogger(__name__)

    async def generate_challenge(
        self,
        challenge_type: str,
        level: str,
    ) -> dict:
        """Gera desafio usando Gemini."""
        try:
            prompt = self._build_prompt(challenge_type, level)

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )

            response_text = getattr(response, "text", None)
            if not response_text:
                raise LLMError("Gemini retornou resposta sem texto")

            # Parse JSON da resposta
            challenge_data = self._parse_response(response_text)

            self.logger.info(
                f"Desafio gerado via Gemini ({self.model_name}): {challenge_type}/{level}"
            )
            return challenge_data

        except json.JSONDecodeError as e:
            raise LLMError(f"Resposta Gemini em formato inválido: {str(e)}")
        except Exception as e:
            raise LLMError(f"Erro ao chamar Gemini: {str(e)}")

    async def is_available(self) -> bool:
        """Verifica se Gemini está disponível."""
        try:
            # Teste rápido
            response = self.client.models.generate_content(
                model=self.model_name,
                contents="Responda apenas com OK",
            )
            return getattr(response, "text", None) is not None
        except Exception:
            return False

    def _build_prompt(self, challenge_type: str, level: str) -> str:
        """Constrói prompt para Gemini."""
        return f"""Gere um desafio de programação no formato JSON.

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

    def _parse_response(self, response_text: str) -> dict:
        """Parse da resposta JSON."""
        # Remove markdown code blocks se houver
        text = response_text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        data = json.loads(text.strip())

        # Validações mínimas
        required_keys = ["title", "description", "example_input", "example_output"]
        for key in required_keys:
            if key not in data:
                raise json.JSONDecodeError(
                    f"Campo obrigatório faltando: {key}", "", 0
                )

        return data
