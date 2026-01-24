@echo off
setlocal

pushd %~dp0

echo [INFO] Style-Bert-VITS2-2.7.0 のセットアップを開始します...
pushd Style-Bert-VITS2-2.7.0
if not exist venv (
  uv venv venv
)
call venv\Scripts\activate.bat
uv pip install "torch<2.4" "torchaudio<2.4" --index-url https://download.pytorch.org/whl/cu118
uv pip install -r requirements.txt
python initialize.py
call venv\Scripts\deactivate.bat
popd

echo [INFO] chara_comm のセットアップを開始します...
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

echo [INFO] セットアップが完了しました。
endlocal
