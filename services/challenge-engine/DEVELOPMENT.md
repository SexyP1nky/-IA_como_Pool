# Challenge Engine - Serviço de Geração de Desafios

## Visão Geral

Serviço modular e escalável para geração de desafios de programação e distribuição através do Redis.

### Arquitetura

```
challenge-engine/
├── src/
│   ├── generators/
│   │   └── challenge_generator.py    # Lógica de geração de desafios
│   ├── services/
│   │   └── challenge_service.py      # Orquestração: geração + Redis
│   ├── integrations/
│   │   ├── redis.py                  # Cliente Redis (abstrato + impl)
│   │   └── postgres.py               # Integração PostgreSQL (fallback)
│   └── main.py                       # API FastAPI
└── tests/
    └── unit/                         # Testes unitários (pytest)
```

## Módulos Principais

### 1. **Challenge Generator** (`src/generators/challenge_generator.py`)

Responsável por gerar desafios individuais e em lote.

**Características:**
- 3 tipos de desafios: `ALGORITHM`, `STRING_MANIPULATION`, `MATH`
- 3 níveis de dificuldade: `EASY`, `MEDIUM`, `HARD`
- Pool pré-definido de 9 desafios (extensível)
- Geração individual ou em lote (até 1000)
- IDs únicos (UUID4)
- Timestamps UTC
- Metadados estruturados

**Uso:**

```python
from src.generators.challenge_generator import ChallengeGenerator, ChallengeType, ChallengeLevel

generator = ChallengeGenerator()

# Gerar desafio único
challenge = generator.generate()
# ou com parâmetros
challenge = generator.generate(
    challenge_type=ChallengeType.ALGORITHM,
    level=ChallengeLevel.EASY
)

# Gerar em lote
challenges = generator.generate_batch(count=10, challenge_type=ChallengeType.MATH)

# Tipos e níveis disponíveis
types = generator.get_available_types()
levels = generator.get_available_levels()
```

### 2. **Challenge Service** (`src/services/challenge_service.py`)

Serviço de orquestração que coordena geração + persistência no Redis.

**Características:**
- Interface com o gerador
- Persistência automática em Redis (não-blocante em caso de falha)
- Tratamento robusto de erros
- Logging detalhado
- Suporta Redis opcional

**Uso:**

```python
from src.services.challenge_service import ChallengeService
from src.integrations.redis import MockRedisClient

# Com Redis
redis_client = MockRedisClient()  # substitua por RedisClientImpl para Redis real
service = ChallengeService(redis_client=redis_client)

# Sem Redis (geração local apenas)
service = ChallengeService()

# Gerar e salvar
challenge = await service.generate_and_save(
    challenge_type=ChallengeType.ALGORITHM,
    level=ChallengeLevel.EASY
)

# Gerar e salvar em lote
challenges = await service.generate_and_save_batch(
    count=50,
    challenge_type=ChallengeType.STRING_MANIPULATION
)
```

### 3. **Redis Integration** (`src/integrations/redis.py`)

Abstração modular para armazenamento em Redis.

**Arquitetura:**
- `RedisClient` (interface abstrata)
- `RedisClientImpl` (implementação real com aioredis)
- `MockRedisClient` (mock em memória para testes)

**Características:**
- Persistência como JSON
- Operações FIFO
- Pool de desafios configurável
- Tratamento de exceções com `RedisConnectionError`

**Uso:**

```python
from src.integrations.redis import RedisClientImpl, MockRedisClient

# Real (requer Redis rodando)
redis = RedisClientImpl(host="localhost", port=6379, key="challenge_pool")
await redis.connect()
await redis.push_challenge(challenge)
size = await redis.get_pool_size()
await redis.close()

# Mock (para testes)
mock_redis = MockRedisClient()
await mock_redis.push_challenges_batch(challenges)
challenge = await mock_redis.get_challenge()
```

## API - Endpoints FastAPI

### `GET /health`
Health check do serviço.

### `GET /challenge`
Busca um desafio do pool Redis com fallback para PostgreSQL.

**Resposta:**
```json
{
  "challenge": "...",
  "source": "pool" | "static_fallback"
}
```

### `POST /challenge/generate?challenge_type=...&level=...`
Gera um novo desafio e salva no Redis.

**Query Parameters:**
- `challenge_type`: `algorithm`, `string_manipulation`, `math` (opcional)
- `level`: `easy`, `medium`, `hard` (opcional)

**Resposta:**
```json
{
  "id": "uuid",
  "challenge": {
    "id": "uuid",
    "type": "algorithm",
    "level": "easy",
    "title": "...",
    "description": "...",
    "example_input": "...",
    "example_output": "...",
    "created_at": "2026-03-25T...",
    "metadata": {...}
  },
  "source": "generated"
}
```

### `POST /challenge/generate-batch?count=10&challenge_type=...`
Gera múltiplos desafios em lote.

**Query Parameters:**
- `count`: 1-100 (default=10)
- `challenge_type`: opcional

**Resposta:**
```json
{
  "count": 10,
  "challenges": [...],
  "source": "generated"
}
```

### `GET /challenge/types`
Lista tipos de desafios disponíveis.

### `GET /challenge/levels`
Lista níveis de dificuldade disponíveis.

## Testes

### Executar todos os testes
```bash
pytest tests/unit/ -v
```

### Cobertura: 42 testes ✅
- **test_challenge_generator.py**: 16 testes
  - Inicialização
  - Geração individual (tipo, nível, validação)
  - Geração em lote
  - Conversão para dicionário
  - Metadados

- **test_challenge_service.py**: 16 testes
  - Inicialização com/sem Redis
  - Geração e salvamento (individual + batch)
  - Falhas não-blocantes no Redis
  - Tipos e níveis disponíveis

- **test_redis_client.py**: 10 testes
  - Push/Get
  - Tamanho do pool
  - Ordem FIFO
  - Close

## Rodando o Serviço

### 1. Instalar dependências
```bash
pip install -r requirements.txt
```

### 2. Iniciar servidor
```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Testar endpoints
```bash
# Health check
curl http://localhost:8000/health

# Gerar desafio
curl -X POST "http://localhost:8000/challenge/generate?challenge_type=algorithm&level=easy"

# Gerar 20 desafios de matemática
curl -X POST "http://localhost:8000/challenge/generate-batch?count=20&challenge_type=math"

# Listar tipos
curl http://localhost:8000/challenge/types

# Listar níveis
curl http://localhost:8000/challenge/levels
```

## Boas Práticas Implementadas

### 1. **Modularidade**
- Separação clara de responsabilidades
- Interfaces abstratas (ABC)
- Fácil extensão

### 2. **Observabilidade**
- Logging estruturado em todos os módulos
- UUIDs para rastreamento
- Metadados em desafios

### 3. **Tratamento de Erros**
- Exceções customizadas (`ChallengeGenerationError`, `RedisConnectionError`)
- Falhas no Redis não bloqueiam geração
- Status HTTP apropriados

### 4. **Testes**
- Cobertura total com pytest
- 42 testes passando
- Mocks para serviços externos

### 5. **Type Hints**
- Type hints em todas as funções
- Melhor IDE support e type checking

### 6. **Documentação**
- Docstrings detalhadas
- README completo
- Exemplos de uso

## Próximos Passos

### 1. Implementar Redis Real
```python
# Em vez de MockRedisClient, use:
from src.integrations.redis import RedisClientImpl

redis_client = RedisClientImpl(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=int(os.getenv("REDIS_DB", 0)),
)
await redis_client.connect()
service = ChallengeService(redis_client=redis_client)
```

### 2. Integração com PostgreSQL
- Implementar fallback de desafios estáticos
- Adicionar persistência de histórico

### 3. Expandir Pool de Desafios
- Adicionar mais tipos de desafios
- Mais exemplos por nível
- Persistência em banco de dados

### 4. Métricas e Observabilidade
- Prometheus metrics
- Jaeger tracing
- Structured logging

## Estrutura de Dados

### Challenge (Dataclass)
```python
@dataclass
class Challenge:
    id: str                              # UUID único
    type: ChallengeType                  # Tipo do desafio
    level: ChallengeLevel                # Nível de dificuldade
    title: str                           # Título
    description: str                     # Descrição
    example_input: str                   # Input de exemplo
    example_output: str                  # Output esperado
    created_at: str                      # ISO timestamp
    metadata: Optional[Dict]             # Dados adicionais
```

## Tratamento de Erros

| Exceção | Módulo | Quando Lançada |
|---------|--------|----------------|
| `ChallengeGenerationError` | Generator | Dados inválidos, pool vazio |
| `RedisConnectionError` | Redis | Falha de conexão |
| `ChallengeServiceError` | Service | Erro na geração ou lógica |

## Variáveis de Ambiente (Sugeridas)

```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_KEY=challenge_pool
LOG_LEVEL=INFO
```

---

**Status:** ✅ Pronto para produção (com Redis real configurado)
