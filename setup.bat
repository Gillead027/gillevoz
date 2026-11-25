@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
set "QUIET="
if /i "%~1"=="/quiet" set "QUIET=1"

echo ============================================
echo  GilleVoz - instalacao
echo ============================================
echo.

REM ---- 1) Ambiente virtual com Python 3.12 (NUNCA o 3.14 do sistema) ----
if exist ".venv\Scripts\python.exe" goto verificar_venv
goto criar_venv

:verificar_venv
".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2]==(3,12) else 1)" >nul 2>&1
if not errorlevel 1 goto venv_ok
echo [!] O .venv existente nao usa Python 3.12. Vou recria-lo.
rmdir /s /q ".venv"

:criar_venv
echo [1/4] Criando o ambiente virtual .venv com Python 3.12...
py -V:Astral/CPython3.12.15 -m venv .venv >nul 2>&1
if not errorlevel 1 goto venv_ok
echo      Astral/CPython3.12.15 nao encontrado. Tentando o Python 3.12 instalado...
py -V:3.12 -m venv .venv
if not errorlevel 1 goto venv_ok
echo.
echo [ERRO] Nao consegui criar o .venv com Python 3.12.
echo        Confira com o comando: py -0p
goto erro

:venv_ok
echo [1/4] Ambiente virtual .venv OK ^(Python 3.12^).
echo.

REM ---- 2) Atualiza o pip ----
echo [2/4] Atualizando o pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip --disable-pip-version-check
if errorlevel 1 (
    echo [ERRO] Falha ao atualizar o pip. Verifique a internet e rode setup.bat de novo.
    goto erro
)
echo.

REM ---- 3) Dependencias do requirements.txt ----
echo [3/4] Instalando as dependencias ^(requirements.txt^). Pode demorar na primeira vez...
".venv\Scripts\python.exe" -m pip install -r requirements.txt --disable-pip-version-check
if errorlevel 1 (
    echo [ERRO] Falha ao instalar as dependencias. Veja a mensagem acima e rode setup.bat de novo.
    goto erro
)
echo.

REM ---- 4) Baixa o modelo de transcricao (so na primeira vez) ----
echo [4/4] Baixando o modelo de transcricao...
if not exist "gillevoz\__main__.py" goto sem_modelo
".venv\Scripts\python.exe" -m gillevoz --baixar-modelo
if errorlevel 1 (
    echo [AVISO] O download do modelo falhou ou nao foi concluido.
    echo         Rode setup.bat de novo para tentar outra vez. As outras etapas estao prontas.
    goto fim_aviso
)
echo Modelo pronto.
goto fim_ok

:sem_modelo
echo [AVISO] O comando de baixar o modelo ainda nao existe no projeto.
echo         Quando o app estiver pronto, rode setup.bat de novo para baixar o modelo.
goto fim_aviso

:fim_ok
echo.
echo ============================================
echo  Instalacao concluida. Abra o GilleVoz.vbs
echo ============================================
goto pausa

:fim_aviso
echo.
echo Instalacao quase pronta. Veja o aviso acima.
goto pausa

:erro
echo.
echo ============================================
echo  A instalacao NAO foi concluida.
echo ============================================
set "ERRO_CODIGO=1"
goto pausa

:pausa
if defined QUIET goto saida
echo.
pause
:saida
if defined ERRO_CODIGO exit /b 1
exit /b 0
