@echo off
rem Keep this file ASCII with CRLF line endings for Windows CMD.
rem Starts the local SQLite demo by default. Docker mode remains optional.
setlocal
chcp 65001 >nul
set "ROOT=%~dp0"

rem Select Git Bash explicitly; Windows bash.exe may launch WSL.
set "BASH_EXE="
if exist "C:\Program Files\Git\bin\bash.exe" set "BASH_EXE=C:\Program Files\Git\bin\bash.exe"
if not defined BASH_EXE if exist "%ProgramFiles(x86)%\Git\bin\bash.exe" set "BASH_EXE=%ProgramFiles(x86)%\Git\bin\bash.exe"
if not defined BASH_EXE (
  echo [finflow] Git Bash not found. Install Git for Windows: https://git-scm.com/download/win
  pause
  exit /b 1
)

echo [finflow] Starting FinFlow. Logs: .run\logs\
"%BASH_EXE%" -lc "cd '%ROOT%' && ./scripts/start-dev.sh %*"
set "FINFLOW_EXIT_CODE=%ERRORLEVEL%"
if not "%FINFLOW_EXIT_CODE%"=="0" echo [finflow] Startup failed. Review the error above and .run\logs\.
echo.
pause
exit /b %FINFLOW_EXIT_CODE%
