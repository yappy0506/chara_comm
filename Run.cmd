@echo off
setlocal

pushd %~dp0

set "LOG_DIR=%CD%\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
for /f %%I in ('powershell -NoProfile -Command "(Get-Date).ToString('yyyyMMdd_HHmmss')"') do set "RUN_TIMESTAMP=%%I"
set "DEBUG_LOG_PATH=%LOG_DIR%\debuglog_%RUN_TIMESTAMP%.log"
set "DEBUG_LOG_TTS_PATH=%LOG_DIR%\debuglog_%RUN_TIMESTAMP%_tts.log"
> "%DEBUG_LOG_PATH%" echo [INFO] Run started at %date% %time%
call :log "[INFO] Debug log: %DEBUG_LOG_PATH%"
call :log "[INFO] TTS log: %DEBUG_LOG_TTS_PATH%"

rem Open TTS server in a new terminal window (1: yes / 0: no)
if not defined TTS_START_IN_NEW_WINDOW set "TTS_START_IN_NEW_WINDOW=1"
if not defined TTS_STOP_ON_EXIT set "TTS_STOP_ON_EXIT=1"

if not exist Style-Bert-VITS2-2.7.0\venv\Scripts\python.exe (
  set "ERR_MSG=Style-Bert-VITS2-2.7.0 virtual environment was not found. Run Setup.cmd first."
  goto fail
)

if not exist .venv\Scripts\python.exe (
  set "ERR_MSG=chara_comm virtual environment was not found. Run Setup.cmd first."
  goto fail
)

set "TTS_HEALTH_URL=http://127.0.0.1:5000/docs"
call :check_tts_health
if %errorlevel%==0 (
  call :log "[INFO] TTS health endpoint is already reachable."
  goto tts_ready
)

call :log "[INFO] Starting Style-Bert-VITS2 API server..."
if /i "%TTS_START_IN_NEW_WINDOW%"=="1" (
  start "TTS" /D "Style-Bert-VITS2-2.7.0" cmd /d /c "venv\Scripts\python.exe server_fastapi.py 1>>%DEBUG_LOG_TTS_PATH% 2>&1"
) else (
  start "TTS" /B /D "Style-Bert-VITS2-2.7.0" cmd /d /c "venv\Scripts\python.exe server_fastapi.py 1>>%DEBUG_LOG_TTS_PATH% 2>&1"
)

call :log "[INFO] Waiting for TTS server to become ready..."
if not defined TTS_WAIT_TIMEOUT_SEC set "TTS_WAIT_TIMEOUT_SEC=30"
set /a TTS_RETRY=0
set /a TTS_RETRY_MAX=%TTS_WAIT_TIMEOUT_SEC% / 2
if %TTS_RETRY_MAX% lss 1 set /a TTS_RETRY_MAX=1
:wait_tts
call :check_tts_health
if %errorlevel%==0 goto tts_ready
set /a TTS_RETRY+=1
if %TTS_RETRY% geq %TTS_RETRY_MAX% (
  goto tts_wait_timeout
)
timeout /t 2 /nobreak >nul
goto wait_tts
:tts_ready
call :log "[INFO] TTS server is ready."
call :check_tts_process
if %errorlevel%==0 (
  call :log "[INFO] TTS process is running (server_fastapi.py)."
) else (
  call :log "[WARN] TTS health is reachable but server_fastapi.py process was not detected."
)
goto start_app

:tts_wait_timeout
call :log "[WARN] Could not confirm TTS server startup."
call :check_tts_process
if %errorlevel%==0 (
  call :log "[WARN] server_fastapi.py process exists, but health check did not become ready."
) else (
  call :log "[WARN] server_fastapi.py process was not detected."
)
call :log "[WARN] Timed out after %TTS_WAIT_TIMEOUT_SEC% seconds while waiting for TTS."
call :log "[WARN] Skipping readiness check and continuing."
call :log "[WARN] Check URL: %TTS_HEALTH_URL%"

:start_app
call :log "[INFO] Starting application..."
.venv\Scripts\python.exe -m app %*
if errorlevel 1 (
  set "ERR_MSG=Application exited with an error. Check logs for details."
  goto fail
)

call :log "[INFO] Run completed successfully."
call :stop_tts_server
popd
endlocal
exit /b 0

:check_tts_health
powershell -NoProfile -Command "try { $r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 -Uri '%TTS_HEALTH_URL%'; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >> "%DEBUG_LOG_PATH%" 2>&1
exit /b %errorlevel%

:check_tts_process
powershell -NoProfile -Command "$p=Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | Where-Object { $_.CommandLine -match 'server_fastapi.py' -and $_.CommandLine -match 'Style-Bert-VITS2-2.7.0' }; if($p){ exit 0 } else { exit 1 }" >> "%DEBUG_LOG_PATH%" 2>&1
exit /b %errorlevel%

:log
set "_LOG_MSG=%~1"
echo %_LOG_MSG%
>> "%DEBUG_LOG_PATH%" echo [%date% %time%] %_LOG_MSG%
exit /b 0

:stop_tts_server
if /i not "%TTS_STOP_ON_EXIT%"=="1" (
  call :log "[INFO] Skipping TTS stop on exit (TTS_STOP_ON_EXIT=%TTS_STOP_ON_EXIT%)."
  exit /b 0
)
set "TTS_STOP_COUNT=0"
for /f %%I in ('powershell -NoProfile -Command "$ErrorActionPreference='SilentlyContinue'; $p=Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | Where-Object { $_.CommandLine -match 'server_fastapi.py' -and $_.CommandLine -match 'Style-Bert-VITS2-2.7.0' }; $n=0; foreach($x in $p){ try { Stop-Process -Id $x.ProcessId -Force -ErrorAction Stop; $n++ } catch {} }; Write-Output $n"') do set "TTS_STOP_COUNT=%%I"
if "%TTS_STOP_COUNT%"=="0" (
  call :log "[INFO] No TTS process to stop."
) else (
  call :log "[INFO] Stopped TTS process count: %TTS_STOP_COUNT%"
)
exit /b 0

:fail
call :log "[ERROR] %ERR_MSG%"
call :stop_tts_server
popd
endlocal
echo.
pause
exit /b 1
