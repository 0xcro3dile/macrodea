@echo off
REM One-command attacker for Windows teammates. RIGHT-CLICK -> Run as administrator.
REM   attack.bat scan     (or: flood | bruteforce | slowloris | normal)
set BOARD=10.42.0.208
route add 10.42.0.0 mask 255.255.255.0 10.40.58.21 >nul 2>&1
if "%1"=="" (set MODE=scan) else (set MODE=%1)
echo route ready - attacking %BOARD% with %MODE%
python simulate.py %BOARD% %MODE%
