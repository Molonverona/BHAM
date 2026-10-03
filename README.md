# ⚡ BHAM – BACS Help Auto Mapper

> **Industrial Telemetry & Network Discovery Daemon per Building Automation e IoT Industriale**

BHAM è un'applicazione stand-alone per tecnici di collaudo, system integrator ed energy manager. Permette di scansionare rapidamente linee bus e reti Ethernet per identificare dispositivi sul campo, mappare registri e generare documentazione di collaudo (Excel / PDF) in tempo reale.

---

## 🌟 Caratteristiche Principali

- **🗺️ Mappa Topologica Interattiva (Network Graph)**:
  - Visualizzazione ad albero e grafo SVG gerarchico delle reti d'impianto (Host BHAM ➔ Canali RS485 / Ethernet ➔ Dispositivi Modbus, BACnet, KNX, ARP)
  - Engine vettoriale reattivo con Pan & Zoom continuo (rotellina o pulsanti HUD), Fit-to-screen e switch di orientamento (Orizzontale / Verticale)
  - Filtro di ricerca real-time per nome, vendor, IP o Slave ID con evidenziazione visiva immediata dei nodi
  - Quick Node Inspector laterale con dettagli metadati e scorciatoie dirette per BACnet Object Explorer e Modbus Slave Inspector
  - Esportazione istantanea del diagramma topologico vettoriale `.svg` ad alta risoluzione per documentazione tecnica d'impianto
- **🔌 Modbus RTU Ultra-Fast Engine & Smart Register Scan**:
  - Phase Zero: ascolto passivo per auto-baud rate con validazione frame CRC-16 puro Python
  - Early Exit: sentinelle su ID strategici ({1, 2, 10}) per aggancio immediato dei parametri seriali
  - Sweep completo su 247 slave con fast-timeout (120ms) e progress granularità al singolo ID
  - Smart Register Scan: euristica predittiva automatica per identificare registri standard (Holding, Input, Coils, Discretes) ed estrarre la mappa canali delle periferiche
- **🏢 BACnet/IP Discovery & Object Explorer**:
  - Who-Is broadcast nativo async su standard BACnet
  - Gestione I-Am con estrazione metadati: Vendor ID, Vendor Name, Model Name, Firmware & Software Version
  - Supporto per serie porte standard e custom: notazione `BAC0`..`BACF` (47808..47823), range e porte numeriche
  - BACnet Object Explorer gerarchico: navigazione istanze d'oggetto (Analog/Binary/Multi-state Input/Output/Value, Schedules, Trend Logs, Device) con Present Value e Status Flags
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
- **⚡ Intelligence & Session Diff ("Prima vs Dopo")**:
  - Confronto analitico deterministico multi-protocollo tra sessioni archiviate (Baseline) e stato attivo (Live State) o tra due collaudi storicizzati
  - Riconoscimento intelligente riassegnazione indirizzi DHCP su base MAC address per dispositivi Ethernet
  - Monitoraggio variazioni firmware, modello, registri mappati e latenza bus
  - Banner con contatori a 4 stati (🟢 Nuovi, 🔴 Scomparsi, 🟡 Modificati, ⚪ Invariati), filtri granulari ed esportazione `.csv` / `.json`
- **🌐 Attraversamento Router (BBMD) & Foreign Device BACnet/IP**:
  - Superamento delle limitazioni broadcast su reti multi-subnet e VLAN tramite registrazione *Foreign Device* nativa (Annex J)
  - Ispezione diagnostica in tempo reale delle tabelle router: **Broadcast Distribution Table (BDT)** e **Foreign Device Table (FDT)** con countdown TTL
  - Rappresentazione gerarchica dedicata dei router BBMD e dei dispositivi instradati nella Mappa Topologica
- **📊 Reportistica Arricchita As-Built 2.0**:
  - Cartella Excel multi-foglio a **8 fogli di lavoro** stilizzati: `Network Topology`, `Modbus Devices`, `BACnet Devices`, `KNX Devices`, `IP Hosts`, `Modbus Registers` (con valori Hex, Int16, Float32 IEEE), `BACnet Objects` (con Present Value e unità ingegneristiche) e `Report Info`
  - Verbale PDF tecnico vettoriale a due passate con diagramma gerarchico topologico d'impianto ad albero e tabelle as-built complete
  - Esportazione grafica topologica vettoriale (.svg) ad alta definizione
  - Import/Export mappe punti compatibili BACS Help (`/api/v1/maps/*`)
- **🎨 Field Engineer Studio Layout & i18n**:
  - Architettura ergonomica a 2 colonne: Sidebar canali e diagnostica a sinistra (360px) + Workspace centrale con Switcher Vista Tabella/Topologia + Dock Diagnostico Inferiore a scomparsa per Live Console e RS485 Inspector
  - Dual Mode (Dark Mode ad alto contrasto per locali tecnici / Light Mode per visibilità sotto luce solare diretta)
  - Color-coding ergonomico per protocollo (Ciano=Modbus, Viola=BACnet, Arancione=KNX, Smeraldo=ARP, Ambra=Diagnostics)
  - Internazionalizzazione completa (Italiano, Inglese, Spagnolo, **228 chiavi per lingua** con parità 100%) e Manuale Tecnico interattivo a bordo (F1)
- **🛠️ Diagnostica di Campo Avanzata & Launcher Unificato (v0.7.0)**:
  - **Launcher Cross-Platform `bham.py`**: Auto-rilevamento requisiti da `requirements.txt`, installazione interattiva o non-interattiva (`--yes`), fallback automatico a `get-pip.py` e supporto Python 3.12/3.13 su Windows e Linux.
  - **Euristica Livello Fisico Bus RS485**: Diagnosi in tempo reale di riflessioni (terminazione 120Ω mancante), polarità A(+)/B(-) invertita, disturbi o saturazione del polling, con badge e tooltip esplicativi.
  - **Quick Diagnostic Self-Test 1-Click**: Verifica di apertura porte seriali con misurazione della latenza in millisecondi, rilevamento schede di rete e verifica privilegi di sistema (`dialout`/admin/Npcap).
  - **Profili Impianto Rapidi (Preset)**: Configurazione istantanea a 1 click per HVAC Standard, Contatori Energia, Gateway DALI o Ricerche Approfondite.
  - **Centro Impostazioni Riprogettato**: Macro-voci verticali chiare (Adattatori, Connettività, Tema, Sessioni, Mappe) con comodi menu a tendina.

---

## 📋 Requisiti di Sistema

- **Python**: `>= 3.12`
- **OS**: Linux (Debian, Ubuntu, CentOS, Fedora, Arch) o Windows 10/11
- **Privilegi**: L'ARP sniffing e l'accesso diretto alle porte seriali `/dev/ttyUSB*` richiedono permessi adeguati (utente nel gruppo `dialout` su Linux, o `sudo` / `cap_net_raw` per sniffing raw socket).

---

## 🚀 Installazione & Avvio (Windows e Linux) – v0.7.0

Un solo comando, identico su entrambi i sistemi. Il launcher `bham.py` legge `requirements.txt`,
mostra l'elenco dei pacchetti mancanti, chiede conferma, crea il `.venv` isolato, installa tutto,
avvia il server e **apre automaticamente la dashboard nel browser predefinito**.

```bash
python3 bham.py        # Linux (Debian, Ubuntu, Raspberry Pi OS, ecc.)
python  bham.py        # Windows (PowerShell / cmd)
```

Opzioni utili del launcher:

| Flag | Effetto |
|------|---------|
| *(nessuno)* | Verifica/installa dipendenze, avvia il demone e apre il browser |
| `--no-browser` | Avvia il server senza aprire il browser (ideale su Raspberry Pi headless o via SSH) |
| `--yes` / `-y` | Installa le dipendenze senza chiedere conferma interattiva |
| `--check` | Verifica soltanto le dipendenze (exit code `0` = OK, `1` = mancanti) |
| `--no-reload` | Avvia senza auto-reload (consigliato in cantiere per massima stabilità) |

### 🌐 Accesso Remoto da Rete LAN (Raspberry Pi / Mini-PC di Campo)

Se BHAM è installato su un PC di quadro, notebook di cantiere o **Raspberry Pi** connesso all'impianto, è possibile controllarlo da qualsiasi altro PC portatile, tablet o smartphone collegato alla stessa rete (Wi-Fi o Ethernet):

1. Avvia BHAM sul Raspberry Pi / PC: il launcher mostrerà a video gli indirizzi IP assegnati alla scheda di rete.
2. Dal tuo portatile o tablet, apri nel browser l'URL della LAN:
   ```
   http://192.168.x.x:8765
   ```
3. Su Linux, se il firewall di sistema è attivo, consenti la porta:
   ```bash
   sudo ufw allow 8765/tcp
   ```

<details>
<summary>Installazione manuale (alternativa)</summary>

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8765
```

Su Linux resta disponibile anche `./start.sh`, che include i controlli permessi `dialout` / `cap_net_raw`.
</details>

Una volta avviato:
- **Dashboard Web UI**: [http://localhost:8765](http://localhost:8765) (o `http://<IP-LAN>:8765`)
- **Documentazione OpenAPI / Swagger**: [http://localhost:8765/docs](http://localhost:8765/docs)
- **Canale WebSocket Live Telemetry**: `ws://<IP-LAN>:8765/api/v1/ws`

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
│   ├── css/main.css      # Design System Stitch v4.2 Field Engineer Studio
│   ├── index.html        # Studio a 2 Colonne, Mappa Topologica SVG & Centro Impostazioni
│   └── js/
│       ├── app.js            # Controller UI, Motore Topologico SVG, WebSocket client, rendering tabelle
│       ├── i18n.js           # Motore multilingua dinamico (IT, EN, ES - 202 chiavi)
│       └── manual-content.js # Contenuti manuale tecnico integrato (F1)
├── reports/              # Motori di reportistica
│   ├── excel.py          # Generatore Excel multi-foglio (openpyxl)
│   └── pdf.py            # Generatore PDF vettoriale a due passate (ReportLab)
├── scanners/             # Motori di scansione protocolli
│   ├── base.py           # BaseScanner e registri di diagnostica/annullamento
│   ├── bacnet.py         # Scanner BACnet/IP con Who-Is, BAC0..BACF e Object Explorer
│   ├── ip_sniffer.py     # Sniffer ARP/IP (scapy)
│   ├── knx.py            # Scanner UDP KNXnet/IP multicast/broadcast
│   ├── modbus.py         # Scanner Modbus RTU/TCP + FC43 + Smart Register Scan (pymodbus)
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
│   └── test_bham.py      # Test unitari e di integrazione (26 test completi)
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

## 📜 Licenza

Progetto interno confidenziale – BACS Help Auto Mapper (BHAM).
