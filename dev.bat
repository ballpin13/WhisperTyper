@echo off
cd /d "%~dp0"
git pull
.venv\Scripts\python main.py
