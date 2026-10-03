# Changelog – BHAM (BACS Help Auto Mapper)

Formato basato su [Keep a Changelog](https://keepachangelog.com/it/1.1.0/), versioni [SemVer](https://semver.org/lang/it/).
Le note della sezione corrispondente alla versione vengono pubblicate automaticamente nella GitHub Release.

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
