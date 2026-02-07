@echo off
setlocal EnableExtensions

if /i "%CHARA_RUN_CMD_ACTIVE%"=="1" (
  echo [ERROR] Recursive Run.cmd invocation detected. Aborting.
  exit /b 1
)
set "CHARA_RUN_CMD_ACTIVE=1"
set "RUN_APP_ARGS=%*"

pushd %~dp0

set "LOG_DIR=%CD%\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
for /f %%I in ('powershell -NoProfile -Command "(Get-Date).ToString('yyyyMMdd_HHmmss')"') do set "RUN_TIMESTAMP=%%I"
set "DEBUG_LOG_PATH=%LOG_DIR%\debuglog_%RUN_TIMESTAMP%.log"
set "DEBUG_LOG_TTS_PATH=%LOG_DIR%\debuglog_%RUN_TIMESTAMP%_tts.log"
set "TTS_SCRIPT_DIR=%CD%\scripts"
set "TTS_BASE_URL=http://127.0.0.1:5000"
set "TTS_HEALTH_URL=%TTS_BASE_URL%/docs"

> "%DEBUG_LOG_PATH%" echo [INFO] Run started at %date% %time%
echo [INFO] Debug log: %DEBUG_LOG_PATH%
>> "%DEBUG_LOG_PATH%" echo [%date% %time%] [INFO] Debug log: %DEBUG_LOG_PATH%
echo [INFO] TTS log: %DEBUG_LOG_TTS_PATH%
>> "%DEBUG_LOG_PATH%" echo [%date% %time%] [INFO] TTS log: %DEBUG_LOG_TTS_PATH%

rem Open TTS server in a new terminal window (1: yes / 0: no)
if not defined TTS_START_IN_NEW_WINDOW set "TTS_START_IN_NEW_WINDOW=1"
if not defined TTS_STOP_ON_EXIT set "TTS_STOP_ON_EXIT=1"
if not defined TTS_WAIT_TIMEOUT_SEC set "TTS_WAIT_TIMEOUT_SEC=30"

if not exist Style-Bert-VITS2-2.7.0\venv\Scripts\python.exe (
  set "ERR_MSG=Style-Bert-VITS2-2.7.0 virtual environment was not found. Run Setup.cmd first."
  goto fail
)

if not exist .venv\Scripts\python.exe (
  set "ERR_MSG=chara_comm virtual environment was not found. Run Setup.cmd first."
  goto fail
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%TTS_SCRIPT_DIR%\check_tts_ready.ps1" -BaseUrl "%TTS_BASE_URL%" >> "%DEBUG_LOG_PATH%" 2>&1
if %errorlevel%==0 goto tts_ready

echo [INFO] Starting Style-Bert-VITS2 API server...
>> "%DEBUG_LOG_PATH%" echo [%date% %time%] [INFO] Starting Style-Bert-VITS2 API server...
if /i "%TTS_START_IN_NEW_WINDOW%"=="1" (
  start "TTS" /D "Style-Bert-VITS2-2.7.0" powershell -NoProfile -ExecutionPolicy Bypass -File "%TTS_SCRIPT_DIR%\run_tts_with_log.ps1" -LogPath "%DEBUG_LOG_TTS_PATH%"
) else (
  start "TTS" /B /D "Style-Bert-VITS2-2.7.0" powershell -NoProfile -ExecutionPolicy Bypass -File "%TTS_SCRIPT_DIR%\run_tts_with_log.ps1" -LogPath "%DEBUG_LOG_TTS_PATH%"
)

echo [INFO] Waiting for TTS server to become ready...
>> "%DEBUG_LOG_PATH%" echo [%date% %time%] [INFO] Waiting for TTS server to become ready...
set /a TTS_RETRY=0
set /a TTS_RETRY_MAX=%TTS_WAIT_TIMEOUT_SEC% / 2
if %TTS_RETRY_MAX% lss 1 set /a TTS_RETRY_MAX=1
:wait_tts
powershell -NoProfile -ExecutionPolicy Bypass -File "%TTS_SCRIPT_DIR%\check_tts_ready.ps1" -BaseUrl "%TTS_BASE_URL%" >> "%DEBUG_LOG_PATH%" 2>&1
if %errorlevel%==0 goto tts_ready
set /a TTS_RETRY+=1
if %TTS_RETRY% geq %TTS_RETRY_MAX% goto tts_wait_timeout
timeout /t 2 /nobreak >nul
goto wait_tts

:tts_ready
echo [INFO] TTS server is ready (voice synthesis probe passed).
>> "%DEBUG_LOG_PATH%" echo [%date% %time%] [INFO] TTS server is ready (voice synthesis probe passed).
goto start_app

:tts_wait_timeout
echo [WARN] Could not confirm TTS server startup.
>> "%DEBUG_LOG_PATH%" echo [%date% %time%] [WARN] Could not confirm TTS server startup.
powershell -NoProfile -ExecutionPolicy Bypass -File "%TTS_SCRIPT_DIR%\check_tts_process.ps1" >> "%DEBUG_LOG_PATH%" 2>&1
if %errorlevel%==0 (
  echo [WARN] server_fastapi.py process exists, but readiness probe failed.
  >> "%DEBUG_LOG_PATH%" echo [%date% %time%] [WARN] server_fastapi.py process exists, but readiness probe failed.
) else (
  echo [WARN] server_fastapi.py process was not detected.
  >> "%DEBUG_LOG_PATH%" echo [%date% %time%] [WARN] server_fastapi.py process was not detected.
)
echo [WARN] Timed out after %TTS_WAIT_TIMEOUT_SEC% seconds while waiting for TTS.
>> "%DEBUG_LOG_PATH%" echo [%date% %time%] [WARN] Timed out after %TTS_WAIT_TIMEOUT_SEC% seconds while waiting for TTS.
echo [WARN] Skipping readiness check and continuing.
>> "%DEBUG_LOG_PATH%" echo [%date% %time%] [WARN] Skipping readiness check and continuing.
echo [WARN] Check URL: %TTS_HEALTH_URL%
>> "%DEBUG_LOG_PATH%" echo [%date% %time%] [WARN] Check URL: %TTS_HEALTH_URL%

:start_app
echo [INFO] Starting application...
>> "%DEBUG_LOG_PATH%" echo [%date% %time%] [INFO] Starting application...
.venv\Scripts\python.exe -m app %RUN_APP_ARGS%
if errorlevel 1 (
  set "ERR_MSG=Application exited with an error. Check logs for details."
  goto fail
)

echo [INFO] Run completed successfully.
>> "%DEBUG_LOG_PATH%" echo [%date% %time%] [INFO] Run completed successfully.
if /i "%TTS_STOP_ON_EXIT%"=="1" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%TTS_SCRIPT_DIR%\stop_tts_server.ps1" >> "%DEBUG_LOG_PATH%" 2>&1
  echo [INFO] TTS stop command executed.
  >> "%DEBUG_LOG_PATH%" echo [%date% %time%] [INFO] TTS stop command executed.
) else (
  echo [INFO] Skipping TTS stop on exit: TTS_STOP_ON_EXIT=%TTS_STOP_ON_EXIT%.
  >> "%DEBUG_LOG_PATH%" echo [%date% %time%] [INFO] Skipping TTS stop on exit: TTS_STOP_ON_EXIT=%TTS_STOP_ON_EXIT%.
)

popd
endlocal
exit /b 0

:fail
echo [ERROR] %ERR_MSG%
>> "%DEBUG_LOG_PATH%" echo [%date% %time%] [ERROR] %ERR_MSG%
if /i "%TTS_STOP_ON_EXIT%"=="1" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%TTS_SCRIPT_DIR%\stop_tts_server.ps1" >> "%DEBUG_LOG_PATH%" 2>&1
  echo [INFO] TTS stop command executed.
  >> "%DEBUG_LOG_PATH%" echo [%date% %time%] [INFO] TTS stop command executed.
) else (
  echo [INFO] Skipping TTS stop on exit: TTS_STOP_ON_EXIT=%TTS_STOP_ON_EXIT%.
  >> "%DEBUG_LOG_PATH%" echo [%date% %time%] [INFO] Skipping TTS stop on exit: TTS_STOP_ON_EXIT=%TTS_STOP_ON_EXIT%.
)
popd
endlocal
echo.
pause
exit /b 1
