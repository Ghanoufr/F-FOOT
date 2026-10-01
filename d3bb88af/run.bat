@echo off
title Foura Goalkeeper Coach - Serveur reseau
set FOURA_OPEN_BROWSER=1
echo.
echo  ============================================================
echo    Demarrage de FOURA GOALKEEPER COACH...
echo.
echo    L'adresse a partager avec vos collegues sur le meme
echo    reseau (Wi-Fi / Ethernet) s'affichera ci-dessous.
echo.
echo    Si Windows demande l'autorisation reseau, cliquez sur
echo    "Autoriser l'acces" (reseaux prives).
echo  ============================================================
echo.
"%~dp0runtime\python.exe" "%~dp0app.py"
pause
