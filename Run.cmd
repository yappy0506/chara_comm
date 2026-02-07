@echo off
setlocal

pushd %~dp0

rem Open TTS server in a new terminal window (1: yes / 0: no)
if not defined TTS_START_IN_NEW_WINDOW set "TTS_START_IN_NEW_WINDOW=1"

if not exist Style-Bert-VITS2-2.7.0\venv\Scripts\python.exe (
  set "ERR_MSG=Style-Bert-VITS2-2.7.0 virtual environment was not found. Run Setup.cmd first."
  goto fail
)

if not exist .venv\Scripts\python.exe (
  set "ERR_MSG=chara_comm virtual environment was not found. Run Setup.cmd first."
  goto fail
)

echo [INFO] Starting Style-Bert-VITS2 API server...
if /i "%TTS_START_IN_NEW_WINDOW%"=="1" (
  start "TTS" /D "Style-Bert-VITS2-2.7.0" venv\Scripts\python.exe server_fastapi.py
) else (
  start "TTS" /B /D "Style-Bert-VITS2-2.7.0" venv\Scripts\python.exe server_fastapi.py
)

echo [INFO] Waiting for TTS server to become ready...
set "TTS_HEALTH_URL=http://127.0.0.1:5000/docs"
if not defined TTS_WAIT_TIMEOUT_SEC set "TTS_WAIT_TIMEOUT_SEC=30"
set /a TTS_RETRY=0
set /a TTS_RETRY_MAX=%TTS_WAIT_TIMEOUT_SEC% / 2
if %TTS_RETRY_MAX% lss 1 set /a TTS_RETRY_MAX=1
:wait_tts
powershell -NoProfile -Command "try { $r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 -Uri '%TTS_HEALTH_URL%'; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }"
if %errorlevel%==0 goto tts_ready
set /a TTS_RETRY+=1
if %TTS_RETRY% geq %TTS_RETRY_MAX% (
  goto tts_wait_timeout
)
timeout /t 2 /nobreak >nul
goto wait_tts
:tts_ready
echo [INFO] TTS server is ready.
goto start_app

:tts_wait_timeout
echo([WARN] Timed out after %TTS_WAIT_TIMEOUT_SEC% seconds while waiting for TTS.
echo([WARN] Skipping readiness check and continuing.
echo([WARN] Check URL: "%TTS_HEALTH_URL%"

:start_app
echo [INFO] Starting application...
.venv\Scripts\python.exe -m app %*
if errorlevel 1 (
  set "ERR_MSG=Application exited with an error. Check logs for details."
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
