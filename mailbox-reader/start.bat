@echo off
cd /d "%~dp0"
if not exist node_modules\vite\bin\vite.js (
  call npm ci
  if errorlevel 1 goto failed
)
call npm run build
if errorlevel 1 goto failed
python app.py --open
:failed
pause
