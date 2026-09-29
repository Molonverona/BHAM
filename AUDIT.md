# BHAM – Audit del Codice

> Analisi statica del sorgente eseguita il 2026-09-29.
> Versione analizzata: v0.3.0. Ambito: `main.py`, `api/`, `core/`, `data/`, `scanners/`, `reports/`, `tests/`.

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

### 8. Nessuna autenticazione + bind su `0.0.0.0` + CORS totalmente aperto
`main.py`: `allow_origins=["*"]` con `allow_credentials=True` (combinazione anche formalmente invalida per i browser) e nessun auth, su un daemon in ascolto su tutte le interfacce. Su una rete cliente chiunque può lanciare scansioni, leggere la topologia scoperta e scaricare i report.

**Fix consigliato:** valutare bind di default su `127.0.0.1`, o un token/API key; almeno documentare il rischio.

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
