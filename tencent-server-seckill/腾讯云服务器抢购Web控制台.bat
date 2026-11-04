@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Seckill - Local Web Console

if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" seckill_web.py --open
    goto end
)
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" seckill_web.py --open
    goto end
)
where python >nul 2>nul
if not errorlevel 1 (
    python seckill_web.py --open
    goto end
)
where py >nul 2>nul
if not errorlevel 1 (
    py -3 seckill_web.py --open
    goto end
)
echo [ERROR] Python 3.10+ not found. Please install Python first.
echo Then run: python -m pip install -r requirements.txt
:end
echo.
echo Local server closed. This window can now be closed.
pause
endlocal
