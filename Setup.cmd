@echo off
setlocal
for /f "tokens=2 delims=:" %%A in ('chcp') do set "OLDCP=%%A"
set "OLDCP=%OLDCP: =%"
chcp 65001 >nul

set "PATH=%USERPROFILE%\.local\bin;%PATH%"

pushd %~dp0

echo [INFO] Starting Style-Bert-VITS2-2.7.0 setup...
pushd Style-Bert-VITS2-2.7.0
if not exist venv (
  uv venv venv
)
call venv\Scripts\activate.bat
uv pip install "torch<2.4" "torchaudio<2.4" --index-url https://download.pytorch.org/whl/cu118
uv pip install -r requirements-infer.txt
python initialize.py
call venv\Scripts\deactivate.bat
popd

echo [INFO] Starting chara_comm setup...
if not exist .venv (
  uv venv .venv
)
call .venv\Scripts\activate.bat
uv pip install -r requirements.txt
if not exist .env (
  copy .env.example .env
)
call .venv\Scripts\deactivate.bat

popd

echo [INFO] Setup completed.
if defined OLDCP chcp %OLDCP% >nul
endlocal

exit /b 0
