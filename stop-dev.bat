@echo off
rem FinFlow 一键停止（开发模式）—— 双击此文件即可
setlocal
set "ROOT=%~dp0"

where bash >nul 2>&1
if errorlevel 1 (
  if exist "C:\Program Files\Git\bin\bash.exe" (
    set "PATH=C:\Program Files\Git\bin;%PATH%"
  ) else if exist "%ProgramFiles(x86)%\Git\bin\bash.exe" (
    set "PATH=%ProgramFiles(x86)%\Git\bin;%PATH%"
  ) else (
    echo [finflow] 未找到 Git Bash。请先安装 Git for Windows: https://git-scm.com/download/win
    pause
    exit /b 1
  )
)

bash -lc "cd '%ROOT%' && ./scripts/stop-dev.sh"
echo.
pause
