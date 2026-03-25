"""
Provedor de LLM usando Groq.
"""
import asyncio
import json
import logging
import os
from typing import Optional

from src.llm.provider import LLMProvider, LLMError

logger = logging.getLogger(__name__)

try:
    from groq import Groq

    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    logger.warning("groq não instalado. Instale com: pip install -q -U groq")


class GroqLLMProvider(LLMProvider):
    """Provedor usando Groq Chat Completions."""

    def __init__(self, api_key: Optional[str] = None):
        if not GROQ_AVAILABLE:
            raise LLMError("groq não está instalado")

        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise LLMError(
                "GROQ_API_KEY não configurada. "
                "Defina a variável de ambiente ou passe api_key="
            )

        self.model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.client = Groq(api_key=self.api_key)
        self.logger = logging.getLogger(__name__)

    async def generate_challenge(self, challenge_type: str, level: str) -> dict:
        """Gera desafio usando Groq."""
        try:
            prompt = self._build_prompt(challenge_type, level)

            completion = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "Você gera apenas JSON válido e sem markdown.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
            )

            content = completion.choices[0].message.content if completion.choices else None
            if not content:
                raise LLMError("Groq retornou resposta vazia")

            challenge_data = self._parse_response(content)
            self.logger.info(
                f"Desafio gerado via Groq ({self.model_name}): {challenge_type}/{level}"
            )
            return challenge_data

        except json.JSONDecodeError as e:
            raise LLMError(f"Resposta Groq em formato inválido: {str(e)}")
        except Exception as e:
            raise LLMError(f"Erro ao chamar Groq: {str(e)}")

    async def is_available(self) -> bool:
        """Verifica se Groq está disponível."""
        try:
            completion = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model_name,
                messages=[{"role": "user", "content": "Responda apenas OK"}],
                max_tokens=5,
                temperature=0,
            )
            return bool(completion.choices and completion.choices[0].message.content)
        except Exception:
            return False

    def _build_prompt(self, challenge_type: str, level: str) -> str:
        """Constrói prompt para Groq."""
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
        text = response_text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        data = json.loads(text.strip())

        required_keys = ["title", "description", "example_input", "example_output"]
        for key in required_keys:
            if key not in data:
                raise json.JSONDecodeError(
                    f"Campo obrigatório faltando: {key}", "", 0
                )

        return data
