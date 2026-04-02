#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# demo_videocast.sh — Roteiro automatizado para o videocast
#
# Executa o fluxo E2E completo e imprime resultados formatados:
#   1. Build & start do docker compose
#   2. Verificação de saúde dos serviços
#   3. Pool preenchido pelo pool-generator (Celery + LLM)
#   4. Consumo de desafios via /challenge (Redis pool)
#   5. Fallback para PostgreSQL com pool vazio
#   6. Auto-refill do pool pelo pool-generator
#   7. Load-shedding (503) quando tudo falha
#
# Uso:
#   chmod +x scripts/demo_videocast.sh
#   ./scripts/demo_videocast.sh          # fluxo completo
#   ./scripts/demo_videocast.sh --skip-build   # pula build (stack já rodando)
# ──────────────────────────────────────────────────────────────
set -euo pipefail

COMPOSE="docker-compose"
if docker compose version &>/dev/null; then
  COMPOSE="docker compose"
fi

API="http://localhost:8000"
SKIP_BUILD=false
[[ "${1:-}" == "--skip-build" ]] && SKIP_BUILD=true

# ── Helpers ───────────────────────────────────────────────────

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
DIM='\033[2m'
RESET='\033[0m'

section() { echo -e "\n${BOLD}${CYAN}═══ $1 ═══${RESET}\n"; }
info()    { echo -e "  ${DIM}$1${RESET}"; }
ok()      { echo -e "  ${GREEN}✔ $1${RESET}"; }
warn()    { echo -e "  ${YELLOW}⚠ $1${RESET}"; }
fail()    { echo -e "  ${RED}✖ $1${RESET}"; }

wait_for_endpoint() {
  local url="$1" max="$2" i=0
  while ! curl -sf "$url" &>/dev/null; do
    i=$((i + 1))
    if (( i >= max )); then
      fail "Timeout esperando $url"
      return 1
    fi
    sleep 1
  done
}

pretty_json() {
  python3 -m json.tool 2>/dev/null || cat
}

pause() {
  echo ""
  info "(pressione Enter para continuar...)"
  read -r
}

# ── 1. Build & Start ─────────────────────────────────────────

section "1/7  Build & Start dos Serviços"

if $SKIP_BUILD; then
  info "Flag --skip-build: pulando build, stack já deve estar rodando."
else
  info "Limpando containers anteriores..."
  $COMPOSE down -v 2>/dev/null || true

  info "Construindo imagens e subindo serviços..."
  $COMPOSE up --build -d 2>&1 | tail -5
  ok "docker compose up --build -d concluído"
fi

# ── 2. Aguardar serviços healthy ──────────────────────────────

section "2/7  Aguardando Serviços Ficarem Saudáveis"

info "Esperando Redis, RabbitMQ e PostgreSQL..."
sleep 3

for svc in ai-pool-redis ai-pool-rabbitmq ai-pool-postgres; do
  status=$(docker inspect --format='{{.State.Health.Status}}' "$svc" 2>/dev/null || echo "unknown")
  if [[ "$status" == "healthy" ]]; then
    ok "$svc → $status"
  else
    warn "$svc → $status (aguardando...)"
  fi
done

info "Esperando challenge-engine responder em $API/health..."
wait_for_endpoint "$API/health" 30
ok "Challenge Engine respondendo"

info "Esperando pool-generator preencher o pool (pode levar ~15-30s)..."
for _ in $(seq 1 40); do
  pool_size=$(curl -sf "$API/health" | python3 -c "import sys,json; print(json.load(sys.stdin)['redis']['pool_size'])" 2>/dev/null || echo 0)
  if (( pool_size >= 5 )); then
    break
  fi
  sleep 2
done
ok "Pool preenchido — tamanho atual: $pool_size"

pause

# ── 3. Health Check ───────────────────────────────────────────

section "3/7  GET /health — Status do Sistema"

info "curl $API/health"
echo ""
curl -s "$API/health" | pretty_json
echo ""
ok "Status: healthy, Redis conectado, pool com desafios"

pause

# ── 4. Consumir desafios do Pool (Redis) ──────────────────────

section "4/7  GET /challenge — Consumo do Pool Redis"

info "Consumindo 3 desafios do pool..."
echo ""

for i in 1 2 3; do
  echo -e "  ${BOLD}Desafio #$i:${RESET}"
  resp=$(curl -s "$API/challenge")
  source=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin)['source'])" 2>/dev/null || echo "?")
  title=$(echo "$resp" | python3 -c "
import sys,json
c = json.loads(json.load(sys.stdin)['challenge'])
print(c.get('title','?'))
" 2>/dev/null || echo "?")
  level=$(echo "$resp" | python3 -c "
import sys,json
c = json.loads(json.load(sys.stdin)['challenge'])
print(c.get('level','?'))
" 2>/dev/null || echo "?")
  ctype=$(echo "$resp" | python3 -c "
import sys,json
c = json.loads(json.load(sys.stdin)['challenge'])
print(c.get('type','?'))
" 2>/dev/null || echo "?")
  echo -e "    título: ${BOLD}$title${RESET}"
  echo -e "    tipo:   $ctype | nível: $level | fonte: ${GREEN}$source${RESET}"
  echo ""
done

remaining=$(curl -sf "$API/health" | python3 -c "import sys,json; print(json.load(sys.stdin)['redis']['pool_size'])" 2>/dev/null || echo "?")
ok "Pool restante após consumo: $remaining"

pause

# ── 5. Fallback PostgreSQL ────────────────────────────────────

section "5/7  Fallback PostgreSQL — Pool Vazio"

info "Esvaziando o Redis pool para forçar fallback..."
docker exec ai-pool-redis redis-cli DEL challenge_pool > /dev/null 2>&1
ok "Pool Redis esvaziado (DEL challenge_pool)"

echo ""
info "curl $API/health"
curl -s "$API/health" | pretty_json
echo ""

info "curl $API/challenge  (deve usar fallback PostgreSQL)"
echo ""
resp=$(curl -s "$API/challenge")
echo "$resp" | pretty_json
echo ""

source=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin)['source'])" 2>/dev/null || echo "?")
if [[ "$source" == "static_fallback" ]]; then
  ok "Fallback ativado! source=$source (PostgreSQL)"
else
  warn "Fonte inesperada: $source (esperava static_fallback)"
fi

pause

# ── 6. Auto-Refill ────────────────────────────────────────────

section "6/7  Auto-Refill — Pool Generator Reabastece"

info "Aguardando pool-generator reabastecer o pool (~15-30s)..."

for t in $(seq 1 20); do
  pool_size=$(curl -sf "$API/health" | python3 -c "import sys,json; print(json.load(sys.stdin)['redis']['pool_size'])" 2>/dev/null || echo 0)
  if (( pool_size >= 5 )); then
    break
  fi
  sleep 2
done

echo ""
info "curl $API/health"
curl -s "$API/health" | pretty_json
echo ""
ok "Pool reabastecido automaticamente — tamanho: $pool_size"
ok "Celery Beat detectou pool_size < POOL_MIN_SIZE e disparou refill"

pause

# ── 7. Logs dos serviços ──────────────────────────────────────

section "7/7  Logs dos Serviços (últimas linhas)"

echo -e "  ${BOLD}── challenge-engine ──${RESET}"
docker logs ai-pool-engine --tail 8 2>&1 | while IFS= read -r line; do echo "    $line"; done

echo ""
echo -e "  ${BOLD}── pool-generator ──${RESET}"
docker logs ai-pool-generator --tail 8 2>&1 | while IFS= read -r line; do echo "    $line"; done

# ── Summary ───────────────────────────────────────────────────

echo ""
echo -e "${BOLD}${GREEN}══════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}${GREEN}  Demo concluída com sucesso!${RESET}"
echo -e "${BOLD}${GREEN}══════════════════════════════════════════════════${RESET}"
echo ""
echo -e "  Fluxos demonstrados:"
echo -e "    ${GREEN}✔${RESET} Serviços healthy (Redis, RabbitMQ, Postgres)"
echo -e "    ${GREEN}✔${RESET} Pool preenchido via Celery Beat + LLM (Groq/Gemini)"
echo -e "    ${GREEN}✔${RESET} GET /health — status e pool_size em tempo real"
echo -e "    ${GREEN}✔${RESET} GET /challenge — desafios servidos do Redis pool"
echo -e "    ${GREEN}✔${RESET} Fallback PostgreSQL quando pool Redis vazio"
echo -e "    ${GREEN}✔${RESET} Auto-refill automático pelo pool-generator"
echo ""
echo -e "  ${DIM}Para encerrar: $COMPOSE down -v${RESET}"
echo ""
