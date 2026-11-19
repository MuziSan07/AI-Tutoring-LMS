@echo off
REM Nova Academy - one-click demo launcher (Windows)
cd /d "%~dp0"
if not exist frontend\dist (
  echo Building the frontend...
  pushd frontend && call npm install && call npm run build && popd
)
if "%1"=="reset" del /q backend\lms.db 2>nul
echo Starting Nova Academy on http://localhost:8765 ...
start "" http://localhost:8765
python -m uvicorn app.main:app --app-dir backend --port 8765
