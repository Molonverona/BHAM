# 📘 BHAM – Manuale Unico di Pubblicazione, Distribuzione & Manutenzione

> **Documento Unificato per Giuliano / BacsHelp**  
> Raccoglie in un unico riferimento pratico tutte le istruzioni, i comandi e le configurazioni per pubblicare BHAM su GitHub, renderlo distribuibile a livello globale tramite **WinGet** e distribuirlo per Linux tramite il dominio **`www.bacshelp.com`**.

---

## 🗺️ Schema Generale di Distribuzione

```text
       ┌────────────────────────────────────────────────────────┐
       │     TU (Sviluppo / Rilascio)                           │
       │     - 1-Click da browser GitHub                        │
       │       OPPURE 1 comando locale: ./scripts/release.sh    │
       └──────────────────────────┬─────────────────────────────┘
                                  │
                                  ▼
       ┌────────────────────────────────────────────────────────┐
       │     GitHub Cloud (Automazione GitHub Actions)          │
       │     - Avanza versione (SemVer) e aggiorna i manifesti  │
       │     - Compila Windows x64 Standalone (PyInstaller)     │
       │     - Compila Linux x64 Standalone + Pacchetto .deb    │
       │     - Calcola Checksum SHA256 ufficiali                │
       │     - Crea GitHub Release con Changelog automatico     │
       └──────────────┬──────────────────────────┬──────────────┘
                      │                          │
                      ▼                          ▼
       ┌──────────────────────────────┐  ┌──────────────────────────────┐
       │   WinGet (Microsoft Store)   │  │   www.bacshelp.com           │
       │   PR automatica a Microsoft  │  │   - One-Line Linux Installer │
       │   Disponibile in tutto il    │  │   - Download permanenti      │
       │   mondo con:                 │  │   - Manuale su sottodominio  │
       │   winget install BacsHelp.BHAM│ │     bham.bacshelp.com        │
       └──────────────┬───────────────┘  └──────────────┬───────────────┘
                      │                                 │
                      ▼                                 ▼
       ┌────────────────────────────────────────────────────────────────┐
       │   TECNICI & SYSTEM INTEGRATOR IN CANTIERE                      │
       │   Windows: winget install BacsHelp.BHAM                        │
       │   Linux:   curl -fsSL https://bacshelp.com/bham/install.sh     │
       └────────────────────────────────────────────────────────────────┘
```

---

## 📑 Indice dei Passaggi Operativi

1. [Fase 1: Primo Push del Progetto su GitHub](#fase-1-primo-push-del-progetto-su-github)
2. [Fase 2: Configurazione GitHub (Permessi & Token WinGet Automatico)](#fase-2-configurazione-github-permessi--token-winget-automatico)
3. [Fase 3: Rilascio Ufficiale della Versione v0.3.0](#fase-3-rilascio-ufficiale-della-versione-v030)
4. [Fase 4: Come i Tecnici Installeranno il Software](#fase-4-come-i-tecnici-installeranno-il-software)
5. [Fase 5: Sfruttare al Massimo www.bacshelp.com](#fase-5-sfruttare-al-massimo-wwwbacshelpcom)
6. [Fase 6: Gestione Automatica delle Versioni Future](#fase-6-gestione-automatica-delle-versioni-future)
7. [Scheda di Controllo Rapida (Cheat Sheet & Troubleshooting)](#scheda-di-controllo-rapida-cheat-sheet--troubleshooting)

---

## 🚀 Fase 1: Primo Push del Progetto su GitHub

Tutto è già pronto e ripulito nel tuo computer locale (`.gitignore`, `LICENSE`, `.github/workflows/`, ecc.).

### 1. Esegui il commit iniziale in locale:
Apri il terminale nella cartella del progetto ed esegui:

```bash
cd /home/giuliano/Documenti/BHAM

# Aggiungi tutti i file puliti al tracking di Git
git add .

# Esegui il primo commit della release
git commit -m "feat: release v0.3.0 - BHAM production release"
```

### 2. Crea il repository su GitHub:
1. Accedi a GitHub con il tuo account (o organizzazione **BacsHelp**).
2. Vai su: **[https://github.com/new](https://github.com/new)**.
3. Compila i campi:
   - **Repository name:** `BHAM`
   - **Description:** `Industrial Telemetry & Network Discovery Daemon for Building Automation (Modbus, BACnet, KNX, ARP)`
   - **Visibility:** **Public** *(necessario per WinGet e per l'accesso pubblico dei tecnici)*.
   - **Initialize repository with:** **NON selezionare nulla** (né README, né .gitignore, né licenza).
4. Clicca su **Create repository**.

### 3. Collega e invia il codice:
Nel terminale della cartella esegui:

```bash
# Collega il repository remoto (usa l'URL del tuo repo)
git remote add origin https://github.com/BacsHelp/BHAM.git

# Invia il codice sul branch principale
git push -u origin main
```

---

## ⚙️ Fase 2: Configurazione GitHub (Permessi & Token WinGet Automatico)

Per consentire a GitHub Actions di creare le release, aggiornare i tag e inviare automaticamente a Microsoft WinGet:

### 1. Abilita i permessi di scrittura di GitHub Actions:
Nel tuo repository su GitHub:
1. Vai su **Settings ➔ Actions ➔ General**.
2. Scorri fino alla sezione **Workflow permissions**.
3. Seleziona: **Read and write permissions**.
4. Clicca **Save**.

### 2. Configura il token per l'aggiornamento automatico di WinGet (Una Tantum):
Questo passaggio evita di dover compilare manifesti a mano o usare tool su Windows:
1. Clicca sulla tua foto profilo in alto a destra su GitHub ➔ **Settings**.
2. Nella colonna sinistra in fondo, clicca su **Developer settings** ➔ **Personal access tokens** ➔ **Tokens (classic)**.
3. Clicca su **Generate new token (classic)**:
   - **Note:** `WinGet Releaser`
   - **Expiration:** Consigliato *No expiration* (o 1 anno)
   - **Select scopes:** Spunta **`public_repo`**
4. Clicca su **Generate token** e copia il codice alfanumerico generato (`ghp_...`).
5. Torna nel repository `BHAM` ➔ **Settings ➔ Secrets and variables ➔ Actions**.
6. Clicca sul pulsante verde **New repository secret**:
   - **Name:** `WINGET_TOKEN`
   - **Secret:** *incolla il token copiato*
7. Clicca **Add secret**.

---

## 📦 Fase 3: Rilascio Ufficiale della Versione v0.3.0

Per avviare la compilazione automatica e pubblicare la prima release ufficiale:

### Opzione A: Direttamente da Browser (Consigliata) 🌟
1. Sul tuo repository GitHub, clicca sulla scheda in alto **Actions**.
2. Nella barra sinistra clicca su **`Release – Standalone Binaries & Winget`**.
3. Clicca a destra sul pulsante **Run workflow**:
   - Seleziona `custom` nel menu a tendina.
   - Nel campo testo scrivi: `0.3.0`
4. Clicca il pulsante verde **Run workflow**.

### Opzione B: Da Terminale Locale
```bash
git tag v0.3.0
git push origin v0.3.0
```

### Cosa accade ora in automatico (in circa 2-3 minuti):
- GitHub Actions crea macchine cloud Windows e Ubuntu.
- Compila gli eseguibili standalone (nessun bisogno di Python per l'utente finale).
- Crea la **Release v0.3.0** pubblica con allegati:
  - `bham-windows-x64.zip` (eseguibile portatile `bham.exe`) + `.sha256`
  - `bham-linux-x64.tar.gz` (binario Linux x86_64) + `.sha256`
  - `bham_0.3.0_amd64.deb` (pacchetto Debian/Ubuntu con servizio di sistema) + `.sha256`
  - `scripts/install.sh` (installer one-line per Linux)
- Invia in automatico a Microsoft la richiesta di pubblicazione per WinGet!

---

## 👥 Fase 4: Come i Tecnici Installeranno il Software

Una volta pubblicata la release, ecco come i tecnici installeranno e useranno BHAM:

### Su Windows (tramite WinGet):
Qualsiasi utente con Windows 10 o Windows 11 apre PowerShell o Prompt dei comandi e digita:
```powershell
winget install BacsHelp.BHAM
```
*BHAM viene scaricato, registrato nel percorso di sistema e reso disponibile immediatamente digitando semplicemente `bham`.*

### Su Linux (qualsiasi distribuzione):
Tramite l'installer one-line da terminale:
```bash
curl -fsSL https://bacshelp.com/bham/install.sh | sudo bash
```
*(Oppure direttamente via GitHub: `curl -fsSL https://raw.githubusercontent.com/BacsHelp/BHAM/main/scripts/install.sh | sudo bash`)*

### Su Debian / Ubuntu / Linux Mint (Pacchetto Nativo .deb):
```bash
sudo apt install ./bham_0.3.0_amd64.deb
```

---

## 🌐 Fase 5: Sfruttare al Massimo www.bacshelp.com

Il dominio `www.bacshelp.com` può diventare il centro unico di controllo per l'identità del software.

### 1. Script di Installazione sul Web Server
Carica il file [`scripts/install.sh`](file:///home/giuliano/Documenti/BHAM/scripts/install.sh) sul tuo server web nel percorso:
`https://www.bacshelp.com/bham/install.sh`

### 2. Redirect Stabili (Consigliati su Nginx / Apache / Cloudflare)
Imposta questi 3 redirect permanenti (302) per offrire link eleganti che non cambiano mai tra una versione e l'altra:

| Link sul tuo dominio | Reindirizza automaticamente a: |
|---|---|
| `https://www.bacshelp.com/bham/download/windows` | `https://github.com/BacsHelp/BHAM/releases/latest/download/bham-windows-x64.zip` |
| `https://www.bacshelp.com/bham/download/deb` | `https://github.com/BacsHelp/BHAM/releases/latest/download/bham_0.3.0_amd64.deb` |
| `https://www.bacshelp.com/bham/download/linux` | `https://github.com/BacsHelp/BHAM/releases/latest/download/bham-linux-x64.tar.gz` |

### 3. Portale Documentazione su Sottodominio (`bham.bacshelp.com`)
1. Nel pannello DNS del registrar di `bacshelp.com`, aggiungi un record **CNAME**:
   - **Host:** `bham`
   - **Destinazione:** `BacsHelp.github.io`
2. Nelle impostazioni del repository GitHub ➔ **Settings ➔ Pages**:
   - Seleziona branch `main` (radice `/`)
   - Nel campo **Custom domain** inserisci `bham.bacshelp.com`
Il manuale tecnico completo sarà online all'indirizzo istituzionale **`https://bham.bacshelp.com`**.

---

## 🔄 Fase 6: Gestione Automatica delle Versioni Future

Quando in futuro apporterai modifiche o aggiungerai nuove feature, il rilascio di un aggiornamento richiederà **solo 1 click**:

### Metodo Web (1-Click dal Browser) 🌟
1. Vai su GitHub ➔ scheda **Actions** ➔ **Release – Standalone Binaries & Winget**.
2. Clicca su **Run workflow**.
3. Seleziona l'incremento:
   - `patch`: per correzioni minori (es. `0.3.0` ➔ `0.3.1`)
   - `minor`: per nuove feature o nuovi protocolli (es. `0.3.0` ➔ `0.4.0`)
   - `major`: per release architetturali (es. `0.3.0` ➔ `1.0.0`)
4. Clicca sul pulsante verde.

**Fine del tuo lavoro.**  
GitHub Actions aggiornerà tutti i file di versione, creerà il tag, compilerà i binari Windows e Linux, pubblicherà la nuova release e aggiornerà WinGet in automatico.

### Metodo da Terminale Locale (Alternativo)
Se preferisci farlo dal tuo terminale:
```bash
# Esegui lo script di rilascio passando patch, minor o major:
./scripts/release.sh patch

# Invia le modifiche al cloud:
git push origin main --tags
```

---

## 📋 Scheda di Controllo Rapida (Cheat Sheet & Troubleshooting)

### File di Infrastruttura Presenti nel Repository
- [`.github/workflows/ci.yml`](file:///home/giuliano/Documenti/BHAM/.github/workflows/ci.yml): Esegue test automatici su Linux e Windows.
- [`.github/workflows/release.yml`](file:///home/giuliano/Documenti/BHAM/.github/workflows/release.yml): Pipeline cloud con build PyInstaller, pacchetti `.deb` e invio WinGet.
- [`scripts/bump_version.py`](file:///home/giuliano/Documenti/BHAM/scripts/bump_version.py): Motore di sincronizzazione versioni SemVer.
- [`scripts/release.sh`](file:///home/giuliano/Documenti/BHAM/scripts/release.sh): Script per rilascio con 1 comando dal terminale.
- [`scripts/package_deb.sh`](file:///home/giuliano/Documenti/BHAM/scripts/package_deb.sh): Compilatore pacchetti Debian nativi con permessi dialout.
- [`scripts/install.sh`](file:///home/giuliano/Documenti/BHAM/scripts/install.sh): Script one-liner di installazione per tecnici.
- [`winget/`](file:///home/giuliano/Documenti/BHAM/winget): Template manifesti ufficiali Microsoft WinGet.

### Troubleshooting Comune

| Problema | Causa | Soluzione |
|---|---|---|
| L'Action fallisce con `permission denied to github-actions[bot]` | Mancano permessi di scrittura ad Actions | Vai su Repo ➔ *Settings ➔ Actions ➔ General ➔ Workflow permissions* e seleziona **Read and write permissions**. |
| L'Action completa ma WinGet non si aggiorna | Manca il segreto `WINGET_TOKEN` | Genera un token GitHub classico con permesso `public_repo` e salvalo come segreto `WINGET_TOKEN` nelle impostazioni del repo. |
| Su Linux la porta seriale `/dev/ttyUSB0` dà errore di permessi | Utente non nel gruppo `dialout` | Lo script `install.sh` o il pacchetto `.deb` aggiungono automaticamente l'utente a `dialout`. In caso manuale: `sudo usermod -aG dialout $USER` e riavvia la sessione. |
