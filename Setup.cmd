@echo off
setlocal

set "PYTHON_VERSION=3.10"

pushd %~dp0

echo [INFO] Starting Style-Bert-VITS2-2.7.0 setup...
pushd Style-Bert-VITS2-2.7.0
call :ensure_venv "venv"
call venv\Scripts\activate.bat
uv pip install "torch<2.4" "torchaudio<2.4" --index-url https://download.pytorch.org/whl/cu118
uv pip install -r requirements-infer.txt
python initialize.py
call venv\Scripts\deactivate.bat
popd

echo [INFO] Starting chara_comm setup...
call :ensure_venv ".venv"
call .venv\Scripts\activate.bat
uv pip install -r requirements.txt
if not exist .env (
  copy .env.example .env
)
call .venv\Scripts\deactivate.bat

popd

echo [INFO] Setup completed.
endlocal
exit /b 0

:ensure_venv
set "VENV_DIR=%~1"
set "VENV_PY="
if exist "%VENV_DIR%\Scripts\python.exe" (
  call :get_pyver "%VENV_DIR%\Scripts\python.exe"
)
if defined VENV_PY (
  if /i not "%VENV_PY%"=="%PYTHON_VERSION%" (
    echo [WARN] %VENV_DIR% uses Python %VENV_PY%. Recreating with Python %PYTHON_VERSION%...
    rmdir /s /q "%VENV_DIR%"
  )
)
if not exist "%VENV_DIR%" (
  uv venv -p %PYTHON_VERSION% "%VENV_DIR%"
)
exit /b 0

:get_pyver
for /f "tokens=2,3 delims=. " %%A in ('"%~1" -V 2^>^&1') do set "VENV_PY=%%A.%%B"
exit /b 0
