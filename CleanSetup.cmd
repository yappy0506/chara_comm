@echo off
setlocal

set "DRY_RUN=0"
set "FORCE_ENV=0"

for %%A in (%*) do (
  if /i "%%~A"=="--dry-run" set "DRY_RUN=1"
  if /i "%%~A"=="--force-env" set "FORCE_ENV=1"
)

pushd %~dp0

echo [INFO] Cleaning setup artifacts in chara_comm...
echo [INFO] Options: DRY_RUN=%DRY_RUN% FORCE_ENV=%FORCE_ENV%

if exist ".venv" (
  if "%DRY_RUN%"=="1" (
    echo [DRY] Remove .venv
  ) else (
    rmdir /s /q ".venv"
    echo [INFO] Removed .venv
  )
) else (
  echo [INFO] .venv does not exist
)

if exist "Style-Bert-VITS2-2.7.0\venv" (
  if "%DRY_RUN%"=="1" (
    echo [DRY] Remove Style-Bert-VITS2-2.7.0\venv
  ) else (
    rmdir /s /q "Style-Bert-VITS2-2.7.0\venv"
    echo [INFO] Removed Style-Bert-VITS2-2.7.0\venv
  )
) else (
  echo [INFO] Style-Bert-VITS2-2.7.0\venv does not exist
)

if "%DRY_RUN%"=="1" (
  echo [DRY] git clean -fdX -- Style-Bert-VITS2-2.7.0
) else (
  git clean -fdX -- Style-Bert-VITS2-2.7.0
  if errorlevel 1 (
    echo [WARN] git clean failed for Style-Bert-VITS2-2.7.0. Continue with remaining cleanup.
  ) else (
    echo [INFO] Removed ignored/generated files under Style-Bert-VITS2-2.7.0
  )
)

if exist ".env" (
  if "%FORCE_ENV%"=="1" (
    if "%DRY_RUN%"=="1" (
      echo [DRY] Remove .env ^(forced^)
    ) else (
      del /f /q ".env"
      echo [INFO] Removed .env ^(forced^)
    )
  ) else (
    echo [INFO] Keeping .env. Use --force-env to delete it.
  )
) else (
  echo [INFO] .env does not exist
)

echo [INFO] Cleanup completed.
if "%DRY_RUN%"=="1" (
  echo [INFO] Dry-run mode: no files were deleted.
)

popd
endlocal
exit /b 0
