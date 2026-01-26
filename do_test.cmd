@echo off

REM ===============================
REM Cleanup
REM ===============================
if exist .env del /f /q .env
if exist .venv (
    taskkill /f /t /im python.exe 2>nul
    timeout /t 1 /nobreak
    rmdir /s /q .venv
)
if exist data rmdir /s /q data
if exist logs rmdir /s /q logs

REM ===============================
REM app setup
REM ===============================
python -m venv .venv
if errorlevel 1 (
    echo Failed to create venv
    exit /b 1
)
call .\.venv\Scripts\activate.bat
if errorlevel 1 (
    echo Failed to activate venv
    exit /b 1
)
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
copy .env.example .env
python -m app