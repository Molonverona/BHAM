# ⚡ BHAM – BACS Help Auto Mapper

> **Industrial Telemetry & Network Discovery Daemon per Building Automation e IoT Industriale**

BHAM è un'applicazione stand-alone per tecnici di collaudo, system integrator ed energy manager. Permette di scansionare rapidamente linee bus e reti Ethernet per identificare dispositivi sul campo, mappare registri e generare documentazione di collaudo (Excel / PDF) in tempo reale.

---

## 🌟 Caratteristiche Principali

- **🔌 Modbus RTU Ultra-Fast Engine**:
  - Phase Zero: ascolto passivo per auto-baud rate con validazione frame CRC-16 puro Python
  - Early Exit: sentinelle su ID strategici ({1, 2, 10}) per aggancio immediato dei parametri seriali
  - Sweep completo su 247 slave con fast-timeout (120ms) e progress granularità al singolo ID
- **🌐 Modbus TCP Multi-Port**:
  - Scansione asincrona concorrente con pool bilanciato (`asyncio.Semaphore(20)`) su singoli IP o intere subnet CIDR
  - Supporto per porte standard (502), porte custom multiple (`502, 503, 5020`) e range (`502-505`)
- **🏢 BACnet/IP Discovery**:
  - Who-Is broadcast nativo async su standard BACnet
  - Gestione I-Am con estrazione metadati: Vendor ID, Vendor Name, Model Name, Firmware & Software Version
  - Supporto per serie porte standard e custom: notazione `BAC0`..`BACF` (47808..47823), range e porte numeriche
- **🏠 KNXnet/IP Discovery**:
  - Scanner asincrono UDP conforme allo standard KNXnet/IP Core (SEARCH_REQUEST / SEARCH_RESPONSE)
  - Multicast 224.0.23.12:3671 con fallback broadcast LAN; parsing DIB Device Info (Area.Linea.Device, seriale, MAC, medium TP1/IP/RF)
- **🕵️ Sniffer Seriale Passivo (RS485 Zero-TX / Stealth Mode)**:
  - Ascolto al 100% passivo e silenzioso su bus RS485 attivi con PLC Master in marcia (Carel, Siemens, Schneider, ecc.) senza collisioni o disturbi
  - Auto-aggancio dinamico baudrate e parità (9600..115200, N/E/O)
  - Dissettore Modbus RTU: differenziazione automatica Master Query (M➔S) e Slave Response (S➔M), decodifica FC01..FC16, FC43 ed estrazione registri
  - Dissettore BACnet MS-TP: riconoscimento preambolo 0x55 0xFF, Header CRC-8, Data CRC-16, monitoraggio Token Ring e nodi
  - Telemetria Bus Health in tempo reale: FPS, Packet Error Rate (PER %), stima Bus Load % e mappa nodi attivi
- **📡 ARP Sniffer**:
  - Rilevamento passivo e attivo degli host connessi sulla subnet locale tramite Scapy
- **🔬 FC43 Device Identification**:
  - Lettura Modbus ME 0x0E (Read Device Identification) per estrarre VendorName, ProductCode, MajorMinorRevision
- **🎨 Design System v2.0 "Industrial Telemetry" & i18n**:
  - Dual Mode (Dark Mode ad alto contrasto per locali tecnici / Light Mode per visibilità sotto luce solare diretta)
  - Color-coding ergonomico per protocollo (Ciano=Modbus, Viola=BACnet, Arancione=KNX, Smeraldo=ARP, Ambra=Diagnostics)
  - Live Console e RS485 Inspector dedicato a schede indipendenti con filtri e streaming WebSocket
  - Internazionalizzazione completa (Italiano, Inglese, Spagnolo) e Manuale Tecnico interattivo a bordo (F1)
- **📊 Reportistica e Mappatura Punti**:
  - Esportazione istantanea Excel (.xlsx) con fogli separati e formattazione industriale
  - Esportazione PDF tecnico vettoriale (ReportLab) con copertina impianto, totali e tabelle color-coded
  - Import/Export mappe punti compatibili BACS Help (`/api/v1/maps/*`)
- **💾 Gestione Sessioni e Riconoscimento HW**:
  - Rilevamento automatico convertitori USB↔RS485 (FTDI, Silicon Labs CP210x, CH340, Prolific)
  - Selezione interfacce di rete attive con modalità single-interface
  - Centro Impostazioni Unificato (5 schede) e ripristino snapshot sessioni salvate

---

## 📋 Requisiti di Sistema

- **Python**: `>= 3.12`
- **OS**: Linux (Debian, Ubuntu, CentOS, Fedora, Arch) o Windows 10/11
- **Privilegi**: L'ARP sniffing e l'accesso diretto alle porte seriali `/dev/ttyUSB*` richiedono permessi adeguati (utente nel gruppo `dialout` su Linux, o `sudo` / `cap_net_raw` per sniffing raw socket).

---

## 🚀 Installazione Rapida

### 1. Clonare il repository ed entrare nella directory

```bash
cd /home/giuliano/Documenti/BHAM
```

### 2. Creare e attivare l'ambiente virtuale

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

### 3. Installare le dipendenze

```bash
pip install -r requirements.txt
```

---

## 💻 Avvio Applicazione

Avviare con lo script rapido:

```bash
./start.sh
```

Oppure con uvicorn:

```bash
.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8765 --reload
```

Una volta avviato:
- **Dashboard Web UI**: [http://localhost:8765](http://localhost:8765)
- **Documentazione OpenAPI / Swagger**: [http://localhost:8765/docs](http://localhost:8765/docs)
- **Canale WebSocket Live Telemetry**: `ws://localhost:8765/api/v1/ws`

---

## ⚙️ Guida al Primo Collaudo

1. **Setup Sessione**:
   All'apertura della UI, viene mostrato il modal di configurazione:
   - Cliccare su **🔍 Scansiona** per rilevare la porta RS485 (es. `/dev/ttyUSB0`)
   - Cliccare su **🔍 Scansiona** per rilevare l'interfaccia di rete (es. `eth0` o `wlan0`)
   - Inserire il nome impianto / cliente e cliccare **✓ Conferma Configurazione**
2. **Avvio Scansioni**:
   - **Modbus RTU**: Selezionare baudrate e range ID (default 1-247) e premere **▶ Avvia RTU**
   - **BACnet/IP**: Premere **▶ Who-Is Broadcast** per interrogare l'intera subnet
   - **ARP Sniffer**: Specificare la durata (es. 30s) e premere **▶ Avvia Sniffing**
3. **Esportazione Risultati**:
   - Cliccare sui bottoni in alto **⬇ Excel** o **⬇ PDF** per scaricare i report completi.
   - Usare **💾 Salva** per salvare un'istantanea persistente nella cartella `sessions/`.

---

## 🗺️ API Mappe BACS Help (`/api/v1/maps`)

- `POST /api/v1/maps/import`: Riceve un JSON con punti e registri per uno o più slave ID.
- `GET /api/v1/maps/export`: Scarica il file JSON consolidato di tutti gli slave registrati.
- `GET /api/v1/maps/{slave_id}`: Ritorna l'elenco dei punti mappati per lo slave specificato.

---

## 📦 Compilazione Eseguibile Standalone (PyInstaller)

Per creare un eseguibile autonomo senza dipendenze Python esterne sul PC target di collaudo:

```bash
# Attivare l'ambiente virtuale
source .venv/bin/activate

# Installare pyinstaller se non presente
pip install pyinstaller

# Compilare tramite spec file
pyinstaller bham.spec
```

L'eseguibile binario standalone verrà generato in `dist/bham`.

---

## 📁 Struttura del Progetto

```
BHAM/
├── api/                  # Endpoint FastAPI (REST & WebSocket)
│   ├── routes.py         # Route HTTP + WebSocket
│   └── websockets.py     # Gestore connessioni e broadcast queue
├── core/                 # Infrastruttura core
│   ├── config.py         # Impostazioni e variabili d'ambiente
│   ├── hw_discovery.py   # Rilevamento seriale RS485 e NIC di sistema
│   ├── logger.py         # Logger asincrono e log per-sessione
│   └── session_store.py  # Persistenza sessioni JSON su disco
├── data/                 # Modelli e stato applicativo
│   ├── maps_manager.py   # Gestione import/export mappe BACS Help
│   ├── models.py         # Modelli Pydantic v2
│   └── state.py          # Singleton di stato in-memory thread-safe
├── frontend/             # Interfaccia Utente
│   ├── css/main.css      # Design System Stitch v2.0 Industrial Telemetry
│   ├── index.html        # Struttura dashboard a 3 colonne & Centro Impostazioni
│   └── js/
│       ├── app.js            # Controller UI, WebSocket client, rendering tabelle
│       ├── i18n.js           # Motore multilingua dinamico (IT, EN, ES)
│       └── manual-content.js # Contenuti manuale tecnico integrato (F1)
├── reports/              # Motori di reportistica
│   ├── excel.py          # Generatore Excel multi-foglio (openpyxl)
│   └── pdf.py            # Generatore PDF vettoriale a due passate (ReportLab)
├── scanners/             # Motori di scansione protocolli
│   ├── bacnet.py         # Scanner BACnet/IP con Who-Is e supporto BAC0..BACF
│   ├── ip_sniffer.py     # Sniffer ARP/IP (scapy)
│   ├── knx.py            # Scanner UDP KNXnet/IP multicast/broadcast
│   ├── modbus.py         # Scanner Modbus RTU/TCP + FC43 ME 0x0E (pymodbus)
│   └── serial_sniffer.py # Sniffer passivo RS485 Zero-TX, Modbus/BACnet MS-TP & Bus Health
├── scripts/              # Script di automazione, installazione e packaging
│   ├── bump_version.py   # Aggiornamento automatico versione SemVer
│   ├── install.sh        # Installer Linux universale one-line (curl | bash)
│   ├── package_deb.sh    # Compilatore pacchetto Debian/Ubuntu .deb
│   └── release.sh        # Script rilascio 1-comando locale
├── winget/               # Manifesti ufficiali Microsoft WinGet
│   ├── BacsHelp.BHAM.yaml
│   ├── BacsHelp.BHAM.installer.yaml
│   └── BacsHelp.BHAM.locale.en-US.yaml
├── sessions/             # Storage sessioni JSON e log storici
├── tests/                # Test suite automatizzata
│   └── test_bham.py      # Test unitari e di integrazione (22 test)
├── .github/workflows/    # Automazioni GitHub Actions
│   ├── ci.yml            # Test suite automatica su Linux e Windows
│   └── release.yml       # Build stand-alone, pacchetti .deb e auto-submit WinGet
├── GUIDA_PUBBLICAZIONE_DISTRIBUZIONE.md # Manuale unico operativo di pubblicazione
├── MANUALE_UTENTE.md     # Manuale d'uso completo per consultazione offline
├── LICENSE               # Licenza Open Source MIT
├── bham.spec             # Specifica packaging PyInstaller standalone
├── DEVLOG.md             # Registro cronologico delle sessioni di sviluppo
├── pyproject.toml        # Configurazione packaging PEP 621
├── requirements.txt      # Dipendenze pinnate
└── main.py               # Entrypoint applicativo FastAPI
```

---

## 📜 Licenza - MIT
