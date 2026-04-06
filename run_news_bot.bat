@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
cd /d C:\Users\neulb\OneDrive\Documents\jieum_bot\japan-news-bot
python -X utf8 test_run.py >> logs\run.log 2>&1
