# LIDDIS — Guia Completo de Deploy e Manutenção

---

## VISÃO GERAL DO PROJETO

LIDDIS é uma plataforma clínica com IA (LUMI) para gestão de consultas médicas.

**Stack de produção:**

```
Usuário
   │  https://liddis.com.br
   ▼
Hostinger DNS
   │  Nameservers: alan.ns.cloudflare.com / paityn.ns.cloudflare.com
   ▼
Cloudflare (proxy + SSL gratuito)
   │  DNS: CNAME @ → liddis-backend-tyi23kxkeq-rj.a.run.app  (proxy ativo)
   │  SSL: Full/Completo
   │
   ├─ Cloudflare Worker: square-shadow-58ea
   │    Routes: liddis.com.br/*  e  *.liddis.com.br/*
   │    Função: proxy reverso — repassa requisições ao Cloud Run
   ▼
Google Cloud Run — southamerica-east1
   Serviço : liddis-backend
   URL     : https://liddis-backend-tyi23kxkeq-rj.a.run.app
   Imagem  : southamerica-east1-docker.pkg.dev/liddis/liddis/liddis-backend
   │
   ├─ Secrets    → Google Secret Manager
   ├─ Banco      → Supabase PostgreSQL (sa-east-1)
   └─ Arquivos   → Google Cloud Storage (bucket: liddis-media)
```

**Por que Cloudflare Worker?**
A região `southamerica-east1` não suporta domain mappings nativos no Cloud Run.
O Worker intercepta os requests, repassa ao Cloud Run e o Django corrige o Host
internamente via `FixCloudRunHostMiddleware`.

---

## ESTRUTURA DO PROJETO

```
liddis-app/
├── config/
│   ├── settings.py          # Configurações Django (debug, db, storage, oauth…)
│   ├── urls.py              # Rotas raiz
│   ├── wsgi.py
│   └── middleware.py        # FixCloudRunHostMiddleware + RemoveWWWMiddleware
├── users/                   # App de autenticação e perfis
│   ├── models.py            # CustomUser, PatientProfessionalAccess, PlatformFeedback…
│   ├── views.py
│   ├── adapters.py          # CustomAccountAdapter, CustomSocialAccountAdapter (Google OAuth)
│   ├── backends.py          # EmailOrUsernameBackend, TestModeBackend
│   └── middleware.py        # EmailVerificationMiddleware, RBACPatientAccessMiddleware
├── consultations/           # App de consultas clínicas
│   ├── models.py            # Consultation, ConsultationImage, DiagnosisCID, Evolution…
│   └── views.py             # upload_image, attachment_proxy, consultas CRUD
├── lumi/                    # IA clínica (LUMI)
│   └── services.py          # ClinicalContextBuilder, LumiService (OpenAI gpt-4o-mini)
├── templates/               # HTML (login, dashboard, consultas, etc.)
├── static/                  # CSS/JS estáticos
├── tests/                   # Testes pytest
├── docs/
│   └── DEPLOY_CHECKLIST.md  # Este arquivo
├── .github/
│   └── workflows/
│       └── deploy.yml       # CI/CD: push → build Docker → deploy Cloud Run
├── Dockerfile               # Multi-stage build (python:3.11-slim)
├── requirements.txt         # Dependências de produção
└── requirements-dev.txt     # Dependências de desenvolvimento
```

**Principais dependências:**

| Pacote | Finalidade |
|--------|-----------|
| Django 5.2 | Framework principal |
| django-allauth | Login normal + Google OAuth |
| django-axes | Rate limiting / bloqueio por tentativas de login |
| django-storages[gcs] | Upload de arquivos no Google Cloud Storage |
| whitenoise | Arquivos estáticos sem nginx adicional |
| dj-database-url | Lê DATABASE_URL do Supabase |
| openai | LUMI — IA clínica (gpt-4o-mini + Vision) |
| pypdf | Extração de texto de PDFs para a LUMI |
| sentry-sdk | Monitoramento de erros em produção |
| gunicorn | Servidor WSGI de produção |

---

## COMO FAZER DEPLOY DE NOVAS ATUALIZAÇÕES

### Deploy normal (fluxo padrão)

Qualquer push para `main` dispara o deploy automaticamente:

```bash
git add .
git commit -m "feat: descrição da mudança"
git push origin main
```

O GitHub Actions (`.github/workflows/deploy.yml`) executa:
1. Build da imagem Docker (multi-stage, ~2-3 min)
2. Push para Artifact Registry
3. Deploy no Cloud Run com todas as variáveis
4. O Cloud Run executa `python manage.py migrate --noinput` automaticamente na inicialização

Acompanhe em: **GitHub → Actions → Deploy to Cloud Run**

> **Atenção:** O deploy leva 3-5 minutos. Requisições durante esse período são
> servidas pela versão anterior até o novo container estar pronto (zero-downtime).

---

### Alterar variáveis de ambiente

Edite `.github/workflows/deploy.yml` na linha `--set-env-vars=`:

```yaml
--set-env-vars=DEBUG=False,ALLOWED_HOSTS=liddis.com.br,...
```

Faça commit e push — o deploy aplica as novas variáveis.

**Variáveis atuais em produção:**

| Variável | Valor |
|----------|-------|
| `DEBUG` | `False` |
| `ALLOWED_HOSTS` | `liddis.com.br,www.liddis.com.br,liddis-backend-tyi23kxkeq-rj.a.run.app` |
| `EMAIL_PROVIDER` | `gmail` |
| `GMAIL_USER` | `liddis.org@gmail.com` |
| `DEFAULT_FROM_EMAIL` | `liddis.org@gmail.com` |
| `SITE_NAME` | `LIDDIS` |
| `CSRF_TRUSTED_ORIGINS` | `https://liddis.com.br,https://www.liddis.com.br,...` |
| `SITE_DOMAIN` | `liddis.com.br` |
| `GCS_BUCKET_NAME` | `liddis-media` |

---

### Alterar secrets (DATABASE_URL, SECRET_KEY, etc.)

Os secrets ficam no **Google Secret Manager**. Para atualizar:

```bash
# Atualizar um secret existente (exemplo: DATABASE_URL)
echo -n "postgresql://nova-url..." | \
  gcloud secrets versions add liddis-database-url --data-file=-
```

O Cloud Run usa `:latest` — a nova versão é usada no próximo deploy.

**Secrets configurados:**

| Secret no GCP | Variável injetada |
|---------------|------------------|
| `liddis-secret-key` | `SECRET_KEY` |
| `liddis-database-url` | `DATABASE_URL` |
| `liddis-google-client-id` | `GOOGLE_CLIENT_ID` |
| `liddis-google-secret` | `GOOGLE_SECRET` |
| `liddis-gmail-app-password` | `GMAIL_APP_PASSWORD` |
| `liddis-openai-api-key` | `OPENAI_API_KEY` |

---

### Criar uma nova migration (alteração de models)

```bash
# 1. Edite o model em users/models.py ou consultations/models.py

# 2. Gere a migration localmente
python manage.py makemigrations

# 3. Verifique o arquivo gerado em users/migrations/ ou consultations/migrations/

# 4. Commit INCLUINDO o arquivo de migration
git add .
git commit -m "feat: adicionar campo X ao model Y"
git push origin main
```

> O Dockerfile executa `migrate --noinput` na inicialização do container.
> Nunca suba código sem a migration correspondente — o deploy vai falhar.

---

### Adicionar uma nova dependência Python

```bash
# 1. Instale e teste localmente
pip install nome-do-pacote

# 2. Adicione ao requirements.txt (com versão mínima)
echo "nome-do-pacote>=1.0" >> requirements.txt

# 3. Commit e push
git add requirements.txt
git commit -m "chore: adicionar nome-do-pacote"
git push origin main
```

---

## CLOUDFLARE — CONFIGURAÇÃO COMPLETA

### DNS (configurado na Hostinger para usar nameservers do Cloudflare)

| Tipo | Nome | Valor | Proxy |
|------|------|-------|-------|
| CNAME | @ | liddis-backend-tyi23kxkeq-rj.a.run.app | ✅ Ativo |
| CNAME | www | liddis-backend-tyi23kxkeq-rj.a.run.app | ✅ Ativo |

> O proxy (nuvem laranja) **deve estar ativo**. Com proxy desativado o Worker não intercepta.

### SSL/TLS

Modo: **Full / Completo** — não usar "Flexível" (causaria loop de redirect).

### Cloudflare Worker — `square-shadow-58ea`

**Acesse:** Cloudflare Dashboard → Workers & Pages → square-shadow-58ea → Edit code

**Código atual do Worker:**

```javascript
export default {
  async fetch(request) {
    const url = new URL(request.url);
    const targetUrl = new URL(
      url.pathname + url.search,
      'https://liddis-backend-tyi23kxkeq-rj.a.run.app'
    );

    const headers = new Headers(request.headers);
    headers.delete('host');

    return fetch(targetUrl.toString(), {
      method: request.method,
      headers: headers,
      body: ['GET', 'HEAD'].includes(request.method) ? null : request.body,
      redirect: 'manual',
    });
  }
};
```

> O Worker apenas repassa as requisições ao Cloud Run.
> A correção do Host para OAuth é feita pelo Django via `FixCloudRunHostMiddleware`.

### Routes do Worker

| Route | Cobre |
|-------|-------|
| `liddis.com.br/*` | Domínio raiz |
| `*.liddis.com.br/*` | www e subdomínios |

---

## GOOGLE CLOUD — INFRAESTRUTURA

### Cloud Run

```bash
# Ver status e URL do serviço
gcloud run services describe liddis-backend \
  --region=southamerica-east1 \
  --format="value(status.url)"

# Logs em tempo real
gcloud run logs tail liddis-backend --region=southamerica-east1

# Forçar novo deploy (sem alterar código)
gcloud run deploy liddis-backend \
  --region=southamerica-east1 \
  --image=southamerica-east1-docker.pkg.dev/liddis/liddis/liddis-backend:latest
```

### Google Cloud Storage (uploads/anexos)

Bucket: `liddis-media`
Service Account: `728883718504-compute@developer.gserviceaccount.com`
Permissão: `roles/storage.objectAdmin`

```bash
# Verificar se arquivos estão sendo salvos corretamente
gcloud storage objects list gs://liddis-media --limit=10

# Listar por pasta
gcloud storage objects list gs://liddis-media/consultations/

# Copiar arquivo do bucket para local (diagnóstico)
gcloud storage cp gs://liddis-media/consultations/foto.jpg ./
```

> **Importante:** `DEFAULT_FILE_STORAGE` foi removido no Django 5.1.
> O projeto usa `STORAGES['default']` (Django 4.2+) com `GoogleCloudStorage`.
> Arquivos em DEV vão para o filesystem local (`media/`).

---

## GOOGLE OAUTH — CONFIGURAÇÃO

### Google Cloud Console

**APIs & Services → Credentials → OAuth 2.0 Client IDs**

**Authorized JavaScript origins:**
```
https://liddis.com.br
https://www.liddis.com.br
http://localhost:8000
```

**Authorized redirect URIs:**
```
https://liddis.com.br/accounts/google/login/callback/
https://www.liddis.com.br/accounts/google/login/callback/
https://liddis-backend-tyi23kxkeq-rj.a.run.app/accounts/google/login/callback/
http://localhost:8000/accounts/google/login/callback/
```

### Por que o OAuth funciona com o Worker

O Cloudflare Worker mantém `Host: *.run.app` para o Cloud Run aceitar a requisição.
O middleware `FixCloudRunHostMiddleware` (primeiro na chain de middlewares) corrige
o host para `liddis.com.br` antes que qualquer código o leia. Assim o allauth constrói
`redirect_uri=https://liddis.com.br/accounts/google/login/callback/` e o callback
OAuth retorna pelo Cloudflare com o cookie de sessão correto.

---

## DESENVOLVIMENTO LOCAL

### Setup inicial

```bash
# Clone e crie o ambiente
git clone https://github.com/liddis-org/liddis-app.git
cd liddis-app
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

pip install -r requirements-dev.txt

# Copie e configure o .env
copy .env.example .env
# Edite .env com suas variáveis locais
```

### Variáveis mínimas no `.env` local

```env
SECRET_KEY=qualquer-chave-forte-para-desenvolvimento
DEBUG=True
USE_SQLITE=True              # usa SQLite local (sem precisar do Supabase)
TEST_MODE=True               # aceita qualquer senha no login (só em DEBUG)
OPENAI_API_KEY=sk-...        # necessário para testar a LUMI
```

### Rodar o servidor

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Acesse: http://localhost:8000

### Rodar testes

```bash
# Todos os testes
pytest tests\ -v

# Com cobertura
pytest tests\ --cov=users --cov=consultations --cov-report=html -v
start htmlcov\index.html     # Windows — abre relatório no browser

# Scripts automatizados (Windows)
dev-env\executar_testes.bat
dev-env\executar_testes.bat cobertura
```

---

## CHECKLIST PRÉ-DEPLOY

```
CÓDIGO:
[ ] requirements.txt atualizado com novas dependências
[ ] Migrations geradas para alterações de models
[ ] Testes passando: pytest tests\ -v
[ ] DEBUG=False no deploy.yml (nunca subir True para produção)

CLOUDFLARE:
[ ] Nameservers Cloudflare ativos na Hostinger
[ ] DNS CNAME @ e www com proxy ativo (nuvem laranja)
[ ] SSL: Full/Completo
[ ] Worker square-shadow-58ea deployado e routes configuradas

GOOGLE CLOUD:
[ ] Secrets no Secret Manager atualizados
[ ] ALLOWED_HOSTS e CSRF_TRUSTED_ORIGINS incluem liddis.com.br
[ ] Bucket liddis-media existe com permissão storage.objectAdmin

GOOGLE OAUTH:
[ ] Redirect URIs incluem https://liddis.com.br/accounts/google/login/callback/
[ ] GOOGLE_CLIENT_ID e GOOGLE_SECRET nos secrets do GCP

PÓS-DEPLOY:
[ ] https://liddis.com.br abre corretamente
[ ] Login por e-mail funcionando
[ ] Login com Google funcionando
[ ] Upload de anexo em consulta → verificar em gcloud storage objects list gs://liddis-media
[ ] Admin acessível: https://liddis.com.br/admin/
[ ] LUMI gerando relatório sem erros
[ ] Monitorar logs: gcloud run logs tail liddis-backend --region=southamerica-east1
```

---

## DIAGNÓSTICO DE PROBLEMAS

### Site retorna 500 ou não sobe

```bash
# Ver erros de inicialização do Django
gcloud run logs tail liddis-backend --region=southamerica-east1

# Causas comuns:
# - Migration faltando (commitar o arquivo de migration gerado)
# - Middleware referenciado no settings.py mas arquivo não commitado
# - Secret no GCP com valor incorreto ou não criado
# - Dependência no requirements.txt mas não instalada na imagem
```

### Login com Google não funciona

Verificar na ordem:
1. `GOOGLE_CLIENT_ID` e `GOOGLE_SECRET` corretos no Secret Manager
2. Redirect URIs cadastrados no Google Console (incluir a URL do Cloud Run)
3. `FixCloudRunHostMiddleware` é o **primeiro** middleware em `settings.py`
4. `ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'https'` em produção

### Uploads/anexos somem

```bash
# Verificar se estão chegando ao bucket
gcloud storage objects list gs://liddis-media --limit=10

# Se vazio: verificar STORAGES['default'] em settings.py
# (DEFAULT_FILE_STORAGE foi removido no Django 5.1 — usar STORAGES dict)

# Verificar permissão da service account
gcloud projects get-iam-policy liddis \
  --flatten="bindings[].members" \
  --filter="bindings.members:728883718504-compute@developer.gserviceaccount.com"
```

### Erros de CSRF

Verificar se `CSRF_TRUSTED_ORIGINS` no `deploy.yml` inclui `https://liddis.com.br`.

### Sessão expira rápido ou perde login

`SESSION_COOKIE_AGE = 60 * 60 * 8` (8 horas) está em `settings.py`.
Para aumentar, altere o valor e faça push.

---

## ADICIONANDO NOVOS SECRETS

```bash
# Criar novo secret
echo -n "VALOR-DO-SECRET" | gcloud secrets create liddis-novo-secret --data-file=-

# Conceder acesso ao Cloud Run
gcloud secrets add-iam-policy-binding liddis-novo-secret \
  --member="serviceAccount:728883718504-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Adicionar ao deploy.yml na linha --set-secrets=
# liddis-novo-secret=liddis-novo-secret:latest

# E no settings.py
# NOVA_VARIAVEL = config('NOVA_VARIAVEL', default='')
```

---

## GITHUB ACTIONS — CI/CD

Arquivo: `.github/workflows/deploy.yml`

**Secrets necessários no repositório GitHub:**

| Secret GitHub | Descrição |
|---------------|-----------|
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | Provider do Workload Identity Federation |
| `GCP_SERVICE_ACCOUNT` | Email da service account do GCP |

Configure em: GitHub → Repositório → Settings → Secrets and variables → Actions

**Fluxo completo a cada `git push origin main`:**

```
git push origin main
       │
       ▼
GitHub Actions
       ├── Checkout do código
       ├── Autenticação GCP (Workload Identity Federation — sem senha)
       ├── docker build (multi-stage, ~2 min)
       ├── docker push → Artifact Registry
       └── gcloud run deploy liddis-backend
                  │
                  └── Container inicia:
                       ├── python manage.py migrate --noinput
                       └── gunicorn config.wsgi:application
```
