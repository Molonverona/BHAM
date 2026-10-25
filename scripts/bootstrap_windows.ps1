<#
.SYNOPSIS
    BHAM – Windows Autonomous Bootstrap & Prerequisite Provisioner
.DESCRIPTION
    Verifica e installa in autonomia (su conferma utente) i prerequisiti per BHAM su Windows:
    - Python 3.12 ufficiale a 64 bit (python.org) con pip e PATH abilitati
    - Driver di cattura pacchetti Npcap (npcap.com) per sniffing di rete L2 / ARP
.EXAMPLE
    .\bootstrap_windows.ps1 -InstallPython
    .\bootstrap_windows.ps1 -InstallNpcap
    .\bootstrap_windows.ps1 -CheckOnly
#>

[CmdletBinding()]
param (
    [switch]$InstallPython,
    [switch]$InstallNpcap,
    [switch]$CheckOnly,
    [switch]$Silent
)

# Forza TLS 1.2 / 1.3 per connessioni HTTPS sicure su Windows 10/11
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13

$PYTHON_VERSION = "3.12.8"
$PYTHON_URL = "https://www.python.org/ftp/python/$PYTHON_VERSION/python-$PYTHON_VERSION-amd64.exe"
$PYTHON_TARGET = "$env:TEMP\python-$PYTHON_VERSION-amd64.exe"

$NPCAP_VERSION = "1.80"
$NPCAP_URL = "https://npcap.com/dist/npcap-$NPCAP_VERSION.exe"
$NPCAP_TARGET = "$env:TEMP\npcap-$NPCAP_VERSION.exe"

function Write-Info($msg) {
    Write-Host "[BHAM-BOOTSTRAP] $msg" -ForegroundColor Cyan
}

function Write-Success($msg) {
    Write-Host "[BHAM-BOOTSTRAP] $msg" -ForegroundColor Green
}

function Write-Warn($msg) {
    Write-Host "[BHAM-BOOTSTRAP] $msg" -ForegroundColor Yellow
}

function Write-Err($msg) {
    Write-Host "[BHAM-BOOTSTRAP] $msg" -ForegroundColor Red
}

function Test-PythonInstalled {
    # Verifica presenza py launcher o python standard
    try {
        $pyCmd = Get-Command "py" -ErrorAction SilentlyContinue
        if ($pyCmd) {
            $ver = & py -3.12 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if ($ver -eq "3.12" -or $ver -eq "3.13") { return $true }
        }
    } catch {}

    try {
        $pythonCmd = Get-Command "python" -ErrorAction SilentlyContinue
        if ($pythonCmd) {
            # Esclude alias Microsoft Store stub (size 0 o percorso WindowsApps senza interprete effettivo)
            if ($pythonCmd.Source -notmatch "WindowsApps") {
                $ver = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
                if ($ver -eq "3.12" -or $ver -eq "3.13") { return $true }
            }
        }
    } catch {}

    # Controllo cartella standard per-user
    $userPy = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
    if (Test-Path $userPy) {
        return $true
    }

    return $false
}

function Test-NpcapInstalled {
    $candidates = @(
        "$env:SystemRoot\System32\Npcap\wpcap.dll",
        "$env:SystemRoot\System32\wpcap.dll",
        "$env:SystemRoot\SysWOW64\Npcap\wpcap.dll",
        "$env:SystemRoot\SysWOW64\wpcap.dll"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { return $true }
    }
    return $false
}

if ($CheckOnly) {
    $hasPy = Test-PythonInstalled
    $hasNpcap = Test-NpcapInstalled
    Write-Host "Python: $hasPy"
    Write-Host "Npcap: $hasNpcap"
    exit 0
}

# ── 1. INSTALLAZIONE AUTONOMA PYTHON ─────────────────────────────────────────
if ($InstallPython) {
    Write-Info "Verifica disponibilità Python 3.12..."
    if (Test-PythonInstalled) {
        Write-Success "Python compatibile è già installato nel sistema."
    } else {
        # Tentativo 1: winget (se presente su Windows 10/11)
        $winget = Get-Command "winget" -ErrorAction SilentlyContinue
        $installedViaWinget = $false
        if ($winget) {
            Write-Info "Trovato Windows Package Manager (winget). Tentativo di installazione rapida..."
            try {
                $process = Start-Process "winget" -ArgumentList "install --id Python.Python.3.12 --exact --silent --accept-source-agreements --accept-package-agreements" -Wait -PassThru -NoNewWindow
                if ($process.ExitCode -eq 0) {
                    Write-Success "Python 3.12 installato con successo via winget."
                    $installedViaWinget = $true
                }
            } catch {
                Write-Warn "Installazione winget non riuscita, procedo con il download diretto da python.org..."
            }
        }

        # Tentativo 2: Download diretto da python.org
        if (-not $installedViaWinget) {
            Write-Info "Download di Python $PYTHON_VERSION ufficiale da python.org..."
            Write-Info "URL: $PYTHON_URL"
            try {
                $wc = New-Object System.Net.WebClient
                $wc.DownloadFile($PYTHON_URL, $PYTHON_TARGET)
            } catch {
                Write-Err "Download fallito tramite WebClient, ritento con Invoke-WebRequest..."
                Invoke-WebRequest -Uri $PYTHON_URL -OutFile $PYTHON_TARGET -UseBasicParsing
            }

            if (-not (Test-Path $PYTHON_TARGET)) {
                Write-Err "Impossibile scaricare l'installer di Python. Verifica la connessione Internet."
                exit 1
            }

            Write-Info "Esecuzione installazione Python 3.12 (modalità controllata per utente corrente)..."
            $installArgs = "/passive InstallAllUsers=0 PrependPath=1 Include_pip=1 SimpleInstall=1"
            $proc = Start-Process -FilePath $PYTHON_TARGET -ArgumentList $installArgs -Wait -PassThru

            if ($proc.ExitCode -ne 0) {
                Write-Err "Installazione Python terminata con codice di errore $($proc.ExitCode)."
                exit $proc.ExitCode
            }
            Write-Success "Python 3.12 installato con successo!"
        }

        # Aggiorna il PATH per la sessione corrente
        $pyPath = "$env:LOCALAPPDATA\Programs\Python\Python312"
        $pyScripts = "$env:LOCALAPPDATA\Programs\Python\Python312\Scripts"
        $env:Path = "$pyPath;$pyScripts;" + $env:Path
    }
}

# ── 2. INSTALLAZIONE AUTONOMA NPCAP ──────────────────────────────────────────
if ($InstallNpcap) {
    Write-Info "Verifica presenza driver Npcap per Windows..."
    if (Test-NpcapInstalled) {
        Write-Success "Driver Npcap già presente nel sistema."
    } else {
        Write-Info "Download installer ufficiale Npcap $NPCAP_VERSION..."
        Write-Info "URL: $NPCAP_URL"
        try {
            $wc = New-Object System.Net.WebClient
            $wc.Headers.Add("User-Agent", "BHAM-Bootstrap/1.2.5")
            $wc.DownloadFile($NPCAP_URL, $NPCAP_TARGET)
        } catch {
            Invoke-WebRequest -Uri $NPCAP_URL -OutFile $NPCAP_TARGET -UseBasicParsing -UserAgent "BHAM-Bootstrap/1.2.5"
        }

        if (-not (Test-Path $NPCAP_TARGET)) {
            Write-Err "Impossibile scaricare l'installer di Npcap. Visita manualmente https://npcap.com"
            exit 1
        }

        Write-Info "Avvio installer Npcap (richiede privilegi Amministratore)..."
        Write-Warn "IMPORTANTE: Durante l'installazione di Npcap, assicurati di selezionare:"
        Write-Warn "  [X] 'Install Npcap in WinPcap API-compatible Mode'"
        Start-Process -FilePath $NPCAP_TARGET -Verb RunAs -Wait
        Write-Success "Installazione Npcap completata o finestra chiusa."
    }
}

exit 0
