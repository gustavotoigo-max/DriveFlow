@echo off
cd /d "%~dp0"
setlocal
".venv\Scripts\python.exe" -m pip install -r requirements-monitoring.txt pyinstaller
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" tools\make_icon.py
if not exist "driveflow\oauth_client.json" echo AVISO: driveflow\oauth_client.json ausente. O executavel pedira o JSON OAuth ao conectar.
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m PyInstaller --noconfirm DriveFlow.spec
if errorlevel 1 exit /b 1
for /f "tokens=2 delims='" %%v in (driveflow\version.py) do set DRIVEFLOW_VERSION=%%v
if "%DRIVEFLOW_VERSION%"=="" echo ERRO: versao nao encontrada em driveflow\version.py& exit /b 1
rem Pacote da versao em pasta: anexo do release usado pelo atualizador das instalacoes em pasta.
powershell -NoProfile -Command "Compress-Archive -Path 'dist\DriveFlow\*' -DestinationPath 'dist\DriveFlow-v%DRIVEFLOW_VERSION%-pasta.zip' -Force"
if errorlevel 1 exit /b 1
set DRIVEFLOW_ONEFILE=1
".venv\Scripts\python.exe" -m PyInstaller --noconfirm DriveFlow.spec
if errorlevel 1 exit /b 1
echo Versao portatil: dist\DriveFlow-v*-portatil.exe. Copie somente esse executavel.
echo Versao em pasta: dist\DriveFlow\DriveFlow.exe (abre mais rapido; o instalador usa esta). Pacote: dist\DriveFlow-v*-pasta.zip.
pause
