# Projeto Engenharia de Sistemas Distribuídos

## Tema: POC 4 — IA como Pool (Não Dependência Síncrona)

---

## Integrantes

Ruanderson Gabriel Alves da Silva Costa de Fontes  
Email: ruanderson.gabriel@academico.ufpb.br  
GitHub: ruanderson1  

Samuel da Silva Ferreira  
Email: bixincorrendo@gmail.com  
GitHub: sad611  

Leonardo Chianca Braga  
Email: lchiancab@gmail.com  
GitHub: leochianca  

Mateus Lima Cavalcanti de Albuquerque  
Email: mateuslca2020@gmail.com  
GitHub: mateuslca  

Yan Feitosa Cláudio  
Email: yanfclaudio2002@gmail.com  
GitHub: YanFeitosa  

Yuri Silva Bezerra de Lima  
Email: gbaigbag@gmail.com  
GitHub: SexyP1nky  

---

# 1. Problema

A geração de desafios utilizando Inteligência Artificial depende de APIs externas que podem apresentar:

- alta latência  
- indisponibilidade  
- limites de uso (rate limit)  

Se utilizada de forma síncrona, essa dependência compromete diretamente o tempo de resposta e a disponibilidade do sistema.

---

# 2. Objetivo

Construir uma arquitetura distribuída onde:

- a IA não bloqueia o fluxo do usuário  
- o sistema continua funcionando mesmo com IA indisponível  
- a entrega de respostas ocorre em baixa latência  
- a geração de conteúdo é desacoplada do consumo  

---

# 3. Arquitetura Geral

A arquitetura é baseada na separação entre:

- fluxo síncrono (atendimento ao usuário)  
- fluxo assíncrono (geração de desafios via IA)  

Essa separação garante resiliência, escalabilidade e baixo acoplamento.

---

# 4. Containers (C4 Nível 2 — Descrição)

O sistema é composto pelos seguintes containers:

## API / Challenge Engine
- Recebe requisições dos usuários  
- Consulta Redis (pool)  
- Aplica fallback no PostgreSQL  
- Retorna resposta em baixa latência  

## Worker / Pool Generator
- Consome mensagens da fila  
- Gera desafios via IA  
- Popula o pool no Redis  

## RabbitMQ
- Responsável pela fila de processamento  
- Suporte a retry automático  
- Dead Letter Queue (DLQ)  

## Redis
- Armazena desafios já gerados (pool)  
- Permite respostas rápidas  

## PostgreSQL
- Base de fallback estático  
- Garante disponibilidade do sistema  

## LLM API (Externa)
- Responsável pela geração de desafios via IA  

---

# 5. Fluxo do Sistema

1. Worker consome mensagens do RabbitMQ  
2. Gera desafios via IA  
3. Armazena no Redis (pool)  
4. Usuário solicita desafio  
5. API consulta:
   - Redis → resposta imediata  
   - PostgreSQL → fallback  
6. Se tudo falhar → HTTP 503  

---

# 6. ADRs (Architecture Decision Records)

## ADR-0001 — Monólito Modular com Worker Assíncrono

Decisão: API e processamento assíncrono no mesmo repositório.  
Motivo: reduzir complexidade operacional e acelerar entrega.  
Trade-off: menor escalabilidade comparado a microsserviços completos.  

---

## ADR-001 — Uso de RabbitMQ para Mensageria

Decisão: utilização de RabbitMQ.  
Motivo: suporte a retry e DLQ.  
Benefício: confiabilidade no processamento assíncrono.  
Trade-off: ausência de replay nativo de eventos.  

---

## ADR-002 — Estratégia de Fallback com PostgreSQL

Decisão: uso de base estática como fallback.  
Motivo: garantir disponibilidade mesmo sem IA.  
Benefício: sistema resiliente.  
Trade-off: menor variedade de conteúdo.  

---

# 7. Padrões Arquiteturais

## Circuit Breaker
Onde: Pool Generator → LLM API  
Evita travamento do sistema diante de falhas da IA.

## Cache-Aside
Onde: Challenge Engine → Redis  
Permite resposta rápida priorizando o cache.

## Retry + Dead Letter Queue (DLQ)
Onde: RabbitMQ  
Permite reprocessamento e isolamento de falhas.

## Bulkhead / Isolation
Onde: separação entre API e Worker  
Evita que falhas em um serviço afetem outro.

## SYNC vs ASYNC
Onde: arquitetura geral  
Desacopla geração de conteúdo do tempo de resposta.

## Load Shedding
Onde: Challenge Engine  
Retorna erro controlado quando sistema está sobrecarregado.

---

# 8. Stack Tecnológico

| Camada | Tecnologia | Justificativa |
|--------|-----------|--------------|
| Backend | FastAPI | alta produtividade |
| Worker | Celery | processamento assíncrono |
| Mensageria | RabbitMQ | robusto e confiável |
| Cache | Redis | baixa latência |
| Banco | PostgreSQL | persistência confiável |
| IA | API externa (LLM) | geração de conteúdo |
| Infra | Docker Compose | padronização |
| CI | GitHub Actions | automação |

---

# 9. Como Executar

## Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) e [Docker Compose](https://docs.docker.com/compose/) instalados
- Python 3.11+ (apenas para rodar testes localmente)
- Uma chave de API da **Google Gemini** ou **Groq** (opcional — sem chave o sistema usa mock)

## 1. Configurar variáveis de ambiente

```bash
cp .env.example .env
```

Edite o arquivo `.env` e preencha pelo menos uma chave de API:

| Variável | Descrição |
|----------|-----------|
| `LLM_PROVIDER` | `gemini` ou `groq` |
| `GEMINI_API_KEY` | Chave da API Google Gemini |
| `GROQ_API_KEY` | Chave da API Groq (free tier em console.groq.com) |

As demais variáveis possuem valores padrão adequados para execução local.

## 2. Subir o sistema

```bash
docker compose up --build
```

Isso inicia cinco serviços: **Redis**, **RabbitMQ**, **PostgreSQL**, **pool-generator** (Celery worker) e **challenge-engine** (FastAPI).

## 3. Endpoints disponíveis

| Endpoint | Descrição |
|----------|-----------|
| `GET http://localhost:8000/health` | Health check — retorna status do Redis e tamanho do pool |
| `GET http://localhost:8000/challenge` | Retorna um desafio do pool (Redis → fallback Postgres) |
| `http://localhost:15672` | Dashboard RabbitMQ (usuário: `admin`, senha: `admin`) |

### Exemplo de resposta — `/health`

```json
{
  "status": "healthy",
  "redis": {
    "connected": true,
    "pool_size": 42
  }
}
```

## 4. Rodar testes

Instale as dependências de teste e execute com `pytest`:

```bash
# Challenge Engine
pip install -r services/challenge-engine/requirements.txt
pytest services/challenge-engine/tests/ -v

# Pool Generator
pip install -r services/pool-generator/requirements.txt
pytest services/pool-generator/tests/ -v
```

## 5. Validar Redis

Com os containers rodando, execute o script de validação para confirmar que o pool está sendo preenchido:

```bash
pip install redis
python scripts/validate_redis.py
```

## 6. Demo E2E (videocast)

Para executar a demonstração completa do sistema (build, health, consumo do pool, fallback PostgreSQL, auto-refill):

```bash
./scripts/demo_videocast.sh
```

Se o stack já estiver rodando, pule o build:

```bash
./scripts/demo_videocast.sh --skip-build
```

O script avança passo a passo com pausa entre cada etapa para narração ao vivo.

## 7. Parar o sistema

```bash
docker compose down
```

Para remover também os volumes persistentes (Redis, Postgres, RabbitMQ):

```bash
docker compose down -v
```

---

## CI

Pipeline no GitHub Actions (`.github/workflows/ci.yml`):

1. Instalar dependências
2. Executar lint (`ruff check`, `ruff format --check`)
3. Rodar testes unitários (`pytest`)
4. Realizar build

---

# 10. Divisão de Responsabilidades

Ruanderson → consolidação da arquitetura  
Samuel → definição da stack tecnológica  
Leonardo → setup e infraestrutura  
Mateus → padrões arquiteturais  
Yan → revisão técnica dos ADRs  
Yuri → diagramas C4  

---

# 11. Diferenciais da Arquitetura

- IA desacoplada do fluxo crítico  
- Sistema resiliente a falhas externas  
- Uso de fallback inteligente  
- Baixa latência garantida  
- Arquitetura simples e escalável  

---

# 12. Conclusão

A arquitetura proposta atende aos requisitos da POC ao garantir:

- disponibilidade  
- desempenho  
- resiliência  
- baixo acoplamento  

- IA fica fora do fluxo crítico.
- RabbitMQ mantém a fila de processamento assíncrono.
- Fallback estático mantém funcionamento quando IA/pool falham.


---

# Diagrama C4
## Nível 1 - Contexto
![nv1](https://github.com/user-attachments/assets/7a7d36e5-51af-4e64-8bfc-7dec88e035d0)

## Nível 2 - Containers
![nv2](https://github.com/user-attachments/assets/584ca9a2-5bfc-4218-95a1-bd4c81e4a3dd)

# LINK PARA O VÍDEO:
## Google Drive 
![nv3](https://drive.google.com/drive/folders/1lkM6arodZTM7yd5HpbLKcFcQ12IiD0Ng) 
