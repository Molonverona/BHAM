/**
 * BHAM – Manual Content Data & Interactive Renderer
 * Provides complete field documentation in Italian, English, and Spanish.
 */

"use strict";

const MANUAL_DATA = {
  it: {
    chapters: [
      { id: "intro", title: "1. Introduzione & Quick Start" },
      { id: "modbus", title: "2. Modbus RTU & TCP (Scan Attivo)" },
      { id: "bacnet", title: "3. BACnet/IP Discovery" },
      { id: "knx", title: "4. KNXnet/IP Discovery" },
      { id: "serial_sniff", title: "5. Sniffer Seriale Passivo (RS485 Zero-TX)" },
      { id: "arp", title: "6. ARP Passive Sniffer" },
      { id: "maps", title: "7. Mappe Registri BACS Help" },
      { id: "troubleshoot", title: "8. Troubleshooting da Campo" },
      { id: "api", title: "9. REST API & Webhooks" }
    ],
    content: {
      intro: `
        <h3>1. Introduzione & Architettura BHAM</h3>
        <p><strong>BHAM (BACS Help Auto Mapper)</strong> è la piattaforma industriale ad alta precisione progettata per i tecnici di collaudo, integratori di sistemi BMS e commissioning engineer. Consente la ricognizione automatizzata, il censimento e la diagnostica multi-protocollo delle reti di automazione edificio.</p>
        
        <div class="bham-callout callout-info">
          <strong>Architettura Software:</strong>
          Backend asincrono Python 3.12 basato su FastAPI con broadcast real-time WebSocket (&lt;15ms) e interfaccia industriale Vanilla JS senza dipendenze pesanti, ottimizzata per laptop da cantiere.
        </div>

        <h4>Quick Start in 4 Passaggi:</h4>
        <ol style="padding-left: 20px; line-height: 1.8;">
          <li><strong>Collegamento Hardware:</strong> Connetti l'adattatore USB-RS485 (FTDI / CH340 / CP210x) al bus seriale e/o il cavo Ethernet alla rete BMS dell'impianto.</li>
          <li><strong>Configurazione Setup:</strong> Apri <em>Impostazioni &gt; Hardware & Porte</em> (o attendi l'auto-popup all'avvio). Clicca <em>Scansiona Porte</em> e <em>Scansiona NIC</em> per selezionare la porta seriale e la scheda di rete adeguate.</li>
          <li><strong>Avvio Collaudo:</strong> Clicca sul pulsante <strong>AVVIA SCAN RAPIDO</strong> in testata. Il motore eseguirà in sequenza automatica: Phase Zero Modbus RTU, Who-Is BACnet/IP, Multicast KNXnet/IP e Sniffing ARP L2.</li>
          <li><strong>Esportazione & Verbale:</strong> Al termine del collaudo, scarica il verbale ufficiale in formato <strong>PDF vettoriale</strong> o <strong>Foglio Excel</strong> multi-scheda dai pulsanti di esportazione.</li>
        </ol>
      `,
      modbus: `
        <h3>2. Modbus RTU (RS485) & Modbus TCP</h3>
        <p>Il protocollo Modbus opera secondo il modello Master-Slave (o Client-Server su TCP). BHAM implementa un motore RTU proprietario a 3 fasi progettato per azzerare i disturbi sul bus e velocizzare il collaudo.</p>

        <h4>Regole Fisiche di Cablaggio RS485:</h4>
        <ul>
          <li><strong>Topologia:</strong> Bus lineare a cascata (Daisy-Chain). Evitare diramazioni a stella superiori a 1 metro.</li>
          <li><strong>Polarità:</strong> Cavo twistato e schermato (STP). Morsetto A o D+ (non invertente), morsetto B o D- (invertente). Collegare sempre lo schermo a terra solo su un capo.</li>
          <li><strong>Terminazione di Linea:</strong> Applicare una resistenza di terminazione da <strong>120 Ω, 1/4W</strong> esattamente ai due estremi fisici del bus RS485 per sopprimere le riflessioni d'onda.</li>
        </ul>

        <h4>Algoritmo RTU in 3 Fasi di BHAM:</h4>
        <ol style="padding-left: 20px; line-height: 1.8;">
          <li><strong>Phase Zero (Ascolto Passivo Silenzioso):</strong> BHAM apre la porta seriale e ascolta il bus senza trasmettere per 1.5s per ogni baudrate. Un algoritmo CRC-16 puro Python analizza il flusso di byte grezzi: se rileva un frame valido, effettua il <em>LOCK</em> immediato dei parametri seriali senza disturbare la comunicazione in corso.</li>
          <li><strong>Early Exit (Sonda Sentinella):</strong> Se il bus è silenzioso, interroga gli Slave ID sentinella {1, 2, 10} a timeout conservativo (500ms). Al primo hit, blocca i parametri di comunicazione ed esclude tutte le combinazioni residue.</li>
          <li><strong>Full Sweep a Velocità Massima:</strong> Esegue la scansione di tutti gli ID richiesti (1-247) con client seriale persistente e timeout ridotto a 120ms (FAST_TIMEOUT).</li>
        </ol>

        <h4>Diagnostica FC43 (Read Device Identification - MEI 0x0E):</h4>
        <p>Permette di interrogare le periferiche Modbus che supportano l'estensione MEI (Modbus Encapsulated Interface) per ottenere in chiaro nome del costruttore, codice prodotto e versione firmware revision.</p>
      `,
      bacnet: `
        <h3>3. BACnet/IP Discovery</h3>
        <p>BACnet (Building Automation and Control networks - ANSI/ASHRAE 135) su IP opera su socket UDP broadcast standard (porta predefinita <code>47808 / 0xBAC0</code>).</p>

        <h4>Funzionamento del Motore BACnet di BHAM:</h4>
        <ul>
          <li><strong>Who-Is Globale:</strong> Invia un messaggio di Who-Is non vincolato in broadcast (255.255.255.255) sulla scheda di rete selezionata.</li>
          <li><strong>Raccolta I-Am Asincrona:</strong> Tutti i dispositivi compatibili (controllori DDC, quadri UTA, pompe, inverter, chiller) rispondono con un frame I-Am contenente il Device Object Instance ID univoco e l'indirizzo IP.</li>
          <li><strong>Arricchimento Telemetria (Read Property Batched):</strong> Un pool concorrente con semaforo interroga ciascun dispositivo individuato per estrarre:
            <ul>
              <li><code>vendor-identifier</code> e <code>vendor-name</code></li>
              <li><code>model-name</code> e <code>firmware-revision</code></li>
              <li><code>application-software-version</code></li>
              <li><code>object-list</code> (conteggio totale degli oggetti hardware analogici/binari configurati).</li>
            </ul>
          </li>
        </ul>

        <h4>Gestione Porte Speciali (BAC0..BACF &amp; Custom):</h4>
        <p>Nei sistemi BACnet/IP le porte UDP sono storicamente designate dalla serie esadecimale <code>0xBAC0</code> fino a <code>0xBACF</code> (porte da 47808 a 47823), impiegate per separare diverse reti virtuali BACnet sulla stessa LAN:</p>
        <ul>
          <li><strong>BAC0:</strong> Porta standard <code>47808</code> (rete BACnet primaria).</li>
          <li><strong>BAC1..BACF:</strong> Porte da <code>47809</code> a <code>47823</code> per reti secondarie, router virtuali o gateway proprietari.</li>
          <li><strong>Sintassi Supportata in BHAM:</strong> Simboli singoli (<code>BAC0</code>, <code>BAC1</code>), intervalli (<code>BAC0..BAC3</code>), elenchi separati da virgola (<code>BAC0, BAC1, 50000</code>) o porte intere personalizzate (es. <code>50000</code>).</li>
        </ul>

        <div class="bham-callout callout-info">
          <strong>Nota sulle sottoreti (BBMD):</strong> Per impianti con router IP tra sottoreti diverse, assicurarsi che il traffico broadcast UDP 47808 sia instradato tramite un BACnet Broadcast Management Device (BBMD).
        </div>
      `,
      knx: `
        <h3>4. KNXnet/IP Discovery</h3>
        <p>Il sottosistema KNXnet/IP di BHAM consente il censimento rapido di router, interfacce IP e gateway KNX installati sull'infrastruttura di rete dell'edificio.</p>

        <h4>Dettagli Tecnici del Protocollo:</h4>
        <ul>
          <li><strong>Multicast Core:</strong> Trasmissione di pacchetti <code>SEARCH_REQUEST</code> (Service Type <code>0x0201</code>) verso l'indirizzo multicast IANA riservato <code>224.0.23.12:3671</code>.</li>
          <li><strong>Fallback Broadcast:</strong> Invio simultaneo su <code>255.255.255.255:3671</code> per garantire la risposta di gateway e interfacce IP che operano con stack multicast disabilitato.</li>
          <li><strong>Decodifica DIB Device Info:</strong>
            <ul>
              <li><strong>Indirizzo Individuale KNX:</strong> Formattato nello standard a 16 bit <code>Area.Linea.Dispositivo</code> (es. <code>1.1.0</code> per accoppiatore di linea).</li>
              <li><strong>Friendly Device Name:</strong> Nome descrittivo memorizzato nella memoria del dispositivo (fino a 30 caratteri Latin-1).</li>
              <li><strong>Numero di Serie &amp; MAC:</strong> 6 byte serial number univoco e indirizzo fisico MAC del dispositivo.</li>
              <li><strong>Medium di Comunicazione:</strong> Rilevamento del tipo di bus collegato (TP1 twisted pair, IP ethernet, RF radiofrequenza, PL110 powerline).</li>
            </ul>
          </li>
        </ul>
      `,
      serial_sniff: `
        <h3>5. Sniffer Seriale Passivo (RS485 Zero-TX)</h3>
        <p>Nei collaudi su impianti in marcia, quando sul doppino RS485 è già presente un PLC Master attivo (Carel, Siemens, Johnson Controls, Honeywell, Schneider, ecc.), l'invio di query master attive causerebbe <strong>collisioni distruttive</strong>, timeout di regolazione e allarmi sui controllori dell'edificio.</p>

        <div class="bham-callout callout-info">
          <strong>Modalità Stealth (Zero-TX):</strong>
          Il modulo di ascolto passivo di BHAM apre la porta seriale in sola lettura hardware (TX disabilitato). Nessun impulso elettrico viene generato sul doppino RS485.
        </div>

        <h4>Funzionalità Principali:</h4>
        <ul>
          <li><strong>Auto-Baudrate &amp; Auto-Parità Silenzioso:</strong> Se i parametri della linea sono ignoti, campiona il flusso di dati grezzi agganciando automaticamente velocità da 9600 a 115200 baud e parità (None, Even, Odd) appena convalida frame conformi.</li>
          <li><strong>Dissettore Modbus RTU:</strong>
            <ul>
              <li>Distingue le <em>Query del Master</em> (M ➔ S) dalle <em>Risposte degli Slave</em> (S ➔ M).</li>
              <li>Decodifica registri e valori restituiti da FC01/FC02 (Coil/Input) e FC03/FC04 (Holding/Input Regs).</li>
              <li>Inserisce automaticamente i dispositivi scoperti nel catalogo Modbus con il tag <code>[SNIFFED]</code>.</li>
            </ul>
          </li>
          <li><strong>Dissettore BACnet MS-TP:</strong>
            <ul>
              <li>Riconosce il preambolo <code>0x55 0xFF</code> e valida l'Header CRC-8 (ASHRAE 135).</li>
              <li>Mappa istantaneamente l'anello dei <em>Token</em> (MAC 0..127) e i frame <em>Poll For Master</em> senza trasmettere un singolo byte.</li>
              <li>Valida il payload dati con CRC-16 (ISO-HDLC).</li>
            </ul>
          </li>
          <li><strong>Diagnostica Bus Health (Salute della Linea):</strong>
            <ul>
              <li><strong>Packet Error Rate (PER %):</strong> Percentuale di frame corrotti o con CRC errato. Un PER &lt; 1% indica una linea eccellente; un PER &gt; 5% segnala problemi fisici (cavi schermati non collegati, terminazione da 120 Ω assente o riflessioni d'onda).</li>
              <li><strong>Bus Load %:</strong> Percentuale stimata di saturazione del canale seriale.</li>
              <li><strong>Frame Rate (fps):</strong> Frequenza dei telegrammi transitanti sul bus.</li>
            </ul>
          </li>
          <li><strong>Live Frame Inspector:</strong> Nella colonna di destra della Web UI, il tab <em>RS485 Inspector</em> mostra il flusso di telegrammi decodificati in tempo reale con evidenziazione a colori per direzione, slave ID, codici funzione e stato CRC.</li>
        </ul>
      `,
      arp: `
        <h3>6. ARP Passive Sniffer &amp; Ricognizione L2</h3>
        <p>Lo sniffer ARP di BHAM è un modulo non intrusivo che ascolta il traffico di broadcast ARP sulla sottorete locale Ethernet senza trasmettere alcun pacchetto attivo.</p>

        <h4>Vantaggi Operativi:</h4>
        <ul>
          <li><strong>Invisibilità totale:</strong> Nessun allarme generato su firewall, IDS di impianto o switch gestiti industriali.</li>
          <li><strong>Risoluzione OUI Vendor:</strong> I primi 3 byte del MAC address vengono automaticamente decodificati per identificare costruttori hardware come Siemens, WAGO, Schneider Electric, Johnson Controls, Moxa, Phoenix Contact o Raspberry Pi.</li>
          <li><strong>Mappatura Host Non Annunciati:</strong> Identifica server BMS, pannelli HMI, convertitori seriali e PLC privi di protocolli di discovery abilitati.</li>
        </ul>
      `,
      maps: `
        <h3>7. Mappe Registri BACS Help &amp; Integrazione BMS</h3>
        <p>BHAM supporta l'importazione ed esportazione di mappe punti in formato JSON compatibile BACS Help. Questo permette di correlare gli Slave ID fisici con le tabelle di variabili ingegneristiche dell'impianto.</p>

        <h4>Struttura dei Punti Registro:</h4>
        <pre class="bham-code-block">{
  "slave_id": 1,
  "register": 100,
  "register_type": "holding",
  "label": "Temperatura Mandata",
  "unit": "°C",
  "scale": 0.1,
  "description": "Sonda PT1000 mandata batteria riscaldamento UTA-01"
}</pre>
        <p>È possibile importare definizioni multiple dal pannello <em>Impostazioni &gt; Mappe BACS Help</em> tramite copia-incolla o caricamento file JSON, e consultare i registri direttamente dal tasto <strong>Dettagli</strong> nella tabella Modbus.</p>
      `,
      troubleshoot: `
        <h3>8. Troubleshooting da Campo &amp; Errori Comuni</h3>
        
        <h4>1. Errore "Permission Denied" su porta seriale (/dev/ttyUSB0):</h4>
        <p>Su sistemi Linux la porta seriale richiede l'appartenenza dell'utente al gruppo di sistema dialout. Esegui nel terminale:</p>
        <pre class="bham-code-block">sudo usermod -a -G dialout $USER</pre>
        <p>Quindi disconnetti e riconnetti la chiavetta USB per applicare i permessi.</p>

        <h4>2. Timeout continuo su Modbus RTU:</h4>
        <ul>
          <li>Verifica l'inversione dei morsetti D+ (A) e D- (B). Numerosi costruttori invertono la nomenclatura standard.</li>
          <li>Accertati che lo schermo del cavo non sia collegato a terra su entrambi i capi (evita anelli di massa).</li>
          <li>Controlla che la resistenza di terminazione da 120 Ω sia presente solo alle estremità della linea.</li>
        </ul>

        <h4>3. Nessun dispositivo BACnet o KNX rilevato:</h4>
        <ul>
          <li>Verifica il firewall di sistema (aprire porta UDP 47808 per BACnet e UDP 3671 per KNX).</li>
          <li>Verifica che nel Setup sia stata selezionata la scheda di rete connessa fisicamente al segmento BACS e non una VPN o l'interfaccia Wi-Fi di navigazione.</li>
        </ul>

        <h4>4. Uso del pulsante ABORT SCAN:</h4>
        <p>Il pulsante rosso <strong>ABORT SCAN</strong> sticky in testata invia un segnale di stop immediato a tutti i worker. Rilascia istantaneamente il descrittore della porta seriale, prevenendo blocchi del driver UART o flood sul bus.</p>
      `,
      api: `
        <h3>9. Riferimento REST API &amp; Webhooks</h3>
        <p>Tutte le funzionalità di BHAM sono fruibili tramite API REST standard con documentazione OpenAPI interattiva disponibile su <a href="/docs" target="_blank" style="color:var(--bham-modbus)">/docs</a>.</p>

        <h4>Esempi di Chiamata Rapida via cURL:</h4>
        <p><strong>1. Avvio Scansione Modbus RTU:</strong></p>
        <pre class="bham-code-block">curl -X POST http://localhost:8765/api/v1/scan/modbus/rtu \\
  -H "Content-Type: application/json" \\
  -d '{"port": "/dev/ttyUSB0", "baudrates": [9600, 19200], "id_range": [1, 2, 3, 4, 5]}'</pre>

        <p><strong>2. Interrogazione Dispositivi Rilevati:</strong></p>
        <pre class="bham-code-block">curl http://localhost:8765/api/v1/devices/modbus
curl http://localhost:8765/api/v1/devices/bacnet
curl http://localhost:8765/api/v1/devices/knx</pre>

        <p><strong>3. Arresto d'Emergenza (Abort):</strong></p>
        <pre class="bham-code-block">curl -X POST http://localhost:8765/api/v1/scan/abort</pre>

        <p><strong>4. Ripristino Sessione Salvata:</strong></p>
        <pre class="bham-code-block">curl -X POST http://localhost:8765/api/v1/saved-sessions/20260927_103507_Test_Site.json/restore</pre>
      `
    }
  },

  en: {
    chapters: [
      { id: "intro", title: "1. Overview & Quick Start" },
      { id: "modbus", title: "2. Modbus RTU & TCP (Active Scan)" },
      { id: "bacnet", title: "3. BACnet/IP Discovery" },
      { id: "knx", title: "4. KNXnet/IP Discovery" },
      { id: "serial_sniff", title: "5. Passive Serial Sniffer (RS485 Zero-TX)" },
      { id: "arp", title: "6. ARP Passive Sniffer" },
      { id: "maps", title: "7. BACS Help Point Maps" },
      { id: "troubleshoot", title: "8. Field Troubleshooting" },
      { id: "api", title: "9. REST API & Webhooks" }
    ],
    content: {
      intro: `
        <h3>1. Overview & BHAM Architecture</h3>
        <p><strong>BHAM (BACS Help Auto Mapper)</strong> is an industrial-grade telemetry and field discovery tool tailored for BMS commissioning engineers, automation technicians, and building controls specialists. It automates inventory, enumeration, and diagnostics across multi-vendor networks.</p>
        
        <div class="bham-callout callout-info">
          <strong>Architecture:</strong>
          Python 3.12 async backend powered by FastAPI with sub-15ms WebSocket live telemetry streaming, and a zero-dependency lightweight Vanilla JS web client designed for field laptops and tablets.
        </div>

        <h4>4-Step Quick Start:</h4>
        <ol style="padding-left: 20px; line-height: 1.8;">
          <li><strong>Hardware Setup:</strong> Plug your USB-to-RS485 adapter (FTDI / CH340 / CP210x) into the serial bus and connect Ethernet to the BMS network switch.</li>
          <li><strong>Configure Settings:</strong> Open <em>Settings &gt; Hardware & Ports</em> (or follow the auto-popup on first load). Click <em>Scan Ports</em> and <em>Scan NICs</em> to pick the right interfaces.</li>
          <li><strong>Run Discovery:</strong> Click <strong>START RAPID SCAN</strong> in the top header. The pipeline sequentially triggers: Modbus RTU Phase Zero, BACnet/IP Who-Is, KNXnet/IP Multicast, and ARP L2 sniffing.</li>
          <li><strong>Export Official Report:</strong> Download commissioning verifications directly as a <strong>Vector PDF</strong> or structured multi-sheet <strong>Excel workbook</strong>.</li>
        </ol>
      `,
      modbus: `
        <h3>2. Modbus RTU (RS485) & Modbus TCP</h3>
        <p>BHAM features a specialized 3-stage RTU discovery engine engineered to avoid bus contention and maximize scan throughput.</p>

        <h4>Physical RS485 Wiring Rules:</h4>
        <ul>
          <li><strong>Topology:</strong> Strict daisy-chain bus. Avoid star branches longer than 1 meter.</li>
          <li><strong>Polarity:</strong> Shielded twisted pair (STP). Wire non-inverting to A (D+) and inverting to B (D-). Ground shield on one end only.</li>
          <li><strong>Line Termination:</strong> Install a <strong>120 Ω, 1/4W resistor</strong> across the bus lines at both physical ends of the line to prevent wave reflections.</li>
        </ul>

        <h4>BHAM 3-Stage Discovery Pipeline:</h4>
        <ol style="padding-left: 20px; line-height: 1.8;">
          <li><strong>Phase Zero (Silent Auto-Baud Listener):</strong> Listens silently without transmitting for 1.5s per baudrate. Pure Python CRC-16 validates frames to LOCK baudrate without disturbing ongoing communications.</li>
          <li><strong>Early Exit (Sentinel Probe):</strong> If silent, probes sentinel slave IDs {1, 2, 10} at 500ms timeout. First hit LOCKS communication parameters and skips remaining permutations.</li>
          <li><strong>Full Sweep:</strong> Sweeps remaining IDs with persistent serial connection and fast 120ms timeout.</li>
        </ol>

        <h4>FC43 Device Identification (MEI 0x0E):</h4>
        <p>Queries supporting Modbus slaves for manufacturer name, model product code, and major/minor firmware revisions.</p>
      `,
      bacnet: `
        <h3>3. BACnet/IP Discovery</h3>
        <p>BACnet over IP operates over UDP broadcast on port <code>47808 (0xBAC0)</code>.</p>

        <h4>How BHAM Discovers BACnet Devices:</h4>
        <ul>
          <li><strong>Global Who-Is:</strong> Broadcasts an unconstrained Who-Is frame (255.255.255.255) on the selected network adapter.</li>
          <li><strong>I-Am Handler:</strong> Controllers, AHUs, pumps, chillers, and VAV boxes reply with their unique Device Object ID and IP address.</li>
          <li><strong>Telemetry Enrichment (Batched Read Property):</strong> Reads essential diagnostic device object properties:
            <ul>
              <li><code>vendor-identifier</code> and <code>vendor-name</code></li>
              <li><code>model-name</code> and <code>firmware-revision</code></li>
              <li><code>application-software-version</code></li>
              <li><code>object-list</code> (total configured input/output objects count).</li>
            </ul>
          </li>
        </ul>

        <h4>Special Ports Management (BAC0..BACF &amp; Custom):</h4>
        <p>In BACnet/IP environments, UDP ports are designated by the hex series <code>0xBAC0</code> to <code>0xBACF</code> (ports 47808 to 47823), commonly used to partition distinct virtual BACnet networks on the same IP subnet:</p>
        <ul>
          <li><strong>BAC0:</strong> Standard port <code>47808</code> (primary BACnet network).</li>
          <li><strong>BAC1..BACF:</strong> Ports <code>47809</code> to <code>47823</code> for secondary networks, virtual routers, or proprietary gateways.</li>
          <li><strong>Supported Syntax in BHAM:</strong> Single symbols (<code>BAC0</code>, <code>BAC1</code>), ranges (<code>BAC0..BAC3</code>), comma-separated lists (<code>BAC0, BAC1, 50000</code>), or custom integer ports (e.g. <code>50000</code>).</li>
        </ul>
      `,
      knx: `
        <h3>4. KNXnet/IP Discovery</h3>
        <p>Enables instantaneous enumeration of KNX routers, IP interfaces, and gateways across building LANs.</p>

        <h4>Protocol Details:</h4>
        <ul>
          <li><strong>Multicast SEARCH_REQUEST:</strong> Sends Service Type <code>0x0201</code> to standard multicast group <code>224.0.23.12:3671</code>.</li>
          <li><strong>Broadcast Fallback:</strong> Simultaneously broadcasts to <code>255.255.255.255:3671</code> for gateways with multicast filtering enabled.</li>
          <li><strong>DIB Device Info Decoding:</strong>
            <ul>
              <li><strong>Individual Address:</strong> Formatted in standard 16-bit <code>Area.Line.Device</code> notation (e.g. <code>1.1.0</code>).</li>
              <li><strong>Device Friendly Name:</strong> Up to 30 characters Latin-1 device identifier string.</li>
              <li><strong>Serial Number &amp; MAC:</strong> 6-byte hex hardware serial and MAC address.</li>
              <li><strong>Medium Type:</strong> Reports bus medium (TP1 twisted pair, IP ethernet, RF wireless, PL110 powerline).</li>
            </ul>
          </li>
        </ul>
      `,
      serial_sniff: `
        <h3>5. Passive Serial Sniffer (RS485 Zero-TX)</h3>
        <p>During commissioning of active plants where a PLC Master is already operating (Carel, Siemens, Johnson Controls, Honeywell, Schneider, etc.), transmitting active master requests causes <strong>destructive bus collisions</strong>, control loop timeouts, and system fault trips.</p>

        <div class="bham-callout callout-info">
          <strong>Stealth Mode (Zero-TX):</strong>
          BHAM's passive serial engine opens the serial UART port in hardware read-only mode (TX disabled). Not a single electrical pulse is injected onto the RS485 bus.
        </div>

        <h4>Key Capabilities:</h4>
        <ul>
          <li><strong>Silent Auto-Baud &amp; Auto-Parity Lock:</strong> Continuously samples line traffic, automatically locking onto baud rates (9600..115200) and parity (None, Even, Odd) upon validating standard CRC frames.</li>
          <li><strong>Modbus RTU Frame Dissector:</strong>
            <ul>
              <li>Distinguishes <em>Master Queries</em> (M ➔ S) from <em>Slave Responses</em> (S ➔ M).</li>
              <li>Decodes registers and numerical values returned by FC01/FC02 (Coils/Inputs) and FC03/FC04 (Holding/Input Regs).</li>
              <li>Automatically enrolls discovered nodes into the Modbus device inventory tagged as <code>[SNIFFED]</code>.</li>
            </ul>
          </li>
          <li><strong>BACnet MS-TP Engine:</strong>
            <ul>
              <li>Detects frame preamble <code>0x55 0xFF</code> and validates Header CRC-8 (ASHRAE 135 standard).</li>
              <li>Maps active Master MAC addresses (0..127) and Poll For Master frames without injecting packets.</li>
              <li>Validates data payloads using ISO-HDLC CRC-16.</li>
            </ul>
          </li>
          <li><strong>Bus Health Telemetry:</strong>
            <ul>
              <li><strong>Packet Error Rate (PER %):</strong> Ratio of corrupted or invalid CRC frames. PER &lt; 1% indicates pristine bus health; PER &gt; 5% indicates severe physical layer issues (missing 120 Ω termination, reflections, ungrounded shields).</li>
              <li><strong>Bus Load %:</strong> Real-time estimation of bus bandwidth utilization.</li>
              <li><strong>Frame Rate (fps):</strong> Live telegram throughput.</li>
            </ul>
          </li>
          <li><strong>Live Frame Inspector:</strong> The <em>RS485 Inspector</em> tab in the right column displays decoded telegrams in real time with direction markers, slave IDs/MACs, function codes, and CRC status.</li>
        </ul>
      `,
      arp: `
        <h3>6. ARP Passive Sniffer &amp; L2 Recon</h3>
        <p>Captures broadcast ARP frames passively on the local subnet without transmitting any probe packets.</p>

        <h4>Key Benefits:</h4>
        <ul>
          <li><strong>Completely stealth:</strong> Will not trigger enterprise IDS or network security alarms.</li>
          <li><strong>OUI Vendor Lookup:</strong> Identifies industrial automation hardware makers (Siemens, Johnson Controls, WAGO, Schneider, Phoenix Contact, Moxa, Raspberry Pi).</li>
          <li><strong>Silent Host Enumeration:</strong> Discovers PLCs, panels, and gateways that do not respond to ping or discovery protocols.</li>
        </ul>
      `,
      maps: `
        <h3>7. BACS Help Point Maps &amp; BMS Integration</h3>
        <p>Correlate discovered Modbus slave IDs with engineering points and register tables using standard BACS Help JSON format.</p>

        <h4>Point Schema Example:</h4>
        <pre class="bham-code-block">{
  "slave_id": 1,
  "register": 100,
  "register_type": "holding",
  "label": "Discharge Air Temp",
  "unit": "°C",
  "scale": 0.1,
  "description": "AHU-01 Heating Coil Discharge Sensor"
}</pre>
        <p>Import and export point maps under <em>Settings &gt; BACS Help Maps</em>. View live points by clicking <strong>Details</strong> on any Modbus device row.</p>
      `,
      troubleshoot: `
        <h3>8. Field Troubleshooting &amp; FAQ</h3>
        
        <h4>1. "Permission Denied" on serial port (/dev/ttyUSB0):</h4>
        <p>Ensure your user is in the Linux dialout group:</p>
        <pre class="bham-code-block">sudo usermod -a -G dialout $USER</pre>
        <p>Then unplug and re-plug your USB converter.</p>

        <h4>2. Continuous Modbus RTU Timeouts:</h4>
        <ul>
          <li>Swap D+ (A) and D- (B) wires; polarity conventions often vary between vendors.</li>
          <li>Check that the shield is grounded at only one point to avoid ground loops.</li>
          <li>Verify 120 Ω termination resistors are placed only at the two extremities of the bus.</li>
        </ul>

        <h4>3. Missing BACnet / KNX Devices:</h4>
        <ul>
          <li>Ensure host firewall allows incoming UDP 47808 (BACnet) and UDP 3671 (KNX).</li>
          <li>Make sure the selected network interface in Settings matches the physical Ethernet connection.</li>
        </ul>

        <h4>4. Emergency Abort:</h4>
        <p>The high-contrast red <strong>ABORT SCAN</strong> button halts all active threads immediately and releases serial port file handles.</p>
      `,
      api: `
        <h3>9. REST API &amp; Webhooks Reference</h3>
        <p>All functionality can be automated via REST endpoints. Interactive Swagger documentation is available at <a href="/docs" target="_blank" style="color:var(--bham-modbus)">/docs</a>.</p>

        <h4>cURL Quick Recipes:</h4>
        <p><strong>1. Start Modbus RTU Scan:</strong></p>
        <pre class="bham-code-block">curl -X POST http://localhost:8765/api/v1/scan/modbus/rtu \\
  -H "Content-Type: application/json" \\
  -d '{"port": "/dev/ttyUSB0", "baudrates": [9600, 19200], "id_range": [1, 2, 3]}'</pre>

        <p><strong>2. Query Discovered Inventory:</strong></p>
        <pre class="bham-code-block">curl http://localhost:8765/api/v1/devices/modbus
curl http://localhost:8765/api/v1/devices/bacnet
curl http://localhost:8765/api/v1/devices/knx</pre>

        <p><strong>3. Emergency Abort:</strong></p>
        <pre class="bham-code-block">curl -X POST http://localhost:8765/api/v1/scan/abort</pre>
      `
    }
  },

  es: {
    chapters: [
      { id: "intro", title: "1. Descripción & Inicio Rápido" },
      { id: "modbus", title: "2. Modbus RTU & TCP" },
      { id: "bacnet", title: "3. BACnet/IP Discovery" },
      { id: "knx", title: "4. KNXnet/IP Discovery" },
      { id: "serial_sniff", title: "5. Sniffer Pasivo Serie (RS485 Zero-TX)" },
      { id: "arp", title: "6. Sniffer Pasivo ARP" },
      { id: "maps", title: "7. Mapas BACS Help" },
      { id: "troubleshoot", title: "8. Resolución de Problemas" },
      { id: "api", title: "9. REST API & Webhooks" }
    ],
    content: {
      intro: `
        <h3>1. Descripción y Arquitectura BHAM</h3>
        <p><strong>BHAM (BACS Help Auto Mapper)</strong> es la plataforma de telemetría industrial diseñada para técnicos de puesta en marcha, integradores BMS e ingenieros de automatización de edificios.</p>

        <div class="bham-callout callout-info">
          <strong>Arquitectura:</strong>
          Backend asíncrono Python 3.12 con FastAPI y transmisión en tiempo real por WebSocket (&lt;15ms). Interfaz táctica Vanilla JS optimizada para portátiles de campo.
        </div>

        <h4>Inicio Rápido en 4 Pasos:</h4>
        <ol style="padding-left: 20px; line-height: 1.8;">
          <li><strong>Conexión Hardware:</strong> Conecte el convertidor USB-RS485 al bus serie y el cable Ethernet a la red BMS.</li>
          <li><strong>Configuración:</strong> Abra <em>Configuración &gt; Hardware y Puertos</em>. Pulse <em>Escanear Puertos</em> y <em>Escanear NICs</em> para seleccionar las interfaces correctas.</li>
          <li><strong>Iniciar Escaneo:</strong> Pulse <strong>INICIAR ESCANEO RÁPIDO</strong>. Se ejecutarán en secuencia: Phase Zero Modbus RTU, Who-Is BACnet/IP, Multicast KNXnet/IP y ARP L2.</li>
          <li><strong>Exportar Informe:</strong> Descargue el acta de pruebas oficial en <strong>PDF vectorial</strong> o <strong>Excel</strong> multih hoja.</li>
        </ol>
      `,
      modbus: `
        <h3>2. Modbus RTU (RS485) &amp; Modbus TCP</h3>
        <p>Motor de escaneo RTU en 3 etapas optimizado para evitar colisiones y reducir al mínimo el tiempo de detección.</p>

        <h4>Reglas de Cableado Físico RS485:</h4>
        <ul>
          <li><strong>Topología:</strong> Conexión en cascada (Daisy-Chain). Evite derivaciones en estrella superiores a 1 metro.</li>
          <li><strong>Polaridad:</strong> Cable trenzado apantallado (STP). Polo no inversor A (D+) y polo inversor B (D-). Conecte la malla a tierra solo en un extremo.</li>
          <li><strong>Terminación de Línea:</strong> Instale una resistencia de <strong>120 Ω, 1/4W</strong> en los dos extremos físicos del bus para evitar reflexiones.</li>
        </ul>

        <h4>Algoritmo en 3 Fases de BHAM:</h4>
        <ol style="padding-left: 20px; line-height: 1.8;">
          <li><strong>Phase Zero (Escucha Pasiva Silenciosa):</strong> Escucha el tráfico sin transmitir durante 1.5s por baudrate. El CRC-16 bloquea los parámetros de inmediato si detecta tramas válidas.</li>
          <li><strong>Early Exit (Sondas Centinela):</strong> Prueba los IDs {1, 2, 10} con timeout de 500ms para identificar la configuración y descartar combinaciones fallidas.</li>
          <li><strong>Full Sweep:</strong> Escaneo completo del rango de IDs a alta velocidad con timeout reducido de 120ms.</li>
        </ol>
      `,
      bacnet: `
        <h3>3. BACnet/IP Discovery</h3>
        <p>BACnet sobre IP opera mediante difusión UDP en el puerto estándar <code>47808 (0xBAC0)</code>.</p>
        <ul>
          <li><strong>Who-Is Global:</strong> Emite difusión Who-Is para recibir respuestas I-Am de todos los controladores.</li>
          <li><strong>Lectura Concurrente de Propiedades:</strong> Obtiene fabricante, modelo, versión de firmware y conteo de objetos de entrada/salida.</li>
        </ul>

        <h4>Gestión de Puertos Especiales (BAC0..BACF y Custom):</h4>
        <p>En redes BACnet/IP los puertos UDP se designan mediante la serie hexadecimal <code>0xBAC0</code> a <code>0xBACF</code> (puertos 47808 a 47823), utilizados para separar diferentes redes virtuales BACnet en la misma subred IP:</p>
        <ul>
          <li><strong>BAC0:</strong> Puerto estándar <code>47808</code> (red BACnet principal).</li>
          <li><strong>BAC1..BACF:</strong> Puertos <code>47809</code> a <code>47823</code> para redes secundarias, routers virtuales o pasarelas propietarias.</li>
          <li><strong>Sintaxis Compatible en BHAM:</strong> Símbolos individuales (<code>BAC0</code>, <code>BAC1</code>), rangos (<code>BAC0..BAC3</code>), listas separadas por coma (<code>BAC0, BAC1, 50000</code>) o puertos enteros personalizados (ej. <code>50000</code>).</li>
        </ul>
      `,
      knx: `
        <h3>4. KNXnet/IP Discovery</h3>
        <p>Detección inmediata de routers e interfaces IP KNX mediante multicast <code>224.0.23.12:3671</code> y difusión de respaldo <code>255.255.255.255:3671</code>.</p>
        <ul>
          <li><strong>Dirección Individual:</strong> Formateada en notación estándar <code>Área.Línea.Dispositivo</code> (ej. <code>1.1.0</code>).</li>
          <li><strong>DIB Info:</strong> Nombre del dispositivo, número de serie de 6 bytes, dirección MAC y medio físico (TP1, IP, RF, PL110).</li>
        </ul>
      `,
      serial_sniff: `
        <h3>5. Sniffer Pasivo Serie (RS485 Zero-TX / Stealth Mode)</h3>
        <p>En pruebas sobre instalaciones en marcha, cuando en el par trenzado RS485 ya opera un PLC Maestro activo (Carel, Siemens, Johnson Controls, Honeywell, Schneider, etc.), el envío de consultas maestras activas provocaría <strong>colisiones destructivas</strong>, tiempos de espera de regulación y alarmas en los controladores del edificio.</p>

        <div class="bham-callout callout-info">
          <strong>Modo Stealth (Zero-TX):</strong>
          El módulo de escucha pasiva de BHAM abre el puerto serie en modo de solo lectura por hardware (transmisión TX deshabilitada). No se genera ningún pulso eléctrico en el bus RS485.
        </div>

        <h4>Funcionalidades Principales:</h4>
        <ul>
          <li><strong>Auto-Baudrate y Auto-Paridad Silencioso:</strong> Si los parámetros del bus son desconocidos, muestrea el flujo de datos sin procesar sincronizando automáticamente velocidades de 9600 a 115200 baudios y paridad (None, Even, Odd) en cuanto valida tramas conformes.</li>
          <li><strong>Disector Modbus RTU:</strong>
            <ul>
              <li>Diferencia las <em>Consultas del Maestro</em> (M ➔ S) de las <em>Respuestas de los Esclavos</em> (S ➔ M).</li>
              <li>Decodifica registros y valores devueltos por FC01/FC02 (Coils/Inputs) y FC03/FC04 (Holding/Input Regs).</li>
              <li>Registra automáticamente los dispositivos descubiertos en el catálogo Modbus con la etiqueta <code>[SNIFFED]</code>.</li>
            </ul>
          </li>
          <li><strong>Disector BACnet MS-TP:</strong>
            <ul>
              <li>Reconoce el preámbulo <code>0x55 0xFF</code> y valida el Header CRC-8 (ASHRAE 135).</li>
              <li>Mapea al instante el anillo de <em>Tokens</em> (MAC 0..127) y tramas <em>Poll For Master</em> sin transmitir un solo byte.</li>
              <li>Valida el payload de datos con CRC-16 (ISO-HDLC).</li>
            </ul>
          </li>
          <li><strong>Diagnóstico Bus Health (Salud de la Línea):</strong>
            <ul>
              <li><strong>Packet Error Rate (PER %):</strong> Porcentaje de tramas corruptas o con CRC inválido. Un PER &lt; 1% indica una línea excelente; un PER &gt; 5% evidencia fallos físicos (cable apantallado sin conectar, resistencia de terminación de 120 Ω ausente o reflexiones de señal).</li>
              <li><strong>Bus Load %:</strong> Porcentaje estimado de saturación del canal serie.</li>
              <li><strong>Frame Rate (fps):</strong> Frecuencia de telegramas en tránsito por el bus.</li>
            </ul>
          </li>
          <li><strong>Live Frame Inspector:</strong> En la columna derecha de la Web UI, la pestaña <em>RS485 Inspector</em> muestra el flujo de telegramas decodificados en tiempo real con colores distintivos por dirección, Slave ID, código de función y verificación de CRC.</li>
        </ul>
      `,
      arp: `
        <h3>6. Sniffer Pasivo ARP</h3>
        <p>Captura pasiva de tramas ARP para inventariar dispositivos IP en la subred sin emitir paquetes activos, identificando fabricantes mediante base de datos OUI.</p>
      `,
      maps: `
        <h3>7. Mapas de Registros BACS Help</h3>
        <p>Importe y exporte definiciones de puntos Modbus (Holding, Input, Coils) en formato JSON para asociar descripciones y factores de escala a cada esclavo.</p>
      `,
      troubleshoot: `
        <h3>8. Resolución de Problemas y FAQ</h3>
        <h4>Permiso denegado en puerto serie (/dev/ttyUSB0):</h4>
        <pre class="bham-code-block">sudo usermod -a -G dialout $USER</pre>
        <p>Desconecte y vuelva a conectar el adaptador USB.</p>
        <h4>Botón ABORT SCAN:</h4>
        <p>Detiene de inmediato todas las rutinas de escaneo y libera el puerto serie de forma segura.</p>
      `,
      api: `
        <h3>9. REST API &amp; Webhooks</h3>
        <p>Documentación Swagger interactiva disponible en <a href="/docs" target="_blank" style="color:var(--bham-modbus)">/docs</a>.</p>
      `
    }
  }
};

let currentChapter = "intro";

function selectManualChapter(chapterId) {
  currentChapter = chapterId;
  renderManualContent();
}

function renderManualContent() {
  const lang = window.I18N?.currentLang || "it";
  const langData = MANUAL_DATA[lang] || MANUAL_DATA.it;

  // Render navigation menu
  const navEl = document.getElementById("manual-nav");
  if (navEl) {
    navEl.innerHTML = langData.chapters.map(ch => `
      <button class="bham-manual-nav-btn ${ch.id === currentChapter ? 'active' : ''}"
              onclick="selectManualChapter('${ch.id}')">
        ${ch.title}
      </button>
    `).join("");
  }

  // Render chapter body
  const bodyEl = document.getElementById("manual-body");
  if (bodyEl) {
    bodyEl.innerHTML = langData.content[currentChapter] || langData.content.intro;
  }
}

window.selectManualChapter = selectManualChapter;
window.renderManualContent = renderManualContent;
