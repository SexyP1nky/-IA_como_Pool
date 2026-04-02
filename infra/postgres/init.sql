-- Schema: fallback de desafios (mesmo payload JSON que o pool Redis).
-- Modelo de referência: ChallengeRecord + Challenge em challenge_generator.py

DROP TABLE IF EXISTS challenges CASCADE;

CREATE TABLE challenges (
    id SERIAL PRIMARY KEY,
    challenge TEXT NOT NULL
);

INSERT INTO challenges (challenge) VALUES ($json${"id": "pg-fallback-1", "type": "algorithm", "level": "easy", "title": "Sum of Two Numbers", "description": "Dado uma lista de números inteiros e um alvo, encontre dois números que somam o alvo.", "example_input": "[2, 7, 11, 15], target=9", "example_output": "[0, 1]", "created_at": "2024-01-01T00:00:00.000000", "metadata": {"source": "postgres_fallback"}}$json$);

INSERT INTO challenges (challenge) VALUES ($json${"id": "pg-fallback-2", "type": "string_manipulation", "level": "medium", "title": "Palindrome Check", "description": "Verifique se uma string é um palíndromo ignorando espaços e maiúsculas.", "example_input": "A man a plan a canal Panama", "example_output": "true", "created_at": "2024-01-01T00:00:00.000000", "metadata": {"source": "postgres_fallback"}}$json$);
