"""
Exemplo de uso do serviço de geração de desafios.

Demonstra:
1. Geração individual de desafios
2. Geração em lote
3. Uso com e sem Redis
4. Tratamento de erros
"""
import asyncio
import logging
from src.generators.challenge_generator import ChallengeGenerator, ChallengeType, ChallengeLevel
from src.services.challenge_service import ChallengeService
from src.integrations.redis import MockRedisClient

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================================================
# EXEMPLO 1: Usando apenas o gerador (sem Redis)
# ============================================================================
def example_generator_only():
    """Exemplo básico de geração sem Redis."""
    print("\n" + "="*70)
    print("EXEMPLO 1: Gerador Apenas (sem Redis)")
    print("="*70)

    generator = ChallengeGenerator()

    # Gerar um desafio aleatório
    print("\n1. Desafio aleatório:")
    challenge = generator.generate()
    print(f"   ID: {challenge.id}")
    print(f"   Tipo: {challenge.type.value}")
    print(f"   Nível: {challenge.level.value}")
    print(f"   Título: {challenge.title}")
    print(f"   Descrição: {challenge.description}")

    # Gerar algoritmo de nível fácil
    print("\n2. Desafio específico (Algoritmo - Fácil):")
    challenge = generator.generate(
        challenge_type=ChallengeType.ALGORITHM,
        level=ChallengeLevel.EASY
    )
    print(f"   Tipo: {challenge.type.value}")
    print(f"   Nível: {challenge.level.value}")
    print(f"   Título: {challenge.title}")

    # Gerar lote de 5 desafios
    print("\n3. Lote de 5 desafios de string:")
    challenges = generator.generate_batch(
        count=5,
        challenge_type=ChallengeType.STRING_MANIPULATION
    )
    print(f"   Gerados: {len(challenges)} desafios")
    for i, ch in enumerate(challenges, 1):
        print(f"   {i}. {ch.title} ({ch.level.value})")

    # Tipos e níveis disponíveis
    print("\n4. Tipos disponíveis:")
    types = generator.get_available_types()
    print(f"   {', '.join(types)}")

    print("\n5. Níveis disponíveis:")
    levels = generator.get_available_levels()
    print(f"   {', '.join(levels)}")


# ============================================================================
# EXEMPLO 2: Usando o serviço com Redis Mock
# ============================================================================
async def example_service_with_redis():
    """Exemplo com serviço e Redis mockado."""
    print("\n" + "="*70)
    print("EXEMPLO 2: Serviço com Redis Mock")
    print("="*70)

    # Criar cliente Redis mock e serviço
    redis_client = MockRedisClient()
    service = ChallengeService(redis_client=redis_client)

    # Gerar e salvar um desafio
    print("\n1. Gerar e salvar um desafio:")
    challenge = await service.generate_and_save(
        challenge_type=ChallengeType.MATH,
        level=ChallengeLevel.MEDIUM
    )
    print(f"   Desafio gerado: {challenge.id}")
    print(f"   Título: {challenge.title}")
    print(f"   No Redis: {await redis_client.get_pool_size()} desafio(s)")

    # Gerar lote
    print("\n2. Gerar e salvar lote de 10 desafios:")
    challenges = await service.generate_and_save_batch(count=10)
    print(f"   Gerados: {len(challenges)} desafios")
    print(f"   Total no Redis: {await redis_client.get_pool_size()} desafios")

    # Recuperar desafios do Redis
    print("\n3. Recuperar desafios do Redis (FIFO):")
    for i in range(3):
        challenge_json = await redis_client.get_challenge()
        if challenge_json:
            import json
            data = json.loads(challenge_json)
            print(f"   {i+1}. {data['title']} ({data['level']})")

    print(f"\n   Desafios restantes: {await redis_client.get_pool_size()}")


# ============================================================================
# EXEMPLO 3: Tratamento de erros
# ============================================================================
async def example_error_handling():
    """Exemplo de tratamento de erros."""
    print("\n" + "="*70)
    print("EXEMPLO 3: Tratamento de Erros")
    print("="*70)

    service = ChallengeService()

    # Tipo inválido
    print("\n1. Tipo inválido:")
    try:
        await service.generate_and_save(challenge_type="tipo_inexistente")
    except Exception as e:
        print(f"   ❌ Erro capturado: {type(e).__name__}")
        print(f"   Mensagem: {str(e)}")

    # Contagem inválida
    print("\n2. Contagem inválida (zero):")
    try:
        await service.generate_and_save_batch(count=0)
    except Exception as e:
        print(f"   ❌ Erro capturado: {type(e).__name__}")
        print(f"   Mensagem: {str(e)}")

    # Contagem acima do limite
    print("\n3. Contagem acima do limite (1001):")
    try:
        await service.generate_and_save_batch(count=1001)
    except Exception as e:
        print(f"   ❌ Erro capturado: {type(e).__name__}")
        print(f"   Mensagem: {str(e)}")

    # Sucesso
    print("\n4. Geração bem-sucedida:")
    challenge = await service.generate_and_save()
    print(f"   ✅ Desafio gerado: {challenge.title}")


# ============================================================================
# EXEMPLO 4: Dados do desafio em JSON
# ============================================================================
def example_challenge_serialization():
    """Exemplo de serialização de desafio para JSON."""
    print("\n" + "="*70)
    print("EXEMPLO 4: Serialização de Desafio (JSON)")
    print("="*70)

    generator = ChallengeGenerator()
    challenge = generator.generate(
        challenge_type=ChallengeType.ALGORITHM,
        level=ChallengeLevel.HARD
    )

    print("\n1. Objeto Challenge:")
    print(f"   ID: {challenge.id}")
    print(f"   Tipo: {challenge.type}")
    print(f"   Nível: {challenge.level}")

    print("\n2. Convertido para dicionário:")
    data = challenge.to_dict()
    import json
    json_str = json.dumps(data, indent=2)
    print(json_str)

    print("\n3. Estrutura:")
    print(f"   Chaves: {', '.join(data.keys())}")
    print(f"   Metadados: {data.get('metadata', {})}")


# ============================================================================
# EXEMPLO 5: Estatísticas
# ============================================================================
def example_statistics():
    """Exemplo mostrando distribuição de desafios."""
    print("\n" + "="*70)
    print("EXEMPLO 5: Distribuição de Desafios (100 aleatórios)")
    print("="*70)

    generator = ChallengeGenerator()
    challenges = generator.generate_batch(count=100)

    # Contar por tipo
    type_count = {}
    level_count = {}
    for ch in challenges:
        type_count[ch.type.value] = type_count.get(ch.type.value, 0) + 1
        level_count[ch.level.value] = level_count.get(ch.level.value, 0) + 1

    print("\n1. Por Tipo:")
    for type_name, count in sorted(type_count.items()):
        percentage = (count / len(challenges)) * 100
        print(f"   {type_name:30s}: {count:3d} ({percentage:5.1f}%)")

    print("\n2. Por Nível:")
    for level_name, count in sorted(level_count.items()):
        percentage = (count / len(challenges)) * 100
        print(f"   {level_name:30s}: {count:3d} ({percentage:5.1f}%)")


# ============================================================================
# MAIN: Executar todos os exemplos
# ============================================================================
async def main():
    """Executar todos os exemplos."""
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*15 + "EXEMPLOS DE USO - CHALLENGE ENGINE" + " "*21 + "║")
    print("╚" + "="*68 + "╝")

    # Exemplo 1: Gerador apenas
    example_generator_only()

    # Exemplo 2: Serviço com Redis
    await example_service_with_redis()

    # Exemplo 3: Tratamento de erros
    await example_error_handling()

    # Exemplo 4: Serialização
    example_challenge_serialization()

    # Exemplo 5: Estatísticas
    example_statistics()

    print("\n" + "="*70)
    print("✅ Todos os exemplos executados com sucesso!")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
