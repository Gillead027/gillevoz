@echo off
REM GilleVoz com janela de console (bom para ver erros). Para uso diario, use GilleVoz.vbs.
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] O ambiente nao existe ainda. Rode setup.bat primeiro.
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"
python -m gillevoz
set "CODIGO=%ERRORLEVEL%"
if not "%CODIGO%"=="0" (
    echo.
    echo [ERRO] O GilleVoz parou com codigo %CODIGO%. Veja a mensagem acima e o arquivo logs\gillevoz.log.
    pause
)
exit /b %CODIGO%
