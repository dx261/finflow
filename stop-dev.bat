@echo off
rem Keep this file ASCII with CRLF line endings for Windows CMD.
rem Stops local application services; Docker infrastructure is kept running.
setlocal
chcp 65001 >nul
set "ROOT=%~dp0"

rem Select the same Git Bash as start-dev.bat, not the WSL launcher.
set "BASH_EXE="
if exist "C:\Program Files\Git\bin\bash.exe" set "BASH_EXE=C:\Program Files\Git\bin\bash.exe"
if not defined BASH_EXE if exist "%ProgramFiles(x86)%\Git\bin\bash.exe" set "BASH_EXE=%ProgramFiles(x86)%\Git\bin\bash.exe"
if not defined BASH_EXE (
  echo [finflow] Git Bash not found. Install Git for Windows: https://git-scm.com/download/win
  pause
  exit /b 1
)

echo [finflow] Stopping FinFlow application services.
"%BASH_EXE%" -lc "cd '%ROOT%' && ./scripts/stop-dev.sh"
set "FINFLOW_EXIT_CODE=%ERRORLEVEL%"
if not "%FINFLOW_EXIT_CODE%"=="0" echo [finflow] Stop failed. Review the error above.
echo.
pause
exit /b %FINFLOW_EXIT_CODE%
