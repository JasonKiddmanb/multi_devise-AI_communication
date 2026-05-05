@echo off
title AI Remote Compute Mesh — 启动中...
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "start.ps1"
pause
