@echo off
setlocal

pushd %~dp0

if not exist Style-Bert-VITS2-2.7.0\venv\Scripts\python.exe (
  echo [ERROR] Style-Bert-VITS2-2.7.0 の仮想環境が見つかりません。Setup.cmd を先に実行してください。
  popd
  exit /b 1
)

if not exist .venv\Scripts\python.exe (
  echo [ERROR] chara_comm の仮想環境が見つかりません。Setup.cmd を先に実行してください。
  popd
  exit /b 1
)

echo [INFO] Style-Bert-VITS2 のAPIサーバを起動します...
start "" Style-Bert-VITS2-2.7.0\venv\Scripts\python.exe Style-Bert-VITS2-2.7.0\server_fastapi.py

echo [INFO] アプリケーションを起動します...
.venv\Scripts\python.exe -m app

popd
endlocal
