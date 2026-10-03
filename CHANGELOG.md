# Changelog – BHAM (BACS Help Auto Mapper)

Formato basato su [Keep a Changelog](https://keepachangelog.com/it/1.1.0/), versioni [SemVer](https://semver.org/lang/it/).
Le note della sezione corrispondente alla versione vengono pubblicate automaticamente nella GitHub Release.

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
