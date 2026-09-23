@echo off
rem Abre o painel para usar do celular, no mesmo wi-fi deste PC.
rem Aponte a camera do celular para o QR code que aparece nesta janela.
cd /d "%~dp0"
python painel.py --celular
pause
