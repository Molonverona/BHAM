# BHAM – BACS Help Auto Mapper
## Manuale Tecnico di Collaudo & Guida Operativa di Campo (v0.5.0)

---

## 1. Panoramica del Sistema & Architettura
**BHAM (BACS Help Auto Mapper)** è una piattaforma di collaudo industriale, ricognizione e diagnostica attiva/passiva progettata per impianti di automazione edificio (BACS / BMS).
Consente l'inventario rapido, l'identificazione hardware, l'arricchimento dei registri, la visualizzazione topologica e l'esportazione di verbali di collaudo per reti:
- **Modbus RTU (RS485)** (Scansione attiva, Smart Scan registri e Sniffing passivo Zero-TX)
- **Modbus TCP**
- **BACnet/IP & BACnet MS-TP** (Who-Is Discovery, Object Explorer e Sniffing passivo Zero-TX)
- **KNXnet/IP**
- **Sottoreti IP (ARP Passive Sniffer)**
- **Diagnostica Telemetrica Bus Health (RS485)**
- **Mappa Topologica d'Impianto Interattiva (Network Graph)**

### Architettura
- **Backend:** Python 3.12, FastAPI, WebSocket streaming a bassa latenza, protocolli nativi asincroni (`pymodbus`, `bacpypes3`, `scapy`).
- **Frontend:** Field Engineer Studio v4.2 in Vanilla JS ad alte prestazioni senza dipendenze esterne: architettura a 2 colonne (Sidebar Canali 360px + Workspace centrale con Switcher Vista Tabella/Topologia + Dock Diagnostico a scomparsa).
- **Mappa Topologica SVG:** Engine vettoriale nativo con calcolo gerarchico, Pan & Zoom continuo, fit-to-screen, orientamento H/V ed esportazione vettoriale .svg.
- **Reporting:** Generazione istantanea di verbali in formato **PDF Vettoriale a due passate (ReportLab)** e **Fogli Excel (openpyxl)** con fogli dedicati e metadati.
- **Internazionalizzazione (i18n):** Supporto completo e reattivo per **Italiano**, **Inglese** e **Spagnolo** (202 chiavi per lingua).

---

## 2. Guida Rapida di Avvio (Quick Start)
1. **Collegamento Periferiche:** Connetti l'adattatore USB↔RS485 al bus seriale e/o il cavo di rete Ethernet alla LAN BMS dell'edificio.
2. **Configurazione Hardware:** Clicca sull'icona **Impostazioni** (ingranaggio in alto a destra) ed entra nella scheda *Hardware & Porte*.
   - Clicca *Scansiona Porte* per rilevare convertitori RS485 FTDI, CH340, CP210x.
   - Clicca *Scansiona NIC* per selezionare l'interfaccia cablata associata alla sottorete dell'impianto.
   - Clicca *Applica Configurazione*.
3. **Avvio Scansione:** Clicca sul pulsante **AVVIA SCAN RAPIDO** in testata. Il sistema eseguirà automaticamente in cascata:
   - Modbus RTU Phase Zero + Early Exit
   - BACnet/IP Who-Is Broadcast
   - KNXnet/IP Discovery
   - ARP Passive Sniffer
4. **Visualizzazione & Esplorazione:**
   - Consulta le tabelle dispositivi per protocollo nel Workspace centrale.
   - Clicca su **Mappa Topologica** per osservare l'albero d'impianto interattivo con canali fisici e nodi.
   - Ispeziona gli oggetti BACnet con l'**Object Explorer** e mappa i registri Modbus con lo **Smart Scan**.
5. **Esportazione Verbale:** Scarica i risultati cliccando sui pulsanti **PDF**, **Excel** o esporta la mappa topologica in formato **SVG**.

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

## 10. Riferimento REST API
Documentazione Swagger interattiva su: `http://localhost:8765/docs`

| Metodo | Endpoint | Descrizione |
|---|---|---|
| `GET` | `/api/v1/health` | Stato del servizio e client WebSocket connessi |
| `GET` | `/api/v1/state` | Snapshot completo di tutti i dispositivi rilevati |
| `DELETE` | `/api/v1/state` | Reset memoria e azzeramento stato di collaudo |
| `GET` | `/api/v1/topology` | Modello topologico ad albero gerarchico d'impianto |
| `POST` | `/api/v1/scan/modbus/rtu` | Avvio scansione Modbus RTU seriale attiva |
| `POST` | `/api/v1/scan/modbus/tcp` | Avvio scansione Modbus TCP su elenco host |
| `POST` | `/api/v1/scan/modbus/smart-scan` | Smart Scan euristico registri slave Modbus |
| `POST` | `/api/v1/scan/serial/sniff` | Avvio ascolto passivo RS485 Zero-TX (Modbus RTU & BACnet MS-TP) |
| `GET` | `/api/v1/diag/serial/health` | Metriche Bus Health in tempo reale (PER %, FPS, Bus Load %, nodi attivi) |
| `POST` | `/api/v1/scan/bacnet/ip` | Avvio Who-Is broadcast BACnet/IP |
| `GET` | `/api/v1/scan/bacnet/device/{device_id}/objects` | Esplorazione completa oggetti dispositivo BACnet |
| `POST` | `/api/v1/scan/knx/ip` | Avvio discovery multicast KNXnet/IP |
| `POST` | `/api/v1/scan/arp` | Avvio sniffer promiscuo ARP L2 |
| `POST` | `/api/v1/scan/abort` | Arresto immediato di tutte le scansioni e sniffer |
| `POST` | `/api/v1/setup/configure` | Applicazione configurazione seriale e rete |
| `POST` | `/api/v1/saved-sessions/save` | Salvataggio sessione di collaudo su disco |
| `GET` | `/api/v1/saved-sessions/list` | Elenco delle sessioni archiviate |
| `POST` | `/api/v1/saved-sessions/{file}/restore` | Ripristino di una sessione archiviata nello stato attivo |
| `DELETE`| `/api/v1/saved-sessions/{file}` | Eliminazione di una sessione salvata |
| `GET` | `/api/v1/report/pdf` | Download diretto report di collaudo in PDF vettoriale |
| `GET` | `/api/v1/report/excel` | Download diretto report di collaudo in formato Excel |

---

## 11. Mappa Topologica Interattiva (Network Graph)
La vista **Mappa Topologica** fornisce una rappresentazione grafica immediata dell'infrastruttura d'impianto rilevata, evidenziando le relazioni tra canali fisici (bus seriale RS485, schede di rete Ethernet) e periferiche di campo.

### Funzionalità dell'Engine Grafico SVG:
- **Albero Gerarchico d'Impianto:**
  - **Nodo Radice (Root):** Rappresenta l'host BHAM con l'indicazione della sessione attiva.
  - **Nodi Canale (Livello 1):** Linea seriale RS485 (porta, baudrate, parità) e Rete Ethernet (interfaccia, IP locale, subnet).
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
