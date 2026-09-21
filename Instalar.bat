@echo off
cd /d "%~dp0"
python -m venv .venv
if errorlevel 1 goto erro
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto erro
echo Instalacao concluida. Use Iniciar.bat.
pause
exit /b 0
:erro
echo Falha na instalacao. Verifique Python 3.11 ou superior e conexao com a internet.
pause
exit /b 1
