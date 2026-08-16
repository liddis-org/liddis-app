#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════════════
#  LIDDIS — Configuração automática de segurança no Cloudflare
#
#  Pré-requisito ÚNICO: um API Token do Cloudflare (leva ~2 min criar).
#
#  Como obter o token:
#    1. Acesse: dash.cloudflare.com/profile/api-tokens
#    2. Clique em "Create Token"
#    3. Use o template "Edit zone DNS" como base OU crie custom com:
#         - Zone > Zone Settings > Edit
#         - Zone > Firewall Services > Edit
#         - Zone > Bot Management > Edit  (se disponível no plano)
#         - Zone > Zone > Read
#    4. Scope: inclua apenas a zona "liddis.com.br"
#    5. Copie o token gerado
#
#  Como executar:
#    export CF_TOKEN="seu_token_aqui"
#    bash infra/setup-cloudflare-security.sh
# ════════════════════════════════════════════════════════════════════════════

set -euo pipefail

DOMAIN="liddis.com.br"

# ── Validação de pré-requisitos ───────────────────────────────────────────────
if [[ -z "${CF_TOKEN:-}" ]]; then
  echo ""
  echo "  ❌ CF_TOKEN não definido."
  echo "     Execute: export CF_TOKEN=\"seu_token_aqui\""
  echo "     Depois:  bash infra/setup-cloudflare-security.sh"
  echo ""
  exit 1
fi

command -v curl  >/dev/null || { echo "❌ curl não encontrado."; exit 1; }
command -v python3 >/dev/null || { echo "❌ python3 não encontrado."; exit 1; }

CF_API="https://api.cloudflare.com/client/v4"
AUTH=(-H "Authorization: Bearer $CF_TOKEN" -H "Content-Type: application/json")

log()  { echo "  ✓ $*"; }
warn() { echo "  ⚠  $*"; }
fail() { echo "  ✗ $*"; exit 1; }

cf_ok() {
  # Verifica se a resposta da API indica sucesso
  python3 -c "
import json, sys
r = json.load(sys.stdin)
if r.get('success'):
    print('ok')
else:
    errs = r.get('errors', [])
    for e in errs:
        print('ERR:', e.get('message',''), file=sys.stderr)
    sys.exit(1)
"
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
ZONE_ID=$(echo "$ZONE_RESP" | python3 -c "
import json, sys
r = json.load(sys.stdin)
results = r.get('result', [])
if not results:
    print('', end='')
else:
    print(results[0]['id'], end='')
")

if [[ -z "$ZONE_ID" ]]; then
  fail "Zona '$DOMAIN' não encontrada. Verifique se o domínio está no Cloudflare e se o token tem permissão de leitura."
fi

log "Zone ID: $ZONE_ID"

# ── 2. Security Level → Medium ────────────────────────────────────────────────
echo ""
echo "[ 2/4 ] Configurando Security Level → Medium..."

RESP=$(curl -s -X PATCH "$CF_API/zones/$ZONE_ID/settings/security_level" \
  "${AUTH[@]}" \
  -d '{"value":"medium"}')

if echo "$RESP" | python3 -c "import json,sys; r=json.load(sys.stdin); sys.exit(0 if r.get('success') else 1)" 2>/dev/null; then
  log "Security Level definido como 'medium'"
else
  warn "Não foi possível definir Security Level via API. Configure manualmente: Security → Settings → Security Level → Medium"
fi

# ── 3. Bot Fight Mode → ON ────────────────────────────────────────────────────
echo ""
echo "[ 3/4 ] Ativando Bot Fight Mode..."

RESP=$(curl -s -X PUT "$CF_API/zones/$ZONE_ID/bot_management" \
  "${AUTH[@]}" \
  -d '{"fight_mode":true}')

if echo "$RESP" | python3 -c "import json,sys; r=json.load(sys.stdin); sys.exit(0 if r.get('success') else 1)" 2>/dev/null; then
  log "Bot Fight Mode ativado"
else
  # Fallback: tenta via zone settings
  RESP2=$(curl -s -X PATCH "$CF_API/zones/$ZONE_ID/settings/bot_fight_mode" \
    "${AUTH[@]}" \
    -d '{"value":"on"}')
  if echo "$RESP2" | python3 -c "import json,sys; r=json.load(sys.stdin); sys.exit(0 if r.get('success') else 1)" 2>/dev/null; then
    log "Bot Fight Mode ativado (via settings)"
  else
    warn "Bot Fight Mode requer ativação manual: Security → Bots → Bot Fight Mode → ON"
  fi
fi

# ── 4. Regras WAF Custom ──────────────────────────────────────────────────────
echo ""
echo "[ 4/4 ] Criando 5 regras WAF..."

# Monta o payload com as 5 regras
RULES_JSON=$(python3 -c "
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
        'expression': r'(http.request.uri.path matches \"\\\\.(php|asp|aspx|env|git|bak|config|sql)$\")',
        'description': 'LIDDIS: Bloquear extensões perigosas',
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
        'description': 'LIDDIS: Bloquear injeção na URL',
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

# Verifica se já existe um ruleset de Custom Rules para esta zona
PHASE="http_request_firewall_custom"
EXISTING=$(curl -s -X GET "$CF_API/zones/$ZONE_ID/rulesets" "${AUTH[@]}")

RULESET_ID=$(echo "$EXISTING" | python3 -c "
import json, sys
r = json.load(sys.stdin)
for rs in r.get('result', []):
    if rs.get('phase') == 'http_request_firewall_custom':
        print(rs['id'])
        break
" 2>/dev/null || true)

if [[ -n "$RULESET_ID" ]]; then
  # Ruleset existe: verifica quantas regras já existem
  EXISTING_RULES=$(curl -s -X GET "$CF_API/zones/$ZONE_ID/rulesets/$RULESET_ID" "${AUTH[@]}" | \
    python3 -c "import json,sys; r=json.load(sys.stdin); print(len(r.get('result',{}).get('rules',[])))" 2>/dev/null || echo "0")

  if [[ "$EXISTING_RULES" -gt 0 ]]; then
    warn "Já existem $EXISTING_RULES regra(s) nesta zona. As 5 regras do LIDDIS serão ADICIONADAS às existentes."
    warn "Se isso ultrapassar 5 regras (limite Free), remova duplicatas no painel."
  fi

  # Adiciona as regras uma a uma (não sobrescreve as existentes)
  RULE_NUM=0
  NAMES=("Ferramentas de ataque" "Extensões perigosas" "Painel admin" "Injeção na URL" "IPs suspeitos no login")
  echo "$RULES_JSON" | python3 -c "
import json, sys
rules = json.load(sys.stdin)['rules']
for i, r in enumerate(rules):
    print(json.dumps(r))
" | while IFS= read -r RULE; do
    RULE_NUM=$((RULE_NUM + 1))
    RESP=$(curl -s -X POST "$CF_API/zones/$ZONE_ID/rulesets/$RULESET_ID/rules" \
      "${AUTH[@]}" \
      -d "$RULE")
    if echo "$RESP" | python3 -c "import json,sys; r=json.load(sys.stdin); sys.exit(0 if r.get('success') else 1)" 2>/dev/null; then
      log "Regra criada: ${NAMES[$((RULE_NUM-1))]}"
    else
      ERR=$(echo "$RESP" | python3 -c "import json,sys; r=json.load(sys.stdin); print(r.get('errors',[{}])[0].get('message','desconhecido'))" 2>/dev/null || echo "erro desconhecido")
      warn "Falha na regra ${NAMES[$((RULE_NUM-1))]}: $ERR"
    fi
  done

else
  # Ruleset não existe: cria via PUT do entrypoint
  RESP=$(curl -s -X PUT \
    "$CF_API/zones/$ZONE_ID/rulesets/phases/$PHASE/entrypoint" \
    "${AUTH[@]}" \
    -d "$RULES_JSON")

  if echo "$RESP" | python3 -c "import json,sys; r=json.load(sys.stdin); sys.exit(0 if r.get('success') else 1)" 2>/dev/null; then
    log "5 regras WAF criadas com sucesso"
  else
    ERR=$(echo "$RESP" | python3 -c "
import json,sys
r=json.load(sys.stdin)
for e in r.get('errors',[]):
    print(e.get('message',''))
" 2>/dev/null || echo "erro desconhecido")
    warn "Erro ao criar regras via Rulesets API: $ERR"
    warn "Tente criar as regras manualmente no painel: Security → WAF → Custom Rules"
  fi
fi

# ── Resultado final ───────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════════════"
echo "  Configuração concluída"
echo "══════════════════════════════════════════════════════════════"
echo ""
echo "  Verifique o resultado em:"
echo "  dash.cloudflare.com → liddis.com.br → Security"
echo ""
echo "  Bot Fight Mode  → Security → Bots"
echo "  Security Level  → Security → Settings"
echo "  Regras WAF      → Security → WAF → Custom Rules"
echo ""
