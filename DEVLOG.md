
# BHAM – Development Log
> Registro cronologico delle sessioni di sviluppo.
> File: `/home/giuliano/Documenti/BHAM/DEVLOG.md`

## Sessione 27 – 2026-10-03 ✅ COMPLETE – VERSIONE 0.8.0 ENTERPRISE (FIELD SAFETY, PROFILES & PACKAGING)
**Libreria Profili Modbus Industriali (ABB, Gavazzi, IME, Schneider, Siemens, Belimo, Isoil, Diehl, Emerson, Carel, Riello, Trox), Gestore Profili Custom, Blocco Sicurezza Manovre (Safe Mode Interlock), Registro Manovre Certificato (Crash-Proof WAL & Chaining SHA-256), Standalone Packaging Duale (Portable vs Installed) e Firma Digitale SignPath**

**Highlights:**
- ✅ **Libreria Profili Modbus Estesa & Custom Manager (`core/profile_manager.py`, `profiles/builtin/*.json`)**:
  - Creati 13 profili industriali ricchi con decodifica scientifica di indirizzi, formati (UInt16, Int16, Float32 BE/LE), fattori di scala, unità di misura e permessi:
    - *Multimetri:* ABB B23, Carlo Gavazzi EM24, Carlo Gavazzi EM111, IME Nemo 96, Schneider Acti9 iEM3150, Schneider PM5350, Siemens SENTRON PAC3200.
    - *Contabilizzatori & Portata:* Belimo Energy Valve (EV), Isoil ISOMAG, Diehl/Hydrometer Sharky 775, Emerson Rosemount 8712.
    - *Attuatori & HVAC:* Belimo Servocomando Modbus, Trox VAV Compact, iSMA CONTROLLI Modulo I/O B-4I4O, Riello Caldaia Condexa Pro, Carel pCO Controllore.
  - Motore di gestione profili custom con persistenza su disco, CRUD, importazione/esportazione JSON.
  - Funzione "Applica a Slave": mappatura immediata del profilo con iniezione di tutti i registri nella vista live del dispositivo e nel `data/maps_manager.py`.
- ✅ **Blocco Sicurezza Manovre (Safe Mode Interlock) (`core/safe_mode.py`)**:
  - Barriera di protezione attiva contro scritture accidentali sul bus (`ModbusQuickCommander` e `BACnetPointCommander` sollevano `SafeModeLockedError` con codice HTTP 403 se il sistema è bloccato).
  - Flusso di armamento ("Arm") con obbligo di specificare Nome Operatore / Tecnico, Commessa / Ordine di Lavoro, e durata finestra temporale (15, 30, 60, 120 min).
  - Disarmo manuale immediato o automatico con timer di scadenza in background.
  - Integrazione completa in testata UI con badge dinamico (verde protetto o rosso pulsante con countdown e dati operatore).
- ✅ **Registro Manovre Certificato (Crash-Proof WAL & SHA-256 Chaining) (`core/audit_journal.py`)**:
  - Write-Ahead Log su file append-only `audit_journal.jsonl`.
  - Registrazione preventiva dell'intento con chiamata esplicita `os.fsync` prima della trasmissione fisica dei byte sul cavo seriale o rete IP.
  - Registrazione del risultato con esito (`SUCCESS` o `FAILED`), latenza di risposta, codice eccezione e valore verificato.
  - Chaining crittografico inviolabile SHA-256: ogni voce concatena `prev_hash` garantendo l'individuazione di qualsiasi manomissione successiva.
  - Auto-recovery degli intenti orfani al riavvio in caso di spegnimento improvviso del PC o caduta di alimentazione.
  - Endpoint `GET /api/v1/audit/verify` e modale per verifica dell'integrità del giornale ed esportazione in formato JSON firmabile.
- ✅ **Packaging Unificato Standalone (Portable vs Installed) & Firma SignPath**:
  - Modulo `core/paths.py` per risoluzione dinamica dei percorsi a runtime:
    - Riconoscimento ambiente PyInstaller congelato (`sys._MEIPASS`).
    - Modalità Portatile tramite sentinella `portable.flag` (sessioni, log, custom profile e audit salvati nella cartella locale dell'applicazione).
    - Modalità Installata conforme agli standard di sistema (`%LOCALAPPDATA%\BHAM` su Windows, `~/.local/share/bham` su Linux).
  - Script Inno Setup `installer/bham.iss` per installer Windows x64 pulito con creazione collegamenti e disinstallazione.
  - Pipeline GitHub Actions `.github/workflows/release.yml` con rilascio duale (archivio portatile ZIP + installer Windows EXE) e integrazione ufficiale `SignPath/github-action-submit-signing-request@v2` per firma crittografica autenticata.
- ✅ **Frontend UI & Sincronizzazione i18n**:
  - Nuovi pulsanti e modali integrati nell'interfaccia (Safe Mode, Audit Journal, Libreria Profili con filtri categoria e visualizzazione tabellare registri).
  - Sincronizzazione al 100% su 289 chiavi per Italiano, Inglese e Spagnolo in `frontend/js/i18n.js`.
  - Validazione JavaScript con `node -c frontend/js/*.js` superata senza errori.
- ✅ **Testing & Validazione**:
  - Test suite estesa a 49 test unitari (`TestPaths`, `TestAuditJournal`, `TestSafeMode`, `TestProfileManager`, `TestEnterpriseV08Routes`).
  - Tutti i 49 test passano con successo al 100% con `-W error` in meno di 6 secondi.

## Sessione 26 – 2026-10-03 ✅ COMPLETE – VERSIONE 0.8.0 STABLE & COMPLETA (INDUSTRIAL FIELD-READY)
**Collaudo Hardware Reale su USB↔RS485 (Moxa UPort 1150 / TI 3410), hot-plug auto-recovery, Banco Prova Operativo (Modbus Quick Commander & BACnet Point Commander con Priority Array), Simulatore d'Impianto Virtuale (Demo Mode) e Live Log Viewer Dock**

**Highlights:**
- ✅ **Collaudo Hardware Reale (Moxa UPort 1150 / TI 3410 su `/dev/ttyUSB0`)**:
  - Rilevato e integrato convertitore seriale Moxa UPort 1150 (VID `0x110A`, PID `0x1150`, TI 3410) in `core/hw_discovery.py`.
  - Esteso controllo permessi in `core/priv_check.py` per supportare gruppi `uucp`, `dialout` e permessi POSIX diretti `os.access(..., R_OK | W_OK)`.
  - Self-Test 1-Click con validazione reale: test apertura/chiusura a 9600 8N1 completato in 74ms con esito `status: ok` e `rs485_likely: True`.
  - Zero-TX Serial Sniffer verificato su linea RS485 a vuoto: diagnosi di linea silenziosa/flottante corretta, nessuna divisione per zero, chiusura pulita delle risorse.
- ✅ **Resilienza Hardware & Hot-Plug Auto-Recovery (`scanners/serial_sniffer.py`)**:
  - Gestione eccezioni `(serial.SerialException, OSError, IOError)` durante lo sniffing senza crash del daemon.
  - Emissione eventi WebSocket `hardware_disconnect` e `hardware_reconnect` con notifica visiva Toast e log semantico.
  - Ciclo di polling per il riaggancio trasparente della porta seriale appena ricollegata.
- ✅ **Banco Prova Operativo ("Field Operational Tools") (`scanners/field_tools.py`)**:
  - **Modbus Quick Commander**: lettura (FC01..FC04) e scrittura (FC05, FC06, FC15, FC16) su Modbus RTU e TCP con decodifica ingegneristica (UInt16, Int16, Float32 BE/LE word-swapped, Hex, Coils).
  - Integrato sia nello Slave Inspector Modbus (tab "⚡ Quick Commander") che nel modale standalone unificato.
  - **BACnet Point Commander**: override forzato del `presentValue` con Priority Array (default Priorità 8: Operatore Manuale) e comando di rilascio forzatura (Relinquish / NULL). Mini-modal accessibile direttamente da ciascun oggetto esplorato.
- ✅ **Simulatore d'Impianto Virtuale BACS (`core/simulator.py`)**:
  - Generatore di telemetria dinamica sinusoidale per Chiller (Slave 1), Pompa (Slave 2), Power Meter (Slave 3), UTA BACnet (Device 1001), VAV (Device 1002), KNX (1.1.1, 1.1.2) e host ARP.
  - Toggle rapido in barra comandi con indicatore DEMO: ON / OFF e opzione `--demo` da riga di comando.
- ✅ **Live Log Viewer & Dock Console**:
  - Filtro dinamico per livello (`ALL`, `DEBUG`, `INFO`, `WARN`, `ERROR`) e ricerca per parole chiave.
  - Streaming strutturato da backend con timestamp, livello, logger e messaggio.
  - Notifiche Toast animate e non-bloccanti.
- ✅ **Qualità & Standard di Rilascio**:
  - Suite di unit test superata al 100% con `-W error`.
  - Parità i18n al 100% su 248 chiavi tra IT, EN ed ES.
  - Validazione JavaScript Vanilla con `node -c`.
  - Version bump globale a `0.8.0` su tutti i manifest e documentazioni.

## Sessione 25 – 2026-10-03 ✅ COMPLETE – REST & WEBSOCKET API HARDENING & DOCUMENTATION 2.0
**Elevazione dell'architettura API a livello enterprise: schemi Pydantic v2 tipizzati per tutti i 39 endpoint, specifiche OpenAPI complete con tag semantici, documentazione esaustiva API_REFERENCE.md e aggiornamento del manuale interattivo**

**Highlights:**
- ✅ **Layer di Schemi Pydantic v2 Tipizzati (`api/schemas.py`)**:
  - Creato modulo dedicato `api/schemas.py` con contratti formali e documentati per tutte le richieste e risposte:
    - *Richieste*: `ModbusRTUScanRequest`, `ModbusTCPScanRequest`, `BACnetIPScanRequest`, `KNXIPScanRequest`, `ARPSniffRequest`, `SerialSniffRequest`, `FC43Request`, `ConfigureRequest`, `SaveSessionRequest`, `ModbusSmartScanBody`.
    - *Risposte*: `HealthResponse`, `StateClearResponse`, `ScanActionResponse`, `ScanAbortResponse`, `ScanAbortSingleResponse`, `SerialPortInfo`, `NetworkInterfaceInfo`, `NetworkInterfacesResponse`, `HardwareSelfTestResponse`, `ConfigureResponse`, `ConfigActiveResponse`, `SaveSessionResponse`, `DeleteSessionResponse`, `RestoreSessionResponse`, `FC43Response`, `ModbusSmartScanRegister`, `ModbusSmartScanResponse`, `BACnetObjectItem`, `BACnetObjectExplorerResponse`, `MapsImportResponse`, `SlaveMapResponse`.
  - Configurato `protected_namespaces = ()` per evitare conflitti con identificatori riservati Pydantic (es. `model_name`).
- ✅ **Metadata OpenAPI & FastAPI App (`main.py`)**:
  - Aggiunti metadati approfonditi con `API_DESCRIPTION` in Markdown dettagliando i protocolli industriali (Modbus RTU/TCP, BACnet/IP, BACnet MS-TP, KNXnet/IP, ARP L2, RS485 Bus Health).
  - Raggruppamento semantico degli endpoint in 10 tag strutturati (`system`, `setup`, `scans`, `devices`, `diagnostics`, `modbus`, `bacnet`, `saved-sessions`, `maps`, `reports`).
  - Configurazione completa per Swagger UI (`/docs`), ReDoc (`/redoc`), licenza MIT e riferimenti di contatto.
- ✅ **Refactoring Route REST (`api/routes.py`)**:
  - Applicazione di `response_model`, `summary` e `description` su tutti gli endpoint mantenendo ritorni dizionario nativi per compatibilità totale con le chiamate dirette dei test unitari.
  - Aggiunto alias di rotta trasparente per `/api/v1/scan/modbus/smart-scan` e `/api/v1/modbus/smart-scan`.
- ✅ **Riferimento Tecnico Completo (`API_REFERENCE.md`)**:
  - Creato documento esaustivo di oltre 800 righe con:
    - Indicazioni su architettura, binding di rete (`0.0.0.0:8765`), sicurezza (avviso assenza autenticazione per impiego sul campo, raccomandazioni VLAN/VPN/reverse-proxy).
    - Specifiche dettagliate dei codici di stato HTTP (`200`, `400`, `404`, `500`) e payload di input/output per tutti i 39 endpoint.
    - Specifiche complete del canale WebSocket `ws://<host>:8765/api/v1/ws` (comandi client, eventi broadcast `scan_progress`, `device_found`, `bus_health_update`, `log_record`).
    - Ricette cURL pronte all'uso e script Python completo per automazione del collaudo ed estrazione report.
- ✅ **Manuali Utente & In-App Documentation (`MANUALE_UTENTE.md`, `frontend/MANUALE_UTENTE.md`, `frontend/js/manual-content.js`)**:
  - Aggiornata la Sezione 10 dei manuali con tabella esaustiva di tutti gli endpoint suddivisi per dominio e link ad `API_REFERENCE.md`.
  - Aggiunti al manuale interattivo (F1) in 3 lingue (IT, EN, ES) i capitoli:
    - *Capitolo 11*: Session Diff & Intelligence ("Prima vs Dopo")
    - *Capitolo 12*: Attraversamento BBMD & Router BACnet/IP
    - *Capitolo 13*: Hardware Self-Test & Accesso Remoto LAN
  - Ampliato il capitolo 9 (API) con tabella integrata e comandi cURL.
- ✅ **Aggiornamento `README.md`**:
  - Inseriti collegamenti diretti a Swagger UI, ReDoc e al nuovo `API_REFERENCE.md`.
- ✅ **Test & Validazione Continua**:
  - Aggiunta classe di test `TestOpenAPISpecAndSchemas` in `tests/test_bham.py`.
  - Suite unitaria: **38/38 test superati al 100% con `-W error`** (zero warning, zero regressioni).
  - Validazione sintassi JS con `node -c` su tutti i file del frontend.
  - Verifica parità dizionari multilingua: 232/232 chiavi su IT, EN, ES (100% parità).

---

## Sessione 24 – 2026-10-03 ✅ COMPLETE – v0.7.0 RELEASE PREP & FIELD ENHANCEMENTS
**Preparazione rilascio v0.7.0: launcher robusto con auto-open browser, accesso remoto LAN Raspberry Pi/PC, autodiagnosi hardware 1-click, euristica RS485 e profili impianto rapidi**

**Highlights:**
- ✅ **Version Bump v0.7.0** su tutti i file (pyproject, config, winget, index.html + cache-buster, i18n ×3, manuali, `package_deb.sh`). Excel ora usa `settings.app_version`.
- ✅ **`scripts/bump_version.py`**: sincronizza anche frontend/i18n/manuali/.deb; nuovo `--files` usato da `release.sh` e `release.yml` per il commit di release.
- ✅ **`bham.py` irrobustito con Auto-Open Browser & Accesso Remoto LAN**:
  - Verifica *ogni* pacchetto di `requirements.txt` (via `importlib.metadata` dentro il venv, incluse versioni pinnate), flag `--yes`/`--check`/`--no-browser`/`--no-reload`.
  - **Auto-Apertura Browser**: probe su porta 8765 e apertura automatica del browser predefinito all'avvio; gestione sicura di ambienti headless (Linux SSH/server senza display).
  - **Accesso Remoto LAN**: rilevamento dinamico di tutti gli IP LAN non-loopback (`get_local_lan_ips()`), banner a console con URL per tablet/PC remoti e indicazioni firewall (`sudo ufw allow 8765/tcp`).
  - Ricerca automatica interpreti supportati (`3.12`, `3.13`, `py -3.12` su Windows o `python3.12` su Linux), fallback con bootstrap automatico di `pip` via `get-pip.py` su distribuzioni Debian/Ubuntu prive di `ensurepip`.
- ✅ **Interfaccia Web & Remote Access (`frontend/index.html`, `frontend/js/app.js`)**:
  - Box dedicato "Accesso Remoto LAN (Tablet / Altri PC)" nella scheda Impostazioni Adattatori & Porte, popolato automaticamente con gli IP dell'host (`http://192.168.x.x:8765`) e pulsante di copia negli appunti con feedback visivo.
  - WebSocket connection URL reso protocol-aware (`wss:` su HTTPS/tunnel, `ws:` su HTTP).
- ✅ **A. Diagnostica Euristica Qualità Bus RS485 (`scanners/serial_sniffer.py`, `data/models.py`)**:
  - Aggiunti campi `physical_status` e `physical_diagnosis` a `BusHealth`.
  - Calcolo automatico di diagnosi euristiche del livello fisico sul bus in base a PER % e Bus Load %: allarme terminazioni 120Ω mancanti o inversione polarità A(+)/B(-), warning disturbi/schermatura cavo, warning saturazione polling Master.
  - Badge diagnostico reattivo `#health-diagnosis` nel banner Bus Health della dock inferiore con tooltip esplicito e codifica colore.
- ✅ **B. Quick Diagnostic Self-Test 1-Click (`core/hw_discovery.py`, `api/routes.py`)**:
  - Nuovo endpoint `GET /api/v1/hardware/self-test` che collauda in < 100ms la porta seriale USB-RS485 selezionata (apertura/chiusura reale con timing), le schede di rete (IP, link cablato vs Wi-Fi) e i privilegi di sistema (dialout, admin, Npcap).
  - Card interattiva nel modale Impostazioni con pulsante `[⚡ Esegui Self-Test]` e chip di stato (Verde/Giallo/Rosso) per prevenire scansioni a vuoto prima di andare in campo.
- ✅ **C. Preset Rapidi di Scansione / Profili Impianto (`frontend/index.html`, `frontend/js/app.js`)**:
  - Menu a tendina sia nella sidebar che nella scheda Scansione per applicare istantaneamente profili tipici: *HVAC Standard* (9600 8N1 + BACnet 47808), *Contatori Energia* (19200 8E1), *Gateway Luce / DALI* (19200 8N1), *Ricerca Approfondita* (timeout estesi, sweep 1-247).
  - Persistenza automatica del profilo selezionato in `localStorage`.
- ✅ **Risoluzione Socket Leak BACnet (`scanners/bacnet.py`)**:
  - Helper `_safe_close` e chiusura sicura in caso di cancellazione/aborto scansione; eliminati tutti i `ResourceWarning` su socket UDP aperti.
- ✅ **Parità & Qualità**:
  - Test suite unificata: **37/37 unit test superati al 100% con flag `-W error`**.
  - Parità i18n al 100% (232 chiavi identiche in IT, EN, ES).
  - Sintassi JavaScript verificata con `node -c`.
  - DOM IDs: 232 elementi unici verificati, 0 duplicati.
- ✅ Nuovo **`CHANGELOG.md`**; README e manuale con quick start e guida all'accesso remoto.

---

## Sessione 23 – 2026-10-03 ✅ COMPLETE – Ottimizzazione UX & Setup Multi-Piattaforma
**Revisione del Centro Impostazioni e Automazione del Setup per Windows e Linux**

**Highlights:**
- ✅ **Setup Multi-Piattaforma & Auto-Dipendenze (`bham.py`)**:
  - Creato un launcher intelligente `bham.py` per avviare il tool in modo uniforme su Windows e Linux.
  - Generazione automatica della lista delle dipendenze da `requirements.txt`.
  - Richiesta esplicita (prompt Y/n) per creare e configurare automaticamente il virtualenv isolato scaricando tutte le dipendenze in modo completamente autonomo.
- ✅ **Restyling Centro Impostazioni (Impostazione "Tool vs Bel Tool") (`frontend/index.html`, `frontend/css/main.css`)**:
  - Rivoluzionato il layout del modale impostazioni rimuovendo i tab orizzontali e adottando una più razionale e pragmatica **sidebar laterale** (colonna sinistra) con tutte le macro-voci (Adattatori, Scansione, Tema, etc.).
  - Sostituiti i pulsanti ingombranti con **menù a tendina chiari e puliti (`<select>`)** per l'impostazione di Lingua e Tema.
  - Aggiunti controlli per sincronizzazione dello stato dei menù a tendina con il salvataggio dei parametri lato frontend (`app.js`).

## Sessione 22 – 2026-09-30 ✅ COMPLETE – v0.6.0 OFFICIAL RELEASE
**Rilascio Ufficiale BHAM v0.6.0: Session Diff Engine, Report Arricchiti 2.0 (8 Fogli & PDF Gerarchico), BBMD Router Traversal & Foreign Device BACnet/IP**

**Final Checks & Packaging:**
- ✅ **Version Bump & Sincronizzazione Completa (v0.6.0)**:
  - `core/config.py`: `app_version = "0.6.0"`
  - `pyproject.toml`: `version = "0.6.0"`
  - `frontend/index.html`: Header, badge e cache busters asset (`?v=0.6.0`)
  - `frontend/js/i18n.js`: `brand_sub: "BACS Help Auto Mapper v0.6.0"` (IT, EN, ES)
  - `README.md`, `MANUALE_UTENTE.md` e `frontend/MANUALE_UTENTE.md` aggiornati e allineati a `v0.6.0`.
  - Manifest Winget (`winget/BacsHelp.BHAM.*.yaml`) e script packaging Debian (`scripts/package_deb.sh`) aggiornati a `0.6.0`.
- ✅ **Qualità del Codice & Test Suite**:
  - Test suite unificata: **32/32 unit test superati al 100% con flag `-W error`** in 5.5s.
  - Sintassi JavaScript: 0 errori (`node -c`).
  - DOM IDs: 221 elementi unici, 0 duplicati.
  - Dizionario i18n: 218 chiavi per lingua con parità assoluta (IT, EN, ES).

---

## Sessione 21 – 2026-09-29 ✅ COMPLETE – v0.6.0 MILESTONE 3 (BBMD Router Traversal & Foreign Device BACnet/IP)
**Attraversamento Router Inter-VLAN via Foreign Device Registration (Annex J), Ispezione Tabelle BDT & FDT, Topologia Gerarchica con Nodi BBMD & Modale Diagnostico**

**Highlights:**
- ✅ **Backend BBMD & Foreign Device Engine (`scanners/bacnet.py`)**:
  - Implementata la registrazione Foreign Device nativa tramite `bacpypes3.ipv4.app.ForeignApplication` con socket UDP asincrono su porta locale dinamica (`:0`).
  - Gestione del flusso di registrazione verso BBMD (`app.register(bbmd_addr, ttl)`) e deregistrazione pulita in blocco `finally` (`app.unregister()`, `app.close()`).
  - Marcatura dei dispositivi scoperti tramite traversata con flag `device.bbmd_routed = True`, `device.routed_via = f"{bbmd_ip}:{bbmd_port}"` e tag `"bbmd_routed"`.
  - Implementato parser e client asincrono UDP puro per i messaggi BVLL (BACnet Virtual Link Layer) secondo standard ASHRAE 135 Annex J:
    - `read_bdt(bbmd_ip, bbmd_port, timeout)`: interroga la Broadcast Distribution Table con comando BVLL `Read-BDT` (`0x81 0x02 0x00 0x04`) e decodifica le entry di 10 byte (4B IP, 2B Port, 4B Broadcast Mask).
    - `read_fdt(bbmd_ip, bbmd_port, timeout)`: interroga la Foreign Device Table con comando BVLL `Read-FDT` (`0x81 0x06 0x00 0x04`) e decodifica le entry di 10 byte (4B IP, 2B Port, 2B TTL, 2B Remaining Seconds).
    - `get_bbmd_tables(bbmd_ip, bbmd_port, timeout)`: esegue la lettura concorrente parallela di BDT ed FDT tramite `asyncio.gather`.
- ✅ **Data Models & REST API (`data/models.py`, `api/routes.py`)**:
  - Modelli `BBDTEntry`, `FDTEntry`, `BBMDInfoResponse`.
  - Estesa `BACnetIPScanRequest` con `bbmd_ip: Optional[str] = None`, `bbmd_port: int | str = 47808`, `bbmd_ttl: int = 60`.
  - Nuovi endpoint REST:
    - `GET /api/v1/bacnet/bbmd/tables`
    - `GET /api/v1/bacnet/bbmd/bdt`
    - `GET /api/v1/bacnet/bbmd/fdt`
- ✅ **Topologia Gerarchica d'Impianto (`data/state.py`)**:
  - `get_topology()` raggruppa automaticamente i dispositivi con tag o flag `bbmd_routed` sotto nodi router dedicati (`node:router:bbmd:<ip>_<port>`), posizionati logicamente tra il bus `node:bus:bacnet_ip` e i rispettivi controllori periferici.
  - La visualizzazione topologica grafica (SVG/PDF/Excel) riflette fedelmente la struttura di routing inter-VLAN dell'infrastruttura BACS.
- ✅ **Frontend UI / UX & Modale Diagnostico (`frontend/index.html`, `frontend/css/main.css`, `frontend/js/app.js`)**:
  - Drawer collassabile compatto nella card BACnet della colonna rack: input `bbmd-ip`, `bbmd-port`, `bbmd-ttl`, e pulsante di interrogazione rapida `[📋 Tabelle BDT/FDT]`.
  - Modale diagnostico interattivo `#bbmd-modal` per l'ispezione immediata delle tabelle BDT e FDT di qualsiasi router di campo, con conteggi in tempo reale, scroll dedicato e gestione errori/NAK.
  - Badge distintivo `[BBMD]` ciano con tooltip esplicito accanto ai dispositivi BACnet scoperti via attraversamento router nella tabella centrale.
- ✅ **i18n & Manuale Operativo (`frontend/js/i18n.js`, `frontend/js/manual-content.js`)**:
  - Aggiunte 15 nuove chiavi tradotte in Italiano, Inglese e Spagnolo (218 chiavi totali per lingua, 100% di parità verificata via script).
  - Aggiornato il capitolo 3 del manuale tecnico con guida all'uso di BBMD e Foreign Device.
- ✅ **Test Suite (`tests/test_bham.py`)**:
  - Aggiunta test suite `TestBACnetBBMD` con mock server UDP asincrono per decodifica pacchetti BDT ed FDT, validazione request model e test gerarchia topologica.
  - **32/32 unit test passati al 100% con flag tassativo `-W error`** in 5.5s.

---

## Sessione 20 – 2026-09-29 ✅ COMPLETE – v0.6.0 MILESTONE 2 (Report Arricchiti con Topologia & As-Built)
**Integrazione Mappa Topologica e As-Built Registri/Oggetti in Report PDF e Cartella Excel v2.0 (8 Fogli)**

**Highlights:**
- ✅ **Cartella Excel Multi-Foglio Arricchita v2.0 (`reports/excel.py`)**:
  - Estesa la generazione da 5 a **8 fogli di lavoro** stilizzati con palette industriale dedicata:
    1. `Network Topology` (Header Slate `#334155`): albero gerarchico d'impianto con livello (Host, Canale, Bus, Nodo), categoria, protocollo, canali fisici, nodi parent e stato operativo.
    2. `Modbus Devices` (Header Cyan `#0E7490`): censimento slave seriali RTU e TCP con parametri seriali e latenza.
    3. `BACnet Devices` (Header Purple `#6D28D9`): censimento controllori con Device Instance ID, IP/MAC, vendor, modello e revisione firmware.
    4. `KNX Devices` (Header Orange `#C2410C`): gateway e nodi KNXnet/IP con indirizzo individuale, seriale, MAC e medium.
    5. `IP Hosts` (Header Green `#065F46`): host di rete rilevati da sniffing ARP L2 con porte aperte e protocol hints.
    6. `Modbus Registers` (Header Amber `#B45309`): censimento analitico di tutti i registri Holding / Input acquisiti da Smart Scan o mappe BACS Help, con valori Raw Hex, Dec Int16 con segno e Float32 IEEE 754 Big-Endian.
    7. `BACnet Objects` (Header Indigo `#4338CA`): censimento oggetti controllori (AI, AO, AV, BI, BO, BV, MSI, MSO) con object-identifier, nome punto, Present Value, unità ingegneristiche (`°C`, `bar`, `%`, `kW`, ecc.) e Status Flags.
    8. `Report Info`: metadati completi di collaudo con conteggio analitico di tutti i nodi topologici, registri e oggetti censiti.
  - Alternanza righe migliorata con fondo morbido e riposante `#F8FAFC`, auto-width colonne fino a 60 caratteri e freeze pane.
- ✅ **Verbale PDF Vettoriale ReportLab Arricchito (`reports/pdf.py`)**:
  - Aggiunta **Sezione 5: "Mappa Topologica Gerarchica d'Impianto"**:
    - Algoritmo tree-walker deterministico a partire dal nodo root `node:host`.
    - Indentazione gerarchica visiva ad albero con prefissi (`🖥️ Host`, `├─ Interfaccia`, `└─ Bus`, `• Nodo Dispositivo`).
    - Tabella 4 colonne: Albero/Nodo con sublabel canali, Livello gerarchico, Protocollo, Stato operativo (ONLINE / ACTIVE / STANDBY).
  - Aggiunta **Sezione 6: "As-Built – Censimento Registri Modbus"**:
    - Generata automaticamente se presenti registri scansionati: Slave ID, Canale/Endpoint, Registro, Raw Hex, Dec Int16, Float32 IEEE, Etichetta/Tag.
  - Aggiunta **Sezione 7: "As-Built – Censimento Oggetti BACnet"**:
    - Generata automaticamente se presenti oggetti esplorati: Device ID, Tipo Oggetto, ID Oggetto, Nome Oggetto, Present Value, Unità di misura.
  - Paginazione dinamica `NumberedCanvas` a due passate (Pagina X di Y) preservata senza overflow di pagina.
- ✅ **Testing & Validazione**:
  - Aggiornato `TestReporting` in `tests/test_bham.py` con verifica formale di tutti gli 8 fogli Excel e compilazione PDF con registri e oggetti.
  - **28/28 unit test passati al 100% con flag tassativo `-W error`** in 5.4s.

---

## Sessione 19 – 2026-09-29 ✅ COMPLETE – v0.6.0 MILESTONE 1 (Intelligence & Session Diff)
**Confronto Differenziale Impianto "Prima vs Dopo", Algoritmo Deterministico Multi-Protocollo, Modale Diagnostico & Esportazione Diff**

**Highlights:**
- ✅ **Backend Diff Engine (`core/session_diff.py`)**:
  - Algoritmo analitico di confronto per snapshot d'impianto con supporto Modbus (RTU/TCP), BACnet (IP/MS-TP), KNXnet/IP e ARP Hosts.
  - Riconoscimento intelligente delle entità fisiche:
    - Match per MAC address preferenziale su apparati Ethernet per identificare riassegnazioni di IP via DHCP vs sostituzioni fisiche.
    - Match per slave ID / protocollo su Modbus e rilevamento variazioni di baudrate, parità, latenza bus (>200ms) o conteggio registri.
    - Match per Device Instance Number su BACnet e rilevamento cambi IP, firmware revision, software version e oggetti censiti.
    - Match per Indirizzo Individuale (Area.Linea.Device) su KNX e tracking gateway IP/porte.
  - Classificazione categorizzata: `ADDED` (🟢), `REMOVED` (🔴), `MODIFIED` (🟡), `UNCHANGED` (⚪) con tracciamento puntuale dei singoli campi variati.
  - Metriche aggregate di sintesi (`added`, `removed`, `modified`, `unchanged`) per protocollo e globali.
- ✅ **REST API (`api/routes.py`)**:
  - Endpoint `POST /api/v1/sessions/diff` con schema `SessionDiffRequest` (`baseline_filename`, `target_filename` opzionale con default a Live AppState).
- ✅ **Frontend UI / UX (`frontend/index.html`, `frontend/css/main.css`, `frontend/js/app.js`)**:
  - Pulsante tattico d'azione rapida `[⚡ Diff Impianto]` nella toolbar centrale delle tabelle.
  - Pulsante diretto `[⚡ Diff]` su ogni riga di sessione salvata nella scheda Archivio del Centro Impostazioni.
  - Modale dedicato `#diff-modal` con:
    - Selettore dinamico Baseline (sessioni archiviate) vs Target (Live State o altra sessione).
    - Banner telemetrico con card contatori di sintesi per stato (🟢 Nuovi, 🔴 Scomparsi, 🟡 Modificati, ⚪ Invariati).
    - Toolbar di filtraggio a doppio livello (Protocollo + Stato variazione).
    - Tabella differenziale ad alto contrasto con badge cromatici e disamina puntuale dei parametri prima/dopo (valori vecchi sbarrati in rosso ➔ nuovi in verde).
    - Esportazione istantanea del verbale di diff in formato `.csv` e `.json`.
- ✅ **Internazionalizzazione (i18n)**:
  - 15 nuove chiavi di traduzione allineate al 100% in Italiano, Inglese e Spagnolo in `frontend/js/i18n.js` (203 chiavi per lingua, 0 mancanti).
- ✅ **Testing & Validazione**:
  - Aggiunta test suite `TestSessionDiff` in `tests/test_bham.py` con test analitico completo di confronto snapshot e test d'integrazione API REST.
  - Risultato test: **28/28 unit test passati al 100% con `-W error`** in 5.4s.
  - Sintassi JavaScript (`node -c`): 0 errori su `app.js`, `i18n.js` e `manual-content.js`.
  - DOM IDs: 206 elementi verificati, 0 duplicati, preservati tutti i 180 preesistenti.

---

## Sessione 18 – 2026-09-29 ✅ COMPLETE – v0.5.0 RELEASE (Field Studio Milestone 2)
**Mappa Topologica Interattiva (Network Graph SVG Engine), View Switcher, Pan & Zoom, Node Inspector & High-Res Export**

**Highlights:**
- ✅ **Backend Graph Model & Endpoint**:
  - Implementato `get_topology` in `data/state.py` e route `GET /api/v1/topology` in `api/routes.py`.
  - Modellazione gerarchica a 4 livelli fisici e logici: Host Collaudo $\rightarrow$ Interfacce (Seriale RS485, NIC Ethernet) $\rightarrow$ Bus/Segmenti (Modbus RTU, BACnet MS-TP, Modbus TCP, BACnet/IP, KNXnet/IP, ARP L2) $\rightarrow$ Nodi/Slave Dispositivi.
  - Test unitari dedicati (`test_get_topology`, `test_topology_endpoint`) integrati in `tests/test_bham.py` (**26/26 test passati con `-W error`**).
- ✅ **View Switcher nella Toolbar Centrale**:
  - Pulsanti ergonomici `[📋 Tabelle]` vs `[🕸️ Mappa Topologica]` integrati nella toolbar con iconografia SVG industriale.
  - Cambio vista istantaneo con persistenza in `localStorage.getItem("bham-main-view")`.
- ✅ **Network Graph SVG Engine (100% Offline-Proof)**:
  - Rendering vettoriale nativo senza CDN o librerie pesanti di terze parti: leggero, reattivo a 60 FPS su laptop da campo.
  - Layout ad albero bilanciato con supporto a doppio orientamento: **Orizzontale** (L-to-R) e **Verticale** (T-to-B).
  - Collegamenti smooth bezier curve con marker a freccia e color-coding rigido per protocollo (Ciano Modbus, Viola BACnet, Arancio KNX, Smeraldo Rete, Ambra Seriale).
  - Floating HUD Bar con controlli: `Zoom In (+)`, `Zoom Out (-)`, `🎯 Centra (Fit to View)`, Selettore Orientamento, Legenda cromatica e `📥 Esporta SVG`.
  - Pan & Zoom fluido: trascinamento su canvas con mouse/touch e zoom progressivo con rotellina centrato sul puntatore.
- ✅ **Filtro di Ricerca Reattivo sul Grafo**:
  - Il campo di ricerca `#device-search` evidenzia in tempo reale i nodi corrispondenti sul grafo, sfumando con effetto dim quelli non pertinenti.
- ✅ **Drawer Ispettore Nodo (Quick Inspection Panel)**:
  - Cliccando su qualsiasi nodo si apre la scheda tecnica laterale (`#topology-inspector`) con telemetrie, latenza, ID e registri.
  - Scorciatoie dirette ai modali diagnostici: apertura diretta di `#slave-modal` con Smart Scan e `#bacnet-modal` con Object Explorer.
- ✅ **Esportazione Vettoriale per Collaudi**:
  - Funzione `exportTopologySVG()` per download istantaneo del diagramma d'impianto in file `.svg` ad alta risoluzione con data e nome sito.
- ✅ **Integrità & Stabilità**:
  - Test unitari: **26/26 OK in 5.3s** con `-W error`.
  - Sintassi JavaScript (`node -c`): 0 errori su `app.js`, `i18n.js` e `manual-content.js`.
  - DOM IDs: 180 elementi univoci (preservati al 100% tutti i 156 ID preesistenti).
  - i18n: 202 chiavi tradotte in Italiano, Inglese e Spagnolo (0 mancanti).
  - Documentazione: `README.md`, `MANUALE_UTENTE.md`, `frontend/MANUALE_UTENTE.md` e Manuale F1 interattivo aggiornati a `v0.5.0`.

---

## Sessione 17 – 2026-09-29 ✅ COMPLETE – v0.5.0 FIELD STUDIO MILESTONE 1
**BACnet Object Explorer, Modbus Smart Register Scan & 100% Offline-Proof Assets**

**Highlights:**
- ✅ **BACnet Object Explorer**:
  - Implementato `explore_bacnet_objects` in `scanners/bacnet.py` e route `GET /api/v1/bacnet/devices/{device_id}/objects`.
  * Supporta enumerazione `object-list` con `present_value`, `object_name`, `units` ingegneristiche formattate (`°C`, `%`, `bar`, `V`, `kW`, ecc.) e timeout short-circuit.
  * Modale frontend dedicato (`#bacnet-modal`) con filtro di ricerca live in tempo reale e pulsante "🔄 Rileggi Oggetti".
- ✅ **Modbus Smart Register Scan**:
  - Implementato `smart_register_scan` in `scanners/modbus.py` e route `POST /api/v1/modbus/smart-scan`.
  * Scansione euristica rapida a blocchi (FC03 Holding e FC04 Input) con isolamento errori 0x02.
  * Calcolo in tempo reale di Dec, Hex, signed Int16 e **Float32 IEEE 754 Big-Endian** per coppie di registri consecutive (es. temperature, pressioni).
  * Tab "Auto-Scan Registri" e pulsante "⚡ Avvia Auto-Scan" integrati in `#slave-modal`.
- ✅ **100% Offline-Proofing**:
  - Rimosso `@import` Google Fonts da `main.css`. Dashboard a latenza zero anche in bunker e centrali termiche interrate senza 4G.
- ✅ **Testing & Stabilità**:
  * Unit test passati: **24/24 OK in 5.1s** (aggiunti `test_modbus_smart_scan_endpoint` e `test_bacnet_objects_endpoint`).
  * Sintassi JavaScript verificata: 0 errori.
  * Selettori DOM verificati: 115/115 presenti in `index.html`.

---

## Sessione 16 – 2026-09-29 ✅ COMPLETE – v0.5.5 FIELD ENGINEER STUDIO
**Pure Light Theme Overhaul, 2-Column Full-Screen Architecture & Collapsible Diagnostic Dock**

**Highlights:**
- ✅ **Pure Light Theme Engine**: Reset forzato del vecchio `localStorage` browser `bham-theme = "dark"` e passaggio a `bham-theme-mode` con default tassativo chiaro (`#f1f5f9` canvas, `#ffffff` card, `#0f172a` testo ad alto contrasto).
- ✅ **Architettura a 2 Colonne a Pieno Schermo**: Eliminata la colonna fissa nera a destra (325px). Lo spazio orizzontale è dedicato interamente ai Canali di Scansione (360px) e all'Area Dati Tabelle flessibile.
- ✅ **Dock Diagnostico Inferiore a Scomparsa (38px)**: Console e ispettore frame seriali racchiusi in una barra inferiore pulita con metriche live (RS485 status, fps, bus load, err) ed espansione con pulsante `▲ Console`.
- ✅ **Cache-Busting Globale**: Aggiunti tag `?v=4.2.0` su CSS e script in `index.html`.

---

## Sessione 15 – 2026-09-29 ✅ COMPLETE – v0.5.1 FIELD PRO COCKPIT
**UI/UX Overhaul & Field Simplification: Soft Slate Palette, Zero Clutter, Central Empty State**

**Highlights:**
- ✅ **Soft Slate Industrial Palette**: Replaced harsh pitch-black canvas with a relaxed, high-legibility dark slate (`#0c121e`, `#141c2e`, `#24334f`) and calm accessible protocol accents.
- ✅ **Zero Overlap & Touch Ergonomics**: Eliminated all squashed text and overlapping elements seen in field tests. Input heights calibrated to 34px and action buttons to 34-36px for field tablets/laptops.
- ✅ **Central Hero Empty State**: Replaced the overwhelming wall of 4 empty tables with an intuitive, friendly discovery launch box (`#discovery-empty-state`). Tables appear automatically when devices are found.
- ✅ **Sidebar De-cluttering**: Removed redundant "Sito/Impianto" summary card from sidebar. Every rack channel now has clean spacing between protocol titles and discovery counter badges.
- ✅ **Testing & Verification**: 22/22 unit tests passing, zero JavaScript console errors, full backwards compatibility with all 101 DOM bindings.

---


## Sessione 14 – 2026-09-29 ✅ COMPLETE – v0.4.5 PRODUCTION RELEASE
**Audit fixes, permissions automation, responsive UI & deployment ready**

**Highlights:**
- ✅ **Audit resolution**: 11 issues fixed (3 critical, 4 high, 4 medium)
  - Race condition WebSocket broadcast (loop.call_soon_threadsafe)
  - AppState thread-safety (threading.Lock + error logging)
  - Serial sniffer error status propagation
  - BACnet MS-TP frame handling (incomplete vs invalid)
  - Modbus TCP CIDR subnet expansion
  - BACnet enrichment single Application reuse
  - Per-session abort events (vs global)
  - Secure tempfile handling + BackgroundTask cleanup
  
- ✅ **Permissions**: Automated setup (`scripts/setup_permissions.sh`)
  - Linux: setcap + dialout group configuration
  - Windows: documented UAC elevation
  - start.sh smart detection + sudo prompt
  - PERMESSI.md complete guide

- ✅ **UI/UX**: Responsive mobile/tablet design
  - Media queries: tablet (1023px), mobile (767px), small (479px)
  - Card-based table rendering for mobile
  - Device table sorting by ID
  - Touch-friendly button sizing

- **Version**: v0.4.0 (was 0.3.5)
- **Commits**: 7 (6 feature/fix + 1 merge)
- **Status**: Ready for production deployment

---

## Sessione 13 – 2026-09-27 ✅ DONE
**Gestione permessi admin – Linux & Windows**

- **`core/priv_check.py`** [NUOVO] – modulo centralizzato di privilege-check:
  - Linux: legge `CapPrm` da `/proc/self/status` (bit 13 = `CAP_NET_RAW`) + fallback raw socket test; controlla gruppo `dialout` via `grp` + `os.getgroups()`; tutto cached dopo il primo check.
  - Windows: `ctypes.windll.shell32.IsUserAnAdmin()`.
  - Espone `check_privileges()`, `has_cap_net_raw()`, `has_dialout()`, `is_admin()`. Mai solleva eccezioni; loga WARNING con comandi correttivi precisi.
- **`main.py`** – chiama `check_privileges()` al boot, prima di registrare i listener.
- **`scanners/ip_sniffer.py`** – pre-flight check `has_cap_net_raw()` prima dello sniff; se mancante chiude la sessione con `ScanStatus.ERROR` + `error_message` visibile dal frontend; `_run_sniff()` ritorna `str|None` per catturare `PermissionError` runtime.
- **`scanners/serial_sniffer.py`** – pre-flight check `has_dialout()` prima di aprire la porta; l'apertura seriale ora distingue `PermissionError` (con hint dialout/admin) da generica `Exception`.
- **`data/models.py`** – aggiunto campo `error_message: Optional[str] = None` a `ScanSession` per trasportare messaggi di errore leggibili verso il WebSocket/frontend.
- **`start.sh`** – blocco pre-avvio che legge `CapPrm` e controlla `groups`; mostra i comandi esatti se i permessi mancano, senza bloccare l'avvio.
- **`bham.exe.manifest`** [NUOVO] – UAC manifest Windows con `asInvoker` (nessuna elevazione forzata al lancio); DPI-aware per schermi ad alta risoluzione; le funzioni che richiedono admin (ARP sniffer) mostrano un errore friendly.
- **`bham.spec`** – aggiunto `manifest=_manifest` all'`EXE()` e `core.priv_check` agli `hiddenimports`.
- **Test:** 22/22 OK con `-W error`.

---

## Sessione 1 – 2026-09-27 ✅ DONE
**Step 1 – Bootstrap progetto**

- Albero directory completo, `main.py`, `core/`, `data/`, `api/`, `scanners/`, `reports/`, `frontend/`
- `.venv/` Python 3.12, tutte le dipendenze installate (pip 26)
- `requirements.txt` versioni pinnate
- Stack: FastAPI 0.115 | Pydantic 2.9 | pymodbus 3.7 | bacpypes3 0.0.102 | scapy 2.6

---

## Sessione 2 – 2026-09-27 ✅ DONE
**Step 2 – Motore Modbus RTU production**

- `scanners/modbus.py` riscritto da zero:
  - `_calc_crc()`, `_crc_valid()`, `_looks_like_modbus_rtu()` – CRC-16 puro Python
  - `_phase_zero()` – listen asincrono multi-baud, detection CRC-validated
  - `_early_exit()` – spy IDs {1,2,10}, LOCK al primo hit
  - `_full_sweep_rtu()` – client persistente, FAST_TIMEOUT=0.12s, progress granulare
  - `scan_tcp()` – Semaphore(20) concorrente, asyncio.as_completed
- Test CRC: frame noto OK, frame corrotto rifiutato ✓

---

## Sessione 3 – 2026-09-27 ✅ DONE
**Step 3 – BACnet production + FC43 + Report + UI progresso**

- `scanners/bacnet.py` riscritto production:
  - Who-Is broadcast via bacpypes3 nativo async
  - I-Am handler con upsert real-time su AppState
  - Read Property batched (Semaphore 10): vendor-id, vendor-name, model-name, fw-rev, sw-ver
- `scanners/modbus.py` – aggiunto `read_device_identification()` / `_fc43_blocking()` (FC43/ME 0x0E)
- `api/routes.py`:
  - `/report/excel` e `/report/pdf` → `FileResponse` reale (download diretto browser)
  - `/diag/modbus/fc43` → lettura Device Identification da slave specifico
- `reports/excel.py` riscritto con stile:
  - Header colorati (cyan/purple/green), righe alternate, auto-width, freeze pane, filtri
  - Foglio "Report Info" con metadati generazione
- `frontend/index.html` – aggiornato:
  - Barra di progresso animata con glow CSS
  - Header con pulsanti ⬇Excel / ⬇PDF / 📖API
  - Pannello FC43 diagnostics
  - Pulsante Clear state
- `frontend/css/main.css` – classi riusabili input-field, btn-primary, progress-active
- `frontend/js/app.js` – upsert idempotente tabelle, progress bar live, FC43 panel

---

## Sessione 4 – 2026-09-27 ✅ DONE
**Step 4.A – Configurazione Periferiche + Persistenza Sessioni**

- `core/hw_discovery.py` – NEW:
  - `list_serial_ports()` – pyserial, VID/PID RS485 noti (FTDI, CH340, CP210x, Prolific…), flag `rs485_likely`
  - `list_network_interfaces()` – psutil, solo NIC UP con IPv4 valido, esclude loopback/link-local
  - `suggest_single_iface()` – True se esiste una sola NIC cablata (stessa NIC per scan + client)
- `core/session_store.py` – NEW:
  - `save_session()` – JSON nominato + copia log in `sessions/`
  - `list_sessions()` – indice metadata (no caricamento risultati completi)
  - `load_session()`, `delete_session()` – con protezione path traversal
- `core/logger.py` – aggiunto `start_session_log()`, `stop_session_log()`, `current_session_log_path()`
- `data/models.py` – aggiunti: `SerialPortInfo`, `NetworkInterface`, `SessionConfig`, `SavedSessionMeta`
- `data/state.py` – aggiunto `session_config: Optional[SessionConfig]`, `set_session_config()`, `snapshot()` aggiornato
- `api/routes.py` – 8 nuovi endpoint (tags: setup, saved-sessions):
  - GET `/setup/serial-ports`, `/setup/network-interfaces`, `/setup/config`
  - POST `/setup/configure` → applica config + avvia session log
  - POST `/saved-sessions/save`, GET `/saved-sessions/list`
  - GET `/saved-sessions/{filename}`, DELETE `/saved-sessions/{filename}`
- `frontend/index.html` – pannello Setup overlay, modal Salva Sessione, modal Sessioni Salvate, badge config in header
- `frontend/js/app.js` – `scanSerialPorts()`, `scanNetworkIfaces()`, `confirmSetup()`, `saveSession()`, `loadSavedSessions()`, `deleteSavedSession()`
- `sessions/` directory creata
- `requirements.txt` – aggiunto `psutil>=5.9`
- Test: tutti passati (CRUD session_store, modelli Pydantic, import routes)

---

## Sessione 5 – 2026-09-27 ✅ DONE
**Step 4.B + UI Reskin Stitch v2.0 Industrial Telemetry**

- `frontend/css/main.css`:
  - Riscritto completamente applicando il Design System Stitch v2.0
  - CSS Custom Properties per Dual Mode: Light (Field High-Contrast) e Dark (Obsidian Telemetry)
  - Color-coding rigido per protocollo: Modbus `#00f2fe`/`#0284c7`, BACnet `#c084fc`/`#7c3aed`, ARP `#10b981`/`#059669`, FC43 `#f59e0b`/`#d97706`, Abort `#ef4444`/`#dc2626`
  - Font `JetBrains Mono` per valori HW (IP, MAC, seriale, registri, ID slave, timestamp), `Inter` per controlli e label
  - Layout a 3 colonne con scrolling indipendente per form, tabelle e live console
- `frontend/index.html`:
  - Default `data-theme="dark"`
  - Pulsante Toggle tema 🌙/☀️ con persistenza in `localStorage`
  - **Pulsante ⛔ Abort sticky in testata** (previene blocchi porta e flood bus)
  - Struttura semantica con classi `bham-*`
- `frontend/js/app.js`:
  - `applyTheme()` e `toggleTheme()` con sync stato
  - Rimosso monkey-patching di `handleEvent` (gestione nativa `config_updated`)
  - Rendering righe tabelle con classi `mono` e color-coding protocollo
- `data/maps_manager.py` – Riscrittura production completa:
  - `MapEntry` dataclass (`slave_id`, `register`, `register_type`, `label`, `unit`, `scale`, `description`)
  - `MapsManager` singleton con in-memory store
  - `import_from_json()` flessibile con supporto formati multipli BACS Help e upsert per slave ID
  - `export_to_json()` consolidato per download
  - `get_map()`, `set_map()`, `clear()`, `load_map()`, `save_map()`
- `api/routes.py`:
  - POST `/maps/import` – importazione definizioni mappa da JSON
  - GET `/maps/export` – esportazione mappa completa BACS Help
  - GET `/maps/{slave_id}` – consultazione mappa singolo slave
- `reports/pdf.py` – Riscrittura report PDF vettoriale production:
  - Layout ReportLab a due passate con `NumberedCanvas` (conteggio dinamico "Pagina X di Y")
  - Copertina impianto con metadati sessione (sito, porta seriale, NIC) e box riassuntivo dispositivi
  - Tabelle color-coded per Modbus (ciano), BACnet (viola) e ARP (smeraldo)
  - Wrapping sicuro celle con `Paragraph` per evitare overflow
- Python 3.12 compatibility:
  - Sostituito `datetime.utcnow()` deprecato con `datetime.now(timezone.utc)` e helper `utc_now` in `data/models.py`, `data/state.py`, `data/maps_manager.py`
  - Filtro mirato per deprecation `ast.NameConstant` di ReportLab
- Packaging & Standalone:
  - `pyproject.toml` (PEP 621) con metadati completi, script CLI `bham = "main:app"` e dipendenze
  - `bham.spec` per compilazione binario unico standalone via PyInstaller (asset frontend inclusi)
  - `README.md` esaustivo con architettura, installazione, guida operativa e documentazione API
- Test: tutti i 16 moduli importati e test funzionali passati con successo con `.venv/bin/python3 -W error` ✓

---

## Sessione 6 – 2026-09-27 ✅ DONE
**Step 5 – Fix Setup Wizard Startup + UI Clean Vector Overhaul + Motore KNXnet/IP Discovery**

- **Fix Setup Wizard al Reload/Avvio**:
  - `frontend/js/app.js`: in `loadInitialState()`, se `!cfgRes?.configured`, invoca automaticamente `openSetupModal()` e notifica a video.
  - Il wizard si apre in automatico se il sistema non è ancora configurato, ma resta sempre richiamabile dai pulsanti *Setup* nell'header o *Modifica Parametri*.
- **Overhaul Grafico & Rimozione Totale Emoji (Stile Industriale Autentico)**:
  - Eliminazione al 100% di tutte le emoji da HTML, CSS e JavaScript per eliminare il look "prototipo AI".
  - Incapsulamento di icone vettoriali SVG pulite, industriali e reattive (14-16px, 1.5-2px stroke) per tutti i controlli: porte seriali, interfacce NIC, download report, impostazioni, beacon live, log console, status pill e azioni modali.
  - Logging tecnico a console standardizzato con tag tecnici tra parentesi quadre: `[NET]`, `[MODBUS]`, `[BACNET]`, `[KNX]`, `[ARP]`, `[OK]`, `[WARN]`, `[ERROR]`, `[ABORT]`.
- **Implementazione Nativa Sottosistema KNXnet/IP Discovery**:
  - `scanners/knx.py` [NEW]:
    - Scanner asincrono UDP conforme standard KNXnet/IP Core (Service Type `0x0201` SEARCH_REQUEST / `0x0202` SEARCH_RESPONSE).
    - Multicast verso `224.0.23.12:3671` con fallback broadcast LAN `255.255.255.255:3671` (massima compatibilità gateway/router KNX commerciali).
    - Parsing DIB Device Info: Indirizzo Individuale a 16 bit formattato `Area.Linea.Device`, Friendly Name dispositivo (30 byte Latin-1), Numero di Serie, MAC Address, Medium di comunicazione (TP1, IP, RF, PL110).
    - Upsert real-time e broadcast WebSocket su `state.knx_devices`.
  - `data/models.py`:
    - Aggiunto `Protocol.KNX_IP = "knx_ip"`.
    - Modello Pydantic `KNXDevice` con attributi dedicati e validazione ISO timestamp `utc_now()`.
  - `data/state.py`:
    - Storage `self.knx_devices: dict[str, KNXDevice]`, metodo atomico `upsert_knx()`, aggiornati `snapshot()` e `clear()`.
  - `api/routes.py`:
    - Endpoint di scansione `POST /scan/knx/ip` con schema `KNXIPScanRequest`.
    - Endpoint dati `GET /devices/knx`.
  - `reports/excel.py`:
    - Aggiunto foglio dedicato "KNX Devices" con header arancione industriale `_HDR_ORANGE` (`#C2410C`), auto-width, filtri e conteggio nel foglio di riepilogo "Report Info".
  - `reports/pdf.py`:
    - Integrazione metadati e box riassuntivo KNXnet/IP nella prima pagina del report PDF.
    - Tabella vettoriale color-coded per periferiche KNX con indirizzo individuale, seriale, MAC e nome gateway.
  - `frontend/css/main.css`:
    - Token colore dedicati per KNX (`--bham-knx: #fb923c` in dark, `#c2410c` in light), badge count, pulsanti `.bham-btn-knx`, colorazione riga tabella `.color-knx`.
  - `frontend/index.html`:
    - Scheda sidebar per avvio scansione KNXnet/IP.
    - Tab filtro toolbar `KNX` con contatore badge dedicato.
    - Tabella dispositivi `KNXNET/IP DEVICES` con colonne: Indirizzo Individuale KNX, Nome Dispositivo, Medium, IP Gateway, MAC Address, Seriale.
  - `frontend/js/app.js`:
    - Gestione store `knx`, rendering idempotente tabella `renderKNXTable()`, avvio scansione `startKNX()`, inclusione nella sequenza "Scansione Rapida Globale", esportazione CSV per KNX.
- **Verifica e Test**:
  - Tutti i 17 moduli Python importati ed eseguiti senza warning con `.venv/bin/python3 -W error`.
  - Test funzionali completi di routing API, serializzazione, generazione foglio Excel KNX e report PDF ReportLab passati con successo ✓

---

## Sessione 7 – 2026-09-27 ✅ DONE
**Step 6 – Internazionalizzazione (IT, EN, ES) + Centro Impostazioni Unificato (De-duplicazione Pulsanti) + Manuale Completo & Help + Test Suite**

- **Supporto Multilingua (i18n)**:
  - `frontend/js/i18n.js` [NEW]:
    - Sistema di internazionalizzazione completo per **Italiano**, **Inglese** e **Spagnolo** (`it`, `en`, `es`).
    - Traduzione istantanea nel DOM di etichette (`data-i18n`), placeholder (`data-i18n-placeholder`) e titoli/tooltip (`data-i18n-title`).
    - Selettore rapido in testata (`IT | EN | ES`) con persistenza in `localStorage.getItem("bham-lang")`.
    - Messaggi dinamici tradotti tramite helper `window.t(key, params)`.
- **Centro Impostazioni Unificato & Eliminazione Pulsanti Doppi**:
  - Risolti i 4 pulsanti duplicati che aprivano la configurazione (header Setup, telemetry strip "Modifica Parametri", Modbus card, sidebar footer "Ricarica Setup").
  - Rimossi i controlli ridondanti: eliminato `Ricarica Setup` dal footer sidebar (sostituito con link rapido `Mappe BACS`); la telemetry strip attiva ora mostra parametri informativi compatti.
  - Sostituito il vecchio modal Setup con il nuovo **Centro Impostazioni BHAM** a 5 schede:
    1. *Hardware & Porte* (Porta seriale RS485 con auto-scan, baud, parity, stop; Interfacce NIC con auto-scan e visualizzazione IP).
    2. *Parametri Scansione* (Timeout Modbus lento/veloce, Spy IDs sentinella, KNX multicast/timeout, ARP duration).
    3. *Aspetto & Lingua* (Selezione lingua, tema chiaro/scuro, buffer console).
    4. *Sessioni Salvate* (Archivio sessioni di collaudo con ripristino istantaneo nello stato attivo, download JSON ed eliminazione).
    5. *Mappe BACS Help* (Visualizzazione mappe attive, importazione diretta da testo/JSON, esportazione e azzeramento).
  - Aggiunto il pulsante per il download del **Report PDF vettoriale** nella toolbar dei report accanto a CSV ed Excel.
  - Toggle tema compatto ad icona unica (☀️ / 🌙) nell'header.
- **Manuale & Help Completo**:
  - `frontend/js/manual-content.js` [NEW]:
    - Guida di campo interattiva integrata nella Web UI con navigazione a capitoli, accessibile dal tasto `Guida & Manuale` nell'header e con scorciatoia tastiera `F1`.
    - 8 capitoli tecnici completi disponibili in IT, EN ed ES: Quick Start, Modbus RTU/TCP, BACnet/IP, KNXnet/IP, ARP L2, Mappe BACS Help, Troubleshooting da campo e REST API.
  - `MANUALE_UTENTE.md` [NEW]:
    - Manuale utente completo in formato Markdown per consultazione offline e stampa, servito direttamente anche dall'applicazione web (`/MANUALE_UTENTE.md`).
- **Verifica e Miglioramenti Software**:
  - `data/state.py`: aggiunto metodo atomico `restore_snapshot()` per ricaricare sessioni archiviate nello stato attivo e trasmetterle via WebSocket a tutti i client connessi.
  - `api/routes.py`: aggiunto endpoint `POST /saved-sessions/{filename}/restore`.
  - `core/session_store.py`: corretto conteggio periferiche in `list_sessions()` con inclusione di `knx`.
  - `scanners/base.py`: aggiunto `reset_abort()` esplicito per prevenire race-condition sul flag abort tra scansioni concorrenti.
  - `frontend/js/app.js`: implementato modal di dettaglio slave per Modbus (sostituito `alert()` primitivo con interfaccia tabellare registri e metadati).
  - Version bump a `v0.3.0` in `core/config.py` e `pyproject.toml`.
  - `bham.spec`: aggiunto `scanners.knx` a `hiddenimports`.
- **Test Suite Automatizzata**:
  - `tests/test_bham.py` [NEW]: suite completa di 15 test unitari e di integrazione (modelli, state, session_store, maps_manager, reportistica Excel/PDF, endpoint REST API).
  - Tutti i 15 test passati con successo con `.venv/bin/python3 -W error -m unittest discover tests` (zero errori, zero warnings) ✓

---

## Prossimi Passi Futuri (Feature opzionali / Espansioni post-collaudo)
- [ ] Recupero/Lookup online registri preconfigurati e profili costruttori (Carel, Schneider, Daikin, ABB, ecc.)
- [ ] `scanners/modbus.py` – Polling registri periodico basato sulle mappe BACS Help importate
- [ ] Supporto BACnet MS-TP nativo su seriale RS485 oltre a BACnet/IP (Master Poller attivo)

---

## Stack confermato
| Componente | Versione |
|---|---|
| Python | 3.12.3 |
| FastAPI | 0.115.0 |
| Pydantic | 2.9.2 |
| pymodbus | 3.7.2 |
| bacpypes3 | 0.0.102 |
| scapy | 2.6.0 |
| openpyxl | 3.1.5 |
| reportlab | 4.2.5 |
| psutil | 7.2.2 |

---

## 🔄 Prompt di Ripartenza – COPIA NELLA NUOVA CHAT

```
Sei un Senior Software Engineer che continua lo sviluppo di BHAM (BACS Help Auto Mapper).

PRIMA AZIONE OBBLIGATORIA – leggi questi due file:
  cat /home/giuliano/Documenti/BHAM/DEVLOG.md
  find /home/giuliano/Documenti/BHAM -not -path '*/.venv/*' -not -path '*/__pycache__/*' -not -path '*/.git/*' | sort

CONTESTO RAPIDO:
  Progetto: /home/giuliano/Documenti/BHAM/
  Venv:     .venv/bin/python3  (Python 3.12, pip già installato)
  Avvio:    .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8765 --reload

SESSIONI COMPLETATE:
  ✅ Sessione 1 – Bootstrap (struttura, main.py, WebSocket, modelli Pydantic)
  ✅ Sessione 2 – Motore Modbus RTU (Phase Zero, Early Exit, Full Sweep, TCP)
  ✅ Sessione 3 – BACnet production, FC43, FileResponse report, UI barra progresso
  ✅ Sessione 4 – hw_discovery (RS485 + NIC), session_store, logger session,
                  modelli SessionConfig, 8 endpoint setup/saved-sessions,
                  UI pannello Setup overlay + modali Salva/Sessioni Salvate
  ✅ Sessione 5 – UI Reskin completo Stitch v2.0 Industrial Telemetry (Dual Theme, font, sticky abort, 3-col layout),
                  maps_manager.py production (import/export BACS Help JSON),
                  3 endpoint /maps/*, PDF report stilizzato con ReportLab e NumberedCanvas,
                  pyproject.toml, bham.spec per PyInstaller standalone, README.md,
                  compatibilità Python 3.12 (utc_now / timezone.utc), test passati con -W error.
  ✅ Sessione 6 – Fix Setup Wizard al reload se non configurato + apertura on-demand,
                  eliminazione totale emoji e introduzione icone SVG industriali incapsulate,
                  implementazione completa modulo KNXnet/IP (scanners/knx.py multicast/broadcast UDP,
                  modelli, rotte API, schede Excel e sezioni PDF dedicate, UI tabella e filtri KNX).
  ✅ Sessione 7 – Internazionalizzazione (IT, EN, ES) dinamica con selettore in header,
                  Centro Impostazioni Unificato (5 schede: Hardware, Scansione, Aspetto, Sessioni con ripristino, Mappe BACS Help),
                  eliminazione completa pulsanti duplicati e layout pulito,
                  Manuale Tecnico & Guida di Campo interattiva (F1) in 3 lingue + MANUALE_UTENTE.md offline,
                  modal ispezione dettagli slave Modbus con tabella registri,
                  integrazione download PDF nella toolbar, suite test automatizzati (15 test passati con -W error).
  ✅ Sessione 8 – Gestione Porte Speciali & Custom (BAC0..BACF, Modbus TCP multi-port, KNX custom) su tutti i pannelli,
                  preset rapidi con chip interattivi e hint dinamici, parametri predefiniti nel Centro Impostazioni,
                  risoluzione bug critico bacpypes3 NormalApplication + abort istantaneo,
                  prevenzione leak socket con chiusura deterministica in finally,
                  aggiornamento manuale in IT/EN/ES, test suite estesa a 19 test passati al 100% con -W error.
  ✅ Sessione 9 – Sniffer Seriale Passivo (RS485 Zero-TX / Stealth Mode), Bus Health telemetria & RS485 Inspector live,
                  dissettori per Modbus RTU (M➔S, S➔M, FC01..FC16, FC43) e BACnet MS-TP (Token Ring, CRC-8, CRC-16),
                  suite test estesa a 22 test passati al 100% con -W error.
  ✅ Sessione 10 – Full Software Audit, Perfezionamento i18n al 100% (157 chiavi tradotte), parità DOM (93/93 elementi),
                   verifica reportistica Excel/PDF e baseline di ripartenza.
  ✅ Sessione 11 – Chiusura Task di Sviluppo Sprint v0.3.0, consolidamento documentazione e specifiche standalone (bham.spec),
                   preparazione e rilascio checklist operativa per Field Testing (Round 1).

REGOLE DI LAVORO:
  - Aggiorna DEVLOG.md ad ogni step completato
  - Testa ogni modulo con .venv/bin/python3 -W error prima di dichiararlo done
  - Non ripetere lavoro già fatto – leggi sempre DEVLOG prima di scrivere codice
  - Stile: type hints completi, docstring, logger.getChild(), costanti tunables isolate
```

---

## Sessione 8 – Gestione Porte Speciali (BAC0..BACF, Custom & Multi-Port) + Full Software Audit

### Obiettivi Richiesti:
1. Gestione scansioni speciali su protocolli come BACnet dove le porte UDP variano secondo la serie `BAC0`, `BAC1`, etc.
2. Possibilità di inserire sia porte basiche/standard che porte custom su ogni singolo pannello di protocollo (Modbus TCP, BACnet/IP, KNXnet/IP).
3. Riverifica completa del software: stabilità, operatività di tutte le funzionalità e assenza di warning/errori.

### Modifiche Implementate:

#### 1. Backend – Gestione Porte Speciali e Parser Multi-Protocollo
- **`scanners/bacnet.py`**:
  - `parse_bacnet_ports(spec)`: supporto per interi (47808), simboli `BAC0`..`BACF` (`0xBAC0`..`0xBACF` = 47808..47823), range (`BAC0..BAC3`, `47808-47812`), elenchi separati da virgola (`BAC0, BAC1, 50000`), prefissi hex `0xBAC0` e notazione con etichetta `BAC0 (47808)`.
  - `port_label(port)`: formattazione con indicatore simbolico.
  - Risolto bug critico stack `bacpypes3`: passaggio da `Application` a `NormalApplication` con gestione automatica del prefisso di sottorete CIDR (`/24` o `/8` su loopback), attesa dei task di inizializzazione endpoint (`_transport_tasks`) prima dell'invio Who-Is.
  - Implementato abort immediato per `app.who_is()`: gestione non bloccante con cancellazione istantanea del future e chiusura pulita dei socket in `finally`.
  - Risolta perdita di descrittore socket nel rilevamento dell'IP host con context manager `with socket.socket(...)`.
- **`scanners/modbus.py`**:
  - `parse_modbus_tcp_ports(spec)`: parser robusto per porte Modbus TCP singole, multiple (es. `502, 503, 5020`) o range (`502-504`).
  - `scan_tcp()`: genera combinazioni `(host, port)` con scansione concorrente via semaforo; sostituito `as_completed` con `asyncio.wait(pending)` per eliminare il warning di coroutine non attese all'abort.
- **`scanners/knx.py`**:
  - `scan()`: invio multicast e broadcast all'effettiva porta configurata `target_port` (standard 3671 o custom 3672, etc.).
  - Chiusura esplicita in `finally` sia del transport che del socket sottostante per prevenire `ResourceWarning`.
- **`api/routes.py`**:
  - Aggiornati i modelli Pydantic `ModbusTCPScanRequest` (`tcp_port: int | str = 502`, `tcp_ports: list[int] = []`) e `KNXIPScanRequest` (`port: int | str = 3671`).

#### 2. Frontend – UI Controlli Porte & Preset Chips
- **`frontend/index.html`**:
  - Modbus TCP: aggiunto input porta TCP con hint dinamico e pulsanti chip rapidi: `502 (Std)`, `503`, `5020`, `Multi`.
  - BACnet/IP: input porta con supporto simboli `BAC0`..`BACF` e chip rapidi: `BAC0 (47808)`, `BAC1 (47809)`, `BAC0..BAC3`, `BAC0..BACF`.
  - KNXnet/IP: input porta con chip rapidi: `3671 (Std)`, `3672`, `Multi`.
  - Centro Impostazioni (*Parametri Scansione*): aggiunti campi di default per porte Modbus TCP, BACnet/IP e KNXnet/IP.
- **`frontend/css/main.css`**:
  - Aggiunti stili per `.bham-preset-pills` e `.bham-btn-chip` compatibili con tema scuro e chiaro.
- **`frontend/js/app.js`**:
  - Implementati helper reattivi `setTcpPortPreset`, `updateTcpPortHint`, `setBacnetPortPreset`, `updateBacnetPortHint`, `setKnxPortPreset`, `updateKnxPortHint`.
  - Aggiornati `startTCP()`, `startBACnet()`, `startKNX()` per trasmettere i valori inseriti dall'utente alle API.
  - Sincronizzazione automatica e persistenza delle porte in `localStorage` (`bham-scan-params`) con caricamento all'avvio.
- **`frontend/js/i18n.js`**:
  - Aggiunte chiavi di traduzione per etichette porte e campi impostazioni in Italiano, Inglese e Spagnolo.
- **`frontend/js/manual-content.js` & `MANUALE_UTENTE.md`**:
  - Documentata l'architettura delle porte speciali BAC0..BACF, i range e le porte gateway Modbus/KNX in tutte le lingue.

#### 3. Test & Verifica di Sistema
- Eseguita suite automatica di 19 test unitari e di integrazione (`tests/test_bham.py`):
  - Verifica modelli e serializzazione timezone-aware
  - Test AppState e ripristino snapshot
  - Test MapsManager (import/export 3 punti su 2 slave)
  - Test esportazione report Excel e PDF
  - Test endpoint REST API (Health, State, Setup, Saved Sessions con restore e delete, Abort)
  - Test parsing porte BACnet (`BAC0`, `BAC1`, `BACF`, range `BAC0..BAC3`, `0xBAC0`, custom)
  - Test etichette porte BACnet (`port_label`)
  - Test parsing porte Modbus TCP (`502`, `503`, `502, 503, 5020`, range, liste)
  - Test avvio scansioni asincrone con porte custom e gestione abort pulito
- Risultato test: **19/19 superati con codice di uscita 0 e ZERO warning/errori** eseguito con flag `-W error`.
- Verifica runtime FastAPI: **36 route HTTP/WS correttamente registrate e montate**.
- Verifica sintassi JS: `node -c` superato con esito positivo per tutti i file frontend.

---

## Sessione 9 – Sniffer Seriale Passivo (RS485 Zero-TX / Stealth Mode), Bus Health & RS485 Inspector

### Obiettivi Richiesti:
1. Implementazione completa del modulo di sniffing seriale passivo RS485 (Zero-TX / Stealth Mode) per operare su bus fisici in marcia con PLC Master attivi (Carel, Siemens, Johnson Controls, Honeywell, Schneider, ecc.) evitando qualsiasi collisione hardware o disturbo al ciclo di regolazione.
2. Dissettore e decodifica approfondita per frame Modbus RTU:
   - Differenziazione automatica tra Query del Master (M ➔ S) e Risposte dello Slave (S ➔ M).
   - Validazione checksum CRC-16.
   - Decodifica codici funzione FC01, FC02, FC03, FC04, FC05, FC06, FC15, FC16, FC43 (MEI).
   - Estrazione automatica registri, conteggi e valori con catalogazione nello stato dei dispositivi con etichetta `[SNIFFED]`.
3. Dissettore per frame BACnet MS-TP:
   - Riconoscimento preambolo `0x55 0xFF`.
   - Validazione Header CRC-8 conforme ASHRAE 135 (residuo `0x55`).
   - Mappatura continua della catena del token ring (MAC 0..127) e frame Poll For Master.
   - Validazione Data CRC-16 (polinomio ISO-HDLC/X.25, residuo `0xF0B8`) e catalogazione automatica nello stato dispositivi.
4. Calcolo in tempo reale della telemetria Bus Health:
   - Frame Rate (FPS).
   - Packet Error Rate % (PER) con soglie visive di qualità del doppino.
   - Stima percentuale di Bus Load in relazione al baudrate attivo.
   - Mappatura nodi e dispositivi attivi rilevati.
5. Integrazione completa nella Web UI:
   - Card dedicata "Sniffer Passivo (RS485)" nella barra laterale con filtri di protocollo, baudrate, parità e durata.
   - Selettore a tab nella colonna di destra: "Live Log" vs "RS485 Inspector" con badge numerico dinamico dei frame catturati.
   - Banner telemetrico Bus Health a scomparsa con chip grafici dei nodi attivi.
   - Tabella Inspector dei frame seriali in tempo reale con streaming via WebSocket (`serial_frame`, `serial_bus_health`).
6. Supporto multi-lingua completo (Italiano, Inglese, Spagnolo) e documentazione manuale interna ed offline.
7. Suite di test di unità e integrazione con verifica a zero warning sotto flag `-W error`.

### Modifiche Implementate:

#### 1. Modelli Dati & Gestione Stato (`data/models.py`, `data/state.py`)
- Definito enum `FrameDirection` (`MASTER_TO_SLAVE`, `SLAVE_TO_MASTER`, `TOKEN`, `POLL_FOR_MASTER`, `BROADCAST`, `UNKNOWN`).
- Creato modello Pydantic `SerialFrame`: timestamp, proto, raw_hex, direction, sender_id, target_id, func_or_type, data_summary, crc_ok, byte_count.
- Creato modello Pydantic `BusHealth`: timestamp, fps, error_rate_pct, bus_load_pct, total_frames, error_frames, active_nodes, status.
- Esteso `AppState`:
  - Aggiunti storage e metodi `update_bus_health()`, `record_serial_frame()` (mantiene gli ultimi 500 frame catturati).
  - Aggiornati metodi `snapshot()` e `clear()` per includere e azzerare `bus_health` e `serial_frames`.

#### 2. Motore di Sniffing Asincrono Zero-TX (`scanners/serial_sniffer.py`)
- Modulo asincrono nativo basato su `pyserial_asyncio` e `asyncio`:
  - Apertura seriale in sola lettura hardware senza mai invocare scritture su TX né commutare linee RTS/DTR.
  - `_auto_detect_baud_parity()`: scansione passiva silenziosa per agganciare baudrate (9600, 19200, 38400, 57600, 115200) e parità (None, Even, Odd) al primo frame valido.
  - `_dissect_modbus_rtu()`: parser a macchina a stati con buffer circolare, validazione CRC-16, tracking delle query del master per correlare indirizzi di registro richiesti con i byte restituiti dallo slave, auto-upsert in `state.upsert_modbus(device)` con flag `sniffed=True`.
  - `_dissect_bacnet_mstp()`: parser preambolo `0x55 0xFF`, calcolo CRC-8 Header (ASHRAE 135) e CRC-16 Data (ISO-HDLC), catalogazione token ring e upsert in `state.upsert_bacnet(device)`.
  - `_health_calculator()`: task periodico (1s) che calcola telemetria del bus e invia aggiornamenti via WebSocket ai client connessi.

#### 3. API REST & Controllo Scansione (`api/routes.py`)
- Definito modello di richiesta `SerialSniffRequest` (`port`, `baudrate`, `parity`, `stopbits`, `protocol_filter`, `duration`).
- Implementato endpoint `POST /api/v1/scan/serial/sniff`: avvio in background dello sniffer passivo con monitoraggio dell'abort flag.
- Implementato endpoint `GET /api/v1/diag/serial/health`: restituzione istantanea della telemetria Bus Health attiva.
- Integrazione con `POST /api/v1/scan/abort` per l'arresto immediato del task di sniffing seriale e rilascio sicuro della porta.

#### 4. Frontend & Design System Industriale (`frontend/index.html`, `frontend/css/main.css`, `frontend/js/app.js`)
- **Card Sniffer Passivo**:
  - Filtro Protocollo (Auto, Modbus RTU, BACnet MS-TP), Baudrate (Auto, 9600..115200), Parità, Durata (15s, 30s, 60s, Continuo).
  - Pulsanti tattici `Avvia Sniffing Passivo` e `Ferma Sniffer`.
- **RS485 Live Inspector & Bus Health Banner**:
  - Switcher a schede `Live Log` / `RS485 Inspector` con contatore telegrammi.
  - Strip telemetrica ad alta visibilità: stato bus (OTTIMO, ACCETTABILE, CRITICO), FPS, Bus Load %, PER %, chip nodi attivi.
  - Tabella ad alto contrasto dei frame: timestamp, protocollo, direzione (`M➔S`, `S➔M`, `TOKEN`, `POLL`), mittente, destinatario, funzione/tipo, registri/dati, badge CRC (`OK` / `ERR`).
- **Streaming WebSocket**:
  - Gestione in tempo reale degli eventi `serial_frame` e `serial_bus_health` con buffering e rendering reattivo senza latenza.

#### 5. Internazionalizzazione & Manualistica (`frontend/js/i18n.js`, `frontend/js/manual-content.js`, `MANUALE_UTENTE.md`)
- Traduzione di tutti i termini, badge e controlli UI in Italiano, Inglese e Spagnolo (`i18n.js`).
- Creazione del capitolo 5: "Sniffer Seriale Passivo (RS485 Zero-TX / Stealth Mode)" nel manuale integrato per IT, EN ed ES con indicazioni sul Packet Error Rate (PER), regole fisiche del bus e mitigazione disturbi.
- Aggiornamento della documentazione offline in `MANUALE_UTENTE.md` e `frontend/MANUALE_UTENTE.md` con tabella REST API e panoramica operativa.

#### 6. Suite di Test Automatizzata (`tests/test_bham.py`)
- Aggiunti 3 test completi in `TestSerialSniffer`:
  - `test_dissect_modbus_rtu_query_and_response()`: verifica correlazione query M➔S ed estrazione registri slave S➔M, validazione CRC-16, upsert su AppState con etichetta `[SNIFFED]`.
  - `test_dissect_bacnet_mstp()`: verifica trame Token e Data MS-TP, validazione Header CRC-8 (ASHRAE 135) e Data CRC-16 (ISO-HDLC), catalogazione nodi.
  - `test_serial_sniff_endpoint_and_health()`: test d'integrazione API per avvio sniffing, intercettazione abort e lettura endpoint `/diag/serial/health`.
- Risultato totale: **22/22 test superati in 0.7s con ZERO errori e ZERO warning con `-W error`**.
- Verifica sintassi JS: `node -c` superato con esito positivo per tutti i file frontend.

---

## Sessione 10 – Full Software Audit, Perfezionamento i18n & Baseline di Ripartenza ✅ DONE

### Obiettivi e Attività Eseguite:
1. **Verifica Globale Backend & Dipendenze**:
   - 24/24 moduli Python caricati e testati senza errori.
   - Censite tutte le 38 route registrate in FastAPI (REST, WS, Docs).
   - Suite di test automatizzata: **22/22 test passati in 0.7s con ZERO errori e ZERO warning con `-W error`**.
2. **Audit e Perfezionamento Frontend / i18n**:
   - Risolto disallineamento su due chiavi HTML (`duration_label` e `selected_port`), aggiunte e allineate in `frontend/js/i18n.js`.
   - Raggiunta parità assoluta (100%) con **157 chiavi tradotte in Italiano, Inglese e Spagnolo**.
   - Integrità DOM: 93/93 elementi interrogati da `app.js` verificati su 116 ID presenti in `index.html`.
   - Manuale utente (`manual-content.js` e `MANUALE_UTENTE.md`): 9 capitoli speculari sincronizzati per IT, EN ed ES.
3. **Validazione Reportistica**:
   - Generazione collaudata con dataset multi-protocollo completo per Excel (.xlsx) e PDF vettoriale (%PDF-1.4).
4. **Stato Runtime**:
   - Demone Uvicorn attivo su `http://0.0.0.0:8765` con bind globale per accesso da rete locale (LAN).
   - Endpoint di controllo verificati: `/api/v1/health` (HTTP 200), `/api/v1/state` (HTTP 200), `/MANUALE_UTENTE.md` (HTTP 200).

### Baseline per la Prossima Chat / Prompt di Ripartenza:
- **Repo / Workspace**: `/home/giuliano/Documenti/BHAM`
- **Ambiente Virtuale**: `.venv/bin/python3` (Python 3.12.3)
- **Avvio Demone**: `.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8765`
- **Esecuzione Test**: `.venv/bin/python3 -W error -m unittest discover -s tests -p "test_*.py"`
- **Stato**: Versione v0.3.0 stabile, pronta per il campo e per nuove evoluzioni, zero debiti tecnici.

---

## Sessione 11 – 2026-09-27 ✅ DONE
**Chiusura Sprint v0.3.0, Consolidamento Task, Allineamento Packaging & Checklist Operativa Field Test (Round 1)**

### 1. Sintesi e Decisioni Strategiche:
- **Chiusura formale di tutti i task di sviluppo per la release v0.3.0**:
  - Il sistema ha raggiunto piena maturità con supporto attivo a Modbus RTU/TCP (multi-port, FC43), BACnet/IP (Who-Is/I-Am, serie `BAC0`..`BACF`), KNXnet/IP (multicast/broadcast), ARP L2 e Sniffer Seriale Passivo RS485 (Zero-TX, Modbus/BACnet MS-TP e Bus Health live).
  - Tutti i task aperti sono stati formalmente completati, verificati e sigillati.
- **Valutazione Feature "Recupero Registri Online / Profili Preconfigurati"**:
  - Come concordato, la ricerca e l'aggancio automatico online dei registri per dispositivi non standardizzati (Carel, Schneider, Daikin, Socomec, ABB, ecc.) presenta complessità significative legate alla varietà delle versioni firmware, formati proprietari e assenza di un registro pubblico unificato.
  - La feature viene catalogata per la roadmap successiva: dopo il primo giro di collaudo sul campo reale, si valuterà se integrare un database/catalogo profili JSON offline precaricato oppure un servizio cloud di lookup.
  - Al momento l'importazione mappe è già pienamente operativa tramite il motore BACS Help JSON (`/api/v1/maps/*` e scheda dedicata nel Centro Impostazioni).

### 2. Manutenzione e Aggiornamento Asset:
- **`bham.spec`**:
  - Aggiunto `'scanners.serial_sniffer'` nei `hiddenimports` per garantire la corretta inclusione dello sniffer seriale passivo e del Bus Health nella compilazione autonoma PyInstaller standalone.
- **`README.md`**:
  - Aggiornato con tutte le caratteristiche introdotte nelle ultime sessioni: scanner KNXnet/IP, Sniffer Seriale Passivo RS485 Zero-TX, telemetria Bus Health, gestione multi-port e range per Modbus TCP e BACnet (`BAC0`..`BACF`), sistema i18n trilingue e Manuale Integrato F1.
  - Aggiornato l'albero della struttura directory con tutti i file attuali (`i18n.js`, `manual-content.js`, `knx.py`, `serial_sniffer.py`, `test_bham.py`, `MANUALE_UTENTE.md`).
- **Test Suite**:
  - 22/22 test unitari e di integrazione passati al 100% con flag `-W error`.

### 3. Esito del Collaudo di Sviluppo & Approvazione Formale (Sprint Sign-Off):
- **Stato**: Esito pienamente positivo, approvazione e piena soddisfazione espressa dall'utente.
- **Release**: `v0.3.0` congelata con successo, zero debiti tecnici, architettura robusta e collaudata.
- **Prossimo Step**: Esecuzione del Round 1 di collaudo e test sul campo (Field Testing su impianti reali).

---

## Sessione 12 – 2026-09-27 ✅ DONE
**Automazione CI/CD Rilasci GitHub, Packaging Debian/Ubuntu (.deb), One-Line Linux Installer e WinGet Auto-Publish**

### Attività Svolte:
1. **Automazione Avanzamento Versioni (`scripts/bump_version.py`)**:
   - Creato script Python per aggiornamento sincronizzato di `pyproject.toml`, `core/config.py` e manifesti WinGet `winget/*.yaml` secondo lo standard SemVer (patch, minor, major o versione custom).
2. **Release 1-Click da Browser (`.github/workflows/release.yml`)**:
   - Aggiunto trigger `workflow_dispatch` con menu a tendina per rilascio in 1 click dal portale web GitHub.
   - Creazione automatica del commit, del Git Tag, compilazione parallela cloud per Windows x64 e Linux x64, calcolo hash SHA256 e pubblicazione della GitHub Release.
3. **Packaging Linux Nativo & One-Line Installer**:
   - `scripts/package_deb.sh`: compilazione pacchetto standard Debian/Ubuntu `.deb` con controllo dipendenze, permessi dialout e servizio systemd.
   - `scripts/install.sh`: universal one-line installer per tecnici di cantiere (`curl -fsSL https://www.bacshelp.com/bham/install.sh | sudo bash`).
4. **Automazione WinGet (`vedantmgoyal2009/winget-releaser`)**:
   - Integrato nel workflow cloud per invio automatico della Pull Request al repository ufficiale Microsoft `microsoft/winget-pkgs` tramite segreto `WINGET_TOKEN`.
5. **Guida Operativa & Brand Domain**:
   - Documentate tutte le procedure in `GUIDA_GITHUB_WINGET.md`, con valorizzazione del dominio `www.bacshelp.com` per redirect permanenti e documentazione su `bham.bacshelp.com`.

---

## Sessione 16 – 2026-09-29 ✅ DONE
**Ricostruzione Radicale UI/UX (Smonta e Riparti): Design System "Field Engineer Studio" v4.2, Risoluzione Causa Nero da localStorage, Cache-Busting & Dock Console Inferiore a Scomparsa**

### Attività Svolte:
1. **Risoluzione della Causa Radice "Schermata Nera"**:
   - Isolato il problema del browser `localStorage` che persisteva la chiave `bham-theme = "dark"` dai test precedenti, forzando la modalità scura su qualsiasi ricaricamento.
   - `frontend/js/app.js`: azzerata programmaticamente la chiave `bham-theme`, impostata nuova chiave `bham-theme-mode` con default tassativo su `light`.
   - `frontend/index.html`: inserito cache-busting `?v=4.2.0` su `<link rel="stylesheet">` e su tutti gli script per impedire al browser di riutilizzare vecchi asset in cache.
2. **Smontaggio e Ricostruzione Architettura (Nuovo Studio a 2 Colonne)**:
   - Eliminata la colonna fissa destra da 325px nera che schiacciava il layout e dava l'impressione di un videogioco terminale.
   - Creazione del **Dock Diagnostico Inferiore a Scomparsa (38px)** con barra telemetrica compatta (RS485 status, fps, load, nodi) ed espansione fluida a 280px con un click sul pulsante `▲ Console`.
   - Ripartizione ottimale a tutto schermo:
     - **Sinistra (360px)**: Canali di scansione verticali in card bianche pure (`#ffffff`), input a 34px, badge discovery live (`0 dev` / `3 dev`).
     - **Destra (Flessibile)**: Toolbar con tab filtri, ricerca rapida, hero empty state e tabelle dati a tutto schermo.
3. **Design System Enterprise Light v4.2 (`frontend/css/main.css`)**:
   - Canvas ardesia chiarissima `#f1f5f9`, card bianche `#ffffff`, bordi sottili `#e2e8f0`, testi antracite ad alto contrasto `#0f172a`.
   - Gerarchia bottoni industriale: primario blu solido `#0284c7`, abort bianco con bordo rosso tenue `#fecaca`.
   - Tabelle con intestazioni sobrie su fondo `#f8fafc`, righe bianche spaziose, badge di stato flat senza bagliori neon.
4. **Verifiche & Integrità**:
   - Sintassi JavaScript (`node -c frontend/js/app.js`): **0 errori**.
   - Integrità selettori DOM: **102/102 verificati e perfettamente allineati**.
   - Suite di test Python: **22/22 superati** (`Ran 22 tests in 0.722s - OK`).

---

## Sessione 17 – 2026-09-29 ✅ DONE
**BACnet Object Explorer, Modbus Smart Register Scan, Font Offline & Risoluzione Visibilità/Accessibilità Live Log ed RS485 Inspector**

### Attività Svolte:
1. **Esploratore Oggetti BACnet (BACnet Object Explorer)**:
   - Backend: endpoint `GET/POST /api/v1/bacnet/devices/{device_id}/objects` e scanner `explore_bacnet_objects` in `scanners/bacnet.py` (lettura `object-list` con fallback a probe selettivo AI, AV, BI, BV, MSI, MSV).
   - Frontend: modale `#bacnet-modal` dedicato con tabella responsive, badge per tipo oggetto, filtro di ricerca istantaneo e pulsante di aggiornamento manuale.
   - Nella tabella BACnet aggiunta azione rapida "🔍 Oggetti" per ogni riga dispositivo.
2. **Modbus Smart Register Scan (Auto-Scan Registri & Decodifica Telemetrie)**:
   - Backend: endpoint `POST /api/v1/modbus/smart-scan` e funzione `smart_register_scan` in `scanners/modbus.py` con probe automatico registri 0..100/40001..40100 (FC03/FC04).
   - Calcolo automatico decodifica: Raw Hex, Int16 con segno e float IEEE 754 Big-Endian (se 2 registri adiacenti sono valorizzati).
   - Frontend: sotto-schede nel modale Modbus Slave ("Registri Mappati" vs "Smart Scan"), pulsante rapido "⚡ Avvia Auto-Scan" e tabella risultati telemetrici.
3. **100% Offline-Proof**:
   - Rimosso `@import url(fonts.googleapis.com)` da `frontend/css/main.css`, sostituito con stack di sistema robusto e zero dipendenze Internet per cantieri privi di connettività.
4. **Risoluzione Visibilità & Funzionamento Live Log e RS485 Inspector**:
   - **Diagnosi della causa radice**: Il dock console inferiore (`#console-col`) aveva la classe `collapsed` di default (altezza 38px, `overflow: hidden`). Quando l'utente cliccava sulle etichette o su "Avvia Ascolto", la funzione `switchConsoleTab()` scambiava solo i tab interni senza mai rimuovere `.collapsed`. Di conseguenza, la tabella dei frame RS485 e il log rimanevano invisibili e tagliati fuori dallo schermo.
   - **Controlli Espliciti Dock**: Introdotte le funzioni `expandConsole()`, `collapseConsole()`, `toggleConsole()`, `handleDockHeaderClick()` e `openConsoleTab(tab)` in `frontend/js/app.js`.
   - **Default & Persistenza Flessibile**: Rimosso `collapsed` iniziale da `index.html`. In `loadSavedScanParams()`, la console si apre sempre visibile a meno che l'utente non abbia espressamente cliccato su "Riduci" (`coll === "1"`).
   - **Pulsanti di Accesso Diretto e Navigazione Rapida**:
     - Nella toolbar centrale delle tabelle (`.bham-toolbar-center`), inseriti i pulsanti rapidi `Live Log` e `RS485 Inspector` con badge contatore frame live sincronizzato (`#center-frame-badge`).
     - Nell'header principale dell'applicazione, aggiunto il pulsante `Console & Sniffer` per apertura/chiusura con un click.
     - Nella card del rack RS485 Sniffer (sidebar), aggiunto il pulsante `🔍 Mostra Tabella Frame`.
     - L'intera barra d'intestazione del dock (`.bham-dock-header`) è ora cliccabile con cursore a puntatore ed effetto hover per espansione/riduzione immediata.
   - **Spazio di Scorrimento (Layout Clearance)**:
     - Applicato `padding-bottom: 290px` a `.bham-col-sidebar` e `.bham-col-center` in `frontend/css/main.css`, permettendo all'utente di scorrere tabelle e moduli fino all'ultimo elemento senza alcuna sovrapposizione da parte del dock aperto (280px).
   - **Autoscroll e Trigger Automatico su Scansione**:
     - L'avvio di qualsiasi scansione attiva (`startRTU`, `startTCP`, `startBACnet`, `startKNX`, `startARP`, `startRapidScan`) apre automaticamente la console sul tab `Live Log`.
     - L'avvio dello sniffer seriale (`startSerialSniff`) o il click sui pulsanti inspector apre automaticamente il dock sul tab `RS485 Inspector` e gestisce l'autoscroll continuo dei pacchetti hex.
   - **Traduzioni Multilingua (i18n)**:
     - Aggiornato `frontend/js/i18n.js` con le etichette in IT, EN ed ES per i nuovi controlli console e sniffer.
5. **Collaudo e Verifica**:
   - Sintassi JavaScript (`node -c`): 0 errori.
   - Verifica DOM: 156 ID tracciati e allineati.
   - Test unitari: **24/24 superati** in 5.1s (`Ran 24 tests - OK`).

---

## 🔄 Baseline & Prompt di Ripartenza Ufficiale – COPIA NELLA NUOVA CHAT

```
Sei un Senior Software Engineer che continua lo sviluppo di BHAM (BACS Help Auto Mapper), la suite diagnostica portatile da cantiere per tecnici di building automation (Modbus RTU/TCP, BACnet/IP, KNXnet/IP, ARP L2 e RS485 Sniffer Zero-TX).

PRIMA AZIONE OBBLIGATORIA – leggi questi due file:
  cat /home/giuliano/Documenti/BHAM/DEVLOG.md
  find /home/giuliano/Documenti/BHAM -not -path '*/.venv/*' -not -path '*/__pycache__/*' -not -path '*/.git/*' | sort

CONTESTO AMBIENTE:
  Progetto: /home/giuliano/Documenti/BHAM/
  Venv:     .venv/bin/python3  (Python 3.12, virtualenv già configurato)
  Avvio:    .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8765 --reload
  Test:     .venv/bin/python3 -W error -m unittest discover -s tests -p "test_*.py"

STATO ATTUALE DEL SOFTWARE (v0.4.5 - Field Engineer Studio):
  - Architettura UI: Studio a 2 Colonne (Sinistra: Canali di Scansione 360px; Centro: Toolbar filtri + Tabelle Discovery + Hero Empty State; Basso: Dock Diagnostico Inferiore a scomparsa con Live Log, RS485 Inspector e Bus Health).
  - Tema: Chiaro di default (Light-first, canvas ardesia #f1f5f9, card bianche #ffffff, pulsanti solidi, 100% offline-proof senza font web esterni).
  - Suite Test: 24/24 unit test passati al 100% (-W error).
  - DOM IDs: 156 elementi DOM unici verificati e sincronizzati con app.js e i18n.js.

SESSIONI COMPLETATE:
  ✅ Sessione 1 – Bootstrap (struttura, main.py, WebSocket, modelli Pydantic)
  ✅ Sessione 2 – Motore Modbus RTU (Phase Zero, Early Exit, Full Sweep, TCP)
  ✅ Sessione 3 – BACnet production, FC43, FileResponse report, UI barra progresso
  ✅ Sessione 4 – hw_discovery (RS485 + NIC), session_store, logger session, setup
  ✅ Sessione 5 – UI Dual Theme, maps_manager.py (BACS Help JSON), PDF ReportLab, bham.spec
  ✅ Sessione 6 – Setup Wizard on-demand, icone SVG industriali, modulo KNXnet/IP (multicast/broadcast)
  ✅ Sessione 7 – i18n dinamico (IT, EN, ES), Centro Impostazioni Unificato (5 schede), Manuale F1 interattivo
  ✅ Sessione 8 – Gestione Porte Speciali & Custom (BAC0..BACF, Modbus TCP multi-port, KNX custom)
  ✅ Sessione 9 – Sniffer Seriale Passivo (RS485 Zero-TX / Stealth Mode), Bus Health telemetria & RS485 Inspector live
  ✅ Sessione 10 – Full Software Audit, i18n 100% (157 chiavi), parità DOM, verifica reportistica Excel/PDF
  ✅ Sessione 11 – Chiusura Sprint v0.3.0, Consolidamento Task, Allineamento Packaging & Docs
  ✅ Sessione 12 – CI/CD Rilasci GitHub, bump_version.py, release.sh, .deb Debian, install.sh Linux, WinGet
  ✅ Sessione 16 – Ricostruzione Radicale UI/UX: Design System "Field Engineer Studio" v4.2, reset forzatura dark localStorage, eliminazione colonna destra 325px, dock console inferiore a scomparsa (38px/280px)
  ✅ Sessione 17 – BACnet Object Explorer (#bacnet-modal con probe selettivo e filtro live), Modbus Smart Register Scan euristico (probe FC03/FC04, decodifica Int16 e Float32 IEEE Big-Endian), tipografia 100% offline-proof, risoluzione definitiva visibilità ed ergonomia di Live Log ed RS485 Inspector (pulsanti diretti in toolbar e header, clearance padding 290px, auto-apertura su scansione, test 24/24 superati)

PROSSIMI TASK IN ROADMAP (Scegli con l'utente come procedere):
  1. Milestone 2: Mappa Topologica Interattiva (Network Graph canvas/SVG per visualizzare gerarchia Host -> Interfaccia -> Nodi/Slave)
  2. Milestone 3: Intelligence & Session Diff ("Prima vs Dopo" per identificare apparati aggiunti/scomparsi/modificati su impianto)
  3. Milestone 4: KNX Group Monitor & Standalone Portable Build (.exe / binary Linux USB)

REGOLE OPERATIVE INDEROGABILI:
  1. Aggiorna sempre DEVLOG.md ad ogni feature o correzione completata.
  2. Esegui sempre `.venv/bin/python3 -W error -m unittest discover -s tests -v` prima di chiudere un task.
  3. Verifica la sintassi JS con `node -c frontend/js/app.js` e non rompere nessuno dei 156 ID DOM.
  4. Mantieni l'interfaccia chiara, pulita e professionale, pensata per il tecnico in cantiere su laptop da campo.
```








