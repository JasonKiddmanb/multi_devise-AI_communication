@echo off
title 下载 Ollama + Tailscale
cd /d "%~dp0"

echo ========================================
echo   下载 Ollama + Tailscale 到本地 tools/
echo ========================================
echo.

REM --- Ollama ---
set OLLAMA_DIR=%~dp0ollama
if not exist "%OLLAMA_DIR%\ollama.exe" (
    echo [1/2] 正在下载 Ollama...
    curl -L -o "%TEMP%\ollama-windows.zip" https://github.com/ollama/ollama/releases/latest/download/ollama-windows-amd64.zip
    tar -xf "%TEMP%\ollama-windows.zip" -C "%OLLAMA_DIR%" 2>nul
    if exist "%OLLAMA_DIR%\ollama.exe" (
        echo   ^> Ollama 已下载到 tools\ollama\
    ) else (
        echo   ^> 下载失败，请手动下载：
        echo      https://github.com/ollama/ollama/releases/latest/download/ollama-windows-amd64.zip
        echo      ^> 解压到 tools\ollama\
    )
) else (
    echo [1/2] Ollama 已存在，跳过
)

REM --- Tailscale ---
set TS_DIR=%~dp0tailscale
if not exist "%TS_DIR%\tailscale-setup.exe" (
    echo [2/2] 正在下载 Tailscale...
    curl -L -o "%TS_DIR%\tailscale-setup.exe" https://pkgs.tailscale.com/stable/tailscale-setup-latest.exe
    if exist "%TS_DIR%\tailscale-setup.exe" (
        echo   ^> Tailscale 已下载到 tools\tailscale\
    ) else (
        echo   ^> 下载失败，请手动下载：
        echo      https://pkgs.tailscale.com/stable/tailscale-setup-latest.exe
        echo      ^> 放到 tools\tailscale\
    )
) else (
    echo [2/2] Tailscale 已存在，跳过
)

echo.
echo 完成！运行上一级目录的 start.bat 启动服务。
pause
