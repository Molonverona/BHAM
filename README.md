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
  - Internazionalizzazione completa (Italiano, Inglese, Spagnolo, **289 chiavi per lingua** con parità 100%) e Manuale Tecnico interattivo a bordo (F1, 22 capitoli)
- **📈 Live Watch List & Polling Registri (v1.0.0 Stable)**:
  - Monitoraggio continuo in tempo reale di registri Modbus (Holding/Input) a intervalli configurabili (500ms..5s)
  - Evidenziazione visiva reattiva dei delta con transizioni cromatiche e buzzer acustico hands-free (Web Audio API)
  - Esportazione istantanea del log campionamenti cronologico in formato CSV
- **🔬 RS485 Stress Test & Latency Benchmark (v1.0.0 Stable)**:
  - Benchmark fisico del bus seriale con raffiche calibrate di pacchetti
  - Calcolo live di Packet Error Rate (PER %), latenza RTT (min, max, avg), jitter e frame scartati per CRC
  - Diagnostica fisica guidata di terminazioni mancanti o disturbi EMI e suggerimento analitico del baudrate ottimale
- **📑 BMS/SCADA Multi-Vendor Tag Exporter (v1.0.0 Stable)**:
  - Generazione file d'importazione nativi per Tridium Niagara 4 (XML), Siemens Desigo CC (CSV), Schneider EcoStruxure (CSV) e BACnet CSV generico
- **📱 Accesso Mobile Hands-Free con Pairing QR Code (v1.0.0 Stable)**:
  - Generatore vettoriale SVG standalone di QR Code per connessione immediata da tablet/smartphone in cantiere sulla LAN (`0.0.0.0:8765`), 100% offline
- **✅ As-Built Commissioning Checklist & Certificazione (v1.0.0 Stable)**:
  - Validazione dispositivo per dispositivo con stato di conformità ('ok', 'warning', 'failed', 'pending'), note tecniche e firma del collaudatore integrata nel verbale finale
- **🌐 BACS IP Scanner Avanzato & OUI Recognition (v0.9.0)**:
  - Scansione asincrona parallela ad alta concorrenza (50 task) di subnet CIDR e range IP (`192.168.1.0/24`, `10.0.0.1-50`)
  - Database integrato IEEE OUI con oltre 100 produttori BACS, HVAC, PLC e Building Automation (Schneider, Siemens, Honeywell, Carel, WAGO, Beckhoff, Moxa, Tridium, Belimo, ABB, Carlo Gavazzi, Danfoss, Phoenix Contact, Johnson Controls, ecc.) con lookup $O(1)$
  - Risoluzione dei nomi host multi-livello con fallback automatico: reverse DNS PTR e NetBIOS Name Service (UDP 137 RFC 1002)
  - Port scanner selettivo per servizi BACS: Modbus TCP (502), BACnet/IP (47808), KNXnet/IP (3671), Web GUI (80/443/8080/8443), Niagara Fox (1911) e MQTT (1883)
- **🧙‍♂️ BACS Discovery Wizard & Adaptive Fallback (v0.9.0)**:
  - Procedura guidata 4-step per il commissioning assistito d'impianto con auto-detect periferiche hardware
  - Fallback adattivo seriale RS485 (se 9600 8N1 fallisce, attiva automaticamente scansione a matrice o 15s di Zero-TX sniffer passivo)
- **🔍 1-Click Device Lens (v0.9.0)**:
  - Scheda tecnica aggregata per ciascun dispositivo di campo con ricerca online immediata dei manuali/datasheet PDF e mappatura 1-click profili Modbus
- **📚 Libreria Profili Modbus Industriali & Custom Manager (v0.9.0)**:
  - **13 Profili Preconfigurati Industriali**: Multimetri (ABB B23, Carlo Gavazzi EM24/EM111, IME Nemo 96, Schneider Acti9 iEM3150 e PM5350, Siemens SENTRON PAC3200), Contabilizzatori ed Energia (Belimo Energy Valve EV, Isoil ISOMAG, Diehl/Hydrometer Sharky 775, Emerson Rosemount 8712), Attuatori & Regolatori HVAC (Belimo Servocomandi Modbus, Trox VAV Compact, iSMA-B-4I4O, Riello Condexa Pro, Carel pCO).
  - **Custom Profiles Manager**: Creazione e modifica profili personalizzati, import/export JSON e funzione "⚡ Applica a Slave" per l'iniezione istantanea dei registri nella vista live e nelle mappe d'impianto.
- **🔒 Blocco Sicurezza Manovre (Safe Mode Interlock Permanente) (v0.9.0)**:
  - Protezione attiva non-disattivabile contro comandi e forzature accidentali su registri Modbus e override BACnet (blocco predefinito HTTP 403 Forbidden).
  - Procedura di sblocco temporizzata e vincolata a: Nome Tecnico/Operatore, Commessa / Ordine di Lavoro, e durata finestra temporale (15..120 min) con auto-disarmo e badge visivo dinamico.
- **📜 Registro Manovre Certificato (Crash-Proof WAL & Chaining SHA-256) (v0.9.0)**:
  - Write-Ahead Log su file append-only `audit_journal.jsonl`.
  - Registrazione preventiva dell'intento con `os.fsync` forzato prima della trasmissione fisica sul bus o su IP.
  - Concatenazione crittografica immutabile stile blockchain: ogni riga calcola `entry_hash = SHA-256(prev_hash + campi)`.
  - Auto-recovery degli intenti orfani al riavvio in caso di blackout o cadute di tensione.
  - Verifica forense dell'integrità del registro con rilevamento manomissioni ed esportazione JSON certificata.
- **📦 Packaging Standalone Unificato & Firma Digitale (SignPath / GPG) (v0.9.0)**:
  - Risoluzione runtime dei percorsi tramite `core/paths.py`: supporto per PyInstaller congelato (`sys._MEIPASS`), rilevamento modalità portatile (`portable.flag`) e fallback su percorsi standard di sistema (`%LOCALAPPDATA%` / `~/.local/share/bham`).
  - Installer Windows Inno Setup x64 pulito (`installer/bham.iss`).
  - Pipeline GitHub Actions con firma autenticata Windows via SignPath (`SignPath/github-action-submit-signing-request@v2`).
  - Script dedicato per firma digitale autonoma su Linux tramite GPG e dpkg-sig (`scripts/sign_linux.sh`).
- **⚡ Banco Prova Operativo ("Field Operational Tools") & Override (v0.9.0)**:
  - **Modbus Quick Commander**: Lettura puntuale (FC01..FC04) e scrittura rapida (FC05, FC06, FC15, FC16) su Modbus RTU/TCP con decodifica scientifica multiformato (UInt16, Int16 signed, Float32 Big/Little Endian swapped, Hex, Coils).
  - **BACnet Point Commander & Priority Array**: Override manuale su uscite analogiche/binarie con Priority Array (default: Priorità 8 – Manual Operator) e comando di Relinquish.
- **🌱 Simulatore Virtuale d'Impianto BACS ("Demo Mode") & Telemetria Dinamica (v0.9.0)**:
  - Impianto HVAC sintetico completo (Chiller Climaveneta, Pompa Grundfos Inverter, Power Meter Schneider PM5350, UTA 01 BACnet con 12 oggetti, VAV Uffici con 4 oggetti, Gateway/Sensori KNX, nodi IP/ARP).
  - Telemetria dinamica sinusoidale in background ed emissione periodica di impulsi WebSocket per test e dimostrazioni offline senza hardware.
- **🛡️ Resilienza Hardware & Hot-Plug Auto-Recovery (v0.9.0)**:
  - Tolleranza totale a disconnessioni accidentali del convertitore USB↔RS485 (FTDI, CH340, CP210x, Moxa UPort 1150 / TI 3410) senza crash del daemon.
  - Auto-riconnessione automatica in background ed eventi WebSocket `hardware_disconnect` / `hardware_reconnect` con notifiche toast non bloccanti.
- **🛠️ Diagnostica di Campo Avanzata & Launcher Unificato (v0.9.0)**:
  - **Launcher Cross-Platform `bham.py`**: Auto-rilevamento requisiti da `requirements.txt`, installazione interattiva o non-interattiva (`--yes`), fallback automatico a `get-pip.py` e supporto Python 3.12/3.13 su Windows e Linux.
  - **Live Log Viewer Dock**: Filtraggio per livello di gravità (`ALL`, `DEBUG`, `INFO`, `WARN`, `ERROR`), ricerca rapida con auto-scroll e streaming strutturato.
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

## 🚀 Installazione & Avvio (Windows e Linux) – v1.3.0

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
- **Documentazione OpenAPI / Swagger UI**: [http://localhost:8765/docs](http://localhost:8765/docs)
- **Documentazione ReDoc**: [http://localhost:8765/redoc](http://localhost:8765/redoc)
- **Canale WebSocket Live Telemetry**: `ws://<IP-LAN>:8765/api/v1/ws`
- **Riferimento Tecnico API Completo**: [API_REFERENCE.md](API_REFERENCE.md) (contratti Pydantic, tutti i 39 percorsi, payload JSON ed esempi cURL/Python)

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

## 🗺️ Architettura API REST & Mappe BACS Help

BHAM include un'architettura completa di oltre 39 endpoint REST e un canale WebSocket per l'automazione industriale. Consulta la guida completa [API_REFERENCE.md](API_REFERENCE.md).

Principali endpoint per le mappe BACS Help (`/api/v1/maps`):
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

L'eseguibile binario standalone verrà generato in `dist/bham` (`dist\bham.exe` su Windows).

### Flag dell'eseguibile standalone

A differenza del launcher da sorgente, il binario compilato espone i propri flag:

| Flag | Effetto |
|------|---------|
| `--check` | Verifica preflight **e** caricamento dei motori di protocollo, poi esce (`0` = sistema pronto) |
| `--port 9000` | Porta di ascolto alternativa |
| `--host 127.0.0.1` | Limita l'ascolto alla sola macchina locale |
| `--version` | Stampa la versione e termina |
| `--no-browser` | Non apre automaticamente il browser |
| `--demo` | Avvia il Simulatore d'Impianto Virtuale |
| `--no-port-fallback` | Disattiva la ricerca automatica di una porta libera |

### Verifica del pacchetto compilato

```bash
pyinstaller bham.spec
python scripts/smoke_frozen.py     # compila -> avvia -> interroga /api/v1/health
```

Lo stesso controllo gira in CI su Windows e Linux a ogni push: compila l'eseguibile,
lo **avvia realmente** e verifica che la console web risponda. È il test che intercetta
le regressioni di packaging invisibili ai test unitari.

---

## 🪟 Risoluzione problemi di installazione su Windows

| Sintomo | Causa & soluzione |
|---------|-------------------|
| La finestra di `bham.exe` si apre e si chiude subito | Guasto delle versioni ≤ 1.1.0 (`Could not import module "main"`): **risolto in 1.2.0**, aggiornare all'ultima release |
| La dashboard non si apre dal tablet, ma funziona sul PC | Windows Firewall blocca le connessioni in ingresso. Reinstallare selezionando l'opzione firewall, oppure eseguire come Amministratore:<br>`netsh advfirewall firewall add rule name="BHAM - BACS Help Auto Mapper" dir=in action=allow protocol=TCP localport=8765` |
| Pagina bianca all'avvio | Pacchetto incompleto: `bham.exe --check` lo segnala esplicitamente |
| Una funzione (es. ARP Sniffer) va in errore mentre il resto funziona | `bham.exe --check` elenca i motori: `[ASSENTE]` = pacchetto incompleto (reinstallare), `[LIMITATO]` = driver mancante su questa macchina |
| "File in uso" durante l'aggiornamento | Risolto in 1.2.0: l'installer chiude l'istanza in esecuzione |
| L'antivirus blocca il download | Risolto in 1.2.0 (UPX disattivato, risorsa di versione e publisher incorporata). Verificare l'hash `.sha256` pubblicato con la release |
| Lo sniffer ARP/L2 non cattura pacchetti | Driver **Npcap** assente: la scheda *Diagnostica & Requisiti* offre il download guidato |
| `winget install BacsHelp.BHAM` restituisce 404 | Manifest corretto in 1.2.0 (puntava a un asset di release inesistente) |

Dopo l'installazione è disponibile nel menu Start la voce **BHAM → Verifica installazione (diagnostica)**:
esegue il controllo completo e mostra l'esito in una finestra che resta aperta, senza bisogno di
aprire un prompt dei comandi. La stessa utilità (`verifica-installazione.bat`) è inclusa
nell'archivio portable.

### Avvio di una scansione rifiutato (HTTP 409)

Alcune risorse di campo ammettono un solo utilizzatore: una porta RS485, il socket
BACnet/IP (47808) e quello KNXnet/IP (3671). Avviare due operazioni sulla stessa
risorsa produrrebbe letture corrotte presentate come valide, quindi la seconda
viene **rifiutata** con `409` e con l'indicazione di cosa la sta occupando:

```json
{
  "detail": "La risorsa è già in uso da «Sniffer passivo RS485», avviata 12 secondi fa.",
  "resource": "serial:/dev/ttyUSB0",
  "conflicting_session_id": "…",
  "hint": "Attendi il termine dell'operazione in corso oppure arrestala con POST /api/v1/scan/abort/{session_id}."
}
```

Per vedere cosa è occupato in un dato momento: `GET /api/v1/system/resources`.
Modbus TCP e la scansione IP non rivendicano nulla (solo connessioni in uscita) e
restano quindi eseguibili in parallelo.

Diagnostica completa dalla UI: **Impostazioni → Diagnostica & Requisiti**, oppure
`GET /api/v1/system/diagnostics` (riporta `is_frozen`, `is_portable`, `listen_port`,
`has_npcap` e `windows_firewall_rule`).

---

## 🔌 Driver di Protocollo & Verifica su Librerie Reali

Dalla v1.3.0 **tutte** le dipendenze sono allineate alle versioni correnti, driver
di protocollo compresi (`pymodbus`, `bacpypes3`, `scapy`, `reportlab`). I minimi
dichiarati in `pyproject.toml` seguono i pin di `requirements.txt`.

L'avanzamento ha fatto emergere tre rotture che la suite preesistente non poteva
vedere, perché i test Modbus passavano dal **Simulatore d'Impianto Virtuale**, che
intercetta le operazioni *prima* della libreria:

| Difetto | Effetto in cantiere |
| --- | --- |
| Cambio di API su slave e numero di registri | Ogni lettura/scrittura Modbus reale falliva all'istante (17 punti di chiamata corretti) |
| Tipo di dato dedotto dalla forma della risposta | Letture di registri **vuote ma dichiarate riuscite** — esito verde senza dati |
| Modulo FC43 spostato | Identificazione costruttore non più caricabile |

Per impedire che si ripeta, `tests/test_protocol_drivers.py` avvia un **vero server
Modbus TCP** in locale con valori noti e interroga le funzioni di BHAM a simulatore
spento: valori esatti, rispetto di indirizzo e quantità, round-trip di scrittura
singola e multipla, scansione, Smart Register Scan, interlock Safe Mode, validità
del PDF e riapertura dell'Excel prodotti, più un presidio sulle firme delle librerie.

```bash
# Suite completa (179 test)
.venv/bin/python -m unittest discover -s tests -v

# Solo i driver su librerie reali
.venv/bin/python -m unittest discover -s tests -p test_protocol_drivers.py -v
```

> **Nota d'ambiente:** usare `unittest discover`, non `python -m unittest tests.<modulo>`:
> `bacpypes3` installa un pacchetto `tests` di primo livello che oscura quello del repo.

**Resta da validare su impianto** (nessuna automazione può sostituirlo): temporizzazione
del bus RS485 fisico (auto-baud, pause fra frame, terminazioni), identificazione
dispositivo su seriale, discovery BACnet/IP su rete di impianto, cattura pacchetti con
Npcap. Dettaglio dei rilievi in [AUDIT.md](AUDIT.md).

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
│   └── test_bham.py      # Test unitari e di integrazione (58 test completi)
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
