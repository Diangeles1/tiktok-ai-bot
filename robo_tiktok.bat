@echo off
rem Robo do TikTok: o Agendador de Tarefas do Windows chama este arquivo
rem logo depois de cada horario do YouTube. O log fica em output\robo_tiktok.log.
cd /d "%~dp0"
if not exist output mkdir output
rem caminho completo: o agendador nem sempre enxerga o mesmo PATH do terminal
set PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
if not exist "%PY%" set PY=python
"%PY%" -m src.tiktok_robo >> output\robo_tiktok.log 2>&1
