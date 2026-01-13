@echo off

REM ===============================
REM �ߋ����̍폜
REM ===============================
if exist .env del .env
if exist .venv rmdir /s /q .venv
if exist data rmdir /s /q data
if exist logs rmdir /s /q logs

REM ===============================
REM app���s
REM ===============================
python -m venv .venv
call .\.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
copy .env.example .env
python -m app