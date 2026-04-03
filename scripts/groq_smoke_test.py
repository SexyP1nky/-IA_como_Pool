#!/usr/bin/env python3
"""Standalone Groq API smoke test.

Usage examples:
    python scripts/groq_smoke_test.py
    python scripts/groq_smoke_test.py --prompt "Gere um haiku sobre APIs"
    python scripts/groq_smoke_test.py --availability
    python scripts/groq_smoke_test.py --env-file .env

The script reads GROQ_API_KEY and GROQ_MODEL from the environment or a .env file.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test for Groq LLM calls")
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to a .env file to load before reading environment variables",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Override GROQ_API_KEY from the environment",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override GROQ_MODEL from the environment",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Prompt enviado ao modelo. Se omitido, usa um pedido de algoritmo em Python.",
    )
    parser.add_argument(
        "--system",
        default="Você é um assistente objetivo e responde de forma direta.",
        help="System prompt enviado ao modelo",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.2,
        help="Temperature da geração",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=256,
        help="Limite de tokens de saída",
    )
    parser.add_argument(
        "--availability",
        action="store_true",
        help="Executa um teste leve de disponibilidade em vez de uma geração completa",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Pede explicitamente uma resposta em JSON no prompt",
    )
    parser.add_argument(
        "--python-algorithm",
        action="store_true",
        help="Pede explicitamente um algoritmo em Python no prompt",
    )
    return parser.parse_args()


def load_env_file(env_file: str) -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    env_path = Path(env_file)
    if env_path.exists():
        load_dotenv(env_path)


def get_api_key(override: str | None) -> str:
    api_key = override or os.getenv("GROQ_API_KEY")
    if not api_key:
        print("ERRO: GROQ_API_KEY não encontrado.", file=sys.stderr)
        sys.exit(1)
    return api_key


def get_model(override: str | None) -> str:
    return override or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


def build_prompt(prompt: str, request_json: bool) -> str:
    if not request_json:
        return prompt

    return (
        "Responda estritamente com JSON válido, sem markdown e sem texto extra. "
        f"{prompt}"
    )


def build_python_algorithm_prompt() -> str:
    return (
        "Escreva um algoritmo em Python para resolver um problema clássico de programação. "
        "Escolha um problema simples, como Two Sum, Fibonacci, ou Valid Parentheses. "
        "Responda com:\n"
        "1. Uma breve explicação de 1 ou 2 frases.\n"
        "2. O código Python completo em um bloco de código.\n"
        "3. Um pequeno exemplo de uso com entrada e saída esperada.\n\n"
        "Regras:\n"
        "- Use Python 3.\n"
        "- O código deve estar pronto para execução.\n"
        "- Não responda em JSON.\n"
        "- Não use pseudocódigo."
    )


async def call_groq(
    *,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
    availability: bool,
) -> dict[str, Any]:
    try:
        from groq import Groq
    except ImportError:
        print("ERRO: pacote 'groq' não está instalado.", file=sys.stderr)
        print("Instale com: pip install groq", file=sys.stderr)
        sys.exit(1)

    client = Groq(api_key=api_key)

    if availability:
        messages = [{"role": "user", "content": "Responda apenas OK"}]
        t0 = time.perf_counter()
        completion = await asyncio.to_thread(
            client.chat.completions.create,
            model=model,
            messages=messages,
            max_tokens=8,
            temperature=0,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
    else:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        t0 = time.perf_counter()
        completion = await asyncio.to_thread(
            client.chat.completions.create,
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000

    content = completion.choices[0].message.content if completion.choices else None
    return {
        "model": model,
        "availability": availability,
        "elapsed_ms": round(elapsed_ms, 1),
        "content": content,
        "raw": completion,
    }


async def main() -> None:
    args = parse_args()
    load_env_file(args.env_file)

    api_key = get_api_key(args.api_key)
    model = get_model(args.model)

    if args.prompt is not None:
        user_prompt = build_prompt(args.prompt, args.json)
    elif args.python_algorithm:
        user_prompt = build_python_algorithm_prompt()
    else:
        user_prompt = (
            "Responda apenas com uma solução em Python para um problema clássico de algoritmo. "
            "Inclua uma breve explicação, o código completo e um exemplo de uso."
        )

    result = await call_groq(
        api_key=api_key,
        model=model,
        system_prompt=args.system,
        user_prompt=user_prompt,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        availability=args.availability,
    )

    print(f"model={result['model']}")
    print(f"elapsed_ms={result['elapsed_ms']}")
    print("--- response ---")
    print(result["content"] or "<empty response>")

    if args.json and result["content"]:
        try:
            parsed = json.loads(result["content"])
            print("--- parsed-json ---")
            print(json.dumps(parsed, ensure_ascii=False, indent=2))
        except json.JSONDecodeError:
            print("--- parsed-json ---")
            print("Response was not valid JSON.")


if __name__ == "__main__":
    asyncio.run(main())
