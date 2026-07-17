@echo off
cd /d "%~dp0"
call crawler\Scripts\activate
python apollo_scraper_with_sessions.py