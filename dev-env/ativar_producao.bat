@echo off
REM ══════════════════════════════════════════════════════════════════════
REM  LIDDIS — Ativar configuração de PRODUÇÃO localmente
REM  Use para simular produção antes do deploy.
REM  ATENÇÃO: Preencha dev-env\.env.production antes de usar!
REM ══════════════════════════════════════════════════════════════════════

cd /d "%~dp0\.."

echo.
echo ================================================
echo   LIDDIS — Modo PRODUCAO (simulacao local)
echo ================================================
echo.

REM Verificar se .env.production foi preenchido
findstr /C:"SUBSTITUA" "dev-env\.env.production" >nul
if %errorlevel%==0 (
    echo [ERRO] dev-env\.env.production ainda tem valores "SUBSTITUA" pendentes!
    echo        Preencha todas as variaveis antes de continuar.
    echo.
    pause
    exit /b 1
)

echo [INFO] Copiando .env.production para .env...
copy "dev-env\.env.production" ".env" /Y
echo [OK] .env configurado para PRODUCAO.

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

echo.
echo [INFO] Coletando arquivos estaticos...
python manage.py collectstatic --noinput

echo.
echo [INFO] Verificando migracoes pendentes...
python manage.py migrate --check
if %errorlevel% NEQ 0 (
    echo [AVISO] Ha migracoes pendentes! Execute: python manage.py migrate
)

echo.
echo [INFO] Iniciando servidor Gunicorn (modo producao)...
echo        Acesse: http://127.0.0.1:8080
echo.
gunicorn config.wsgi:application --workers 2 --threads 2 --timeout 60 --bind 127.0.0.1:8080

pause
