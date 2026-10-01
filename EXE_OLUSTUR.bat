@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
echo Odak 2.2 - Windows x64 uygulama derlemesi.
echo Ilk derlemede PyPI ve resmi Qt sunucularindan bagimliliklar indirilir.
if exist ".build-env\Scripts\python.exe" goto install
where py >nul 2>&1
if not errorlevel 1 (
    py -3.13 -m venv .build-env
) else (
    python -m venv .build-env
)
if errorlevel 1 goto failed
:install
.build-env\Scripts\python.exe -m pip install --index-url https://pypi.org/simple -r requirements-build.txt
if errorlevel 1 goto failed
.build-env\Scripts\python.exe build_release.py
if errorlevel 1 goto failed
echo.
echo Hazir: release\2.2.0.0-portable\OdakPomodoro\OdakPomodoro.exe
echo EXE'ye kisayol olusturabilirsin. OdakPomodoro klasorunu butun olarak tasi.
echo Eski EXE'yi kapatip yeni EXE'yi acin. Calisma kayitlariniz korunur.
pause
exit /b 0
:failed
echo.
echo EXE olusturulamadi. Yukaridaki hata mesajini kontrol edin.
echo Python 3.13 x64 kullan. Mevcut release ciktisini tasimadan ustune yazilmaz.
pause
exit /b 1
