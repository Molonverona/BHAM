# BHAM – Audit del Codice

> Analisi statica del sorgente eseguita il 2026-09-29 (riferita allo stato v0.3.0).
> **Stato di Risoluzione (v0.8.0):** Tutti gli 11 rilievi (#1–#11) sono stati integralmente risolti nelle release v0.4.0 – v0.8.0 (thread-safe event loop dispatching, serial sniffer error propagation, CIDR expansion, background tempfile cleanup, Safe Mode, e certificazione Write-Ahead Log).
> **Verifica indipendente (v1.2.5, 2026-10-25):** la chiusura degli 11 rilievi è stata ricontrollata sul codice attuale e **risulta confermata**; sono però emersi 6 rilievi nuovi, documentati nella sezione seguente, tutti risolti in v1.2.5.

---

# Controllo generale v1.2.5 (2026-10-25)

Secondo giro di revisione, condotto sul codice della v1.2.0 pubblicata.

## Verifica dei rilievi storici #1–#11

Ogni rilievo è stato riaperto e ricontrollato nel sorgente:

| # | Rilievo originale | Esito della verifica |
| --- | --- | --- |
| 1 | Race condition cross-thread nel broadcast WebSocket | **Confermato risolto** – `api/websockets.py` marshalla con `loop.call_soon_threadsafe` |
| 2 | `AppState` mutato da più thread senza lock | **Confermato risolto** – `threading.Lock` reale usato in tutte le mutazioni… *con un'eccezione*, vedi N4 |
| 3 | `_notify` inghiotte le eccezioni | **Confermato risolto** – ramo d'errore ora loggato a WARNING |
| 4 | Marker di conflitto git nel README | **Confermato risolto** – nessun marker presente |
| 5 | Sniffer seriale segnala COMPLETED su errore | **Confermato risolto** – `_run_capture_loop` ritorna un esito e imposta `ScanStatus.ERROR` |
| 6 | MS-TP: frame validi ma incompleti distrutti | **Confermato risolto** – distinzione fra header CRC invalido e payload non ancora arrivato |
| 7 | Modbus TCP senza espansione CIDR | **Confermato risolto** – espansione implementata con deduplica |
| 8 | Nessuna autenticazione + CORS aperto | **Confermato risolto** in v1.1.0 (token LAN + CORS conforme) |
| 9 | 10 `Application()` BACnet concorrenti sulla stessa porta | **Confermato risolto** – `Application` condivisa nell'enrichment |
| 10 | `abort_event` globale condiviso | **Parzialmente risolto** – abort per-sessione introdotto, ma la mutua esclusione sulla risorsa seriale era rimasta aperta: vedi N2 |
| 11 | `tempfile.mktemp` e file temporanei mai cancellati | **Confermato risolto** – `mkstemp` + `BackgroundTask` di pulizia |

I minori segnalati (import di `Any`, import inutilizzati, `health()` che accedeva a `manager._active`) risultano anch'essi sistemati.

---

## 🔴 Critici

### N1. L'arresto d'emergenza globale rispondeva HTTP 500
`POST /api/v1/scan/abort` dichiara `ScanAbortResponse.sessions: list[str]` ("Elenco ID delle sessioni terminate"), ma l'handler restituiva l'**intero** di `abort_all()`. La validazione della risposta di FastAPI falliva, quindi l'endpoint rispondeva **500 Internal Server Error**: la funzione di arresto d'emergenza non ha mai funzionato via HTTP.

Il difetto è sopravvissuto perché la suite invoca `routes.abort_all_scans()` **direttamente**, bypassando la validazione contro il `response_model`: nessun test esercitava il contratto dichiarato.

**Risolto in v1.2.5:** `abort_all()` ritorna la lista degli ID effettivamente fermati (coerente con lo schema e più utile). Aggiunta una famiglia di test che valida l'uscita degli handler contro il `response_model` realmente dichiarato sulla route, più un test che impone a ogni endpoint `/scan*` di dichiararne uno.

---

## 🟠 Alti

### N2. Nessuna mutua esclusione sulle risorse di campo esclusive
Rimasto aperto dal rilievo #10. Una porta RS485 ammette un solo lettore, ma nulla impediva di avviare contemporaneamente una scansione Modbus RTU e uno sniffer passivo sulla **stessa** `/dev/ttyUSB0`: i due consumatori si rubano i byte a vicenda, falsando sia la mappatura sia la diagnosi di Bus Health. Lo stesso valeva per il discovery BACnet/IP (bind della 47808) e per discovery KNXnet/IP e Group Monitor, che condividono il socket multicast 3671.

**Impatto:** letture corrotte presentate come valide, senza alcun avviso all'operatore.

**Risolto in v1.2.5:** nuovo `core/resource_guard.py` con registro delle rivendicazioni protetto da lock. Le route di avvio rivendicano la risorsa e un conflitto viene rifiutato con **HTTP 409**, indicando quale operazione la detiene, da quanti secondi e come arrestarla. La verifica precede la creazione della sessione, così un conflitto non lascia una sessione fantasma nello storico. Nuovo endpoint `GET /api/v1/system/resources` per ispezionare le risorse occupate.

---

## 🟡 Medi

### N3. Registro degli abort mai liberato, con conteggio fuorviante
`scanners/base.py`: `_abort_events` accumulava una voce per ogni scansione e **non veniva mai ripulito**, crescendo per tutta la durata del processo. Inoltre `abort_all()` ritornava `len(_abort_events)`, cioè il numero di sessioni mai registrate — non le scansioni effettivamente attive.

**Risolto in v1.2.5:** `release_session()` invocata quando il task di scansione termina (in qualunque modo, tramite done-callback), e `abort_all()` ritorna solo le sessioni effettivamente fermate.

### N4. Lo storico sessioni cresceva senza limiti ed era inviato per intero via WebSocket
`data/state.py`: `self.sessions` non aveva alcun tetto e veniva serializzato **integralmente** in ogni `snapshot()`, cioè a ogni connessione WebSocket e a ogni evento di stato. Durante una giornata di collaudo con decine di scansioni il payload cresceva di continuo. `clear()` inoltre non azzerava lo storico, a differenza di tutte le altre collezioni.

Nello stesso punto: `sessions` era **l'unica collezione mutata fuori da `_state_lock`**, mentre `snapshot()` la itera tenendolo — residuo del rilievo #2, corretto altrove ma non qui. Gli scanner aggiornano le sessioni da thread di executor, quindi la lettura poteva risultare incoerente.

**Risolto in v1.2.5:** tetto `max_sessions` (200) con scarto delle più vecchie fra quelle **concluse** (le scansioni in corso non vengono mai rimosse), mutazioni portate sotto `_state_lock`, e `clear()` che azzera lo storico concluso preservando le sessioni attive.

### N5. Dipendenze ferme a circa due anni
12 delle 14 dipendenze pinnate erano indietro di versioni (fastapi 0.115→0.162, uvicorn 0.30→0.54, pydantic 2.9→2.14, websockets 13.1→17.3, pymodbus 3.7→3.16, reportlab 4.2→5.1), senza aggiornamenti di sicurezza da due anni.

**Affrontato in v1.2.5 con cautela differenziata:**
- **Aggiornate e verificate** le dipendenze infrastrutturali (fastapi, uvicorn, websockets, pydantic, pydantic-settings, aiofiles, python-dotenv, python-multipart): suite completa verde, binario congelato ricompilato e canale WebSocket live verificato end-to-end.
- **Deliberatamente lasciate pinnate** `pymodbus`, `bacpypes3`, `scapy` e `reportlab`: governano il comportamento sul filo (RS485, BACnet/IP, cattura L2) e l'impaginazione dei certificati PDF. Il simulatore non può sostituire una validazione su hardware reale, quindi il loro avanzamento resta un intervento da pianificare con strumentazione in linea.

### N6. Lo smoke test del binario non copriva il canale WebSocket
La telemetria live è il cuore della console di collaudo, ma `scripts/smoke_frozen.py` verificava solo le route REST: un bundle con l'implementazione WebSocket incompleta avrebbe superato il test. La lacuna era particolarmente rilevante proprio mentre si aggiornava `websockets` da 13.1 a 17.3.

**Risolto in v1.2.5:** lo smoke test apre una connessione al canale live e pretende lo snapshot iniziale, verificando anche il nuovo registro risorse. La verifica si autoesclude con un avviso se la libreria `websockets` non è presente nell'ambiente che esegue il test.

---

## ⚪ Note ambientali (non difetti del prodotto)

- La dipendenza `bacpypes3` installa un pacchetto `tests` di primo livello in `site-packages`, che oscura la directory `tests/` del repository: `python -m unittest tests.<modulo>` fallisce con un `ModuleNotFoundError: pytest` proveniente da quel pacchetto. Per questo la CI usa `unittest discover -s tests`, che risolve per percorso. Usare `discover` anche in locale.

---

# Audit storico v0.3.0 (2026-09-29)

> Primo giro di revisione, conservato per tracciabilità. Tutti i rilievi di
> questa sezione risultano chiusi: la verifica è nella tabella in testa al
> documento.

## Sintesi

Base di codice **ben strutturata e sopra la media**: architettura pulita con separazione netta dei moduli, type hints diffusi, i18n, degradazione gestita quando mancano le dipendenze, protezione path-traversal nel session store, controlli privilegi con messaggi correttivi.

Tuttavia il claim del DEVLOG "zero debiti tecnici / 22/22 test" è ottimistico. Esistono bug concreti, alcuni proprio nella feature di punta (sniffer passivo RS485). Di seguito i rilievi per priorità, con riferimenti a file.

---

## 🔴 Critici

### 1. Race condition cross-thread nel broadcast WebSocket (sniffer seriale e ARP)
`asyncio.Queue.put_nowait()` **non è thread-safe**, ma viene invocato da thread diversi dall'event loop:

- `scanners/serial_sniffer.py` → `_run_capture_loop` gira in `run_in_executor` (thread) e chiama direttamente `state.update_bus_health()` / `record_serial_frame()` / `upsert_modbus()` / `upsert_bacnet()` → `data/state.py::_notify` → `api/websockets.py::enqueue_state_event` → `put_nowait`.
- `scanners/ip_sniffer.py` → `_packet_callback` gira nel thread di `scapy.sniff` e fa lo stesso via `upsert_ip_host`.

`put_nowait` internamente fa `future.set_result` sui getter in attesa: chiamarlo da un thread esterno non risveglia in modo affidabile il pump task e può corrompere lo stato interno della coda.

**Impatto:** frame RS485, Bus Health e host ARP possono non arrivare al frontend, o arrivare in modo intermittente / con errori.

**Fix consigliato:** marshallare sull'event loop, es. salvare il riferimento al loop all'avvio e usare `loop.call_soon_threadsafe(self._queue.put_nowait, payload)`. Nota: `broadcast_sync()` esiste ma non è mai usato, e presenta lo stesso difetto.

### 2. `AppState` mutato da più thread senza lock, mentre `snapshot()` itera i dict
`data/state.py`: la docstring dichiara "Thread-safe", ma `self._lock = asyncio.Lock()` **non è mai usato**. Mentre lo sniffer (thread) esegue `upsert_*` sui dizionari, un client WebSocket che si connette scatena `snapshot()` che itera gli stessi dict dall'event loop.

**Impatto:** possibile `RuntimeError: dictionary changed size during iteration`.

**Fix consigliato:** strategia coerente — marshalling sul loop (come al punto 1) oppure lock reali attorno alle mutazioni e allo snapshot.

### 3. `_notify` inghiotte silenziosamente tutte le eccezioni
`data/state.py`:
```python
def _notify(self, payload):
    for hook in self._broadcast_hooks:
        try: hook(payload)
        except Exception: pass
```
Nasconde esattamente gli errori dei punti 1–2, rendendoli invisibili in campo.

**Fix consigliato:** almeno un `log.debug`/`log.warning` sul ramo di eccezione.

---

## 🟠 Alti

### 4. README con marker di conflitto git non risolti
`README.md` contiene `<<<<<<< HEAD` … `=======` … `>>>>>>> 862444e9…`. È la landing page pubblica su GitHub (owner Molonverona). Da risolvere subito; verificare sia la copia su disco sia quella nel progetto.

### 5. Lo sniffer seriale segnala COMPLETED anche quando la porta non si apre
`scanners/serial_sniffer.py::sniff()`: dopo `run_in_executor(self._run_capture_loop, req)` viene sempre chiamato `finish_session(..., COMPLETED)`. Ma `_run_capture_loop`, in caso di errore di apertura porta (inesistente, occupata), logga e fa solo `return` senza propagare.

**Impatto:** il frontend mostra "successo" su uno sniff fallito (l'ARP sniffer invece propaga correttamente lo stato ERROR).

**Fix consigliato:** far ritornare a `_run_capture_loop` un esito (o sollevare) e impostare `ScanStatus.ERROR` + `error_message`.

### 6. Dissettore BACnet MS-TP: distrugge frame validi ma incompleti
`scanners/serial_sniffer.py::_process_buffer`: quando trova il preambolo `55 FF` e `_parse_mstp_frame` ritorna `None`, il codice assume "Header CRC Error". Ma `_parse_mstp_frame` ritorna `None` anche quando l'header è **valido** e sta solo aspettando il payload (`len(buf) < total_len`). In quel caso viene cancellato il preambolo ed emesso un falso frame d'errore.

**Impatto:** frame valido perso e PER% gonfiato. Si manifesta con letture frammentate (frame MS-TP > 512 byte o al confine di un chunk).

**Fix consigliato:** distinguere "header CRC invalido" da "payload non ancora arrivato" (es. far ritornare a `_parse_mstp_frame` un sentinel diverso per il caso "attendi altri byte").

### 7. Modbus TCP: la scansione CIDR promessa nel README non è implementata
`scanners/modbus.py::scan_tcp`/`_probe_tcp_host` usa `req.hosts` così com'è; non c'è alcuna espansione di subnet (nessun uso di `ipaddress`). Passando `192.168.1.0/24` prova a connettersi alla stringa letterale e fallisce. Il README dichiara "intere subnet CIDR".

**Fix consigliato:** implementare l'espansione (`ipaddress.ip_network(cidr, strict=False).hosts()`) oppure correggere la documentazione.

---

## 🟡 Medi

### 8. Nessuna autenticazione + bind su `0.0.0.0` + CORS totalmente aperto [RISOLTO in v1.1.0]
`main.py`: `allow_origins=["*"]` con `allow_credentials=True` (combinazione anche formalmente invalida per i browser) e nessun auth, su un daemon in ascolto su tutte le interfacce. Su una rete cliente chiunque poteva lanciare scansioni, leggere la topologia scoperta e scaricare i report.

**Risolto in v1.1.0:**
- **CORS Hardening:** Rimossa la combinazione non conforme di `allow_origins=["*"]` con `allow_credentials=True` (impostato compliant `allow_credentials=False`).
- **LAN Security Token:** Introdotto middleware `lan_security_middleware` con token crittografico casuale a 16 byte generato automaticamente all'avvio (`secrets.token_urlsafe(16)`) o configurabile via `.env` (`BHAM_API_TOKEN`).
- **Esenzione Localhost Trasparente:** Tutte le connessioni loopback (`127.0.0.1`, `::1`) mantengono accesso diretto senza credenziali per massima usabilità sul dispositivo di collaudo.
- **Protezione Connessioni Remote LAN & WebSocket:** Le richieste da host LAN remoti richiedono obbligatoriamente il token via header HTTP `X-BHAM-Token` o query parameter `?token=`. Gli handshake WebSocket remoti sprovvisti di token valido vengono rifiutati con codice `4401`.
- **Pairing QR Code Integrato:** Il generatore offline di codici QR inietta automaticamente il token di sicurezza nell'URL rilevato della LAN per accoppiare tablet e smartphone di cantiere in 1-click.

### 9. Enrichment BACnet: 10 `Application()` concorrenti sulla stessa porta
`scanners/bacnet.py::_enrich_devices` usa `Semaphore(10)` e ogni `_read_device_properties` istanzia una nuova `Application` che tenta il bind sulla porta BACnet di default → probabili collisioni di bind, con errori inghiottiti dal try/except. In campo l'arricchimento può fallire spesso.

**Fix consigliato:** riusare una singola `Application` per l'intera fase di enrichment.

### 10. `abort_event` globale condiviso tra tutti gli scanner
`scanners/base.py`: `reset_abort()` viene chiamato all'inizio di ogni nuova scansione, quindi avviare una scansione B azzera l'abort di una A in corso, e l'abort ferma tutto. Non c'è guard "scansione già in corso" né mutua esclusione sulla porta seriale (due sniff sulla stessa `/dev/ttyUSB0` si scontrano).

**Fix consigliato:** abort/stato per-sessione, e un lock sulla risorsa seriale. Accettabile in single-user, ma da esplicitare.

### 11. Report: `tempfile.mktemp` deprecato/insicuro e file mai cancellati
`api/routes.py::export_excel`/`export_pdf`: `tempfile.mktemp` è deprecato e soggetto a race; i file temporanei non vengono mai rimossi (`background=None`) → accumulo in `/tmp`.

**Fix consigliato:** `mkstemp`/`NamedTemporaryFile` + `starlette.background.BackgroundTask` per la pulizia post-invio.

---

## ⚪ Minori

- `Any` usato nelle annotazioni di `parse_bacnet_ports` (`scanners/bacnet.py`) e `parse_modbus_tcp_ports` (`scanners/modbus.py`) senza importarlo; salvato solo da `from __future__ import annotations` (i linter / `typing.get_type_hints` lo segnalerebbero).
- `import os` in `api/routes.py` e la variabile `e` nel fallback bind di `scanners/knx.py` non usati.
- `data/state.py::restore_snapshot` non ripristina `sessions` né `bus_health`.
- `api/routes.py::health` accede a `manager._active` (attributo privato).
- `tests/test_bham.py`: i test di CRC/dissezione MS-TP generano i frame con le **stesse** funzioni che testano — verificano la coerenza interna, non la conformità ASHRAE 135 reale. Un vettore di riferimento esterno darebbe più garanzie.

---

## Punti di forza (da preservare)

- Architettura modulare chiara (api / core / data / scanners / reports).
- Sniffing RS485 realmente passivo (Zero-TX) — design corretto per bus in marcia.
- CRC Modbus/MS-TP in puro Python, senza dipendenze aggiuntive.
- Degradazione gestita quando mancano `pyserial`/`scapy`/`bacpypes3`/`pymodbus`.
- Protezione path-traversal in `core/session_store.py`.
- Controlli privilegi (`core/priv_check.py`) con messaggi correttivi precisi per Linux/Windows.
- i18n IT/EN/ES e parser porte (BAC0..BACF, range, liste) robusti e ben testati.

---

## Priorità d'intervento suggerita

1. #1 / #2 / #3 — thread-safety del broadcast (sblocca l'affidabilità dello sniffer).
2. #4 — README (visibile pubblicamente).
3. #5 / #6 — correttezza dello sniffer seriale (stato ERROR + frame MS-TP frammentati).
4. #7 — CIDR Modbus TCP (codice o documentazione).
5. #8–#11 — sicurezza, robustezza BACnet, gestione risorse.
