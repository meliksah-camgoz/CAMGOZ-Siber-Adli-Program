
@echo off
title CAMGOZ Build System

echo ========================================
echo          CAMGOZ BUILD SYSTEM
echo ========================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo HATA: Sanal ortam bulunamadi!
    pause
    exit /b 1
)

echo [1/3] Eski build dosyalari temizleniyor...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo.
echo [2/3] CAMGOZ paketleniyor...
.venv\Scripts\python.exe -m PyInstaller --noconfirm CAMGOZ.spec

if errorlevel 1 (
    echo.
    echo HATA: Paketleme basarisiz!
    pause
    exit /b 1
)

echo.
echo [3/3] Paketleme tamamlandi!
echo.
echo EXE konumu:
echo dist\CAMGOZ\CAMGOZ.exe
echo.
pause
