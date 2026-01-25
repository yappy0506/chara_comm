@echo off
chcp 65001 >nul
setlocal

pushd %~dp0

if not exist Style-Bert-VITS2-2.7.0\venv\Scripts\python.exe (
  set "ERR_MSG=Style-Bert-VITS2-2.7.0 の仮想環境が見つかりません。Setup.cmd を先に実行してください。"
  goto fail
)

if not exist .venv\Scripts\python.exe (
  set "ERR_MSG=chara_comm の仮想環境が見つかりません。Setup.cmd を先に実行してください。"
  goto fail
)

echo [INFO] Style-Bert-VITS2 のAPIサーバを起動します...
start "" /D "Style-Bert-VITS2-2.7.0" venv\Scripts\python.exe server_fastapi.py

echo [INFO] TTSサーバの起動完了を待機します...
set "TTS_HEALTH_URL=http://127.0.0.1:5000/docs"
set /a TTS_RETRY=0
set /a TTS_RETRY_MAX=60
:wait_tts
powershell -NoProfile -Command "try { $r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 -Uri '%TTS_HEALTH_URL%'; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }"
if %errorlevel%==0 goto tts_ready
set /a TTS_RETRY+=1
if %TTS_RETRY% geq %TTS_RETRY_MAX% (
  set "ERR_MSG=TTSサーバの起動を確認できませんでした。%TTS_HEALTH_URL% にアクセスできるか確認してください。"
  goto fail
)
timeout /t 2 /nobreak >nul
goto wait_tts
:tts_ready
echo [INFO] TTSサーバの起動を確認しました。

echo [INFO] アプリケーションを起動します...
.venv\Scripts\python.exe -m app
if errorlevel 1 (
  set "ERR_MSG=アプリケーションがエラーで終了しました。ログを確認してください。"
  goto fail
)

popd
endlocal
exit /b 0

:fail
echo [ERROR] %ERR_MSG%
popd
endlocal
echo.
pause
exit /b 1
