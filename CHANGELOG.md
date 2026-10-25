# Changelog – BHAM (BACS Help Auto Mapper)

Formato basato su [Keep a Changelog](https://keepachangelog.com/it/1.1.0/), versioni [SemVer](https://semver.org/lang/it/).
Le note della sezione corrispondente alla versione vengono pubblicate automaticamente nella GitHub Release.

## [1.2.5] – 2026-10-25

Versione dedicata al **controllo generale dell'applicazione**: i rilievi dell'audit storico sono stati ricontrollati uno per uno sul codice attuale (tutti confermati chiusi) e sono emersi 6 difetti nuovi, qui risolti. Il dettaglio completo, con la tabella di verifica, è in `AUDIT.md`.

### Risolto (critico)
- **L'arresto d'emergenza globale rispondeva HTTP 500 (`api/routes.py`, `scanners/base.py`)**:
  - `POST /api/v1/scan/abort` dichiara `ScanAbortResponse.sessions` come `list[str]` ("Elenco ID delle sessioni terminate"), ma l'handler restituiva l'**intero** di `abort_all()`. La validazione della risposta di FastAPI falliva e l'endpoint rispondeva **500 Internal Server Error**: la funzione di arresto d'emergenza non ha mai funzionato via HTTP.
  - Il difetto era sfuggito perché la suite invoca le funzioni handler **direttamente**, bypassando la validazione contro il `response_model`: nessun test esercitava i contratti dichiarati.
  - `abort_all()` ritorna ora la lista degli ID effettivamente fermati, coerente con lo schema e più informativa.

### Aggiunto
- **Mutua esclusione sulle risorse di campo esclusive (`core/resource_guard.py`)**:
  - Una porta RS485 ammette un solo lettore, ma nulla impediva di avviare contemporaneamente una scansione Modbus RTU e uno sniffer passivo sulla **stessa** `/dev/ttyUSB0`: i due consumatori si rubano i byte a vicenda, falsando mappatura e diagnosi di Bus Health senza alcun avviso. Lo stesso valeva per il discovery BACnet/IP (bind della 47808) e per discovery KNXnet/IP e Group Monitor, che condividono il socket multicast 3671.
  - Le route di avvio rivendicano ora la risorsa; il conflitto viene rifiutato con **HTTP 409** indicando quale operazione la detiene, da quanti secondi e come arrestarla. La verifica precede la creazione della sessione, così un conflitto non lascia una sessione fantasma nello storico.
  - Risorsa e stato di abort vengono liberati quando il task termina, in qualunque modo, tramite done-callback.
  - Nuovo endpoint **`GET /api/v1/system/resources`** per ispezionare le risorse occupate: serve a capire perché un avvio è stato rifiutato.
- **Test di contratto sulle risposte API (`tests/test_resource_contracts.py`)**:
  - L'uscita degli handler viene validata contro il `response_model` realmente dichiarato sulla route — la verifica che avrebbe intercettato l'arresto d'emergenza rotto — e ogni endpoint `/scan*` deve dichiararne uno.
- **Verifica del canale WebSocket nello smoke test (`scripts/smoke_frozen.py`)**:
  - La telemetria live è il cuore della console di collaudo, ma lo smoke test copriva solo le route REST: un bundle con l'implementazione WebSocket incompleta lo avrebbe superato. Ora apre una connessione al canale live e pretende lo snapshot iniziale, verificando anche il registro risorse.

### Modificato
- **Registro degli abort: perdita di memoria e conteggio fuorviante (`scanners/base.py`)**:
  - `_abort_events` accumulava una voce per ogni scansione e non veniva **mai** ripulito, crescendo per tutta la durata del processo. La pulizia avviene ora al termine del task.
  - `abort_all()` ritornava il numero di sessioni mai registrate invece delle scansioni attive; `abort_session()` segnala ora una sola volta e riporta se ha effettivamente fermato qualcosa.
- **Storico sessioni: tetto, lock e azzeramento coerente (`data/state.py`)**:
  - `self.sessions` non aveva alcun limite ed era serializzato **integralmente** in ogni `snapshot()`, cioè a ogni connessione WebSocket e a ogni evento di stato: durante una giornata di collaudo con decine di scansioni il payload cresceva di continuo. Introdotto il tetto `max_sessions` (200) che scarta le più vecchie fra quelle **concluse**, mai le scansioni in corso.
  - `sessions` era l'unica collezione mutata fuori da `_state_lock` mentre `snapshot()` la itera tenendolo — residuo del rilievo #2, corretto altrove ma non qui. Gli scanner aggiornano le sessioni da thread di executor, quindi la lettura poteva risultare incoerente.
  - `clear()` azzera ora lo storico concluso come le altre collezioni, preservando le sessioni attive.
- **Dipendenze: aggiornamento con cautela differenziata**:
  - 12 delle 14 dipendenze pinnate erano ferme da circa due anni. **Aggiornate e verificate** quelle infrastrutturali: fastapi `0.115.0→0.162.0`, uvicorn `0.30.6→0.54.0`, websockets `13.1→17.3`, pydantic `2.9.2→2.14.1`, pydantic-settings `2.5.2→2.16.1`, aiofiles `24.1.0→25.1.0`, python-dotenv `1.0.1→1.2.4`, python-multipart `0.0.9→0.0.32`.
  - **Deliberatamente lasciate pinnate** `pymodbus`, `bacpypes3`, `scapy` e `reportlab`: governano il comportamento sul filo (RS485, BACnet/IP, cattura L2) e l'impaginazione dei certificati PDF. Il simulatore non sostituisce una validazione su hardware reale, quindi il loro avanzamento resta da pianificare con strumentazione in linea.
  - `bham.spec`: rimossi `wsproto` e `wsproto_impl`, non più dipendenze di `uvicorn[standard]` (producevano solo un avviso di hiddenimport mancante a ogni build); aggiunta l'implementazione sans-io che `--ws auto` seleziona.
- **Spegnimento più pulito (`main.py`)**: le risorse rivendicate vengono rilasciate all'arresto, così un riavvio immediato non trova porte seriali o socket marcati come occupati da sessioni ormai morte; il numero di scansioni interrotte viene registrato nel log.

### Test
- Suite estesa da 140 a 162 test, verdi su Linux e Windows. Le nuove aree coperte: contratti di risposta contro i `response_model` dichiarati, registro di mutua esclusione (conflitto, idempotenza, rilascio protetto dal proprietario), rifiuto HTTP 409 delle route di avvio senza sessioni fantasma, rilascio di risorsa e stato di abort al termine del task, tetto e ritenzione dello storico sessioni.

## [1.2.0] – 2026-10-21

### Risolto (critico)
- **Il binario standalone non si avviava: installazione Windows inutilizzabile (`main.py`, `bham.spec`)**:
  - `main.py` consegnava a uvicorn la *stringa di import* `"main:app"`. In un bundle PyInstaller lo script di ingresso viene eseguito come `__main__` e il modulo `main` **non è importabile**: l'eseguibile terminava immediatamente con
    `ERROR: Error loading ASGI app. Could not import module "main".`
  - Il guasto colpiva **tutti** gli artefatti compilati: `bham.exe` installato dall'installer Inno Setup, l'edizione portable `bham-windows-x64-portable.zip` e il binario Linux `bham-linux-x64.tar.gz`. Restava funzionante solo l'avvio da sorgente (`bham.py` / `bham.bat`), motivo per cui la CI non lo rilevava.
  - Introdotta `server_target()`: in modalità congelata viene passato direttamente l'**oggetto applicazione**, da sorgente si mantiene la stringa di import necessaria all'auto-reload. L'auto-reload viene ora disattivato d'ufficio quando il target non è una stringa.
  - Il re-exec automatico nel virtualenv è disattivato nel binario congelato: l'eseguibile porta con sé il proprio runtime e non deve mai saltare in un `.venv` presente accanto a sé.
  - Rimossa la dipendenza del runtime dal launcher: `main.py` non importa più `bham.py` (le utility di apertura browser vivono in `core/browser.py`, solo stdlib).

### Aggiunto
- **Preflight di avvio & fallback automatico di porta (`core/preflight.py`)**:
  - Verifica della directory dati effettivamente scrivibile (diagnostica immediata delle installazioni in `Program Files`), della presenza reale degli asset del frontend nel bundle (causa tipica della pagina bianca) e della disponibilità della porta di ascolto.
  - Se la porta 8765 è occupata da un'istanza già avviata, BHAM passa automaticamente alla prima porta libera invece di terminare con un traceback, allineando log di avvio, URL LAN e QR code di pairing alla porta reale.
  - Messaggi di errore azionabili in italiano al posto delle eccezioni non gestite; `--no-port-fallback` ripristina il comportamento rigido.
- **Interfaccia a riga di comando del binario standalone (`main.py`)**:
  - L'eseguibile accettava e ignorava qualunque argomento. Nuovi flag: `--host`, `--port`, `--no-browser`, `--demo`, `--no-port-fallback`, `--check` (preflight ed uscita, 0 = OK) e `--version`.
- **Rilevamento regola Windows Firewall (`core/system_requirements.py`, `installer/bham.iss`)**:
  - `check_windows_firewall_rule()` verifica via `netsh` la presenza della regola che autorizza BHAM: la sua assenza è la causa più frequente di *"il QR code non si apre dal telefono"*, con il demone raggiungibile solo da localhost.
  - L'installer crea la regola in ingresso su richiesta (porta 8765/TCP, profili `private` e `domain` — mai `public`) e la rimuove alla disinstallazione.
- **Verifica dei motori di protocollo nel pacchetto compilato (`core/preflight.py`, `main.py --check`)**:
  - `check_engines()` tenta il caricamento di Modbus, BACnet, sniffer L2, seriale RS485, report Excel/PDF e telemetria di sistema. In un bundle PyInstaller un `hiddenimport` dimenticato non si manifesta all'avvio: l'eseguibile parte regolarmente e fallisce settimane dopo, in cantiere, all'apertura della funzione. La verifica è particolarmente rilevante su Windows, dove scapy carica moduli di piattaforma diversi da quelli raccolti nella build Linux.
  - Distinzione esplicita fra **`[ASSENTE]`** (modulo non presente nel pacchetto → bundle incompleto, va reinstallato) e **`[LIMITATO]`** (modulo presente ma non inizializzabile su quella macchina, tipicamente per l'assenza del driver Npcap): solo il primo caso fa fallire `--check`, evitando di suggerire una reinstallazione inutile.
  - Gli avvisi e i traceback che scapy scrive su stderr durante l'import vengono trattenuti, mantenendo leggibile l'esito della verifica.
- **Collegamento "Verifica installazione" nel menu Start (`installer/verifica-installazione.bat`, `installer/bham.iss`)**:
  - Script wrapper che esegue `bham.exe --check` e mantiene la finestra aperta, con esito tradotto in azioni concrete (`[ASSENTE]` → reinstallare, `[LIMITATO]` → driver di sistema mancante). Il tecnico può così diagnosticare una postazione senza aprire un prompt dei comandi a mano.
  - Incluso anche nell'edizione portable, dove non esiste un menu Start.
- **Manifest Windows: code page UTF-8 e percorsi lunghi (`bham.exe.manifest`)**:
  - `activeCodePage = UTF-8` (Windows 10 1903+): la console rende correttamente i messaggi accentati e i caratteri di cornice del banner di avvio, risolvendo il problema di codifica all'origine invece di aggirarlo.
  - `longPathAware = true` (Windows 10 1607+): verbali di collaudo e snapshot di sessione salvati sotto cartelle di commessa profondamente annidate non superano più il limite di 260 caratteri.
- **Smoke test del binario congelato (`scripts/smoke_frozen.py`, `.github/workflows/ci.yml`)**:
  - Nuovo job CI su Linux **e** Windows che compila l'eseguibile, lo avvia davvero e verifica `--version`, `--check`, `/api/v1/health`, la console web servita dal bundle e l'endpoint di diagnostica. È il controllo che intercetta le regressioni di packaging invisibili ai test unitari.
  - Su Windows il job **compila anche l'installer Inno Setup** e lo pubblica come artefatto scaricabile per il collaudo manuale: prima lo script `bham.iss` veniva compilato per la prima volta durante la release, dove un errore di sintassi blocca la pubblicazione.
  - La suite gira ora anche sui rami di lavoro (`claude/**`, `feature/**`, `fix/**`) e può essere lanciata a richiesta (`workflow_dispatch`): in precedenza una feature branch non riceveva alcuna verifica fino all'apertura della pull request.
  - Arresto dell'eseguibile per albero di processi: in un bundle onefile PyInstaller il bootloader avvia l'applicazione come processo figlio, quindi su Windows `terminate()` chiudeva solo il bootloader lasciando il server orfano con la porta occupata. Lo smoke test usa ora `taskkill /T` e verifica esplicitamente il rilascio della porta.

### Verificato su Windows
- Build e avvio reale dell'eseguibile su `windows-latest`: `--version`, `--check` (tutti e 7 i motori caricati dal bundle, scapy incluso con i suoi moduli di piattaforma Windows), `/api/v1/health`, console web e diagnostica.
- Compilazione dello script Inno Setup con ISCC 6.7.1 e produzione dell'installer firmabile da 30,1 MB, pubblicato come artefatto di CI per il collaudo manuale.
- **Metadati di packaging nella diagnostica (`/api/v1/system/diagnostics`)**:
  - Nuovi campi `app_version`, `is_frozen`, `is_portable`, `listen_port` e `windows_firewall_rule` per il supporto di campo.
  - Il binario congelato non segnala più come "non supportata" la versione dell'interprete di sistema: il runtime è incorporato nell'eseguibile.

### Modificato
- **Hardening del packaging Windows (`bham.spec`)**:
  - Il manifest applicativo `bham.exe.manifest` (UAC `asInvoker`, DPI awareness `PerMonitorV2`) era presente nel repository ma **non veniva mai applicato** all'eseguibile: ora viene generato con la versione corrente e incorporato.
  - Aggiunta la risorsa `VERSIONINFO` (nome prodotto, versione, publisher, copyright): senza di essa SmartScreen e gli antivirus trattano l'eseguibile come binario anonimo.
  - **UPX disattivato**: la compressione corrompe alcune DLL del runtime Python e innesca falsi positivi antivirus sui bundle onefile, bloccando l'installazione.
  - Versione letta direttamente da `pyproject.toml` (unica fonte di verità) e `hiddenimports` estesi (implementazioni HTTP/WebSocket di uvicorn, `serial.tools.list_ports`, `core.preflight`, `core.browser`, `core.qr_svg`, `core.tag_exporter`).
- **Installer Inno Setup (`installer/bham.iss`)**:
  - `CloseApplications=yes` con Restart Manager: l'aggiornamento sopra una versione precedente non fallisce più con *"file in uso"* quando BHAM è in esecuzione.
  - Aggiunti `SetupMutex`, `MinVersion=6.3`, `AppVerName`, `UninstallDisplayIcon`, `UninstallDisplayName` e le risorse `VersionInfo*` del setup.
- **Launcher a doppio clic Windows (`bham.bat`)**:
  - Il file conteneva caratteri Unicode (`⚡`, `–`) resi illeggibili dalle code page legacy della console Windows (850 / 437): ora è **puro ASCII**, con `chcp 65001` per l'output del processo Python figlio. Un controllo CI impedisce la regressione.
  - Rilevamento esteso a Python 3.13 (`py -3.13` e `%LOCALAPPDATA%\Programs\Python\Python313`), prima cercato solo per 3.12.
- **Manifest winget (`winget/`)**:
  - `InstallerUrl` puntava al repository errato (`BacsHelp/BHAM` invece di `Molonverona/BHAM`) e a un asset **inesistente** (`bham-windows-x64.zip` invece di `bham-windows-x64-portable.zip`): entrambe le installazioni via winget restituivano 404.
  - Il workflow di release genera e pubblica il manifest già compilato con lo SHA256 reale dell'asset.
- **Variabili d'ambiente con prefisso di progetto (`core/config.py`)**:
  - `BHAM_API_TOKEN` era documentato ma **non veniva letto** (la configurazione accettava solo `API_TOKEN`). Ora `host`, `port`, `debug`, `api_token` e `lan_auth_required` accettano sia il nome semplice sia la forma `BHAM_*`, coerentemente con `BHAM_DEMO` / `BHAM_NO_BROWSER` / `BHAM_PORTABLE`.
- **Sincronizzazione versioni (`scripts/bump_version.py`, `.github/workflows/ci.yml`)**:
  - `bham.bat`, `scripts/bootstrap_windows.ps1` e `core/system_requirements.py` contenevano la versione in chiaro ma non erano coperti né dallo script di bump né dal controllo CI: erano rimasti indietro. Ora sono target di bump e il job statico verifica ogni file di packaging.

### Test
- Suite estesa da 90 a 128 test unitari e di integrazione, eseguiti con successo su Linux e Windows: scelta del target ASGI in modalità congelata, flag CLI, preflight e fallback di porta, rilevamento firewall Windows, alias delle variabili d'ambiente, allineamento versioni su 15 file di packaging, validità dei manifest winget e hardening dello spec PyInstaller.

## [1.1.0] – 2026-10-11

### Aggiunto
- **Network Security, LAN Token & CORS Hardening (`main.py`, `core/config.py`, `api/routes.py`, `frontend/js/app.js`)**:
  - Middleware di sicurezza `lan_security_middleware` con token crittografico casuale a 16 byte (generato automaticamente o configurabile via `BHAM_API_TOKEN`).
  - Esenzione automatica trasparente per tutte le connessioni originate da localhost e loopback (`127.0.0.1`, `::1`).
  - Protezione zero-trust per connessioni LAN remote su tutte le chiamate REST e canali WebSocket (rifiuto con codice 4401 in assenza di token).
  - Iniezione automatica del token di sicurezza nei codici QR generati per accoppiamento mobile immediato e protetto da tablet e smartphone di cantiere.
  - Policy CORS formalmente hardening conforme agli standard OWASP (`allow_credentials=False` con `allow_origins=["*"]`).
  - Risoluzione definitiva dell'audit issue #8.
- **KNX Group Monitor & Live Telegram Sniffer (`scanners/knx.py`, `api/routes.py`, `data/models.py`, `data/state.py`, `frontend/`)**:
  - Ricevitore asincrono passivo multicast UDP su `224.0.23.12:3671` (standard KNXnet/IP) per la cattura trasparente di frame `ROUTING_INDICATION` e `TUNNELING_REQUEST`.
  - Motore di parsing cEMI nativo con decodifica di Control Field (priorità system, urgent, normal, low), Hop Count, Indirizzo Sorgente Individuale, Indirizzo di Gruppo Destinazione (notazione a 3 livelli Main/Middle/Sub) e APCI Service (`GroupValueWrite`, `GroupValueResponse`, `GroupValueRead`).
  - Decodificatore euristico DPT per datapoint comuni: DPT 1.001 Bool (`ON`/`OFF`), DPT 5.001 Percentuale (0-100%), DPT 9.001 Float16 2-octet (`°C`), DPT 14.xxx Float32 IEEE 754 e stringhe ASCII DPT 16.001.
  - Generazione di telegrammi sintetici realistici nel Simulatore d'Impianto Virtuale in Demo Mode.
  - Nuova scheda "KNX Monitor" nella console di collaudo con badge conteggio, filtro per gruppo/indirizzo, auto-scroll ed esportazione della sequenza in CSV.
  - Endpoint REST dedicati: `POST /api/v1/knx/monitor/start`, `POST /api/v1/knx/monitor/stop`, `GET /api/v1/knx/telegrams`, `DELETE /api/v1/knx/telegrams`.
- **BACnet Point Trend Polling & Integrazione Watch List (`scanners/field_tools.py`, `api/routes.py`, `frontend/js/app.js`)**:
  - Nuovo endpoint di lettura real-time `POST /api/v1/tools/bacnet/read` con supporto completo a dispositivi fisici via `bacpypes3` e al Virtual Plant Simulator.
  - Pulsante **📈 Segui** integrato direttamente in ogni riga del modale *BACnet Object Explorer* per aggiungere istantaneamente qualsiasi oggetto alla Watch List.
  - Polling periodico automatico della Watch List esteso a oggetti BACnet con mini-grafici SVG sparkline, tracciamento min/max, calcolo delta e feedback audio hands-free.
  - Esportazione unificata Modbus & BACnet in formato CSV.
- **Modbus Decodifica & Scrittura Estesa 32-bit e 64-bit (`scanners/field_tools.py`)**:
  - Estensione di `decode_modbus_value` e `encode_modbus_value` con supporto a:
    - 32-bit: `uint32_be`, `uint32_le` (word-swapped CDAB), `int32_be`, `int32_le`.
    - 64-bit: `float64_be` (doppia precisione IEEE 754 su 4 registri) e `int64`.
- **Manuale Tecnico & Guida Operativa di Campo**:
  - Aggiunto Capitolo 23 completo in Italiano, Inglese e Spagnolo (`MANUALE_UTENTE.md`, `frontend/MANUALE_UTENTE.md` e `frontend/js/manual-content.js`).

- **Session Diff Engine Evolvuto & As-Built Tracking (`core/session_diff.py`, `frontend/index.html`, `frontend/js/app.js`)**:
  - Tracciamento analitico delle variazioni di stato collaudo (`commissioning_status` e note peritali `commissioning_notes`) tra snapshot baseline e target per tutti i protocolli (Modbus, BACnet, KNX, Host IP).
  - Confronto dettagliato dei valori dei registri Modbus comuni (scostamenti di setpoint e registri di stato da vecchio a nuovo valore).
  - Rilevamento variazioni degli elenchi oggetti BACnet censiti oltre al conteggio complessivo.
  - Ricerca full-text istantanea integrata nella barra filtri del visualizzatore di confronto e pill cromatiche per gli esiti As-Built.
- **Safe Mode Interlock Hardening & Estensione a Caldo (`core/safe_mode.py`, `api/routes.py`, `api/schemas.py`, `frontend/`)**:
  - Nuovo endpoint `POST /api/v1/safe-mode/extend` e metodo `extend(extra_minutes)` protetto da lock rientrante `threading.RLock()` per prolungare la finestra temporale attiva (+15m, +30m) senza interruzioni operative, con tracciamento crittografico WAL.
  - Memorizzazione persistente operatore/commessa in `localStorage` con auto-fill automatico all'apertura del modale.
  - Live dynamic ticker a 1Hz con countdown continuo al secondo (`MM:SS`) sia nel modale che nel badge in testata.
  - Indicatore visivo di allerta per scadenza imminente (`bham-safe-mode-expiring`) sotto i 2 minuti.
  - Intercettazione automatica dei comandi di forzatura bloccati con apertura contestuale del modale di sblocco.
- **Cross-Platform Parity & Auto-Provisioning Prerequisiti (`bham.bat`, `scripts/bootstrap_windows.ps1`, `core/system_requirements.py`, `core/priv_check.py`, `api/`)**:
  - **Launcher a doppio clic Windows (`bham.bat`)**: Rilevamento automatico di Python 3.12/3.13; se assente o obsoleto, chiede conferma all'utente e provvede al download e installazione autonoma tramite PowerShell e python.org.
  - **Script PowerShell di bootstrap (`scripts/bootstrap_windows.ps1`)**: Download e installazione controllata di Python 3.12 (con pip e PATH abilitati) e driver Npcap.
  - **Modulo unificato requisiti di sistema (`core/system_requirements.py`)**: Rilevamento completo e continuo di OS, runtime Python, virtualenv, driver di cattura L2 (Npcap su Windows, CAP_NET_RAW su Linux), porte seriali e strumenti companion (Wireshark/tshark).
  - **Download controllato companion tools (`POST /api/v1/system/companions/download`)**: Download su richiesta utente dell'installer ufficiale Npcap (`npcap-1.80.exe`) con registrazione WAL e guida all'installazione.
  - **Endpoint diagnostico `/api/v1/system/diagnostics`**: Fornisce al frontend il quadro analitico dei requisiti di sistema e le azioni correttive consigliate.
  - **Scheda "Diagnostica & Requisiti" nella Web UI**: Tab dedicato nel centro impostazioni per monitorare la salute di sistema, con rilevamento istantaneo dell'assenza di Npcap su Windows e pulsante di download guidato 1-click.
- **Engine i18n & Sidebar Channel Hardening (`frontend/js/i18n.js`, `frontend/index.html`)**:
  - Blindata la funzione `applyTranslations()` con guardia `if (trans && trans !== key)` per prevenire l'esposizione di chiavi grezze.
  - Copertura e allineamento trilingue (IT, EN, ES) al 100% su tutte le 332 chiavi dell'interfaccia (233 attributi `data-i18n` e 15 chiavi runtime) e su tutti i 23 capitoli della documentazione tecnica.
- **Allineamento Versioni Core Exporters (`core/tag_exporter.py`, `reports/pdf.py`)**:
  - Versionamento centralizzato tramite `settings.app_version` per esportazioni JSON di tag BMS e intestazioni dei certificati di collaudo PDF.
- **Test Suite Completa BHAM**: Espansione a 90 test unitari e di integrazione eseguiti con successo al 100% su Linux e Windows (copertura LAN security, cEMI parser, DPT decoding, Safe Mode extend, session diff con collaudo/registri, requisiti di sistema cross-platform e CI green).
- **Integrità WAL**: Registro manovre certificato con oltre 1620 record concatenati SHA-256 e zero errori di catena.

## [1.0.0] – 2026-10-06 – Stable Release

### Aggiunto
- **Live Watch List & Register Polling Monitor (`frontend/js/app.js`)**:
  - Monitoraggio continuo in tempo reale di registri Modbus selezionati (Holding e Input) con frequenze regolabili (500ms, 1s, 2s, 5s).
  - Evidenziazione dinamica dei delta con transizioni cromatiche e buzzer audio hands-free sintetizzato via Web Audio API.
  - Esportazione cronologica dei campionamenti in formato CSV.
- **RS485 Stress Test & Latency Benchmark (`scanners/field_tools.py`, `api/routes.py`, `api/schemas.py`)**:
  - Test diagnostico fisico del bus RS485/Modbus con calcolo in tempo reale di Packet Error Rate (PER %), latenza RTT (min, max, avg), jitter e frame scartati per checksum CRC corrotto.
  - Diagnostica fisica guidata con raccomandazione analitica del baudrate ottimale.
  - Endpoint dedicati `POST /api/v1/tools/modbus/benchmark` e `POST /api/v1/modbus/benchmark`.
- **BMS/SCADA Multi-Vendor Tag Exporter (`core/tag_exporter.py`, `api/routes.py`)**:
  - Esportazione istantanea dei punti e registri censiti nei formati nativi dei principali supervisori BMS: Tridium Niagara 4 (XML), Siemens Desigo CC (CSV), Schneider EcoStruxure Building Operation (CSV) e BACnet CSV generico.
  - Endpoint dedicato `GET /api/v1/export/tags?format=standard_csv|niagara_csv|json`.
- **Accesso Mobile Hands-Free con Pairing QR Code (`core/qr_svg.py`, `api/routes.py`)**:
  - Generatore vettoriale SVG standalone di QR Code per connessione istantanea da smartphone o tablet sulla rete LAN (`0.0.0.0:8765`), 100% offline senza dipendenze cloud o esterne.
  - Endpoint dedicato `GET /api/v1/network/qr-code`.
- **As-Built Commissioning Checklist & Certificazione (`data/state.py`, `api/routes.py`)**:
  - Checklist ufficiale per la validazione punto per punto dei dispositivi collaudati con annotazioni tecniche e firma operatore.
  - Endpoint `POST /api/v1/device/commissioning-status`.
- **1-Click Launch Script (`open.sh`) & Auto-Browser Robustness**:
  - Script eseguibile per avvio immediato e rilancio sicuro del browser.
  - Risoluzione intelligente del browser di sistema (fallback esplicito su `/usr/bin/firefox` quando assente `google-chrome`).
  - Auto-reexec trasparente in virtualenv (`.venv/bin/python3`) in `main.py` e preservazione variabili grafiche `$DISPLAY` e `$XAUTHORITY` in `start.sh`.

### Modificato & Ottimizzato
- **Centro Assistenza & Manuale di Campo**: Esteso a 22 capitoli tecnici completi in Italiano, Inglese e Spagnolo, con calcolatori integrati e guide al troubleshooting.
- **Esclusione M-Bus**: Rimozione completa di ogni riferimento o dipendenza M-Bus per garantire massima focalizzazione e pulizia architetturale.
- **Parità Crittografica WAL**: Verifica di integrità forense su 1073 record del registro manovre con certificazione SHA-256 e zero errori.
- **Test Suite**: Espansione a 58 test unitari e di integrazione passati con successo al 100%.

## [0.9.0] – 2026-10-05

### Aggiunto
- **BACS IP Scanner Avanzato & OUI Hardware Recognition (`scanners/ip_scanner.py`, `core/oui_lookup.py`)**:
  - Scansione asincrona parallela ad alta concorrenza (semaphoring a 50 task concorrenti) di subnet CIDR e range IP (`192.168.1.0/24`, `10.0.0.1-50`).
  - Database integrato IEEE OUI con oltre 100 produttori BACS, HVAC, PLC e Building Automation (Schneider, Siemens, Honeywell, Carel, WAGO, Beckhoff, Moxa, Tridium, Belimo, ABB, Carlo Gavazzi, Danfoss, Phoenix Contact, Johnson Controls, ecc.) con lookup prefisso O(1) e normalizzazione formati MAC (`:` e `-`).
  - Risoluzione dei nomi host multi-livello con fallback automatico: reverse DNS PTR e query NetBIOS Name Service (UDP 137 RFC 1002).
  - Port scanner selettivo per servizi di automazione edificio: Modbus TCP (502), BACnet/IP (47808), KNXnet/IP (3671), Web GUI HTTP/HTTPS (80, 443, 8080, 8443), Niagara Fox (1911) e MQTT (1883).
  - Endpoint REST dedicati `POST /api/v1/scan/ip` e `GET /api/v1/network/oui/{mac}`.
- **BACS Discovery Wizard (Commissioning Guidato d'Impianto)**:
  - Modale interattivo in 4 passaggi per il collaudo rapido di nuovi impianti di campo:
    1. *Rilevamento Hardware*: scansione automatica porte seriali RS485 (chipset Moxa, FTDI, CH340) e schede di rete LAN/WLAN con rilevamento IP e subnet.
    2. *Configurazione Bus Seriale*: selezione baudrate e parità con Adaptive Fallback (se 9600 8N1 fallisce, attiva automaticamente scansione a matrice o 15s di Zero-TX sniffer passivo).
    3. *Scansione Multi-Protocollo*: esecuzione combinata o selettiva di Modbus RTU, Modbus TCP, BACnet/IP, KNXnet/IP e BACS IP Scanner.
    4. *Riepilogo & Azioni*: report sintetico dei nodi censiti con link immediati a Mappe Topologiche, Report Excel/PDF ed esportazione sessione.
- **"1-Click Device Lens" & Modbus Auto-Profile Mapping**:
  - Modale di ispezione tecnica per ciascun host IP o nodo di campo rilevato.
  - Ricerca mirata manuali/datasheet in 1-Click con query contestualizzata su produttore e modello.
  - Mappatura istantanea profili Modbus industriali su slave e controller rilevati.
- **Blocco Scrittura Safe Mode Permanentemente Non Disattivabile**:
  - Architettura di sicurezza rigorosa: Safe Mode è permanentemente attivo e non può essere disabilitato o bypassato globalmente da configurazione, env o API.
  - Sblocco esclusivamente temporizzato con tracciamento obbligatorio dell'identità dell'operatore, codice commessa/ordine di lavoro e finestra temporale con auto-scadenza e disarmo immediato.
  - Verifica totale nel motore di forzatura fisica `field_tools.py` per Modbus RTU/TCP e BACnet presentValue override.
- **Reportistica Avanzata Excel & PDF con Sezione IP Hosts & OUI**:
  - Foglio Excel dedicato `"BACS IP Hosts"` con IP, MAC, Costruttore OUI, Hostname NetBIOS, Servizi BACS e latenza ms.
  - Tabella PDF Section 4 arricchita con vendor OUI, hostname e servizi di automazione edificio.
  - Grafo topologico SVG con etichette produttore OUI e pulsante diretto Device Lens nell'Inspector.

## [0.8.5] – 2026-10-03

### Aggiunto
- **Collaudo Hardware Reale USB↔RS485 (Industrial Field-Ready)**:
  - Rilevamento automatico chipset Moxa UPort 1150 (VID `0x110A`, PID `0x1150`, TI 3410) e adattatori standard FTDI, CH340, CP210x, Prolific.
  - Verifica permessi non-root Linux flessibile (`uucp`, `dialout`, ACL POSIX `os.access(..., R_OK | W_OK)`).
  - Self-Test hardware 1-Click con misurazione latenza di apertura porta (<75ms).
  - Sniffer RS485 Zero-TX ultra-resiliente con gestione hot-plug USB: recupero automatico in caso di scollegamento accidentale con riapertura trasparente al reinserimento e broadcast eventi WebSocket (`hardware_disconnect`, `hardware_reconnect`).
  - Protezione linea flottante/a vuoto: azzeramento divisioni per zero ed emissione corretta di telemetria e diagnostica a 0 frame/s senza errori.
- **Banco Prova Operativo ("Field Operational Tools")**:
  - **Modbus Quick Commander**: lettura (FC01..FC04) e scrittura/forzatura (FC05, FC06, FC15, FC16) sia seriale RTU che Ethernet TCP.
  - Decodifica ingegneristica automatica in UInt16, Int16 Signed, Float32 IEEE-754 (Big-Endian e Word-Swapped Little-Endian), Hex e Booleani / Coils.
  - Integrazione diretta nello Slave Inspector Modbus (tab "⚡ Quick Commander") e nel modale standalone unificato da barra comandi.
  - **BACnet Point Commander**: forzatura immediata del `presentValue` su oggetti `analogOutput`, `binaryOutput`, `multiStateOutput`, ecc., con gestione del Priority Array (default Priorità 8: Operatore Manuale) e rilascio forzatura (Relinquish / NULL).
  - Mini-modal di override richiamabile direttamente da ogni riga della tabella oggetti BACnet.
- **Simulatore d'Impianto Virtuale (Demo / Offline Mode)**:
  - Motore di simulazione HVAC/BACS integrato con ciclo asincrono di oscillazione dinamica dei valori (temperatura, pressione, potenza, stati).
  - Dispositivi virtuali pre-popolati: Chiller Modbus (Slave 1), Pompa Primaria (Slave 2), Analizzatore Rete (Slave 3), Unità Trattamento Aria BACnet (Device 1001), VAV Box (Device 1002), KNX Touch & Sensore (1.1.1, 1.1.2), Host ARP.
  - Switcher rapido nella barra comandi superiore con pill dinamica `DEMO: ON / DEMO: OFF` e flag CLI `--demo`.
- **Live Log Viewer & Dock Console Avanzato**:
  - Filtro per livello di severità in tempo reale (`ALL`, `DEBUG`, `INFO`, `WARN`, `ERROR`).
  - Casella di ricerca full-text istantanea con evidenziazione.
  - Formato strutturato dei messaggi WebSocket (`level`, `logger`, `created`, `message`).
  - Sistema di notifiche Toast non-bloccanti a scomparsa automatica con codice colore semantico.
- **Libreria Profili Modbus Estesa & Custom Profiles Manager**:
  - 13 profili industriali integrati: Multimetri (ABB B23, Carlo Gavazzi EM24, Carlo Gavazzi EM111, IME Nemo 96, Schneider iEM3150, Schneider PM5350, Siemens PAC3200), Contabilizzatori ed Energia (Belimo Energy Valve EV, Isoil ISOMAG, Diehl/Hydrometer Sharky 775, Emerson Rosemount 8712), Attuatori & Regolatori HVAC (Belimo Attuatore Modbus, Trox VAV Compact, iSMA-B-4I4O, Riello Caldaia Condexa Pro, Carel pCO).
  - Gestione profili personalizzati (creazione, visualizzazione, import/export JSON, eliminazione).
  - Funzione "Applica a Slave": mappatura istantanea su slave ID e inserimento punti nei registri e mappe d'impianto.
- **Registro Manovre Certificato (Crash-Proof WAL & Chaining Crittografico SHA-256)**:
  - Write-Ahead Log su file append-only `audit_journal.jsonl`.
  - Registrazione preventiva dell'intento con `os.fsync` prima della trasmissione fisica sul bus o rete IP.
  - Registrazione del risultato con tempo di risposta, stato di successo/errore e valore verificato.
  - Concatenazione crittografica (blockchain-style): ogni riga calcola `entry_hash = SHA-256(prev_hash + campi)`.
  - Recupero automatico degli intenti orfani all'avvio in caso di crash o interruzione improvvisa dell'alimentazione.
  - Endpoint e modale di verifica integrità del registro con rilevamento manomissioni.
  - Esportazione certificata dell'audit journal in formato JSON firmabile.
- **Blocco Sicurezza Manovre (Safe Mode Interlock)**:
  - Blocco preventivo delle manovre di scrittura su registri Modbus e override BACnet con codice `403 Forbidden`.
  - Sblocco temporizzato ("Arm") con obbligo di specificare Nome Operatore / Tecnico, Commessa / Ordine di Lavoro, e Finestra Temporale di sblocco (15, 30, 60, 120 minuti).
  - Disarmo manuale immediato o automatico al decorso del timeout.
  - Badge dinamico in testata (verde: protetto / bloccato; rosso pulsante: sbloccato / armato con conto alla rovescia).
- **Packaging Unificato Standalone (Portable vs Installed) & Firma Digitale SignPath**:
  - Risoluzione runtime dei percorsi tramite `core/paths.py`: supporto per PyInstaller congelato (`sys._MEIPASS`), rilevamento modalità portatile (`portable.flag`) e fallback su percorsi standard di sistema (`%LOCALAPPDATA%` / `~/.local/share/bham`).
  - Script Inno Setup `installer/bham.iss` per installer Windows x64 pulito con creazione collegamenti e disinstallazione.
  - Pipeline GitHub Actions `.github/workflows/release.yml` con integrazione `SignPath/github-action-submit-signing-request@v2` per firma autenticata del codice e rilascio sia dell'archivio portatile (.zip con `portable.flag`) sia dell'installer Windows (.exe firmato).

### Modificato
- Bump versione globale a `0.8.0` in tutti i componenti (backend, frontend, packaging Debian, Winget, documentazione OpenAPI).
- Sincronizzazione i18n al 100% su 289 chiavi per ciascuna lingua (Italiano, Inglese, Spagnolo).

## [0.7.0] – 2026-10-03

### Aggiunto
- **Launcher cross-platform `bham.py`** (Windows e Linux): un solo comando per installare e avviare.
  - Legge `requirements.txt` e confronta ogni pacchetto con quanto installato nel `.venv`.
  - Mostra l'elenco delle dipendenze mancanti o con versione diversa, chiede conferma e installa tutto da solo in un ambiente isolato.
  - Auto-apertura del browser web predefinito all'avvio su localhost (con supporto ambienti headless e flag `--no-browser`).
  - Flag `--yes` (non interattivo), `--check` (solo verifica, exit code 0/1), `--no-reload` (uso in cantiere).
- **Accesso Remoto e da Rete Locale (LAN)**:
  - Piena compatibilità d'uso su Raspberry Pi o PC di quadro industriale con connessione remota tramite browser (`http://192.168.x.x:8765`).
  - Stampa automatica a terminale di tutti gli URL LAN rilevati all'avvio con indicazioni firewall (`ufw allow 8765/tcp`).
  - Box dedicato "Accesso Remoto LAN" in Impostazioni con URL rilevati e pulsante di copia negli appunti con feedback visivo.
  - WebSocket resiliente e protocol-aware (`wss:` su HTTPS/tunnel e `ws:` su standard HTTP).
- **Diagnostica Euristica Qualità Bus RS485**: calcolo automatico dello stato del livello fisico del bus nello sniffer seriale con allarmi per terminazioni 120Ω mancanti, polarità A(+)/B(-) invertita, disturbi o saturazione del bus. Badge informativo e tooltip nel banner Bus Health.
- **Quick Diagnostic Self-Test 1-Click**: endpoint `GET /api/v1/hardware/self-test` e card diagnostica nelle impostazioni per collaudo rapido di apertura porta seriale RS485 con tempi di latenza, stato schede di rete e privilegi OS (dialout/admin/Npcap).
- **Profili Impianto Rapidi (Preset)**: selettore a tendina in sidebar e impostazioni per applicare con 1 click configurazioni per HVAC Standard, Contatori Energia, Gateway DALI o Ricerche Approfondite.
- **CI**: smoke test dell'auto-installazione su Ubuntu e Windows, controllo sintassi JavaScript, verifica dell'allineamento di tutte le stringhe di versione.
- **Release**: note di rilascio estratte da questo CHANGELOG e nuovo bundle `bham-source-<ver>.zip` (sorgenti + launcher).

### Modificato
- **Centro Impostazioni**: le tab orizzontali sono sostituite da una colonna laterale con le macro-voci (Adattatori & Porte, Connettività & Scansione, Tema & Lingua, Sessioni Salvate, Mappe BACS Help).
- **Tema e Lingua**: menu a tendina al posto dei pulsanti, sincronizzati con la preferenza salvata.
- `scripts/bump_version.py` ora sincronizza anche frontend (titolo, badge, cache-buster), i18n, manuali e `package_deb.sh`; nuovo `--files` per gli script di release.
- Il report Excel legge la versione da `core/config.py` invece di averla scritta nel codice.

## [0.6.0] – 2026-09-30

### Aggiunto
- Session Diff Engine ("Prima vs Dopo"), report Excel a 8 fogli e PDF gerarchico, BBMD Router Traversal e Foreign Device BACnet/IP.
