# BHAM – BACS Help Auto Mapper
## Manuale Tecnico di Collaudo & Guida Operativa di Campo (v0.8.1)

---

## 1. Panoramica del Sistema & Architettura
**BHAM (BACS Help Auto Mapper)** è una piattaforma di collaudo industriale, ricognizione e diagnostica attiva/passiva progettata per impianti di automazione edificio (BACS / BMS).
Consente l'inventario rapido, l'identificazione hardware, l'arricchimento dei registri, la visualizzazione topologica, il confronto differenziale di sessione e l'esportazione di verbali di collaudo per reti:
- **Modbus RTU (RS485)** (Scansione attiva, Smart Scan registri e Sniffing passivo Zero-TX)
- **Modbus TCP**
- **BACnet/IP & BACnet MS-TP** (Who-Is Discovery, Object Explorer, Sniffing passivo Zero-TX e attraversamento Router BBMD/Foreign Device)
- **KNXnet/IP**
- **Sottoreti IP (ARP Passive Sniffer)**
- **Diagnostica Telemetrica Bus Health (RS485)**
- **Mappa Topologica d'Impianto Interattiva (Network Graph)**
- **Intelligence & Session Diff ("Prima vs Dopo")** (Confronto deterministico baseline vs collaudo corrente)
- **Reporting As-Built 2.0** (Cartella Excel a 8 fogli e PDF vettoriale con diagramma gerarchico)

### Architettura
- **Backend:** Python 3.12, FastAPI, WebSocket streaming a bassa latenza, protocolli nativi asincroni (`pymodbus`, `bacpypes3`, `scapy`).
- **Frontend:** Field Engineer Studio v4.2 in Vanilla JS ad alte prestazioni senza dipendenze esterne: architettura a 2 colonne (Sidebar Canali 360px + Workspace centrale con Switcher Vista Tabella/Topologia + Dock Diagnostico a scomparsa).
- **Mappa Topologica SVG:** Engine vettoriale nativo con calcolo gerarchico, Pan & Zoom continuo, fit-to-screen, orientamento H/V ed esportazione vettoriale .svg.
- **Reporting:** Generazione istantanea di verbali in formato **PDF Vettoriale a due passate (ReportLab)** e **Fogli Excel (openpyxl)** a 8 fogli di lavoro con metadati, as-built registri e oggetti.
- **Internazionalizzazione (i18n):** Supporto completo e reattivo per **Italiano**, **Inglese** e **Spagnolo** (232 chiavi per lingua con parità al 100%).
- **Launcher Cross-Platform & Accesso Remoto:** Auto-apertura del browser all'avvio e piena accessibilità da altri dispositivi in rete locale (es. Raspberry Pi su `http://192.168.x.x:8765`).

---

## 2. Guida Rapida di Avvio (Quick Start)
1. **Avvio & Auto-Apertura Browser:** Esegui `python3 bham.py` (Linux) o `python bham.py` (Windows). Il launcher verifica le dipendenze, crea l'ambiente isolato se necessario e apre automaticamente la dashboard nel browser.
2. **Accesso da Tablet o Altri PC (Rete LAN):** Se BHAM è in esecuzione su un Raspberry Pi o PC industriale in quadro elettrico, collegati via Wi-Fi o cavo e apri nel browser l'indirizzo LAN visualizzato a video o nella scheda Impostazioni (es. `http://192.168.1.50:8765`).
3. **Collegamento Periferiche:** Connetti l'adattatore USB↔RS485 al bus seriale e/o il cavo di rete Ethernet alla LAN BMS dell'edificio.
4. **Configurazione Hardware:** Clicca sull'icona **Impostazioni** (ingranaggio in alto a destra) ed entra nella scheda *Adattatori & Porte*.
   - Clicca *⚡ Esegui Self-Test* per collaudo rapido hardware e permessi di sistema.
   - Clicca *Scansiona Porte* per rilevare convertitori RS485 FTDI, CH340, CP210x.
   - Clicca *Scansiona NIC* per selezionare l'interfaccia cablata associata alla sottorete dell'impianto.
   - Clicca *Applica Configurazione*.
5. **Avvio Scansione:** Clicca sul pulsante **AVVIA SCAN RAPIDO** in testata. Il sistema eseguirà automaticamente in cascata:
   - Modbus RTU Phase Zero + Early Exit
   - BACnet/IP Who-Is Broadcast
   - KNXnet/IP Discovery
   - ARP Passive Sniffer
6. **Visualizzazione & Esplorazione:**
   - Consulta le tabelle dispositivi per protocollo nel Workspace centrale.
   - Clicca su **Mappa Topologica** per osservare l'albero d'impianto interattivo con canali fisici e nodi.
   - Ispeziona gli oggetti BACnet con l'**Object Explorer** e mappa i registri Modbus con lo **Smart Scan**.
7. **Esportazione Verbale:** Scarica i risultati cliccando sui pulsanti **PDF**, **Excel** o esporta la mappa topologica in formato **SVG**.

---

## 3. Motore Modbus RTU (RS485) & TCP
### Regole Fisiche per il Bus RS485:
- **Topologia:** Lineare Daisy-Chain (a cascata). Nessun cablaggio a stella superiore a 1 metro.
- **Cavo:** Schermato a coppia ritorta (STP). Collegare lo schermo a terra da un solo lato.
- **Terminazione:** Resistenza da 120 Ω (1/4 Watt) da applicare esattamente ai due nodi estremi del bus per eliminare riflessioni RF.
- **Polarità:** D+ (morsetto non invertente A) e D- (morsetto invertente B).

### Algoritmo di Scansione RTU a 3 Fasi:
1. **Phase Zero (Silent Auto-Baud):** Ascolto passivo asincrono sul bus per 1.5s per ogni velocità (9600, 19200, 38400, 115200). Un parser CRC-16 puro individua i frame validi e blocca la configurazione seriale senza emettere pacchetti di disturbo.
2. **Early Exit (Sonda Sentinella):** Se il bus è inattivo, interroga gli ID sentinella {1, 2, 10} con timeout conservativo. Al primo hit blocca i parametri di comunicazione.
3. **Full Sweep Rapido:** Scansiona l'intero intervallo ID con client seriale persistente e timeout ridotto a 120ms.

### Modbus TCP Multi-Porta:
- Supporto per la porta standard `502` e porte alternative industriali/gateway (es. `503`, `5020`, `8502`).
- Possibilità di inserire porte singole, liste separate da virgola (es. `502, 503, 5020`) o range con test concorrente asincrono su ciascun endpoint.

### Diagnostica Modbus FC43 (MEI 0x0E):
Interrogazione diretta dello standard MEI (Modbus Encapsulated Interface) per ottenere:
- Nome Costruttore (Vendor Name)
- Codice Prodotto (Product Code)
- Versione Revisione Firmware (Major/Minor Revision).

### Modbus Smart Register Scan:
Funzionalità euristica per il sondaggio automatico dei registri di uno slave Modbus:
- Esegue una scansione predittiva a blocchi su indirizzi standard per Holding Registers (FC03), Input Registers (FC04), Coils (FC01) e Discrete Inputs (FC02).
- Distingue registri attivi da indirizzi non mappati o errori di eccezione (Illegal Data Address 0x02).
- Popola la mappa registri dello slave con visualizzazione immediata dei valori in formato Integer, Float ed Esadecimale.

---

## 4. Motore BACnet/IP Discovery
- **Notazione e Porte UDP Speciali:**
  - **BAC0:** Porta standard `47808` (`0xBAC0`), rete BACnet primaria.
  - **BAC1..BACF:** Porte da `47809` (`0xBAC1`) a `47823` (`0xBACF`), usate per partizionare sottoreti virtuali BACnet, gateway e router.
  - **Sintassi flessibile:** BHAM accetta notazione simbolica (`BAC0`, `BAC1`), range (`BAC0..BAC3`), liste separate da virgola (`BAC0, BAC1, 50000`) e porte intere arbitrarie (es. `50000`).
- **Who-Is Broadcast:** Invia pacchetti broadcast 255.255.255.255 per rilevare tutti i nodi operativi (DDC, pompe, UTA, chiller) su ciascuna porta specificata.
- **Arricchimento Telemetria:** Interroga concorrentemente con semaforo protetto (max 10 richieste parallele) le proprietà diagnostiche:
  - `vendor-identifier` e `vendor-name`
  - `model-name` e `firmware-revision`
  - `application-software-version`
  - `object-list` (conteggio punti fisici ed entità software configurate).

### BACnet Object Explorer:
Consente l'esplorazione gerarchica approfondita di tutti gli oggetti istanziati su un dispositivo BACnet selezionato:
- Interrogazione asincrona della proprietà `object-list` con risoluzione puntuale delle proprietà fondamentali.
- Supporto per tutti i tipi standard BACnet: Analog Input/Output/Value (AI/AO/AV), Binary Input/Output/Value (BI/BO/BV), Multi-state (MSI/MSO/MSV), Schedule, Trend Log, Calendar, Notification Class, Device, Loop.
- Visualizzazione in tempo reale di Present Value, Unità di Misura (Engineering Units), Status Flags (In Alarm, Fault, Overridden, Out of Service) e Object Name.
- Filtri veloci per tipologia di oggetto e casella di ricerca immediata per nome/istanza.

---

## 5. Sniffer Seriale Passivo (RS485 Zero-TX / Stealth Mode)
Nei collaudi su impianti in marcia con controllori PLC Master attivi (Carel, Siemens, Johnson Controls, Honeywell, Schneider, ecc.), l'invio di interrogazioni attive sul doppino causerebbe **collisioni hardware distruttive**, ritardi di regolazione e allarmi sui BMS di edificio. BHAM risolve il problema con il motore di ascolto passivo **Zero-TX**.

### Principi Operativi:
- **Stealth Mode (Zero-TX):** Apertura della porta seriale in sola lettura hardware. Nessun impulso elettrico né segnale di pilotaggio (RTS/DE) viene generato sul bus RS485.
- **Auto-Baudrate & Auto-Parità Silenzioso:** Campionamento asincrono del flusso di byte grezzi con aggancio automatico delle velocità da 9600 a 115200 baud e parità (None, Even, Odd) alla validazione del primo frame integro.
- **Dissettore Modbus RTU:**
  - Classificazione istantanea della direzione: *Query del Master* (M ➔ S) vs *Risposta dello Slave* (S ➔ M).
  - Decodifica registri e valori da FC01/FC02 (Coils/Inputs) ed FC03/FC04 (Holding/Input Regs).
  - Catalogazione automatica degli slave scoperti con contrassegno `[SNIFFED]`.
- **Dissettore BACnet MS-TP:**
  - Rilevazione preambolo `0x55 0xFF` e validazione Header CRC-8 (standard ASHRAE 135 con residuo `0x55`).
  - Mappatura completa dell'anello dei *Token* (MAC 0..127) e dei frame *Poll For Master*.
  - Validazione CRC-16 del payload dati (polinomio ISO-HDLC con residuo `0xF0B8`).
- **Telemetria Bus Health (Salute del Bus):**
  - **Packet Error Rate (PER %):** Percentuale di tramas corrotte o con CRC errato. Un PER < 1% indica una linea perfetta; PER > 5% denota problemi fisici di cablaggio (schermatura flottante, assenza di terminazione 120 Ω o riflessioni d'onda).
  - **Bus Load %:** Stima della saturazione temporale del canale RS485 in base alla velocità baud selezionata.
  - **Frame Rate (FPS):** Frequenza dei telegrammi transitanti sul bus.
- **RS485 Live Inspector:** Scheda dedicata nella Web UI con visualizzazione in tempo reale di ogni frame decodificato (timestamp, protocollo, direzione, mittente, destinatario, funzione/tipo, registri/dati, esito CRC).

---

## 6. Motore KNXnet/IP Discovery
- **Multicast Discovery:** Invio frame `SEARCH_REQUEST` (Service Type `0x0201`) all'indirizzo riservato `224.0.23.12:3671`.
- **Broadcast Fallback:** Spedizione contemporanea a `255.255.255.255:3671` per raggiungere gateway con multicast filtrato.
- **Decodifica DIB:**
  - Indirizzo Individuale KNX: formattazione `Area.Linea.Dispositivo` (es. `1.1.0`).
  - Friendly Name dispositivo (fino a 30 byte Latin-1).
  - Numero di serie hardware a 12 caratteri esadecimali e indirizzo MAC.
  - Medium fisico del bus (TP1, IP, RF, PL110).

---

## 7. Sniffer ARP Passivo L2
- Ricognizione non intrusiva basata su Scapy.
- Cattura pacchetti ARP broadcast senza generare frame di interrogazione attivi (invisibile agli IDS).
- Risoluzione OUI del costruttore MAC address (Siemens, Johnson Controls, WAGO, Schneider Electric, Phoenix Contact, Moxa, Raspberry Pi).

---

## 8. Mappe Registri BACS Help
BHAM supporta l'importazione ed esportazione di mappe punti in formato JSON compatibile BACS Help per correlare variabili e registri agli Slave ID:
```json
{
  "slave_id": 1,
  "register": 100,
  "register_type": "holding",
  "label": "Temperatura Mandata",
  "unit": "°C",
  "scale": 0.1,
  "description": "Sonda mandata UTA-01"
}
```

---

## 9. Guida al Troubleshooting
- **Errore porte seriali (Permesso Negato):**
  Esegui `sudo usermod -a -G dialout $USER`, scollega e ricollega la porta USB.
- **Mancata risposta Modbus:**
  Inverti i cavi D+ e D-. Verifica la presenza della resistenza di terminazione da 120 Ω.
- **Mancata rilevazione BACnet/KNX:**
  Apri le porte UDP nel firewall locale (`ufw allow 47808/udp` e `ufw allow 3671/udp`) e seleziona la scheda di rete corretta nel Centro Impostazioni.
- **Pulsante di Emergenza ABORT SCAN:**
  Arresta immediatamente tutti i thread e chiude la porta seriale per prevenire blocchi bus.

---

## 10. Riferimento REST & WebSocket API
La suite BHAM include un set completo di API RESTful e un canale WebSocket per l'automazione, l'integrazione con sistemi terzi, script di collaudo automatico e telemetria live.

- **Documentazione Swagger UI:** `http://localhost:8765/docs`
- **Documentazione ReDoc:** `http://localhost:8765/redoc`
- **Riferimento Tecnico Completo:** Consulta il file [API_REFERENCE.md](API_REFERENCE.md) per schemi Pydantic, contratti JSON, codici di stato ed esempi di integrazione Python/cURL.
- **Canale WebSocket Live:** `ws://<HOST_IP>:8765/api/v1/ws`

### Tabella degli Endpoint Principali

| Metodo | Endpoint | Dominio | Descrizione |
|---|---|---|---|
| `GET` | `/api/v1/health` | Sistema | Stato del servizio, versione demone e client WebSocket connessi |
| `GET` | `/api/v1/state` | Stato | Snapshot completo memoria: configurazione e dispositivi attivi |
| `DELETE` | `/api/v1/state` | Stato | Reset memoria e azzeramento stato di collaudo corrente |
| `GET` | `/api/v1/topology` | Topologia | Grafo gerarchico d'impianto (Host ➔ Canali ➔ Router ➔ Nodi) |
| `GET` | `/api/v1/hardware/self-test` | Hardware | Collaudo automatico porte seriali, interfacce di rete e permessi OS |
| `GET` | `/api/v1/setup/serial-ports` | Hardware | Rilevamento convertitori USB/RS485 (FTDI, CP210x, CH340, Prolific) |
| `GET` | `/api/v1/setup/network-interfaces` | Rete | Elenco schede NIC attive, IP LAN remoti e velocità negoziata |
| `POST` | `/api/v1/setup/configure` | Setup | Applicazione configurazione fisica seriale e rete per la sessione |
| `GET` | `/api/v1/setup/config` | Setup | Configurazione hardware correntemente attiva |
| `POST` | `/api/v1/scan/modbus/rtu` | Scansioni | Avvio sweep attivo Modbus RTU seriale (Phase Zero + Early Exit) |
| `POST` | `/api/v1/scan/modbus/tcp` | Scansioni | Scansione Modbus TCP multi-porta su host singoli o subnet CIDR |
| `POST` | `/api/v1/modbus/smart-scan` | Modbus | Smart Scan euristico predittivo registri holding/input slave Modbus |
| `POST` | `/api/v1/diag/modbus/fc43` | Modbus | Interrogazione MEI FC43 (0x0E) per Vendor, Product e Revision |
| `POST` | `/api/v1/scan/serial/sniff` | Sniffer | Avvio ascolto passivo RS485 Zero-TX (Modbus RTU & BACnet MS-TP) |
| `GET` | `/api/v1/diag/serial/health` | Diagnostica | Metriche fisiche Bus Health (PER %, FPS, Bus Load %, nodi attivi) |
| `POST` | `/api/v1/scan/bacnet/ip` | Scansioni | Who-Is broadcast BACnet/IP (Annex J) e attraversamento BBMD |
| `GET/POST`| `/api/v1/bacnet/devices/{id}/objects` | BACnet | Esplorazione approfondita gerarchica object-list dispositivo |
| `GET` | `/api/v1/bacnet/bbmd/tables` | BBMD | Ispezione combinata tabelle BDT ed FDT del router BBMD |
| `GET` | `/api/v1/bacnet/bbmd/bdt` | BBMD | Lettura Broadcast Distribution Table da router BBMD |
| `GET` | `/api/v1/bacnet/bbmd/fdt` | BBMD | Lettura Foreign Device Table da router BBMD con conto alla rovescia TTL |
| `POST` | `/api/v1/scan/knx/ip` | Scansioni | Discovery multicast UDP KNXnet/IP con estrazione DIB e indirizzi fisici |
| `POST` | `/api/v1/scan/arp` | Scansioni | Sniffer promiscuo Layer-2 ARP per rilevamento host silenti e OUI MAC |
| `POST` | `/api/v1/scan/abort` | Controllo | Arresto d'emergenza immediato di tutte le scansioni e sniffer |
| `POST` | `/api/v1/scan/abort/{session_id}` | Controllo | Arresto di un task di scansione specifico |
| `GET` | `/api/v1/devices/modbus` | Dispositivi | Elenco dispositivi Modbus RTU/TCP censiti nello stato attivo |
| `GET` | `/api/v1/devices/bacnet` | Dispositivi | Elenco controllori BACnet/IP censiti con metadati vendor/firmware |
| `GET` | `/api/v1/devices/knx` | Dispositivi | Elenco gateway e attuatori KNXnet/IP censiti |
| `GET` | `/api/v1/devices/hosts` | Dispositivi | Elenco apparati IP rilevati dallo sniffer ARP con risoluzione costruttore |
| `POST` | `/api/v1/saved-sessions/save` | Sessioni | Salvataggio snapshot di collaudo su file JSON persistente |
| `GET` | `/api/v1/saved-sessions/list` | Sessioni | Elenco cronologico di tutte le sessioni archiviate su disco |
| `GET` | `/api/v1/saved-sessions/{file}` | Sessioni | Download contenuto JSON grezzo di una sessione archiviata |
| `DELETE`| `/api/v1/saved-sessions/{file}` | Sessioni | Eliminazione permanente di una sessione archiviata |
| `POST` | `/api/v1/saved-sessions/{file}/restore` | Sessioni | Ripristino istantaneo di una sessione salvata nello stato attivo |
| `POST` | `/api/v1/sessions/diff` | Intelligence | Confronto analitico deterministico Baseline vs Collaudo corrente |
| `POST` | `/api/v1/maps/import` | Mappe | Importazione mappe punti/registri compatibili BACS Help |
| `GET` | `/api/v1/maps/export` | Mappe | Esportazione consolidata delle mappe registri caricate |
| `GET` | `/api/v1/maps/{slave_id}` | Mappe | Ritorna l'elenco dei punti mappati per lo slave specificato |
| `GET` | `/api/v1/report/pdf` | Report | Generazione e download verbale collaudo in PDF vettoriale |
| `GET` | `/api/v1/report/excel` | Report | Generazione e download cartella as-built in formato Excel a 8 fogli |
| `WS` | `/api/v1/ws` | Live Stream | Telemetria real-time (progressi scan, dispositivi, bus health, log) |

---

## 11. Mappa Topologica Interattiva (Network Graph)
La vista **Mappa Topologica** fornisce una rappresentazione grafica immediata dell'infrastruttura d'impianto rilevata, evidenziando le relazioni tra canali fisici (bus seriale RS485, schede di rete Ethernet), router BBMD e periferiche di campo.

### Funzionalità dell'Engine Grafico SVG:
- **Albero Gerarchico d'Impianto:**
  - **Nodo Radice (Root):** Rappresenta l'host BHAM con l'indicazione della sessione attiva.
  - **Nodi Canale (Livello 1):** Linea seriale RS485 (porta, baudrate, parità) e Rete Ethernet (interfaccia, IP locale, subnet).
  - **Nodi Router BBMD:** Nodi intermedi di routing per dispositivi inter-VLAN.
  - **Nodi Dispositivo (Livello 2):** Periferiche scoperte con badge colorati per protocollo (Ciano=Modbus, Viola=BACnet, Arancione=KNX, Smeraldo=ARP) e contatori (registri mappati, oggetti BACnet).
- **Controlli HUD Flottanti:**
  - **Zoom In / Zoom Out (`+` / `-`):** Ingrandimento continuo o riduzione dell'area di lavoro (supportato anche tramite rotellina del mouse).
  - **Fit-to-Screen (Adatta Vista):** Ricalcola coordinate e scala per centrare l'intero grafo nell'area visibile.
  - **Orientamento Orizzontale / Verticale:** Commuta la disposizione dell'albero tra sviluppo orizzontale (da sinistra a destra) e verticale (dall'alto in basso).
  - **Filtro di Ricerca Live:** Evidenzia istantaneamente i nodi corrispondenti a nome, costruttore o indirizzo/slave ID, sfocando i nodi non pertinenti.
- **Node Quick Inspector (Drawer Laterale):**
  - Cliccando su qualsiasi nodo della mappa, si apre il pannello laterale con i dettagli completi del dispositivo (tipo, protocollo, indirizzo, vendor, canali/registri).
  - Include scorciatoie contestuali per aprire direttamente il **BACnet Object Explorer** o l'**Ispezione Slave Modbus**.
- **Esportazione Vettoriale SVG:**
  - Il pulsante **Esporta SVG** genera un file vettoriale `.svg` autonomo ad alta definizione, ideale per allegare lo schema as-built ai verbali di collaudo o presentazioni al cliente.

---

## 12. Intelligence & Session Diff ("Prima vs Dopo")
La funzionalità **Session Diff** consente di confrontare determinismo e precisione una sessione di collaudo archiviata (*Baseline* o stato "Prima") con la sessione di lavoro attiva (*Live State* o stato "Dopo") o tra due collaudi storicizzati differenti.

### Caratteristiche Principali:
- **Riconoscimento Entità Multi-Protocollo:**
  - Mappatura su base MAC per apparati Ethernet per discernere riassegnazioni DHCP da sostituzioni hardware reali.
  - Mappatura per Slave ID su Modbus con rilevamento variazioni baudrate, parità, latenza bus o registri.
  - Mappatura per Device Instance su BACnet con rilevamento cambi firmware, modello e oggetti.
  - Mappatura per Indirizzo Individuale su KNX.
- **Classificazione degli Stati di Variazione:**
  - 🟢 **ADDED:** Nuovo dispositivo rilevato sul campo non presente nella baseline.
  - 🔴 **REMOVED:** Dispositivo presente nella baseline ora spento, rimosso o irraggiungibile.
  - 🟡 **MODIFIED:** Dispositivo presente in entrambe ma con variazioni nei parametri (IP, firmware, canali).
  - ⚪ **UNCHANGED:** Dispositivo stabile e identico.
- **Interfaccia e Reportistica Diff:**
  - Modale interattivo `#diff-modal` con 4 card contatori, filtri a due livelli e confronto visivo (vecchi parametri sbarrati in rosso ➔ nuovi in verde).
  - Esportazione diretta del verbale differenziale in formato standard `.csv` e `.json`.

---

## 13. Attraversamento Router BBMD & Foreign Device BACnet/IP
Nelle reti BACS complesse con segmentazione di sicurezza (VLAN o subnet IP separate), i pacchetti UDP broadcast (Who-Is) non superano i router di layer 3.

### Soluzione BHAM:
- **Foreign Device Registration (Annex J):** BHAM si registra temporaneamente come *Foreign Device* presso il router BBMD di campo specificato, potendo così trasmettere Who-Is e ricevere risposte I-Am da controllori dislocati su altre sottoreti.
- **Ispezione Tabelle BDT & FDT:**
  - **Broadcast Distribution Table (BDT):** Rileva l'elenco dei router BBMD peer configurati per l'instradamento broadcast inter-subnet.
  - **Foreign Device Table (FDT):** Mostra l'elenco dei dispositivi remoti registrati, le rispettive porte, il TTL assegnato e il conto alla rovescia dei secondi rimanenti.
- **Topologia di Rete Trasparente:** I dispositivi raggiunti attraverso un router vengono contrassegnati con il badge **BBMD** e raggruppati gerarchicamente sotto il nodo router corrispondente nella Mappa Topologica.

---

## 14. Banco Prova Operativo di Campo ("Field Operational Tools") & Override
La versione 0.8.0 introduce la suite **Field Tools ("Banco Prova & Override")**, concepita per consentire al collaudatore di verificare attuatori, pompe, valvole e sonde direttamente dall'interfaccia o tramite API, senza ricorrere a software di terze parti o disconnettere il bus.

### 14.1 Modbus Quick Commander
Permette la lettura puntuale e la scrittura rapida di singoli registri o blocchi continui sia su linea fisica (RTU/TCP) sia su impianto simulato.
- **Funzioni di Lettura Supportate:**
  - `FC01 Read Coils` (0x)
  - `FC02 Read Discrete Inputs` (1x)
  - `FC03 Read Holding Registers` (4x)
  - `FC04 Read Input Registers` (3x)
- **Funzioni di Scrittura Supportate:**
  - `FC05 Write Single Coil`
  - `FC06 Write Single Register`
  - `FC15 Write Multiple Coils`
  - `FC16 Write Multiple Registers`
- **Tipi di Dato & Decodifica Scientifica:**
  - `UInt16` (Decimale non segnato 0..65535)
  - `Int16` (Decimale con segno -32768..32767)
  - `Float32 Big-Endian` (IEEE 754 standard MSW:LSW)
  - `Float32 Little-Endian` (IEEE 754 word-swapped LSW:MSW)
  - `Hex Raw` (Notazione esadecimale es. `0x1F40`)
  - `Boolean / Coils` (0 / 1 / true / false)
- **Accesso Operativo:**
  - Clicca sul pulsante **⚡ Strumenti di Campo** in testata oppure dal modale di ispezione slave Modbus nella tab **⚡ Comando Rapido**.
  - Risultati visualizzati in tempo reale con griglia sinottica decimale, esadecimale e float.

### 14.2 BACnet Point Commander & Priority Array
Consente il comando manuale immediato o l'override forzato su oggetti BACnet (`analogOutput`, `analogValue`, `binaryOutput`, `binaryValue`):
- **Gestione Priority Array (1..16):**
  - Conforme allo standard ANSI/ASHRAE 135.
  - Priorità predefinita per collaudo: **Priorità 8 (Manual Operator)**.
  - Supporto per priorità di emergenza (Priorità 1/2) o regolazione logica supervisore (Priorità 16).
- **Comando di Relinquish (Rilascio Priorità):**
  - Rilascia istantaneamente il comando al livello di priorità selezionato impostando `value = null`, permettendo al controllore locale o alla logica automatica di riprendere il controllo del campo.
- **Accesso Diretto:**
  - Dall'Object Explorer BACnet (`#bacnet-modal`), clicca sul pulsante **⚡ Override** accanto all'oggetto desiderato, seleziona la priorità (1..16), imposta il valore numerico o booleano e invia con feedback istantaneo.

---

## 15. Simulatore Virtuale d'Impianto ("Demo Mode") & Resilienza Hot-Plug
Per sessioni di formazione, collaudo logico offline o sviluppo in assenza di hardware di campo collegato, BHAM integra un motore di simulazione virtuale completo.

### 15.1 Virtual Plant Engine (Modalità Demo)
- **Attivazione Semplice:**
  - Da CLI: `python3 bham.py --demo`
  - Da variabile d'ambiente: `export BHAM_DEMO=1`
  - Da interfaccia: pulsante toggle **DEMO MODE** in testata.
  - Via API REST: `POST /api/v1/demo/toggle` (o `/api/v1/demo/enable`, `/api/v1/demo/disable`).
- **Dispositivi Virtuali Inclusi:**
  1. *Chiller di Centrale Frigo:* Modbus RTU Slave 1 (`/dev/ttyUSB0`), stato compressori, temperature mandata/ritorno, setpoint, pressione R410A.
  2. *Pompa Primaria Inverter:* Modbus RTU Slave 2 (`/dev/ttyUSB0`), modulazione frequenza (Hz), pressione differenziale (bar), portata idraulica (m³/h), potenza assorbita (kW).
  3. *Misuratore di Energia Trifase:* Modbus TCP Slave 1 (`192.168.1.50:502`), tensione concatenata/fase, corrente per fase, potenza attiva istantanea (kW), energia cumulativa (kWh).
  4. *Unità Trattamento Aria (UTA 01):* BACnet/IP Device ID 1001, 12 oggetti tra cui ventilatori mandata/ripresa con Priority Array, serrande aria esterna, sonde temperatura e allarmi gelo.
  5. *Regolatore VAV Uffici:* BACnet/IP Device ID 1002, 4 oggetti tra cui portata aria ambiente e posizione servocomando.
  6. *Infrastruttura KNXnet/IP:* Gateway DALI (`1.1.1`) e Termostato Touch Screen (`1.1.2`).
  7. *Host di Rete IP:* 5 nodi virtuali censiti tramite ARP passivo.
- **Telemetria Dinamica Real-Time:**
  - Il motore esegue un loop asincrono in background che oscilla realisticamente le variabili di processo (temperature sinusoidali, potenze, portate) con emissione di impulsi WebSocket periodici.

### 15.2 Resilienza Seriale Hardware & Hot-Plug Auto-Recovery
- **Tolleranza ai Guasti e Disconnessioni Fisiche:**
  - Protezione completa per disconnessioni accidentali del convertitore USB↔RS485 o sbalzi di massa su porta seriale.
  - Gli errori di livello kernel (`serial.SerialException`, `OSError: [Errno 5] Input/output error`, `[Errno 19] No such device`) vengono intercettati dal layer di supervisione senza causare crash del demone o perdita dello stato d'impianto.
  - L'evento WebSocket `hardware_disconnect` viene trasmesso istantaneamente all'interfaccia utente con notifica toast arancione non bloccante.
  - Polling intelligente in background: appena il dispositivo seriale viene ricollegato alla medesima porta (`/dev/ttyUSB0`), il canale viene ripristinato automaticamente, inviando l'evento `hardware_reconnect` e consentendo il proseguimento immediato del collaudo.
- **Live Log Viewer & Sistema Toast:**
  - Filtro multi-livello dei log di console (`ALL`, `DEBUG`, `INFO`, `WARN`, `ERROR`).
  - Ricerca testuale rapida con evidenziazione dei messaggi rilevanti.
  - Sistema di notifiche toast non invasive con icone semantiche e auto-chiusura temporizzata.

---

## 16. Libreria Profili Modbus Estesa & Gestione Profili Custom
Per eliminare la necessità di consultare manuali cartacei o file PDF dei produttori durante il collaudo in cantiere, BHAM include una ricca libreria integrata di strutture registri Modbus predefinite, arricchite con tipi di dato, fattori di scala, unità ingegneristiche e descrizioni dettagliate.

### 16.1 Profili Industriali Preconfigurati (Built-in)
- **Multimetri & Analizzatori di Rete:**
  - **ABB B23:** Tensione di fase/concatenata, Corrente, Potenza attiva (W), Energia attiva importata (kWh).
  - **Carlo Gavazzi EM24 & EM111:** Tensioni L-N/L-L, Correnti, Potenze di fase e trifase, Energia totale (kWh) e parziale.
  - **IME Nemo 96:** Tensioni, Correnti di linea, Frequenza di rete (Hz), Potenze e Cosφ.
  - **Schneider Electric Acti9 iEM3150 & PM5350:** Tensione, Corrente, Potenza attiva/reattiva, Frequenza e Contatori energetici bidirezionali.
  - **Siemens SENTRON PAC3200:** Tensioni di fase, Correnti, Potenza attiva (kW), Potenza apparente (kVA), Cosφ e Frequenza.
- **Contabilizzatori di Calore ed Energia / Misuratori di Portata:**
  - **Belimo Energy Valve (EV):** Portata volumetrica istantanea (l/s), Temperatura di mandata/ritorno (°C), Salto termico Delta-T (K), Potenza termica (kW) e Posizione valvola (%).
  - **Isoil ISOMAG:** Portata volumetrica (m³/h), Velocità di flusso (m/s) e Conteggio volume cumulato (m³).
  - **Diehl / Hydrometer Sharky 775 (H&A):** Energia termica cumulativa (MWh), Volume cumulativo (m³), Portata (m³/h), Potenza (kW) e Temperature mandata/ritorno.
  - **Emerson Rosemount 8712:** Portata volumetrica, Totalizzatore flusso volumetrico e Stato diagnostico sensore.
- **Attuatori & Regolatori HVAC:**
  - **Belimo Servocomandi Modbus (Rotativi e Lineari):** Posizione attuale (%), Setpoint comando (%), Coppia relativa, Allarmi e Ore di funzionamento.
  - **Trox VAV Compact:** Portata effettiva (m³/h), Portata nominale, Setpoint portata d'aria (%) e Posizione serranda (%).
  - **iSMA CONTROLLI Moduli I/O (B-4I4O):** 4 Ingressi Digitali/Contatori e 4 Uscite a Relè con forzatura e conteggio impulsi.
  - **Riello Caldaia Condexa Pro:** Temperatura mandata/ritorno caldaia, Modulazione bruciatore (%), Pressione circuito primario (bar) e Codici di blocco/allarme.
  - **Carel pCO (Controllore Programmabile):** Temperatura ambiente, Sonda umidità (%), Setpoint riscaldamento/raffrescamento, Stato ventilatore e allarmi generali.

### 16.2 Gestione Profili Personalizzati (Custom Profiles Manager)
L'integratore può creare nuovi profili o modificare quelli esistenti:
- **Creazione e Modifica:** Dalla finestra *Libreria Profili*, clicca su *➕ Nuovo Profilo Custom* per inserire nome costruttore, modello e definire la tabella registri (indirizzo, nome, formato, scala, unità, permessi R/W).
- **Importazione ed Esportazione JSON:** I profili personalizzati possono essere salvati in formato `.json`, scambiati tra colleghi o archiviati insieme alla commessa d'impianto.
- **Applica a Slave (Apply to Slave):** Con un solo clic (*⚡ Applica*), tutti i registri definiti nel profilo vengono associati allo Slave ID selezionato sul bus, popolando automaticamente la vista live dei registri e la Mappa Registri di BHAM.

---

## 17. Blocco Sicurezza Manovre (Safe Mode Interlock)
Nelle centrali termiche, sale CED o reparti ospedalieri critici, una manovra involontaria su un attuatore (es. chiusura serranda aria, stop pompa primaria o reset contatore) può causare interruzioni di servizio o danni fisici. BHAM implementa il sistema **Safe Mode Interlock** come barriera di protezione attiva.

### 17.1 Principio di Funzionamento
- **Bloccato per Default (Locked):** All'avvio del sistema, tutte le operazioni di scrittura su bus (Modbus FC05, FC06, FC15, FC16 e BACnet Point Override) sono rigorosamente inibite. Qualsiasi tentativo di scrittura genera un errore `403 Forbidden` (`SafeModeLockedError`).
- **Procedura di Sblocco Responsabile ("Arming"):** Per effettuare manovre di collaudo, il tecnico deve cliccare sul badge in testata e compilare:
  1. *Nome Operatore / Tecnico Responsabile:* Nome e cognome di chi esegue il test.
  2. *Commessa / Ordine di Lavoro:* Identificativo dell'impianto o del cantiere (es. `COMM-2026-OSPEDALE-01`).
  3. *Finestra Temporale di Sblocco:* Durata dell'autorizzazione (15, 30, 60 o 120 minuti).
- **Scadenza Automatica e Disarmo:** Un timer in tempo reale decrementa i secondi rimanenti. Al termine della finestra temporale o cliccando su *🔒 Blocca Immediatamente (Disarm)*, il sistema si riblocca automaticamente senza lasciare canali aperti.
- **Segnalazione Visiva Dinamica:**
  - *Stato Protetto:* Badge verde `🛡️ Safe Mode: ATTIVO` con bordo fisso.
  - *Stato Sbloccato:* Badge rosso con pulsazione dinamica e indicazione operatore e countdown rimanente.

---

## 18. Registro Manovre Certificato (Crash-Proof WAL & Chaining Crittografico SHA-256)
Quando un tecnico esegue una manovra sul campo (es. apertura valvola al 100% o cambio setpoint), è indispensabile garantire la non-ripudiabilità e la tracciabilità forense, anche qualora il computer si spenga improvvisamente, si verifichi un blackout o il cavo venga strappato durante la scrittura.

### 18.1 Write-Ahead Logging (WAL) & Flusso in Due Fasi
BHAM adotta il pattern di registrazione preventiva Write-Ahead Log:
1. **Registrazione Preventiva dell'Intento (Phase INTENT):** Prima di trasmettere qualsiasi pacchetto sul bus RS485 o sulla rete IP, BHAM scrive su disco (`audit_journal.jsonl`) un record contenente: identificativo univoco, timestamp ISO ad alta precisione, operatore, commessa, protocollo, slave target, registro/oggetto, valore richiesto e hash della riga precedente (`prev_hash`).
2. **Sincronizzazione Disco Forzata (`os.fsync`):** Il sistema forza il flush dei buffer del sistema operativo su disco fisico prima di inviare i byte sul cavo, garantendo che anche in caso di blackout immediato l'intenzione sia registrata in modo indelebile.
3. **Esecuzione Fisica sul Campo:** Il pacchetto viene inviato all'hardware.
4. **Registrazione del Risultato (Phase RESULT):** Al ritorno della risposta (o in caso di timeout/eccezione), viene scritto un secondo record con esito (`SUCCESS` o `FAILED`), latenza effettiva in millisecondi, codice eccezione e valore verificato letto a valle.

### 18.2 Catena Crittografica SHA-256 (Tamper-Evident)
- Ogni riga del giornale include l'hash SHA-256 del record precedente (`prev_hash`).
- L'hash dell'evento corrente (`entry_hash`) viene generato sui campi salienti concatenati con algoritmo `SHA-256`.
- Qualsiasi modifica manuale o manomissione successiva del file invalida la catena crittografica a partire dal blocco corrotto.
- L'endpoint `GET /api/v1/audit/verify` e il pulsante *Riverifica Integrità* eseguono una scansione forense dell'intero file verificando riga per riga la validità crittografica della sequenza.

### 18.3 Recupero Automatico Intenti Orfani (Crash Recovery)
Se il computer o il processo si arresta improvvisamente durante una scrittura (prima della registrazione del record di risultato), al riavvio successivo il motore analizza il file WAL, individua l'intento rimasto orfano e inserisce automaticamente un record di sistema `safe_mode_orphan_recovery` contrassegnato con `INTERRUPTED_BY_SHUTDOWN`.

### 18.4 Esportazione Certificata
Dal modale Registro Manovre è possibile scaricare l'intero giornale in formato JSON (`GET /api/v1/audit/export`) per allegarlo come allegato certificato al verbale di collaudo d'impianto.

---

## 19. Distribuzione Standalone (Portable vs Installer) & Firma Digitale SignPath
Per soddisfare le esigenze sia dei tecnici che utilizzano chiavette USB di collaudo (senza diritti di amministratore sui PC di cantiere), sia delle aziende che richiedono installazioni gestite con MSI/Setup certificato, BHAM offre un'architettura di distribuzione duale.

### 19.1 Architettura Percorsi Dinamici (`core/paths.py`)
BHAM rileva dinamicamente il contesto di esecuzione:
- **Modalità Portatile (Portable Mode):**
  - Riconosciuta tramite la presenza del file sentinella `portable.flag` nella cartella dell'eseguibile o tramite l'argomento `--portable`.
  - Tutte le cartelle operative (`sessions/`, `logs/`, `data/profiles/custom/`, file di configurazione e giornale audit) risiedono all'interno della cartella locale del programma (ideale per esecuzione diretta da pendrive USB).
- **Modalità Installata (Installed Mode):**
  - Quando installato tramite setup Windows o pacchetto Linux DEB, l'eseguibile risiede in una cartella di sistema in sola lettura (es. `C:\Program Files\BHAM` o `/usr/bin/bham`).
  - BHAM salva automaticamente tutti i dati utente, sessioni e audit nei percorsi standard di sistema:
    - *Windows:* `%LOCALAPPDATA%\BHAM\` (es. `C:\Users\<Utente>\AppData\Local\BHAM\`)
    - *Linux:* `~/.local/share/bham/`
- **Ambiente Bundled (PyInstaller Freeze):**
  - I profili built-in e i file statici del frontend vengono estratti in modo trasparente dal runtime congelato `sys._MEIPASS`.

### 19.2 Installer Windows Inno Setup (`installer/bham.iss`)
- Script di compilazione per Inno Setup 6:
  - Genera l'installer x64 `bham-setup-0.8.0.exe`.
  - Icona applicativa dedicata, creazione collegamenti nel Menu Start e sul Desktop.
  - Registrazione pulita nel Pannello di Controllo / App di Windows per una disinstallazione sicura senza file residui.

### 19.3 Integrazione Firma Digitale SignPath (Code Signing Windows)
Per prevenire gli avvisi bloccanti di Microsoft SmartScreen o falsi positivi degli antivirus sui laptop aziendali:
- La pipeline di CI/CD (`.github/workflows/release.yml`) integra l'azione ufficiale `SignPath/github-action-submit-signing-request@v2`.
- Sia l'eseguibile compilato `bham.exe` sia l'installer Inno Setup `bham-setup-0.8.0.exe` vengono sottomessi a SignPath per la firma crittografica con certificato attendibile prima della pubblicazione nella GitHub Release.

### 19.4 Firma Digitale Autonoma su Linux (GPG & dpkg-sig)
Mentre per Windows la firma è automatizzata con SignPath, per i pacchetti e rilasci Linux la firma crittografica viene gestita in piena autonomia tramite chiave GPG locale:
- **Script dedicato `./scripts/sign_linux.sh`:**
  - Esecuzione: `./scripts/sign_linux.sh` (chiave GPG predefinita) oppure `./scripts/sign_linux.sh <KEY_ID>`.
  - Calcola l'impronta crittografica SHA-256 di tutti i pacchetti generati (`bham_*.deb`, `bham-linux-x64.tar.gz`) producendo la tabella `SHA256SUMS`.
  - Firma in chiaro la tabella checksum generando `SHA256SUMS.asc`.
  - Crea firme staccate GPG ASCII-armored (`.deb.asc`, `.tar.gz.asc`) per ciascun archivio.
  - Se `dpkg-sig` è presente nel sistema, appone anche la firma interna al file binario `.deb`.
- **Verifica di autenticità per il cliente/committente:**
  ```bash
  gpg --verify SHA256SUMS.asc
  sha256sum --check SHA256SUMS
  ```



