@echo off
rem ==============================================================================
rem  BHAM - BACS Help Auto Mapper (Windows Double-Click Launcher)
rem  Avvio automatico con auto-provisioning dei prerequisiti (Python / venv / driver)
rem
rem  NOTA: questo file resta volutamente in puro ASCII. La console di Windows usa
rem  per default una code page legacy (850 / 437) e qualunque carattere Unicode
rem  nei messaggi verrebbe mostrato come caratteri illeggibili.
rem ==============================================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"
title BHAM - BACS Help Auto Mapper

rem Code page UTF-8: rende leggibile l'output del processo Python figlio.
chcp 65001 >nul 2>&1

set "BHAM_VERSION=1.3.0"

echo ======================================================================
echo   BHAM - BACS Help Auto Mapper (Field Engineering Station)
echo   https://www.bacshelp.com  ^|  Versione !BHAM_VERSION!
echo ======================================================================

rem -- 1. Verifica se esiste gia' il virtualenv locale .venv --------------------
if exist "%~dp0.venv\Scripts\python.exe" (
    echo [OK] Ambiente virtuale rilevato ^(.venv^). Avvio diretto di BHAM...
    "%~dp0.venv\Scripts\python.exe" bham.py %*
    goto :END
)

rem -- 2. Ricerca interprete Python compatibile (3.12 o 3.13) ------------------
set "PY_EXE="

rem Controllo 2.1: Python Launcher 'py -3.12' / 'py -3.13'
for %%V in (3.12 3.13) do (
    if not defined PY_EXE (
        py -%%V -c "import sys; sys.exit(0 if sys.version_info[:2] in ((3,12),(3,13)) else 1)" >nul 2>&1
        if !errorlevel! equ 0 set "PY_EXE=py -%%V"
    )
)
if defined PY_EXE goto :PYTHON_FOUND

rem Controllo 2.2: Python standard in PATH
python -c "import sys; sys.exit(0 if sys.version_info[:2] in ((3,12),(3,13)) else 1)" >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_EXE=python"
    goto :PYTHON_FOUND
)

rem Controllo 2.3: Installazioni per-user standard in %LOCALAPPDATA%
for %%D in (Python312 Python313) do (
    if not defined PY_EXE (
        if exist "%LOCALAPPDATA%\Programs\Python\%%D\python.exe" set "PY_EXE=%LOCALAPPDATA%\Programs\Python\%%D\python.exe"
    )
)
if defined PY_EXE goto :PYTHON_FOUND

rem -- 3. Python non trovato: richiesta di auto-provisioning all'utente --------
echo.
echo [!] ATTENZIONE: Nessun interprete Python 3.12 / 3.13 rilevato su questo PC.
echo.
echo     BHAM necessita di un runtime Python 3.12 (64-bit) isolato per gestire
echo     le interfacce RS485, i protocolli industriali (Modbus, BACnet, KNX)
echo     e il server locale di collaudo.
echo.
echo     Desideri scaricare e installare automaticamente Python 3.12 ufficiale
echo     da python.org adesso?
echo.
set /p "CHOICE=Procedere con il download e l'installazione automatica? [S/N]: "
if /i "!CHOICE!"=="S" goto :INSTALL_PYTHON
if /i "!CHOICE!"=="SI" goto :INSTALL_PYTHON
if /i "!CHOICE!"=="Y" goto :INSTALL_PYTHON
if /i "!CHOICE!"=="YES" goto :INSTALL_PYTHON

echo.
echo Installazione annullata dall'utente.
echo Per avviare BHAM manualmente, installa Python 3.12 (64-bit) da https://www.python.org
echo selezionando la casella "Add python.exe to PATH", poi rilancia questo file.
pause
goto :END

:INSTALL_PYTHON
echo.
echo Avvio procedura di installazione automatica tramite PowerShell...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bootstrap_windows.ps1" -InstallPython
if !errorlevel! neq 0 (
    echo.
    echo [ERRORE] Impossibile completare l'installazione automatica di Python.
    echo Scarica manualmente Python 3.12 da https://www.python.org/downloads/
    pause
    goto :END
)

rem Rivaluta presenza di Python dopo l'installazione
for %%D in (Python312 Python313) do (
    if not defined PY_EXE (
        if exist "%LOCALAPPDATA%\Programs\Python\%%D\python.exe" set "PY_EXE=%LOCALAPPDATA%\Programs\Python\%%D\python.exe"
    )
)
if defined PY_EXE goto :PYTHON_FOUND

python -c "import sys; sys.exit(0 if sys.version_info[:2] in ((3,12),(3,13)) else 1)" >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_EXE=python"
    goto :PYTHON_FOUND
)

echo.
echo [ERRORE] Python installato ma non ancora visibile nella sessione corrente.
echo Prova a chiudere questa finestra e riaprire bham.bat.
pause
goto :END

:PYTHON_FOUND
echo [OK] Interprete Python rilevato: !PY_EXE!
echo.
echo Passaggio al launcher unificato BHAM...
!PY_EXE! bham.py %*

:END
if !errorlevel! neq 0 (
    echo.
    echo BHAM e' stato arrestato con codice: !errorlevel!
    pause
)
endlocal
