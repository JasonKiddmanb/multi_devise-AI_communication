@echo off
chcp 65001 >nul
title AI Remote Compute Mesh - Server

cd /d "%~dp0app"

:: 清理旧进程，释放端口
echo [*] Cleaning up old processes...
taskkill /F /IM python3.exe 2>nul >nul
taskkill /F /IM python.exe  2>nul >nul
timeout /t 2 /nobreak >nul

:: 清空旧日志以便只看本次会话
if exist server.log (
    copy /Y server.log server.log.bak >nul 2>nul
    del /Q server.log >nul 2>nul
)

echo.
echo [*] Starting AI Remote Compute Mesh server...
echo ============================================================
echo   Server: http://localhost:8080
echo   Ctrl+C to stop
echo ============================================================
echo.

:: 直接前台运行 —— 日志实时输出到控制台，和 admin 面板系统日志内容一致
python server.py

echo.
echo [*] Server stopped.
pause
