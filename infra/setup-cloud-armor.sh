#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════════════════
#  LIDDIS — Cloud Armor + HTTPS Load Balancer
#
#  Execute no Google Cloud Shell (não localmente):
#    chmod +x setup-cloud-armor.sh && ./setup-cloud-armor.sh
#
#  Pré-requisitos:
#    gcloud auth login
#    gcloud config set project liddis
#
#  IMPORTANTE: Execute em dois estágios:
#    Estágio 1 (agora)   → Cria LB + Cloud Armor
#    Estágio 2 (após DNS) → Restringe ingress do Cloud Run ao LB
# ════════════════════════════════════════════════════════════════════════════════

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-liddis}"
REGION="southamerica-east1"
SERVICE="liddis-backend"
DOMAIN="liddis.com.br"
POLICY_NAME="liddis-waf-policy"

echo_step() { echo ""; echo "══════════════════════════════════════════"; echo "  $1"; echo "══════════════════════════════════════════"; }
maybe_create() { "$@" 2>/dev/null && echo "✓ Criado" || echo "→ Já existe, pulando"; }

# ── 1. Serverless NEG ─────────────────────────────────────────────────────────
echo_step "1/9 — Serverless Network Endpoint Group"
maybe_create gcloud compute network-endpoint-groups create liddis-neg \
  --region="$REGION" \
  --network-endpoint-type=serverless \
  --cloud-run-service="$SERVICE" \
  --project="$PROJECT_ID"

# ── 2. Backend Service ────────────────────────────────────────────────────────
echo_step "2/9 — Backend Service"
maybe_create gcloud compute backend-services create liddis-backend-service \
  --global \
  --load-balancing-scheme=EXTERNAL_MANAGED \
  --project="$PROJECT_ID"

# Adiciona NEG ao Backend Service (idempotente)
gcloud compute backend-services add-backend liddis-backend-service \
  --global \
  --network-endpoint-group=liddis-neg \
  --network-endpoint-group-region="$REGION" \
  --project="$PROJECT_ID" 2>/dev/null || true

# ── 3. URL Map (roteamento) ───────────────────────────────────────────────────
echo_step "3/9 — URL Map HTTPS"
maybe_create gcloud compute url-maps create liddis-url-map \
  --default-service=liddis-backend-service \
  --project="$PROJECT_ID"

# ── 4. Certificado SSL gerenciado pelo Google ─────────────────────────────────
echo_step "4/9 — Certificado SSL (Google Managed)"
echo "⚠  O provisionamento do certificado pode levar até 60 minutos."
echo "   O DNS precisa apontar para o IP do LB para o cert ser emitido."
maybe_create gcloud compute ssl-certificates create liddis-ssl-cert \
  --domains="${DOMAIN},www.${DOMAIN}" \
  --global \
  --project="$PROJECT_ID"

# ── 5. Target HTTPS Proxy ─────────────────────────────────────────────────────
echo_step "5/9 — Target HTTPS Proxy"
maybe_create gcloud compute target-https-proxies create liddis-https-proxy \
  --url-map=liddis-url-map \
  --ssl-certificates=liddis-ssl-cert \
  --global \
  --project="$PROJECT_ID"

# ── 6. Forwarding Rule HTTPS (443) ───────────────────────────────────────────
echo_step "6/9 — Forwarding Rule HTTPS :443"
maybe_create gcloud compute forwarding-rules create liddis-https-rule \
  --global \
  --target-https-proxy=liddis-https-proxy \
  --ports=443 \
  --project="$PROJECT_ID"

# ── 7. Redirect HTTP → HTTPS ─────────────────────────────────────────────────
echo_step "7/9 — Redirect HTTP :80 → HTTPS"
maybe_create gcloud compute url-maps create liddis-http-redirect \
  --default-redirect-response-code=301 \
  --global \
  --project="$PROJECT_ID"

# Configura o redirect via import YAML
gcloud compute url-maps import liddis-http-redirect \
  --global \
  --project="$PROJECT_ID" \
  --source=- <<'YAML' 2>/dev/null || true
name: liddis-http-redirect
defaultUrlRedirect:
  httpsRedirect: true
  redirectResponseCode: MOVED_PERMANENTLY_DEFAULT
YAML

maybe_create gcloud compute target-http-proxies create liddis-http-proxy \
  --url-map=liddis-http-redirect \
  --project="$PROJECT_ID"

maybe_create gcloud compute forwarding-rules create liddis-http-rule \
  --global \
  --target-http-proxy=liddis-http-proxy \
  --ports=80 \
  --project="$PROJECT_ID"

# ── 8. Cloud Armor Security Policy ───────────────────────────────────────────
echo_step "8/9 — Cloud Armor WAF Policy"

maybe_create gcloud compute security-policies create "$POLICY_NAME" \
  --description="LIDDIS WAF — OWASP Top 10 + Rate Limiting" \
  --global \
  --project="$PROJECT_ID"

# Função auxiliar para criar regras (idempotente)
add_rule() {
  local PRIORITY=$1; shift
  gcloud compute security-policies rules create "$PRIORITY" \
    --security-policy="$POLICY_NAME" \
    --global \
    --project="$PROJECT_ID" \
    "$@" 2>/dev/null && echo "  ✓ Regra $PRIORITY criada" || echo "  → Regra $PRIORITY já existe"
}

echo "  Configurando regras WAF (OWASP preconfigured)..."

# SQLi — sensitivity 1 minimiza falsos positivos
add_rule 1000 \
  --expression="evaluatePreconfiguredWaf('sqli-v33-stable', {'sensitivity': 1})" \
  --action=deny-403 \
  --description="Block SQL Injection"

# XSS
add_rule 1001 \
  --expression="evaluatePreconfiguredWaf('xss-v33-stable', {'sensitivity': 1})" \
  --action=deny-403 \
  --description="Block XSS"

# Local File Inclusion
add_rule 1002 \
  --expression="evaluatePreconfiguredWaf('lfi-v33-stable', {'sensitivity': 1})" \
  --action=deny-403 \
  --description="Block LFI"

# Remote Code Execution
add_rule 1003 \
  --expression="evaluatePreconfiguredWaf('rce-v33-stable', {'sensitivity': 1})" \
  --action=deny-403 \
  --description="Block RCE"

# Scanner e crawlers maliciosos
add_rule 1004 \
  --expression="evaluatePreconfiguredWaf('scannerdetection-v33-stable', {'sensitivity': 1})" \
  --action=deny-403 \
  --description="Block malicious scanners"

# Ataques de protocolo HTTP
add_rule 1005 \
  --expression="evaluatePreconfiguredWaf('protocolattack-v33-stable', {'sensitivity': 1})" \
  --action=deny-403 \
  --description="Block HTTP protocol attacks"

# Rate limiting por IP — 300 req/min; acima disso retorna 429
# Conservador para não bloquear redes compartilhadas (hospitais, clínicas)
add_rule 2000 \
  --expression="true" \
  --action=throttle \
  --rate-limit-threshold-count=300 \
  --rate-limit-threshold-interval-sec=60 \
  --conform-action=allow \
  --exceed-action=deny-429 \
  --enforce-on-key=IP \
  --description="Rate limit 300 req/min per IP"

echo "  Vinculando política ao backend service..."
gcloud compute backend-services update liddis-backend-service \
  --global \
  --security-policy="$POLICY_NAME" \
  --project="$PROJECT_ID"
echo "  ✓ Cloud Armor ativo"

# ── 9. Exibir IP do Load Balancer ─────────────────────────────────────────────
echo_step "9/9 — IP do Load Balancer"
LB_IP=$(gcloud compute forwarding-rules describe liddis-https-rule \
  --global \
  --format="value(IPAddress)" \
  --project="$PROJECT_ID" 2>/dev/null || echo "PENDENTE")

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  LIDDIS — Cloud Armor configurado                        ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  Load Balancer IP: $LB_IP"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  PRÓXIMOS PASSOS (manual):                               ║"
echo "║                                                           ║"
echo "║  1. Atualize os registros DNS do liddis.com.br:          ║"
echo "║     A    @         → $LB_IP"
echo "║     A    www       → $LB_IP"
echo "║                                                           ║"
echo "║  2. Aguarde o certificado SSL ser provisionado (~60 min). ║"
echo "║     Verifique com:                                        ║"
echo "║     gcloud compute ssl-certificates describe liddis-ssl-cert --global"
echo "║                                                           ║"
echo "║  3. Após confirmar que o HTTPS funciona via LB, restrinja ║"
echo "║     o ingress do Cloud Run (executa abaixo):              ║"
echo "║     gcloud run services update liddis-backend \\          ║"
echo "║       --region=southamerica-east1 \\                      ║"
echo "║       --ingress=internal-and-cloud-load-balancing         ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "⚠  NÃO execute o passo 3 antes de confirmar HTTPS via LB."
echo "   Isso bloquearia o acesso direto ao Cloud Run URL."
