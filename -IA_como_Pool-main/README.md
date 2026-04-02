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

# 9. Setup Inicial

## Docker Compose

Serviços definidos:

- api  
- worker  
- rabbitmq  
- redis  
- postgres  

Objetivo: permitir execução padronizada do sistema localmente.

---

## CI Básico

Pipeline inicial:

1. Instalar dependências  
2. Executar lint  
3. Rodar testes unitários  
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
