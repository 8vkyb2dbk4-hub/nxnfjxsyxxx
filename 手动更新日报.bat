@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -m pip install -r requirements.txt
python scripts\update.py
echo.
echo 更新完成。按任意键关闭。
pause >nul
