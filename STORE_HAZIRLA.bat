@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
chcp 65001 >nul
echo Odak - Microsoft Store MSIX derlemesi.
echo Once STORE_YAYIN_REHBERI.md dosyasini oku.
if exist ".build-env\Scripts\python.exe" goto install
where py >nul 2>&1
if errorlevel 1 goto python
py -3.13 -m venv .build-env
if errorlevel 1 goto failed
goto install
:python
python -m venv .build-env
if errorlevel 1 goto failed
:install
.build-env\Scripts\python.exe -m pip install --index-url https://pypi.org/simple -r requirements-build.txt
if errorlevel 1 goto failed
.build-env\Scripts\python.exe build_release.py --msix --interactive
if errorlevel 1 goto failed
echo.
echo Dosyalar release klasorunde. Bu islem Store'a yukleme veya yayinlama yapmaz.
pause
exit /b 0
:failed
echo.
echo Derleme durdu. Yukaridaki hata mesajini kontrol et.
echo Windows x64, Python 3.13 x64, Windows SDK ve Store kimligi gereklidir.
pause
exit /b 1
