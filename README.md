# Projeto Engenharia de Sistemas Distribuídos

## Tema: POC 4 - IA como Pool (Não Dependência Síncrona)

## Integrantes:
    Ruanderson Gabriel Alves da Silva Costa de fontes
      Contato: ruanderson.gabriel@academico.ufpb.br
      Github: ruanderson1
  
    Samuel da Silva Ferreira 
      Contato: bixincorrendo@gmail.com
      Github: sad611
    
    Leonardo Chianca Braga
      Contato: lchiancab@gmail.com
      Github: leochianca
    
    Mateus Lima Cavalcanti de Albuquerque
      Contato: mateuslca2020@gmail.com
      Github: mateuslca
    
    Yan Feitosa Cláudio
      Contato: yanfclaudio2002@gmail.com
      Github: YanFeitosa
    
    Yuri Silva Bezerra de Lima
      Contato: gbaigbag@gmail.com
      Github: SexyP1nky

# Padrões Arquiteturais

---

## Circuit Breaker
**Onde:** Pool Generator → LLM API

A LLM API é externa e pode cair ou ficar lenta. Sem proteção, workers do Celery ficariam
travados esperando timeout, esgotando o pool no Redis. O Circuit Breaker monitora falhas
consecutivas e, ao atingir o threshold, para de tentar chamar a API por um período —
liberando os workers e evitando degradação em cascata.

---

## Cache-Aside
**Onde:** Challenge Engine → Redis

O Challenge Engine sempre consulta o Redis antes de qualquer outra fonte. Se o desafio
está lá, entrega imediatamente. Se não está, cai para o banco estático. Quem popula o
cache é o Pool Generator em background — o Engine só lê. Isso mantém a entrega rápida
sem depender da IA no caminho crítico.

---

## Retry + Dead Letter Queue (DLQ)
**Onde:** RabbitMQ — falhas de geração

Quando a geração de um desafio falha, a mensagem não é descartada — o RabbitMQ a
recoloca na fila automaticamente para nova tentativa. Após N tentativas sem sucesso,
a mensagem vai para a DLQ. Isso garante que nenhuma falha seja silenciosa e permite
analisar o que causou os erros.

---

## Bulkhead / Isolation
**Onde:** Pool Generator e Challenge Engine como serviços separados

Cada serviço roda em seu próprio container com recursos isolados. Se o Pool Generator
ficar sobrecarregado processando a fila, isso não consome CPU nem memória do Challenge
Engine. A separação garante que uma falha em um serviço não afeta o outro.

---

## SYNC vs ASYNC
**Onde:** geração de desafios (async) vs entrega ao jogador (sync)

Gerar um desafio via LLM pode levar segundos. Entregar ao jogador precisa ser em
milissegundos. A solução é desacoplar os dois no tempo: o Pool Generator gera em
background sem ninguém esperando, e o Challenge Engine entrega o que já está pronto
no Redis. Esse desacoplamento é o argumento central da POC.

---

## Load Shedding
**Onde:** Challenge Engine — último recurso

Se nem Redis nem PostgreSQL estiverem disponíveis, o Engine retorna HTTP 503
imediatamente em vez de ficar tentando indefinidamente. A decisão de rejeitar
a requisição de forma explícita e rápida é preferível a travar o serviço inteiro
sob uma carga que ele não consegue processar.

---

## Resumo

| Padrão | Onde | Problema que resolve |
|---|---|---|
| Circuit Breaker | Pool Generator → LLM API | Evita travar workers quando a IA está fora ou lenta |
| Cache-Aside | Challenge Engine → Redis | Entrega rápida sem depender da IA no caminho crítico |
| Retry + DLQ | RabbitMQ | Falhas de geração não são perdidas silenciosamente |
| Bulkhead / Isolation | Dois serviços separados | Lentidão no Generator não afeta o Engine |
| SYNC vs ASYNC | Geração vs entrega | Desacopla o tempo de geração do tempo de resposta |
| Load Shedding | Challenge Engine | Rejeita carga explicitamente quando nada está disponível |
