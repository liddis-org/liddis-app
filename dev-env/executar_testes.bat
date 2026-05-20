@echo off
REM ══════════════════════════════════════════════════════════════════════
REM  LIDDIS — Executar Suite de Testes
REM  Execute: dev-env\executar_testes.bat
REM
REM  Opcoes:
REM   sem argumento  → todos os testes
REM   models         → apenas testes de models
REM   auth           → apenas testes de autenticacao
REM   permissions    → apenas testes de permissoes
REM   cobertura      → todos com relatorio de cobertura HTML
REM ══════════════════════════════════════════════════════════════════════

cd /d "%~dp0\.."

REM Garantir que .env de dev está ativo
if not exist ".env" (
    copy "dev-env\.env.development" ".env"
)

REM Garantir TEST_MODE=True para os testes
set DJANGO_SETTINGS_MODULE=config.settings

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

echo.
echo ================================================
echo   LIDDIS — Suite de Testes
echo ================================================
echo.

if "%1"=="models" (
    echo Executando: testes de models...
    pytest tests\test_models_users.py tests\test_models_consultations.py -v
) else if "%1"=="auth" (
    echo Executando: testes de autenticacao...
    pytest tests\test_auth.py -v
) else if "%1"=="permissions" (
    echo Executando: testes de permissoes RBAC...
    pytest tests\test_permissions.py -v
) else if "%1"=="cobertura" (
    echo Executando: todos os testes com cobertura...
    pytest tests\ --cov=users --cov=consultations --cov-report=html --cov-report=term-missing -v
    echo.
    echo Relatorio HTML gerado em: htmlcov\index.html
    start htmlcov\index.html
) else (
    echo Executando: todos os testes...
    pytest tests\ -v
)

echo.
echo Testes concluidos!
pause
