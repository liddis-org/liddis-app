# Checklist de Deploy — LIDDIS
## Supabase + Google Cloud Run + Google OAuth

---

## PARTE 1 — Supabase (Banco de Dados PostgreSQL)

### 1.1 Criar Projeto no Supabase
1. Acesse https://supabase.com e faça login
2. Clique em **New Project**
3. Preencha:
   - **Name:** liddis-producao
   - **Database Password:** gere uma senha forte (guarde em local seguro)
   - **Region:** South America (São Paulo) → `sa-east-1`
4. Aguarde ~2 minutos para o projeto ser criado

### 1.2 Obter a Connection String
1. No projeto criado → **Project Settings** (ícone de engrenagem)
2. Vá em **Database** → **Connection string**
3. Selecione a aba **URI**
4. **IMPORTANTE:** Use o **Connection Pooler** (porta **6543**, modo Transaction)
   - Motivo: Cloud Run é serverless, muitas conexões simultâneas
   - A URI terá formato: `postgresql://postgres.[REF]:[SENHA]@aws-0-sa-east-1.pooler.supabase.com:6543/postgres`
5. Copie essa URI para `DATABASE_URL` no seu `.env`

### 1.3 Configurar SSL (já configurado)
O `settings.py` já exige SSL em produção (`ssl_require=not DEBUG`).
Supabase aceita conexões SSL por padrão. ✅

### 1.4 Aplicar Migrações no Supabase
```bash
# No terminal, com DATABASE_URL do Supabase no .env:
python manage.py migrate

# Criar superusuário admin
python manage.py createsuperuser
```

### 1.5 Configurar Site no Django Admin
```bash
python manage.py setup_site
```
Depois, no Admin (https://SEU-DOMINIO.run.app/admin) → Sites → altere o domínio.

---

## PARTE 2 — Google Cloud Run

### 2.1 Pré-requisitos
```bash
# Instalar Google Cloud CLI: https://cloud.google.com/sdk/docs/install
gcloud auth login
gcloud config set project SEU-PROJECT-ID
```

### 2.2 Habilitar APIs necessárias
```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com
```

### 2.3 Criar repositório de imagens Docker
```bash
gcloud artifacts repositories create liddis \
  --repository-format=docker \
  --location=southamerica-east1 \
  --description="Imagens Docker do LIDDIS"
```

### 2.4 Armazenar segredos no Secret Manager
```bash
# SECRET_KEY
echo -n "SUA_SECRET_KEY_FORTE" | \
  gcloud secrets create liddis-secret-key --data-file=-

# DATABASE_URL (Supabase)
echo -n "postgresql://postgres.[REF]:..." | \
  gcloud secrets create liddis-database-url --data-file=-

# Google OAuth
echo -n "SEU_CLIENT_ID.apps.googleusercontent.com" | \
  gcloud secrets create liddis-google-client-id --data-file=-

echo -n "GOCSPX-SEU_SECRET" | \
  gcloud secrets create liddis-google-secret --data-file=-

# Resend API Key (e-mail)
echo -n "re_SUA_API_KEY" | \
  gcloud secrets create liddis-resend-key --data-file=-
```

### 2.5 Dar permissão ao Cloud Build
```bash
# Obter número do projeto
PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get-value project) --format='value(projectNumber)')

# Service Account do Cloud Build
SA="$PROJECT_NUMBER@cloudbuild.gserviceaccount.com"

# Permissões necessárias
gcloud projects add-iam-policy-binding $(gcloud config get-value project) \
  --member="serviceAccount:$SA" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding $(gcloud config get-value project) \
  --member="serviceAccount:$SA" \
  --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding $(gcloud config get-value project) \
  --member="serviceAccount:$SA" \
  --role="roles/iam.serviceAccountUser"
```

### 2.6 Build e Deploy manual (primeira vez)
```bash
# Na raiz do projeto:
gcloud builds submit --config cloudbuild.yaml
```

### 2.7 Configurar CI/CD automático
1. Google Cloud Console → Cloud Build → **Triggers**
2. Clique em **Create Trigger**
3. Conecte seu repositório GitHub
4. Configurações:
   - **Event:** Push to a branch
   - **Branch:** `^main$`
   - **Configuration:** Cloud Build configuration file (`cloudbuild.yaml`)
5. Salve → agora cada push em `main` faz deploy automático

### 2.8 Verificar deploy
```bash
gcloud run services describe liddis-backend \
  --region=southamerica-east1 \
  --format="value(status.url)"
```

---

## PARTE 3 — Google OAuth

### 3.1 Configurar no Google Cloud Console
1. Acesse https://console.cloud.google.com
2. **APIs & Services** → **Credentials**
3. Clique em **Create Credentials** → **OAuth 2.0 Client IDs**
4. Application type: **Web application**
5. Name: `LIDDIS`
6. **Authorized JavaScript origins:**
   ```
   https://SEU-SERVICO.a.run.app
   http://localhost:8000   ← para desenvolvimento
   ```
7. **Authorized redirect URIs:**
   ```
   https://SEU-SERVICO.a.run.app/accounts/google/login/callback/
   http://localhost:8000/accounts/google/login/callback/   ← para desenvolvimento
   ```
8. Clique em **Create**
9. Copie o **Client ID** e **Client Secret**

### 3.2 Configurar no Django Admin
1. Acesse `/admin/` no seu domínio
2. Vá em **Social Applications** (django-allauth)
3. Clique em **Add Social Application**
4. Preencha:
   - **Provider:** Google
   - **Name:** Google OAuth
   - **Client ID:** (seu Client ID)
   - **Secret Key:** (seu Client Secret)
   - **Sites:** mova o site da esquerda para a direita
5. Salve

### 3.3 Testar OAuth
1. Acesse a página de login
2. Clique em "Entrar com Google"
3. Autorize o acesso
4. Deve redirecionar para `/dashboard/`

---

## PARTE 4 — Variáveis de Ambiente Finais

Variáveis que o Cloud Run precisa ter configuradas (via Secret Manager ou direto):

| Variável | Obrigatória | Fonte |
|---------|------------|-------|
| SECRET_KEY | ✅ | Secret Manager |
| DATABASE_URL | ✅ | Secret Manager (Supabase) |
| GOOGLE_CLIENT_ID | ✅ | Secret Manager |
| GOOGLE_SECRET | ✅ | Secret Manager |
| DEBUG | ✅ | direto: `False` |
| ALLOWED_HOSTS | ✅ | direto: URL do Cloud Run |
| EMAIL_PROVIDER | ✅ | direto: `resend` |
| RESEND_API_KEY | ✅ | Secret Manager |
| CSRF_TRUSTED_ORIGINS | ✅ | direto: URL completa com https:// |
| SITE_DOMAIN | ✅ | direto: URL do Cloud Run |
| SENTRY_DSN | Recomendado | Secret Manager |

---

## PARTE 5 — Guia de Testes Passo a Passo

### 5.1 Instalar dependências de teste
```bash
# Ative o venv primeiro
pip install -r requirements-dev.txt
```

### 5.2 Configurar ambiente de teste
```bash
# Copiar .env de desenvolvimento
copy dev-env\.env.development .env    # Windows
cp dev-env/.env.development .env      # Linux/Mac
```

### 5.3 Rodar todos os testes
```bash
pytest tests\ -v
```

### 5.4 Rodar testes por categoria
```bash
# Apenas models de usuários
pytest tests\test_models_users.py -v

# Apenas models de consultas
pytest tests\test_models_consultations.py -v

# Apenas autenticação
pytest tests\test_auth.py -v

# Apenas permissões RBAC
pytest tests\test_permissions.py -v
```

### 5.5 Rodar com cobertura de código
```bash
pytest tests\ --cov=users --cov=consultations --cov-report=html -v
# Abrir relatório:
start htmlcov\index.html    # Windows
open htmlcov/index.html     # Mac
```

### 5.6 Rodar teste específico
```bash
# Sintaxe: pytest caminho::Classe::metodo
pytest tests\test_permissions.py::TestHasPermission::test_medico_pode_criar_consulta -v
```

### 5.7 Rodar com DEBUG detalhado (falhas)
```bash
pytest tests\ -v --tb=long
```

### 5.8 Usar o script automático (Windows)
```bash
dev-env\executar_testes.bat           # todos os testes
dev-env\executar_testes.bat models    # só models
dev-env\executar_testes.bat auth      # só auth
dev-env\executar_testes.bat cobertura # com relatório HTML
```

---

## PARTE 6 — Checklist Final Antes do Deploy

```
PRÉ-DEPLOY:
[ ] requirements.txt atualizado (python-decouple incluído)
[ ] Todas as migrations aplicadas localmente sem erro
[ ] Tests passando: pytest tests\ -v
[ ] .env.production preenchido completamente (sem "SUBSTITUA")
[ ] SECRET_KEY forte (>50 chars, aleatória)
[ ] DEBUG=False no .env de produção
[ ] ALLOWED_HOSTS inclui domínio do Cloud Run

SUPABASE:
[ ] Projeto Supabase criado em sa-east-1
[ ] Connection Pooler URL copiada (porta 6543)
[ ] DATABASE_URL testada localmente
[ ] Migrações aplicadas: python manage.py migrate
[ ] Superusuário criado: python manage.py createsuperuser

GOOGLE CLOUD:
[ ] APIs habilitadas (Cloud Run, Cloud Build, Artifact Registry, Secret Manager)
[ ] Repositório Artifact Registry criado
[ ] Todos os secrets criados no Secret Manager
[ ] Cloud Build SA tem permissões corretas

GOOGLE OAUTH:
[ ] OAuth Client ID criado no Google Console
[ ] Redirect URIs configurados (produção e desenvolvimento)
[ ] Social Application criada no Django Admin
[ ] Fluxo OAuth testado manualmente

E-MAIL:
[ ] Domínio verificado no Resend/SendGrid
[ ] RESEND_API_KEY configurada
[ ] Envio de OTP testado manualmente

PÓS-DEPLOY:
[ ] Acesse /admin/ e configure o Site (domain + name)
[ ] Teste login normal
[ ] Teste login com Google
[ ] Teste registro + verificação de e-mail
[ ] Verifique Sentry recebendo eventos
[ ] Monitore logs: gcloud run logs tail liddis-backend --region=southamerica-east1
```
