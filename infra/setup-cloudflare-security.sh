#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════════════
#  LIDDIS — Configuração automática de segurança no Cloudflare
#
#  Como executar (Git Bash, com venv ativado):
#    source venv/Scripts/activate
#    export CF_TOKEN="seu_token_aqui"
#    bash infra/setup-cloudflare-security.sh
# ════════════════════════════════════════════════════════════════════════════

set -euo pipefail

DOMAIN="liddis.com.br"

# ── Validação de pré-requisitos ───────────────────────────────────────────────
if [[ -z "${CF_TOKEN:-}" ]]; then
  echo "  ❌ CF_TOKEN não definido."
  echo "     Execute: export CF_TOKEN=\"seu_token_aqui\""
  exit 1
fi

command -v curl >/dev/null || { echo "❌ curl não encontrado."; exit 1; }

# Detecta Python funcional (ignora alias do Windows Store)
_py_works() { "$1" -c "import sys" >/dev/null 2>&1; }

if [[ -n "${VIRTUAL_ENV:-}" ]] && _py_works "${VIRTUAL_ENV}/Scripts/python.exe"; then
  PY="${VIRTUAL_ENV}/Scripts/python.exe"
elif _py_works python3; then
  PY=python3
elif _py_works python; then
  PY=python
else
  echo "❌ Python não encontrado. Ative o venv: source venv/Scripts/activate"; exit 1
fi
echo "  → Python: $PY"

CF_API="https://api.cloudflare.com/client/v4"
AUTH=(-H "Authorization: Bearer $CF_TOKEN" -H "Content-Type: application/json")

log()  { echo "  ✓ $*"; }
warn() { echo "  ⚠  $*"; }
fail() { echo "  ✗ $*"; exit 1; }

py_ok() {
  "$PY" -c "
import json, sys
r = json.load(sys.stdin)
sys.exit(0 if r.get('success') else 1)
" 2>/dev/null
}

echo ""
echo "══════════════════════════════════════════════════════════════"
echo "  LIDDIS — Configuração de Segurança Cloudflare"
echo "  Domínio: $DOMAIN"
echo "══════════════════════════════════════════════════════════════"

# ── 1. Obter Zone ID ──────────────────────────────────────────────────────────
echo ""
echo "[ 1/4 ] Identificando zona do Cloudflare..."

ZONE_RESP=$(curl -s -X GET "$CF_API/zones?name=$DOMAIN&status=active" "${AUTH[@]}")
ZONE_ID=$(echo "$ZONE_RESP" | "$PY" -c "
import json, sys
r = json.load(sys.stdin)
results = r.get('result', [])
print(results[0]['id'] if results else '', end='')
")

if [[ -z "$ZONE_ID" ]]; then
  fail "Zona '$DOMAIN' não encontrada. Verifique se o domínio está no Cloudflare e se o token tem permissão Zone:Read."
fi

log "Zone ID: $ZONE_ID"

# ── 2. Security Level → Medium ────────────────────────────────────────────────
echo ""
echo "[ 2/4 ] Configurando Security Level → Medium..."

RESP=$(curl -s -X PATCH "$CF_API/zones/$ZONE_ID/settings/security_level" \
  "${AUTH[@]}" -d '{"value":"medium"}')

if echo "$RESP" | py_ok; then
  log "Security Level → medium"
else
  warn "Não foi possível via API. Configure manualmente: Security → Settings → Security Level → Medium"
fi

# ── 3. Bot Fight Mode → ON ────────────────────────────────────────────────────
echo ""
echo "[ 3/4 ] Ativando Bot Fight Mode..."

RESP=$(curl -s -X PUT "$CF_API/zones/$ZONE_ID/bot_management" \
  "${AUTH[@]}" -d '{"fight_mode":true}')

if echo "$RESP" | py_ok; then
  log "Bot Fight Mode ativado"
else
  RESP2=$(curl -s -X PATCH "$CF_API/zones/$ZONE_ID/settings/bot_fight_mode" \
    "${AUTH[@]}" -d '{"value":"on"}')
  if echo "$RESP2" | py_ok; then
    log "Bot Fight Mode ativado (via settings)"
  else
    warn "Ativar manualmente: Security → Bots → Bot Fight Mode → ON"
  fi
fi

# ── 4. Regras WAF Custom ──────────────────────────────────────────────────────
echo ""
echo "[ 4/4 ] Criando 5 regras WAF..."

RULES_JSON=$("$PY" -c "
import json
rules = [
    {
        'action': 'block',
        'expression': '(http.user_agent contains \"sqlmap\") or (http.user_agent contains \"nikto\") or (http.user_agent contains \"masscan\") or (http.user_agent contains \"nuclei\") or (http.user_agent contains \"nmap\")',
        'description': 'LIDDIS: Bloquear ferramentas de ataque',
        'enabled': True,
    },
    {
        'action': 'block',
        'expression': r'(http.request.uri.path matches \"\\\\.(php|asp|aspx|env|git|bak|config|sql)\$\")',
        'description': 'LIDDIS: Bloquear extensoes perigosas',
        'enabled': True,
    },
    {
        'action': 'js_challenge',
        'expression': '(http.request.uri.path contains \"/admin/\") and (cf.threat_score gt 20)',
        'description': 'LIDDIS: Proteger painel administrativo',
        'enabled': True,
    },
    {
        'action': 'block',
        'expression': '(http.request.uri.query contains \"UNION SELECT\") or (http.request.uri.query contains \"<script\") or (http.request.uri.query contains \"javascript:\") or (http.request.uri.query contains \"DROP TABLE\")',
        'description': 'LIDDIS: Bloquear injecao na URL',
        'enabled': True,
    },
    {
        'action': 'js_challenge',
        'expression': '(http.request.uri.path eq \"/login/\") and (cf.threat_score gt 10)',
        'description': 'LIDDIS: Desafiar IPs suspeitos no login',
        'enabled': True,
    },
]
print(json.dumps({'rules': rules}))
")

PHASE="http_request_firewall_custom"
EXISTING=$(curl -s -X GET "$CF_API/zones/$ZONE_ID/rulesets" "${AUTH[@]}")

RULESET_ID=$(echo "$EXISTING" | "$PY" -c "
import json, sys
r = json.load(sys.stdin)
for rs in r.get('result', []):
    if rs.get('phase') == 'http_request_firewall_custom':
        print(rs['id'])
        break
" 2>/dev/null || true)

NAMES=("Ferramentas de ataque" "Extensoes perigosas" "Painel admin" "Injecao na URL" "IPs suspeitos no login")

if [[ -n "$RULESET_ID" ]]; then
  EXISTING_RULES=$(curl -s -X GET "$CF_API/zones/$ZONE_ID/rulesets/$RULESET_ID" "${AUTH[@]}" | \
    "$PY" -c "import json,sys; r=json.load(sys.stdin); print(len(r.get('result',{}).get('rules',[])))" 2>/dev/null || echo "0")

  if [[ "$EXISTING_RULES" -gt 0 ]]; then
    warn "Ja existem $EXISTING_RULES regra(s). As 5 regras LIDDIS serao adicionadas."
    warn "Se ultrapassar 5 (limite Free), remova duplicatas no painel."
  fi

  IDX=0
  while IFS= read -r RULE; do
    RESP=$(curl -s -X POST "$CF_API/zones/$ZONE_ID/rulesets/$RULESET_ID/rules" \
      "${AUTH[@]}" -d "$RULE")
    if echo "$RESP" | py_ok; then
      log "Regra criada: ${NAMES[$IDX]}"
    else
      ERR=$(echo "$RESP" | "$PY" -c "import json,sys; r=json.load(sys.stdin); print(r.get('errors',[{}])[0].get('message','?'))" 2>/dev/null || echo "?")
      warn "Falha em ${NAMES[$IDX]}: $ERR"
    fi
    IDX=$((IDX + 1))
  done < <(echo "$RULES_JSON" | "$PY" -c "
import json, sys
for r in json.load(sys.stdin)['rules']:
    print(json.dumps(r))
")

else
  RESP=$(curl -s -X PUT \
    "$CF_API/zones/$ZONE_ID/rulesets/phases/$PHASE/entrypoint" \
    "${AUTH[@]}" -d "$RULES_JSON")

  if echo "$RESP" | py_ok; then
    log "5 regras WAF criadas com sucesso"
  else
    ERR=$(echo "$RESP" | "$PY" -c "
import json,sys
r=json.load(sys.stdin)
print(' | '.join(e.get('message','') for e in r.get('errors',[])))
" 2>/dev/null || echo "?")
    warn "Erro ao criar regras: $ERR"
    warn "Crie manualmente: Security → WAF → Custom Rules"
  fi
fi

echo ""
echo "══════════════════════════════════════════════════════════════"
echo "  Configuracao concluida"
echo "══════════════════════════════════════════════════════════════"
echo ""
echo "  Verifique em: dash.cloudflare.com → liddis.com.br → Security"
echo "  Bot Fight Mode  → Security → Bots"
echo "  Security Level  → Security → Settings"
echo "  Regras WAF      → Security → WAF → Custom Rules"
echo ""
