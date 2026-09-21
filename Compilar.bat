@echo off
cd /d "%~dp0"
setlocal
".venv\Scripts\python.exe" -m pip install pyinstaller
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" tools\make_icon.py
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m PyInstaller --noconfirm DriveFlow.spec
if errorlevel 1 exit /b 1
set DRIVEFLOW_ONEFILE=1
".venv\Scripts\python.exe" -m PyInstaller --noconfirm DriveFlow.spec
if errorlevel 1 exit /b 1
echo Versao portatil: dist\DriveFlow-v*-portatil.exe. Copie somente esse executavel.
echo Versao em pasta: dist\DriveFlow\DriveFlow.exe. Esta alternativa requer a pasta inteira.
pause
