@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto check
where py >nul 2>&1
if not errorlevel 1 (
    py -3 -m venv .venv
) else (
    python -m venv .venv
)
if errorlevel 1 goto failed
:check
.venv\Scripts\python.exe -c "from PySide6.QtWidgets import QApplication" >nul 2>&1
if not errorlevel 1 goto run
echo Ilk kurulum: Qt arayuz paketi indiriliyor. Internet gerekir.
.venv\Scripts\python.exe -m pip install --index-url https://pypi.org/simple -r requirements.txt
if errorlevel 1 goto failed
:run
.venv\Scripts\python.exe app.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo.
echo Islem tamamlanamadi. Yukaridaki hata mesajini kontrol edin.
echo Python 3.10 veya ustu, 64 bit Windows gerekir.
pause
exit /b 1
