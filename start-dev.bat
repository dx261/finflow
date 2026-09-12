@echo off
rem FinFlow 一键启动（开发模式）—— 双击此文件即可
rem 效果：Docker 基础设施 + 后端 API(:8000) + Celery worker + 前端(:5173)
setlocal
set "ROOT=%~dp0"

rem 优先用 Git 自带 Bash；Git Bash 不在 PATH 时尝试常见安装路径
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

echo [finflow] 启动 FinFlow 开发环境（日志: .run\logs\）...
bash -lc "cd '%ROOT%' && ./scripts/start-dev.sh %*"
echo.
pause
