@echo off
title AI Remote — 正在重启...
cd /d "%~dp0"

echo ==============================
echo  AI Remote — 手动重启工具
echo ==============================

:: 1. 查找并杀死 8080 端口上的旧进程
echo [1/3] 正在停止旧服务器...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8080 "') do (
    taskkill /F /PID %%a >nul 2>nul
)
timeout /t 2 /nobreak >nul

:: 2. 确认端口已释放
netstat -ano | findstr ":8080 " >nul 2>nul
if %errorlevel% equ 0 (
    echo [错误] 端口 8080 仍在占用，请检查是否有其他程序。
    pause
    exit /b 1
)
echo [完成] 端口已释放

:: 3. 启动服务器
echo [2/3] 正在启动服务器...
start "AI Remote Server" python server.py

:: 4. 等待并验证
timeout /t 3 /nobreak >nul
echo [3/3] 正在验证...

netstat -ano | findstr ":8080 " >nul 2>nul
if %errorlevel% equ 0 (
    echo [成功] AI Remote 已启动！
    echo   本机: http://localhost:8080
    echo   日志: %~dp0server.log
) else (
    echo [错误] 服务器启动失败，请手动运行: python server.py
)

echo ==============================
pause
