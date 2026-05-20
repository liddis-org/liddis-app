# Guia de Testes — LIDDIS
## Como testar o sistema do zero

---

## O que são os testes?

Os testes verificam automaticamente se o sistema funciona corretamente.
Em vez de você abrir o navegador e testar manualmente cada funcionalidade,
o pytest faz isso em segundos e avisa se algo quebrou.

---

## PASSO 1 — Preparar o ambiente

### 1a. Ativar o ambiente virtual
```bash
# Windows
venv\Scripts\activate

# Verificar se ativou (deve aparecer "(venv)" no início do terminal)
```

### 1b. Instalar dependências de teste (se ainda não fez)
```bash
pip install -r requirements-dev.txt
```

### 1c. Configurar o .env de desenvolvimento
```bash
# Windows — executa o script que configura tudo automaticamente:
dev-env\iniciar_dev.bat

# OU manualmente:
copy dev-env\.env.development .env
python manage.py migrate
```

---

## PASSO 2 — Rodar os testes pela primeira vez

```bash
pytest tests\ -v
```

Você verá algo assim:
```
tests/test_models_users.py::TestCustomUser::test_criar_paciente PASSED
tests/test_models_users.py::TestCustomUser::test_display_name_retorna_nome_completo PASSED
tests/test_auth.py::TestLogin::test_login_por_email PASSED
...
==================== 42 passed in 3.21s ====================
```

---

## PASSO 3 — O que cada arquivo de teste verifica

### `test_models_users.py`
Verifica se os dados são salvos e recuperados corretamente.
- Criar usuário, paciente, médico
- Verificar soft delete
- Códigos OTP (expiração, invalidação)
- Vínculo paciente-profissional (criar, revogar)
- Logs de auditoria

### `test_models_consultations.py`
Verifica o núcleo clínico do sistema.
- Criar consulta, sinais vitais, evoluções
- Sessões de atendimento (token, expiração)
- Prescrições, diagnósticos CID, exames laboratoriais

### `test_auth.py`
Verifica o fluxo de autenticação.
- Registro de novo usuário
- Login por e-mail e por username
- Proteção de rotas (redireciona se não logado)
- Verificação de código OTP

### `test_permissions.py`
Verifica o controle de acesso (RBAC).
- Médico pode criar consulta, paciente não pode
- Admin tem acesso total
- Verificação de vínculo para acesso a dados
- Filtro de evoluções por papel

---

## PASSO 4 — Comandos úteis

```bash
# Rodar testes de um arquivo específico
pytest tests\test_permissions.py -v

# Rodar um teste específico
pytest tests\test_auth.py::TestLogin::test_login_por_email -v

# Rodar testes com mais detalhes (útil quando falha)
pytest tests\ -v --tb=long

# Rodar com cobertura de código
pytest tests\ --cov=users --cov=consultations --cov-report=html -v
start htmlcov\index.html   # abre o relatório no navegador

# Rodar repetindo automaticamente a cada mudança de arquivo
# (instale primeiro: pip install pytest-watch)
ptw tests\
```

---

## PASSO 5 — Interpretando os resultados

```
PASSED  ✅  O teste funcionou corretamente
FAILED  ❌  Algo está errado — leia a mensagem de erro
ERROR   🔴  Erro no próprio código do teste (não do sistema)
SKIPPED ⏭️  Teste pulado (não afeta o resultado)
```

### Exemplo de falha e como ler:
```
FAILED tests/test_models_users.py::TestCustomUser::test_email_unico

E       django.db.IntegrityError: UNIQUE constraint failed: users.email

>       assert response.status_code == 302
E       AssertionError: assert 200 == 302
```

Isso significa: o código esperava um redirecionamento (302) mas recebeu a
página de volta (200), indicando que algo na validação não está funcionando.

---

## PASSO 6 — Testar manualmente (complementar)

Além dos testes automáticos, teste manualmente os fluxos principais:

### Fluxo de Paciente:
1. Acesse http://localhost:8000/register
2. Crie uma conta como **Paciente**
3. Verifique o código OTP (aparece no terminal com EMAIL_PROVIDER=console)
4. Acesse o dashboard — deve mostrar "Bem-vindo, [nome]"
5. Vá em **Sinais Vitais** e adicione uma medição
6. Vá em **Atendimento** → **Iniciar atendimento** → gere um token

### Fluxo de Médico:
1. Abra outra aba/janela anônima
2. Acesse http://localhost:8000/login e faça login como médico
3. Vá em **Entrar em atendimento** e insira o token gerado pelo paciente
4. Preencha a consulta e salve
5. Verifique no dashboard do médico que a consulta aparece

### Fluxo de Admin:
1. Acesse http://localhost:8000/admin
2. Login: admin@liddis.dev / admin123 (criado pelo script iniciar_dev.bat)
3. Verifique os modelos: Users, Consultations, Organizations, AuditLogs

---

## PASSO 7 — Rodar testes antes de um deploy

Sempre rode antes de fazer deploy em produção:
```bash
pytest tests\ -v --tb=short
```

Se algum teste falhar, corrija antes de fazer deploy.

---

## Troubleshooting

**Erro: "no module named users"**
→ Certifique que está na raiz do projeto e com o venv ativado.

**Erro: "database is locked"**
→ SQLite lock — feche outros terminais que têm o servidor rodando.

**Erro: "DJANGO_SETTINGS_MODULE not defined"**
→ O arquivo `pytest.ini` define isso. Certifique que ele existe na raiz.

**Testes passam mas o site não funciona**
→ Rode `python manage.py migrate` e reinicie o servidor.
