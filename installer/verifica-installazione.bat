@echo off
rem ==============================================================================
rem  BHAM - Verifica installazione (diagnostica di campo)
rem  Lanciato dal collegamento creato dall'installer nel menu Start.
rem  File volutamente in puro ASCII: la console di Windows usa per default una
rem  code page legacy e i caratteri Unicode risulterebbero illeggibili.
rem ==============================================================================

chcp 65001 >nul 2>&1
title BHAM - Verifica installazione

echo ======================================================================
echo   BHAM - Verifica installazione
echo ======================================================================
echo.
echo Controllo di preflight e caricamento dei motori di protocollo...
echo.

"%~dp0bham.exe" --check
set "RC=%errorlevel%"

echo.
echo ======================================================================
if "%RC%"=="0" (
    echo   ESITO: installazione corretta. BHAM e' pronto all'uso.
) else (
    echo   ESITO: rilevati problemi ^(codice %RC%^).
    echo.
    echo   - Voci [ASSENTE]: il pacchetto e' incompleto, reinstalla BHAM.
    echo   - Voci [LIMITATO]: manca un driver di sistema ^(tipicamente Npcap^);
    echo     il pacchetto e' integro e le altre funzioni restano operative.
)
echo ======================================================================
echo.
pause
exit /b %RC%
