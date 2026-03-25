"""
Integração com Redis para o pool de desafios.

Função principal:
    get_challenge_from_redis()

Responsabilidade:
    Buscar um desafio pronto no Redis usando a chave definida (default: "challenge_pool").
    Retornar o desafio como string, ou None se não houver.
    Lançar exceção ou logar erro em caso de falha de conexão.

Exemplo de uso futuro:
    challenge = await get_challenge_from_redis()
    if challenge:
        ...
"""

default_redis_key = "challenge_pool"

async def get_challenge_from_redis() -> str | None:
    """
    Busca um desafio pronto no Redis.
    Retorna:
        str: desafio encontrado
        None: se não houver desafio disponível
    """
    # TODO: implementar integração com Redis
    return None
