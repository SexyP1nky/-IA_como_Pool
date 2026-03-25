"""
Integração com PostgreSQL para fallback de desafios.

Função principal:
    get_challenge_from_postgres()

Responsabilidade:
    Buscar um desafio na tabela 'challenges' do banco PostgreSQL.
    Retornar o desafio como string, ou None se não houver.
    Lançar exceção ou logar erro em caso de falha de conexão.

Exemplo de uso futuro:
    challenge = await get_challenge_from_postgres()
    if challenge:
        ...
"""

async def get_challenge_from_postgres() -> str | None:
    """
    Busca um desafio no banco PostgreSQL.

    Onde buscar:
        - Tabela: challenges
        - Campo a buscar: challenge (string)
        - Exemplo de query: SELECT challenge FROM challenges LIMIT 1;

    Onde salvar (se for necessário no futuro):
        - Tabela: challenges
        - Campo a salvar: challenge (string)
        - Exemplo de insert: INSERT INTO challenges (challenge) VALUES ('...');

    Retorna:
        str: desafio encontrado
        None: se não houver desafio disponível
    """
    # TODO: implementar integração com PostgreSQL
    # Buscar desafio: SELECT challenge FROM challenges LIMIT 1;
    # Salvar desafio (se necessário): INSERT INTO challenges (challenge) VALUES (...);
    return None
