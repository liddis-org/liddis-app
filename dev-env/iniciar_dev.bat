@echo off
REM ══════════════════════════════════════════════════════════════════════
REM  LIDDIS — Script de inicialização do ambiente de DESENVOLVIMENTO
REM  Execute a partir da raiz do projeto: dev-env\iniciar_dev.bat
REM ══════════════════════════════════════════════════════════════════════

echo.
echo ================================================
echo   LIDDIS — Iniciando ambiente de desenvolvimento
echo ================================================
echo.

REM ── 1. Ir para a raiz do projeto ───────────────────────────────────────────
cd /d "%~dp0\.."

REM ── 2. Copiar .env de desenvolvimento se não existir ─────────────────────
if not exist ".env" (
    echo [INFO] Criando .env a partir do template de desenvolvimento...
    copy "dev-env\.env.development" ".env"
    echo [OK] .env criado com configuracoes de desenvolvimento.
) else (
    echo [INFO] .env ja existe — mantendo configuracao atual.
)

REM ── 3. Ativar virtualenv ──────────────────────────────────────────────────
if exist "venv\Scripts\activate.bat" (
    echo [INFO] Ativando virtualenv...
    call venv\Scripts\activate.bat
) else (
    echo [AVISO] venv nao encontrado. Criando...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo [INFO] Instalando dependencias de desenvolvimento...
    pip install -r requirements-dev.txt
)

REM ── 4. Aplicar migrações ──────────────────────────────────────────────────
echo.
echo [INFO] Aplicando migracoes...
python manage.py migrate --run-syncdb

REM ── 5. Criar superusuário de teste (se não existir) ───────────────────────
echo.
echo [INFO] Verificando superusuario de teste...
python manage.py shell -c "
from users.models import CustomUser
if not CustomUser.objects.filter(email='admin@liddis.dev').exists():
    u = CustomUser.objects.create_superuser('admin', 'admin@liddis.dev', 'admin123')
    u.role = 'ADMIN'
    u.is_email_verified = True
    u.save()
    print('[OK] Superusuario criado: admin@liddis.dev / admin123')
else:
    print('[INFO] Superusuario ja existe.')
"

REM ── 6. Iniciar servidor ───────────────────────────────────────────────────
echo.
echo ================================================
echo   Servidor rodando em: http://127.0.0.1:8000
echo   Admin:               http://127.0.0.1:8000/admin
echo   Login dev:           admin@liddis.dev / admin123
echo   Pressione Ctrl+C para parar
echo ================================================
echo.
python manage.py runserver 8000

pause
