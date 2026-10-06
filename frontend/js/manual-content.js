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
      { id: "api", title: "9. REST & WebSocket API" },
      { id: "topology", title: "10. Mappa Topologica & Explorer" },
      { id: "diff", title: "11. Session Diff ('Prima vs Dopo')" },
      { id: "bbmd", title: "12. Attraversamento BBMD & Router BACnet" },
      { id: "selftest", title: "13. Self-Test Hardware & Accesso LAN" },
      { id: "field_tools", title: "14. Banco Prova Operativo & Override" },
      { id: "simulator", title: "15. Simulatore Virtuale & Resilienza" },
      { id: "profiles", title: "16. Libreria Profili Modbus Industriali" },
      { id: "safemode", title: "17. Blocco Sicurezza Manovre (Safe Mode)" },
      { id: "audit", title: "18. Registro Manovre Certificato (WAL)" },
      { id: "standalone", title: "19. Standalone (Portable/Install) & SignPath" },
      { id: "watch_list", title: "20. Live Watch List & Polling Registri" },
      { id: "rs485_benchmark", title: "21. RS485 Stress Test & Latency Benchmark" },
      { id: "bms_export_mobile", title: "22. BMS Tag Exporter & Accesso Mobile QR" }
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
          <strong>Attraversamento Router (BBMD) &amp; Foreign Device:</strong> Per impianti multisito o con router/VLAN intermedie che bloccano i broadcast UDP, inserisci l'IP del router BBMD nella sezione dedicata della card BACnet. BHAM effettuerà una registrazione <em>Foreign Device</em> (Annex J) per inoltrare ed acquisire telegrammi Who-Is/I-Am attraverso la subnet remota. Tramite il pulsante <strong>Tabelle BDT/FDT</strong> è possibile interrogare in sola lettura la Broadcast Distribution Table e la Foreign Device Table del router.
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
        <h3>9. Riferimento REST &amp; WebSocket API</h3>
        <p>BHAM espone oltre 39 endpoint RESTful con schemi Pydantic v2 e un canale streaming WebSocket per l'automazione industriale e l'integrazione di sistemi BMS terzi.</p>
        
        <div class="bham-callout callout-info" style="margin-bottom:14px;">
          <strong>Documentazione Interattiva &amp; Specifica Completa:</strong><br>
          • <strong>Swagger UI:</strong> <a href="/docs" target="_blank" style="color:var(--bham-modbus); font-weight:600;">/docs</a> &nbsp;|&nbsp;
          • <strong>ReDoc:</strong> <a href="/redoc" target="_blank" style="color:var(--bham-modbus); font-weight:600;">/redoc</a> &nbsp;|&nbsp;
          • <strong>Manuale Tecnico:</strong> Consulta il file <code>API_REFERENCE.md</code> alla radice del progetto per tutti i contratti JSON dettagliati.
        </div>

        <h4>Tabella Sintetica Endpoint:</h4>
        <div style="overflow-x:auto; margin-bottom:14px;">
          <table class="bham-data-table" style="font-size:12px; width:100%;">
            <thead>
              <tr><th>Metodo</th><th>Endpoint</th><th>Ambito</th><th>Descrizione</th></tr>
            </thead>
            <tbody>
              <tr><td><code>GET</code></td><td><code>/api/v1/health</code></td><td>Sistema</td><td>Stato del servizio, versione e client WebSocket attivi</td></tr>
              <tr><td><code>GET</code></td><td><code>/api/v1/state</code></td><td>Stato</td><td>Snapshot completo dei nodi e configurazione attiva</td></tr>
              <tr><td><code>GET</code></td><td><code>/api/v1/topology</code></td><td>Topologia</td><td>Albero gerarchico d'impianto vettoriale</td></tr>
              <tr><td><code>GET</code></td><td><code>/api/v1/hardware/self-test</code></td><td>Hardware</td><td>Collaudo rapido porte seriali, NIC e permessi OS</td></tr>
              <tr><td><code>POST</code></td><td><code>/api/v1/scan/modbus/rtu</code></td><td>Scan</td><td>Avvio sweep Modbus RTU seriale attivo (Phase Zero)</td></tr>
              <tr><td><code>POST</code></td><td><code>/api/v1/scan/modbus/tcp</code></td><td>Scan</td><td>Scansione Modbus TCP multi-porta su subnet</td></tr>
              <tr><td><code>POST</code></td><td><code>/api/v1/modbus/smart-scan</code></td><td>Modbus</td><td>Smart Scan euristico registri Holding/Input slave</td></tr>
              <tr><td><code>POST</code></td><td><code>/api/v1/scan/serial/sniff</code></td><td>Sniffer</td><td>Ascolto passivo RS485 Zero-TX e telemetria Bus Health</td></tr>
              <tr><td><code>GET</code></td><td><code>/api/v1/diag/serial/health</code></td><td>Diagnostica</td><td>Metriche fisiche linea RS485 (PER %, FPS, Bus Load %)</td></tr>
              <tr><td><code>POST</code></td><td><code>/api/v1/scan/bacnet/ip</code></td><td>Scan</td><td>Who-Is broadcast BACnet/IP e supporto Foreign Device</td></tr>
              <tr><td><code>GET/POST</code></td><td><code>/api/v1/bacnet/devices/{id}/objects</code></td><td>BACnet</td><td>Esplorazione approfondita gerarchica object-list</td></tr>
              <tr><td><code>GET</code></td><td><code>/api/v1/bacnet/bbmd/tables</code></td><td>BBMD</td><td>Lettura congiunta tabelle BDT ed FDT router BBMD</td></tr>
              <tr><td><code>POST</code></td><td><code>/api/v1/scan/knx/ip</code></td><td>Scan</td><td>Discovery multicast UDP KNXnet/IP</td></tr>
              <tr><td><code>POST</code></td><td><code>/api/v1/scan/arp</code></td><td>Scan</td><td>Sniffer promiscuo Layer-2 ARP</td></tr>
              <tr><td><code>POST</code></td><td><code>/api/v1/scan/abort</code></td><td>Controllo</td><td>Arresto d'emergenza immediato di tutte le scansioni</td></tr>
              <tr><td><code>POST</code></td><td><code>/api/v1/sessions/diff</code></td><td>Intelligence</td><td>Confronto analitico Baseline vs Collaudo corrente</td></tr>
              <tr><td><code>GET</code></td><td><code>/api/v1/report/pdf</code></td><td>Report</td><td>Download verbale di collaudo in PDF vettoriale</td></tr>
              <tr><td><code>GET</code></td><td><code>/api/v1/report/excel</code></td><td>Report</td><td>Download cartella as-built Excel a 8 fogli</td></tr>
            </tbody>
          </table>
        </div>

        <h4>Esempi Rapidi via cURL:</h4>
        <p><strong>1. Hardware Self-Test:</strong></p>
        <pre class="bham-code-block">curl -X GET http://localhost:8765/api/v1/hardware/self-test</pre>

        <p><strong>2. Avvio Scansione Modbus RTU:</strong></p>
        <pre class="bham-code-block">curl -X POST http://localhost:8765/api/v1/scan/modbus/rtu \\
  -H "Content-Type: application/json" \\
  -d '{"port": "/dev/ttyUSB0", "baudrates": [9600, 19200], "id_range": [1, 2, 3, 4, 5]}'</pre>

        <p><strong>3. Download Verbale Excel As-Built:</strong></p>
        <pre class="bham-code-block">curl -X GET http://localhost:8765/api/v1/report/excel -o collaudo_as_built.xlsx</pre>

        <h4>Canale WebSocket Live Telemetry:</h4>
        <p>Connessione: <code>ws://&lt;host&gt;:8765/api/v1/ws</code><br>
        Eventi trasmessi dal demone: <code>scan_progress</code>, <code>device_found</code>, <code>bus_health_update</code>, <code>log_record</code>.</p>
      `,
      topology: `
        <h3>10. Mappa Topologica Interattiva &amp; Explorer Avanzati</h3>
        <p>La <strong>Mappa Topologica</strong> (accessibile dallo switcher vista in alto a destra nel Workspace) trasforma l'inventario testuale in un albero vettoriale SVG dinamico, illustrando l'architettura di interconnessione fisica e logica dell'impianto BMS.</p>

        <h4>Gerarchia dell'Albero d'Impianto:</h4>
        <ul>
          <li><strong>Root (Host BHAM):</strong> Nodo centrale rappresentante la postazione di collaudo con l'indicazione della sessione attiva.</li>
          <li><strong>Canali Fisici:</strong> Ramo seriale RS485 (porta COM/ttyUSB, velocità baud, parità) e Ramo di rete Ethernet (interfaccia NIC, indirizzo IP, subnet).</li>
          <li><strong>Nodi Dispositivo:</strong> Periferiche scoperte collegate al rispettivo canale, con codice colore per protocollo (Ciano=Modbus, Viola=BACnet, Arancione=KNX, Smeraldo=ARP) e contatori integrati.</li>
        </ul>

        <h4>Controlli HUD e Navigazione:</h4>
        <ul>
          <li><strong>Pan &amp; Zoom:</strong> Trascina la mappa con il mouse per effettuare il pan. Usa i tasti <code>+</code> e <code>-</code> dell'HUD o la rotellina del mouse per lo zoom continuo.</li>
          <li><strong>Adatta Vista (Fit-to-Screen):</strong> Centra e ridimensiona l'intero albero per adattarlo automaticamente al viewport.</li>
          <li><strong>Orientamento:</strong> Commuta l'albero tra layout orizzontale (da sinistra a destra) e verticale (dall'alto in basso).</li>
          <li><strong>Filtro di Ricerca Live:</strong> Digita nel box di ricerca per evidenziare i nodi corrispondenti per nome, costruttore o ID/IP, attenuando gli altri.</li>
          <li><strong>Esporta SVG:</strong> Scarica il diagramma vettoriale <code>.svg</code> ad alta risoluzione per la documentazione finale d'impianto.</li>
        </ul>

        <h4>Quick Node Inspector &amp; Explorer:</h4>
        <p>Cliccando su un qualsiasi nodo della mappa si apre il cassetto laterale <em>Node Quick Inspector</em> con i metadati completi del dispositivo e pulsanti di accesso rapido:</p>
        <ul>
          <li><strong>BACnet Object Explorer:</strong> Naviga gerarchicamente tutti gli oggetti del dispositivo (AI, AO, AV, BI, BO, BV, MSI, MSO, Schedules, Trend Logs) con Present Value e Status Flags.</li>
          <li><strong>Ispezione Modbus &amp; Smart Scan:</strong> Esegue il sondaggio euristico dei registri standard con decodifica automatica in numeri interi, decimali float o stringhe.</li>
        </ul>
      `,
      diff: `
        <h3>11. Intelligence &amp; Session Diff ("Prima vs Dopo")</h3>
        <p>La funzionalità <strong>Session Diff</strong> consente di confrontare determinismo e precisione una sessione di collaudo archiviata (<em>Baseline</em> o stato "Prima") con la sessione di lavoro attiva (<em>Live State</em> o stato "Dopo") o tra due sessioni storiche differenti.</p>

        <h4>Caratteristiche del Motore Differenziale:</h4>
        <ul>
          <li><strong>Riconoscimento Multi-Protocollo:</strong> Correlazione su base MAC per host Ethernet, Slave ID per Modbus, Device Instance ID per BACnet e Indirizzo Fisico per KNX.</li>
          <li><strong>Classificazione delle Variazioni:</strong>
            <ul>
              <li><span class="badge" style="background:#22c55e; color:#000;">ADDED</span> Nuovo dispositivo rilevato in campo non presente nella baseline.</li>
              <li><span class="badge" style="background:#ef4444; color:#fff;">REMOVED</span> Dispositivo presente nella baseline ora spento, disconnesso o guasto.</li>
              <li><span class="badge" style="background:#eab308; color:#000;">MODIFIED</span> Dispositivo presente ma con parametri variati (IP, baudrate, firmware, latenza).</li>
              <li><span class="badge" style="background:#64748b; color:#fff;">UNCHANGED</span> Dispositivo stabile e identico.</li>
            </ul>
          </li>
          <li><strong>Visualizzazione Affiancata:</strong> Modale interattivo con vecchi parametri evidenziati in rosso sbarrato e nuovi valori in verde.</li>
          <li><strong>Esportazione Verbale Diff:</strong> Download immediato in formato standard <code>.csv</code> o <code>.json</code> per allegati di collaudo.</li>
        </ul>
      `,
      bbmd: `
        <h3>12. Attraversamento BBMD &amp; Router BACnet/IP</h3>
        <p>Nelle architetture d'automazione complesse distribuite su più VLAN o sottoreti di livello 3, i pacchetti Who-Is broadcast <code>255.255.255.255</code> non possono attraversare i router IP per limitazioni standard di rete.</p>

        <h4>Soluzione BHAM Annex J:</h4>
        <ul>
          <li><strong>Foreign Device Registration:</strong> BHAM si registra come <em>Foreign Device</em> presso il router BBMD di riferimento con un intervallo TTL (Time To Live, default 60s), instradando le interrogazioni Who-Is verso tutte le sottoreti collegate.</li>
          <li><strong>Ispezione Tabelle BDT &amp; FDT:</strong>
            <ul>
              <li><strong>Broadcast Distribution Table (BDT):</strong> Elenco dei router BBMD distribuiti nelle diverse sottoreti dell'edificio.</li>
              <li><strong>Foreign Device Table (FDT):</strong> Elenco degli apparati registrati con indirizzo IP, porta UDP, TTL concesso e countdown dei secondi rimanenti.</li>
            </ul>
          </li>
          <li><strong>Integrazione Grafica:</strong> I dispositivi scoperti attraverso un router vengono contrassegnati con il badge <code>BBMD</code> e collocati graficamente sotto il router corrispondente nella Mappa Topologica.</li>
        </ul>
      `,
      selftest: `
        <h3>13. Hardware Self-Test &amp; Accesso Remoto LAN</h3>
        <p>BHAM include strumenti avanzati di autodiagnostica hardware e supporto nativo per l'utilizzo da remoto sul campo.</p>

        <h4>⚡ Hardware Self-Test:</h4>
        <p>Accessibile dal Centro Impostazioni (<em>Adattatori &amp; Porte &gt; ⚡ Esegui Self-Test</em>) o via API <code>GET /api/v1/hardware/self-test</code>:</p>
        <ul>
          <li><strong>Porta Seriale RS485:</strong> Test reale di apertura, impostazione baudrate e chiusura socket seriale con calcolo della latenza in millisecondi.</li>
          <li><strong>Schede di Rete:</strong> Verifica instradamento verso il gateway predefinito e capacità di binding broadcast.</li>
          <li><strong>Permessi del Sistema Operativo:</strong> Verifica appartenenza al gruppo <code>dialout</code> (Linux), privilegi di Amministratore (Windows) e capacità di cattura pacchetti grezzi (<code>cap_net_raw</code> su Linux o Npcap su Windows).</li>
        </ul>

        <h4>🌐 Accesso Remoto da Tablet o PC (Rete LAN):</h4>
        <p>Quando BHAM viene avviato su un Raspberry Pi o mini-PC installato all'interno di un quadro elettrico:</p>
        <ul>
          <li>Il server si mette in ascolto su <code>0.0.0.0:8765</code> rendendo l'interfaccia accessibile da qualunque dispositivo sulla stessa rete locale.</li>
          <li>Gli indirizzi IP della LAN per l'accesso remoto vengono mostrati chiaramente nel Centro Impostazioni e nel log di avvio della console (es. <code>http://192.168.1.50:8765</code>).</li>
        </ul>
      `,
      field_tools: `
        <h3>14. Banco Prova Operativo di Campo ("Field Tools") &amp; Override</h3>
        <p>La suite <strong>Field Tools</strong> consente ai tecnici di collaudo di comandare attuatori, pompe e valvole o forzare letture puntuali direttamente da BHAM sia su bus reale che su impianto virtuale.</p>
        
        <h4>⚡ Modbus Quick Commander:</h4>
        <ul>
          <li><strong>Funzioni di Lettura:</strong> FC01 (Coils), FC02 (Discrete Inputs), FC03 (Holding Registers), FC04 (Input Registers).</li>
          <li><strong>Funzioni di Scrittura:</strong> FC05 (Single Coil), FC06 (Single Register), FC15 (Multiple Coils), FC16 (Multiple Registers).</li>
          <li><strong>Formati di Dato:</strong> UInt16, Int16 (signed), Float32 Big-Endian (MSW:LSW), Float32 Little-Endian (LSW:MSW), Hex grezzo, Booleani.</li>
          <li><strong>Accesso:</strong> Pulsante <em>⚡ Strumenti di Campo</em> in testata o tab <em>⚡ Comando Rapido</em> nell'ispezione slave Modbus.</li>
        </ul>

        <h4>⚡ BACnet Point Commander &amp; Priority Array:</h4>
        <ul>
          <li><strong>Override Manuale:</strong> Comando su oggetti <code>analogOutput</code>, <code>analogValue</code>, <code>binaryOutput</code>, <code>binaryValue</code> al livello di priorità selezionato (default <strong>Priorità 8 – Manual Operator</strong>).</li>
          <li><strong>Comando di Relinquish:</strong> Rilascio istantaneo della priorità (impostando valore nullo), consentendo alla logica automatica di riprendere il controllo.</li>
          <li><strong>Accesso:</strong> Pulsante <em>⚡ Override</em> accanto a ogni oggetto nell'Object Explorer BACnet.</li>
        </ul>
      `,
      simulator: `
        <h3>15. Simulatore Virtuale d'Impianto ("Demo Mode") &amp; Resilienza</h3>
        <p>BHAM include un motore di simulazione virtuale completo per verifiche offline, collaudi preliminari e dimostrazioni senza hardware reale.</p>

        <h4>🌱 Virtual Plant Engine (Demo Mode):</h4>
        <ul>
          <li><strong>Attivazione Rapida:</strong> Switch <em>DEMO MODE</em> in testata, flag CLI <code>--demo</code>, variabile <code>BHAM_DEMO=1</code> o endpoint REST <code>/api/v1/demo/toggle</code>.</li>
          <li><strong>Dispositivi Simulati:</strong> Chiller Climaveneta Modbus RTU, Pompa inverter Grundfos Modbus RTU, Power Meter Schneider PM5350 Modbus TCP, UTA 01 BACnet/IP con 12 oggetti, VAV Zone North BACnet/IP con 4 oggetti, Gateway e sensori KNX, nodi ARP di rete.</li>
          <li><strong>Telemetria Dinamica:</strong> Oscillazione in tempo reale di temperature, portate, frequenze e potenze con broadcast WebSocket.</li>
        </ul>

        <h4>🛡️ Resilienza Hardware &amp; Hot-Plug Auto-Recovery:</h4>
        <ul>
          <li><strong>Tolleranza alle Disconnessioni:</strong> Intercettazione trasparente di disconnessioni accidentali del convertitore USB↔RS485 senza crash del demone o perdita della sessione.</li>
          <li><strong>Auto-Recovery:</strong> Riconnessione automatica non appena la porta viene ripristinata e notifiche toast non bloccanti a video.</li>
          <li><strong>Console Log Potenziata:</strong> Filtraggio immediato per gravità (<code>ALL</code>, <code>DEBUG</code>, <code>INFO</code>, <code>WARN</code>, <code>ERROR</code>) e barra di ricerca rapida.</li>
        </ul>
      `,
      profiles: `
        <h3>16. Libreria Profili Modbus Industriali &amp; Custom Manager</h3>
        <p>BHAM include una ricca libreria integrata di profili Modbus predefiniti per eliminare la consultazione di manuali cartacei durante il collaudo in campo.</p>

        <h4>📚 Profili Industriali Inclusi:</h4>
        <ul>
          <li><strong>Multimetri:</strong> ABB B23, Carlo Gavazzi EM24 ed EM111, IME Nemo 96, Schneider Acti9 iEM3150 e PM5350, Siemens SENTRON PAC3200.</li>
          <li><strong>Contabilizzatori ed Energia:</strong> Belimo Energy Valve (EV), Isoil ISOMAG, Diehl/Hydrometer Sharky 775, Emerson Rosemount 8712.</li>
          <li><strong>Attuatori &amp; Regolatori HVAC:</strong> Belimo Servocomandi Modbus, Trox VAV Compact, iSMA-B-4I4O Modulo I/O, Riello Caldaia Condexa Pro, Carel pCO Controllore.</li>
        </ul>

        <h4>🛠️ Gestione Profili Custom:</h4>
        <ul>
          <li><strong>Creazione &amp; Modifica:</strong> Definizione rapida di costruttore, modello, registri con indirizzo, formato (UInt16, Float32, ecc.), scala e unità ingegneristiche.</li>
          <li><strong>Import / Export JSON:</strong> Salvataggio e condivisione dei profili personalizzati in formato JSON standard.</li>
          <li><strong>⚡ Applica a Slave:</strong> Assegnazione istantanea del profilo allo Slave ID selezionato con iniezione automatica nella Mappa Registri attiva.</li>
        </ul>
      `,
      safemode: `
        <h3>17. Blocco Sicurezza Manovre (Safe Mode Interlock)</h3>
        <p>Sistema di protezione attiva per impedire manovre e forzature accidentali su apparecchiature critiche di centrale e regolatori d'impianto.</p>

        <h4>🔒 Protezione Interbloccata:</h4>
        <ul>
          <li><strong>Blocco Predefinito:</strong> All'avvio tutte le manovre di scrittura (Modbus FC05/FC06/FC15/FC16 e BACnet Point Override) sono inibite con errore <code>403 Forbidden</code>.</li>
          <li><strong>Procedura di Sblocco ("Arm"):</strong> Richiede l'indicazione di Nome Tecnico/Operatore, Commessa/Ordine di lavoro e durata della finestra temporale (15, 30, 60 o 120 minuti).</li>
          <li><strong>Disarmo Automatico:</strong> Alla scadenza del timer o cliccando su <em>🔒 Blocca Immediatamente</em>, il sistema ripristina la protezione senza canali aperti.</li>
          <li><strong>Badge Visivo:</strong> Segnalazione verde protetta o rossa pulsante con operatore e conto alla rovescia in testata.</li>
        </ul>
      `,
      audit: `
        <h3>18. Registro Manovre Certificato (Crash-Proof WAL)</h3>
        <p>Tracciabilità forense indelebile di tutte le operazioni di collaudo con tecnologia Write-Ahead Log (WAL) e sigillo crittografico SHA-256.</p>

        <h4>🛡️ Caratteristiche del Registro:</h4>
        <ul>
          <li><strong>Registrazione Preventiva (Write-Ahead):</strong> Ogni intento di scrittura viene registrato su disco con <code>os.fsync</code> prima di trasmettere i dati sul cavo fisico.</li>
          <li><strong>Catena Crittografica SHA-256:</strong> Ogni voce include l'hash della riga precedente (<code>prev_hash</code>) calcolando una catena blockchain-style resistente a manomissioni.</li>
          <li><strong>Recupero Crash Automatico:</strong> Al riavvio dopo blackout o cadute di alimentazione, gli intenti rimasti orfani vengono individuati e contrassegnati automaticamente.</li>
          <li><strong>Verifica Integrità &amp; Export:</strong> Scansione riga per riga del giornale con rilevamento violazioni ed esportazione del verbale in JSON firmabile.</li>
        </ul>
      `,
      standalone: `
        <h3>19. Standalone (Portable/Install) &amp; Firma Digitale SignPath</h3>
        <p>BHAM supporta una distribuzione ibrida adatta sia all'esecuzione portatile da pendrive USB che all'installazione centralizzata su laptop aziendali.</p>

        <h4>📦 Modalità Operative (<code>core/paths.py</code>):</h4>
        <ul>
          <li><strong>Versione Portatile (Portable):</strong> Riconosce la presenza del file <code>portable.flag</code> e memorizza sessioni, log e profili direttamente nella cartella dell'eseguibile.</li>
          <li><strong>Versione Installata (Installed):</strong> Utilizza percorsi standard del sistema operativo (<code>%LOCALAPPDATA%\\BHAM</code> su Windows e <code>~/.local/share/bham</code> su Linux) per esecuzione sicura in sola lettura.</li>
          <li><strong>Firma Digitale Windows (SignPath):</strong> Integrazione CI/CD con <code>SignPath/github-action-submit-signing-request@v2</code> per la firma autenticata dei binari Windows.</li>
          <li><strong>Firma Digitale Autonoma Linux (GPG):</strong> Script <code>./scripts/sign_linux.sh</code> per la firma autonoma locale di <code>.deb</code>, <code>.tar.gz</code> e <code>SHA256SUMS.asc</code> con la propria chiave GPG.</li>
        </ul>
      `,
      watch_list: `
        <h3>20. Live Watch List &amp; Polling Registri</h3>
        <p>La <strong>Live Watch List</strong> consente il monitoraggio continuo in tempo reale di registri Modbus selezionati (Holding e Input Registers) durante le prove di taratura, il bilanciamento idronico o la diagnostica di anomalie dinamiche.</p>

        <h4>Funzionalità Principali:</h4>
        <ul>
          <li><strong>Aggiunta Rapida Punti:</strong> Inserimento diretto dei registri dalla tabella registri dello slave o dal modale di ispezione cliccando sull'icona dell'occhio <code>👁️</code>.</li>
          <li><strong>Intervallo di Polling Adattivo:</strong> Frequenza configurabile a <strong>500ms</strong>, <strong>1s</strong>, <strong>2s</strong> o <strong>5s</strong> con query Modbus mirata e non invasiva sul bus.</li>
          <li><strong>Evidenziazione Cromatica dei Delta:</strong> I valori che subiscono variazioni vengono evidenziati all'istante con transizioni cromatiche (verde per incremento, arancione per decremento/variazione), facilitando l'individuazione di fluttuazioni rapide.</li>
          <li><strong>Feedback Acustico (Web Audio Buzzer):</strong> Segnalatore sonoro sintetizzato via browser (Web Audio API) che emette un tono discreto ad ogni variazione di valore registrata, consentendo all'operatore di lavorare con le mani sul quadro elettrico senza dover fissare il monitor.</li>
          <li><strong>Esportazione Log CSV:</strong> Download con un click dell'intero storico dei campionamenti registrati con timestamp millisecondo, Slave ID, Indirizzo e Valore numerico per analisi trend in Excel.</li>
        </ul>
      `,
      rs485_benchmark: `
        <h3>21. RS485 Stress Test &amp; Latency Benchmark</h3>
        <p>Strumento diagnostico fisico del canale di trasmissione seriale RS485 per verificare la qualità della linea, l'assenza di riflessioni d'onda e la stabilità del baudrate prima del rilascio definitivo dell'impianto.</p>

        <h4>Parametri del Benchmark:</h4>
        <ul>
          <li><strong>Raffiche di Stress Calibrate:</strong> Invio di sequenze consecutive di richieste Modbus (50, 100 o 200 campioni) a frequenza controllata su nodi sentinella o attivi.</li>
          <li><strong>Metriche Misurate in Tempo Reale:</strong>
            <ul>
              <li><strong>Packet Error Rate (PER %):</strong> Percentuale di pacchetti persi o con timeout sul totale trasmesso.</li>
              <li><strong>Round-Trip Time (RTT):</strong> Latenza minima, media e massima espressa in millisecondi (ms).</li>
              <li><strong>Jitter di Trasmissione:</strong> Variazione statistica del tempo di risposta della linea fisica.</li>
              <li><strong>CRC Corrotti:</strong> Conteggio frame scartati per checksum errato (indice primario di disturbi elettromagnetici).</li>
            </ul>
          </li>
          <li><strong>Diagnostica Fisica Guidata:</strong> L'algoritmo analizza la distribuzione degli errori ed emette raccomandazioni immediate:
            <ul>
              <li><em>Jitter elevato / CRC Fail isolati:</em> Possibile assenza di terminazione di linea da 120 Ω su uno o entrambi i capi del bus.</li>
              <li><em>Timeout casuali distribuiti:</em> Possibili interferenze generate da inverter o cavi di potenza posati nello stesso canale.</li>
              <li><em>PER &gt; 50%:</em> Doppino troppo lungo per la velocità impostata o polarità A/B degradata.</li>
            </ul>
          </li>
          <li><strong>Baudrate Ottimale Consigliato:</strong> Suggerisce la velocità massima consigliata per garantire un PER &lt; 0.5% in servizio continuo.</li>
        </ul>
      `,
      bms_export_mobile: `
        <h3>22. BMS/SCADA Multi-Vendor Tag Exporter &amp; Accesso Mobile QR</h3>
        <p>BHAM accelera la fase di messa in servizio esportando l'inventario dei punti d'impianto direttamente nei formati nativi dei principali supervisori BMS di mercato e fornendo accesso mobile hands-free sul campo.</p>

        <h4>Esportatore Tag Multi-Vendor (<code>/api/v1/export/tags/{format}</code>):</h4>
        <ul>
          <li><strong>Tridium Niagara 4:</strong> Genera file XML conforme per l'importazione diretta nei driver Modbus Async Network e BACnet Device Points di Niagara Workbench, preservando tipi di punto, indirizzi e conversioni.</li>
          <li><strong>Siemens Desigo CC:</strong> File CSV strutturato secondo la gerarchia standard di importazione Desigo (Identifier, DP_Type, Address, Description, Engineering Units).</li>
          <li><strong>Schneider EcoStruxure Building Operation (EBO):</strong> Tabella CSV formattata per l'importazione massiva di Device e I/O points in EcoStruxure WorkStation.</li>
          <li><strong>BACnet CSV Universale:</strong> Tabella standard contenente Object Identifier, Object Name, Object Type, Present Value, Description e Engineering Units.</li>
        </ul>

        <h4>Accesso Mobile Hands-Free (QR Code LAN Pairing):</h4>
        <ul>
          <li><strong>Generazione Vettoriale SVG:</strong> Cliccando sul pulsante 📱 QR Code nella barra di stato o nel Centro Impostazioni, BHAM genera istantaneamente un QR Code vettoriale puro (senza dipendenze esterne o connessione Internet).</li>
          <li><strong>Riconoscimento IP LAN Automatico:</strong> Il QR Code codifica l'URL effettivo dell'interfaccia di rete selezionata (es. <code>http://192.168.1.50:8765</code>).</li>
          <li><strong>Puntamento Istantaneo da Tablet/Smartphone:</strong> Il tecnico inquadra il QR con la fotocamera del tablet da cantiere e si connette alla dashboard completa via Wi-Fi senza digitare indirizzi IP.</li>
          <li><strong>Sintesi Sonora Web Audio API:</strong> Notifiche e conferme vocali/sonore generate interamente nel browser senza necessità di cuffie cablate o file audio pesanti.</li>
        </ul>
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
      { id: "api", title: "9. REST & WebSocket API" },
      { id: "topology", title: "10. Topological Map & Explorer" },
      { id: "diff", title: "11. Session Diff ('Before vs After')" },
      { id: "bbmd", title: "12. BBMD Traversal & BACnet Routers" },
      { id: "selftest", title: "13. Hardware Self-Test & Remote LAN" },
      { id: "field_tools", title: "14. Field Operational Tools & Override" },
      { id: "simulator", title: "15. Virtual Plant Simulator & Resilience" },
      { id: "profiles", title: "16. Industrial Modbus Profiles Library" },
      { id: "safemode", title: "17. Safe Mode Interlock" },
      { id: "audit", title: "18. Crash-Proof Audit Journal (WAL)" },
      { id: "standalone", title: "19. Standalone Packaging & SignPath" },
      { id: "watch_list", title: "20. Live Watch List & Register Polling" },
      { id: "rs485_benchmark", title: "21. RS485 Stress Test & Latency Benchmark" },
      { id: "bms_export_mobile", title: "22. BMS Tag Exporter & Mobile QR LAN Access" }
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

        <div class="bham-callout callout-info">
          <strong>BBMD Router Traversal &amp; Foreign Device Registration:</strong> For multi-subnet facilities or VLAN networks blocking UDP broadcast forwarding, specify the BBMD router IP in the BACnet card drawer. BHAM performs an active <em>Foreign Device Registration</em> (Annex J) to route Who-Is and collect I-Am telegrams across distant subnets. Click <strong>BDT/FDT Tables</strong> to inspect the router's active Broadcast Distribution Table and registered Foreign Device Table in real-time.
        </div>
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
        <h3>9. REST &amp; WebSocket API Reference</h3>
        <p>BHAM provides 39+ RESTful endpoints with typed Pydantic v2 contracts and a live WebSocket streaming channel for commissioning automation and third-party BMS integration.</p>

        <div class="bham-callout callout-info" style="margin-bottom:14px;">
          <strong>Interactive Documentation &amp; Technical Reference:</strong><br>
          • <strong>Swagger UI:</strong> <a href="/docs" target="_blank" style="color:var(--bham-modbus); font-weight:600;">/docs</a> &nbsp;|&nbsp;
          • <strong>ReDoc:</strong> <a href="/redoc" target="_blank" style="color:var(--bham-modbus); font-weight:600;">/redoc</a> &nbsp;|&nbsp;
          • <strong>Technical Guide:</strong> Consult <code>API_REFERENCE.md</code> in the repository root for comprehensive payload contracts.
        </div>

        <h4>Endpoints Summary Table:</h4>
        <div style="overflow-x:auto; margin-bottom:14px;">
          <table class="bham-data-table" style="font-size:12px; width:100%;">
            <thead>
              <tr><th>Method</th><th>Endpoint</th><th>Domain</th><th>Description</th></tr>
            </thead>
            <tbody>
              <tr><td><code>GET</code></td><td><code>/api/v1/health</code></td><td>System</td><td>Daemon operational status, version, and active WS clients</td></tr>
              <tr><td><code>GET</code></td><td><code>/api/v1/state</code></td><td>State</td><td>Complete snapshot of active discovered devices and config</td></tr>
              <tr><td><code>GET</code></td><td><code>/api/v1/topology</code></td><td>Topology</td><td>Hierarchical plant topology vector graph</td></tr>
              <tr><td><code>GET</code></td><td><code>/api/v1/hardware/self-test</code></td><td>Hardware</td><td>Automated check of serial ports, NICs, and OS permissions</td></tr>
              <tr><td><code>POST</code></td><td><code>/api/v1/scan/modbus/rtu</code></td><td>Scan</td><td>Start active Modbus RTU serial sweep (Phase Zero)</td></tr>
              <tr><td><code>POST</code></td><td><code>/api/v1/scan/modbus/tcp</code></td><td>Scan</td><td>Multi-port Modbus TCP scanning across host subnets</td></tr>
              <tr><td><code>POST</code></td><td><code>/api/v1/modbus/smart-scan</code></td><td>Modbus</td><td>Predictive smart register scan for holding/input registers</td></tr>
              <tr><td><code>POST</code></td><td><code>/api/v1/scan/serial/sniff</code></td><td>Sniffer</td><td>Passive Zero-TX RS485 listening and Bus Health telemetry</td></tr>
              <tr><td><code>GET</code></td><td><code>/api/v1/diag/serial/health</code></td><td>Diagnostics</td><td>Physical layer metrics (PER %, FPS, Bus Load %)</td></tr>
              <tr><td><code>POST</code></td><td><code>/api/v1/scan/bacnet/ip</code></td><td>Scan</td><td>BACnet/IP Who-Is broadcast and Foreign Device registration</td></tr>
              <tr><td><code>GET/POST</code></td><td><code>/api/v1/bacnet/devices/{id}/objects</code></td><td>BACnet</td><td>Deep hierarchical object-list exploration</td></tr>
              <tr><td><code>GET</code></td><td><code>/api/v1/bacnet/bbmd/tables</code></td><td>BBMD</td><td>Joint inspection of BBMD BDT and FDT tables</td></tr>
              <tr><td><code>POST</code></td><td><code>/api/v1/scan/knx/ip</code></td><td>Scan</td><td>KNXnet/IP multicast UDP discovery</td></tr>
              <tr><td><code>POST</code></td><td><code>/api/v1/scan/arp</code></td><td>Scan</td><td>Layer-2 promiscuous ARP sniffer</td></tr>
              <tr><td><code>POST</code></td><td><code>/api/v1/scan/abort</code></td><td>Control</td><td>Emergency halt for all active scans and sniffers</td></tr>
              <tr><td><code>POST</code></td><td><code>/api/v1/sessions/diff</code></td><td>Intelligence</td><td>Deterministic Baseline vs Live Session comparison</td></tr>
              <tr><td><code>GET</code></td><td><code>/api/v1/report/pdf</code></td><td>Report</td><td>Download vector PDF commissioning report</td></tr>
              <tr><td><code>GET</code></td><td><code>/api/v1/report/excel</code></td><td>Report</td><td>Download 8-sheet as-built Excel workbook</td></tr>
            </tbody>
          </table>
        </div>

        <h4>cURL Integration Recipes:</h4>
        <p><strong>1. Hardware Self-Test:</strong></p>
        <pre class="bham-code-block">curl -X GET http://localhost:8765/api/v1/hardware/self-test</pre>

        <p><strong>2. Trigger Modbus RTU Scan:</strong></p>
        <pre class="bham-code-block">curl -X POST http://localhost:8765/api/v1/scan/modbus/rtu \\
  -H "Content-Type: application/json" \\
  -d '{"port": "/dev/ttyUSB0", "baudrates": [9600, 19200], "id_range": [1, 2, 3, 4, 5]}'</pre>

        <p><strong>3. Export As-Built Excel:</strong></p>
        <pre class="bham-code-block">curl -X GET http://localhost:8765/api/v1/report/excel -o as_built_report.xlsx</pre>

        <h4>Live WebSocket Telemetry:</h4>
        <p>Connect to: <code>ws://&lt;host&gt;:8765/api/v1/ws</code><br>
        Events emitted: <code>scan_progress</code>, <code>device_found</code>, <code>bus_health_update</code>, <code>log_record</code>.</p>
      `,
      topology: `
        <h3>10. Interactive Topological Map &amp; Advanced Explorers</h3>
        <p>The <strong>Topological Map</strong> (accessible via the view switcher button in the top right of the Workspace) turns the device inventory into an interactive SVG network graph, illustrating the physical and logical architecture of the BMS installation.</p>

        <h4>Plant Hierarchy Tree:</h4>
        <ul>
          <li><strong>Root Node (BHAM Host):</strong> Represents the commissioning workstation and active site session.</li>
          <li><strong>Physical Channels:</strong> RS485 Serial branch (port, baud rate, parity) and Ethernet branch (NIC interface, local IP, subnet).</li>
          <li><strong>Device Nodes:</strong> Field controllers connected to their respective channel, color-coded by protocol (Cyan=Modbus, Purple=BACnet, Orange=KNX, Emerald=ARP) with resource counters.</li>
        </ul>

        <h4>HUD Controls &amp; Interaction:</h4>
        <ul>
          <li><strong>Pan &amp; Zoom:</strong> Drag with mouse to pan. Use <code>+</code> and <code>-</code> buttons or mouse wheel for smooth continuous zooming.</li>
          <li><strong>Fit to Screen:</strong> Automatically scales and centers the graph within the viewport.</li>
          <li><strong>Orientation Toggle:</strong> Switch tree layout between Horizontal (left-to-right) and Vertical (top-to-bottom).</li>
          <li><strong>Live Search Filter:</strong> Type in the HUD search input to highlight matching nodes by name, vendor, or IP/Slave ID while dimming non-matching nodes.</li>
          <li><strong>Export SVG:</strong> Downloads a standalone high-resolution <code>.svg</code> vector file suitable for commissioning reports and submittals.</li>
        </ul>

        <h4>Node Quick Inspector &amp; Explorers:</h4>
        <p>Clicking any node opens the lateral <em>Node Quick Inspector</em> drawer with full telemetry details and direct action buttons:</p>
        <ul>
          <li><strong>BACnet Object Explorer:</strong> Hierarchically navigate all instantiated objects (AI, AO, AV, BI, BO, BV, MSI, MSO, Schedules, Trend Logs) with Present Value and Status Flags.</li>
          <li><strong>Modbus Smart Register Scan:</strong> Heuristic discovery of standard holding, input, and coil registers with automatic integer, float, and hex decoding.</li>
        </ul>
      `,
      diff: `
        <h3>11. Intelligence &amp; Session Diff ("Before vs After")</h3>
        <p>The <strong>Session Diff</strong> engine compares a stored baseline session ("Before") against the active live session ("After") or between any two saved sessions.</p>

        <h4>Key Capabilities:</h4>
        <ul>
          <li><strong>Multi-Protocol Identity:</strong> MAC-based tracking for Ethernet devices, Modbus Slave IDs, BACnet Device Instances, and KNX Physical Addresses.</li>
          <li><strong>Variation Statuses:</strong>
            <ul>
              <li><span class="badge" style="background:#22c55e; color:#000;">ADDED</span> New hardware discovered on site not present in the baseline.</li>
              <li><span class="badge" style="background:#ef4444; color:#fff;">REMOVED</span> Baseline device now unreachable or disconnected.</li>
              <li><span class="badge" style="background:#eab308; color:#000;">MODIFIED</span> Device present in both but with altered parameters (IP, baudrate, firmware, latency).</li>
              <li><span class="badge" style="background:#64748b; color:#fff;">UNCHANGED</span> Stable, identical hardware.</li>
            </ul>
          </li>
          <li><strong>Side-by-Side Visualizer:</strong> Interactive modal displaying old values strikethrough in red and new values highlighted in green.</li>
          <li><strong>Exportable Diff:</strong> Instant download in standard <code>.csv</code> and <code>.json</code> formats.</li>
        </ul>
      `,
      bbmd: `
        <h3>12. BBMD Traversal &amp; BACnet/IP Routers</h3>
        <p>In enterprise BMS installations spanning multiple VLANs or Layer-3 subnets, standard Who-Is UDP broadcasts do not traverse network routers.</p>

        <h4>BHAM Solution:</h4>
        <ul>
          <li><strong>Foreign Device Registration:</strong> BHAM registers as a <em>Foreign Device</em> with the site BBMD router using configurable TTL (default 60s), forwarding discovery requests across subnets.</li>
          <li><strong>BDT &amp; FDT Inspection:</strong>
            <ul>
              <li><strong>Broadcast Distribution Table (BDT):</strong> List of peer BBMD routers routing broadcasts across facility subnets.</li>
              <li><strong>Foreign Device Table (FDT):</strong> List of active registered IP clients with port and remaining TTL countdown.</li>
            </ul>
          </li>
          <li><strong>Topology Mapping:</strong> Remote devices are badged with <code>BBMD</code> and nested under their respective router node in the Topological Map.</li>
        </ul>
      `,
      selftest: `
        <h3>13. Hardware Self-Test &amp; Remote LAN Access</h3>
        <p>BHAM incorporates automated self-diagnostics and built-in capabilities for remote field commissioning.</p>

        <h4>⚡ Hardware Self-Test:</h4>
        <p>Accessible from Settings (<em>Adapters &amp; Ports &gt; ⚡ Run Self-Test</em>) or via API <code>GET /api/v1/hardware/self-test</code>:</p>
        <ul>
          <li><strong>RS485 Serial Port:</strong> Live probe verifying port open/close cycles and timing latency in milliseconds.</li>
          <li><strong>Network Interfaces:</strong> Default gateway route verification and broadcast socket binding check.</li>
          <li><strong>Operating System Privileges:</strong> Confirms <code>dialout</code> group membership (Linux), Administrator rights (Windows), and packet capture capabilities (<code>cap_net_raw</code> or Npcap).</li>
        </ul>

        <h4>🌐 Remote Tablet / PC Access over LAN:</h4>
        <p>When running BHAM on a portable Raspberry Pi or headless panel PC inside an electrical panel:</p>
        <ul>
          <li>The daemon automatically listens on <code>0.0.0.0:8765</code>, allowing connection from any tablet or laptop on the technician Wi-Fi or LAN.</li>
          <li>LAN IP addresses for remote access are displayed in the Settings modal and terminal startup log (e.g., <code>http://192.168.1.50:8765</code>).</li>
        </ul>
      `,
      field_tools: `
        <h3>14. Field Operational Tools &amp; Point Override</h3>
        <p>The <strong>Field Tools</strong> suite enables commissioning engineers to command actuators, inverter pumps, and valves, or perform ad-hoc read/write probes directly from BHAM across physical buses or the virtual plant.</p>
        
        <h4>⚡ Modbus Quick Commander:</h4>
        <ul>
          <li><strong>Read Functions:</strong> FC01 (Coils), FC02 (Discrete Inputs), FC03 (Holding Registers), FC04 (Input Registers).</li>
          <li><strong>Write Functions:</strong> FC05 (Single Coil), FC06 (Single Register), FC15 (Multiple Coils), FC16 (Multiple Registers).</li>
          <li><strong>Data Types:</strong> UInt16, Int16 (signed), Float32 Big-Endian (MSW:LSW), Float32 Little-Endian (LSW:MSW), Raw Hex, Booleans.</li>
          <li><strong>Access:</strong> <em>⚡ Field Tools</em> button in header or <em>⚡ Quick Command</em> subtab inside Modbus slave inspector.</li>
        </ul>

        <h4>⚡ BACnet Point Commander &amp; Priority Array:</h4>
        <ul>
          <li><strong>Manual Override:</strong> Direct write to <code>analogOutput</code>, <code>analogValue</code>, <code>binaryOutput</code>, <code>binaryValue</code> at selectable priority (default <strong>Priority 8 – Manual Operator</strong>).</li>
          <li><strong>Relinquish Command:</strong> Release priority slot back to null, allowing autonomous plant logic to resume control.</li>
          <li><strong>Access:</strong> <em>⚡ Override</em> button next to each object in BACnet Object Explorer.</li>
        </ul>
      `,
      simulator: `
        <h3>15. Virtual Plant Simulator (Demo Mode) &amp; Hardware Resilience</h3>
        <p>BHAM features a built-in virtual plant simulator for offline engineering, pre-commissioning verification, and live demos without physical hardware.</p>

        <h4>🌱 Virtual Plant Engine (Demo Mode):</h4>
        <ul>
          <li><strong>Activation:</strong> Header <em>DEMO MODE</em> switch, CLI flag <code>--demo</code>, environment variable <code>BHAM_DEMO=1</code>, or REST endpoint <code>/api/v1/demo/toggle</code>.</li>
          <li><strong>Simulated Equipment:</strong> Climaveneta Chiller Modbus RTU, Grundfos Inverter Pump Modbus RTU, Schneider PM5350 Power Meter Modbus TCP, AHU 01 BACnet/IP (12 objects), VAV Zone North BACnet/IP (4 objects), KNX gateways/thermostats, and ARP network hosts.</li>
          <li><strong>Dynamic Telemetry:</strong> Realistic continuous sinusoidal oscillation of water temperatures, airflow, inverter Hz, and electrical loads with real-time WebSocket telemetry pulses.</li>
        </ul>

        <h4>🛡️ Hardware Resilience &amp; Hot-Plug Auto-Recovery:</h4>
        <ul>
          <li><strong>Fault Tolerance:</strong> Transparent interception of accidental USB-RS485 disconnects or serial I/O errors without daemon crashes or data loss.</li>
          <li><strong>Auto-Recovery:</strong> Background polling automatically reconnects as soon as the adapter is plugged back in, notifying the technician via non-blocking toasts.</li>
          <li><strong>Enhanced Live Log Viewer:</strong> Multi-level filtering (<code>ALL</code>, <code>DEBUG</code>, <code>INFO</code>, <code>WARN</code>, <code>ERROR</code>), instant search filter, and smooth auto-scroll.</li>
        </ul>
      `,
      profiles: `
        <h3>16. Industrial Modbus Profiles Library &amp; Custom Manager</h3>
        <p>BHAM incorporates a comprehensive offline register profiles library to eliminate flipping through manufacturer PDF manuals during field commissioning.</p>

        <h4>📚 Included Industrial Profiles:</h4>
        <ul>
          <li><strong>Power Meters:</strong> ABB B23, Carlo Gavazzi EM24 &amp; EM111, IME Nemo 96, Schneider Acti9 iEM3150 &amp; PM5350, Siemens SENTRON PAC3200.</li>
          <li><strong>Heat &amp; Flow Meters:</strong> Belimo Energy Valve (EV), Isoil ISOMAG, Diehl/Hydrometer Sharky 775, Emerson Rosemount 8712.</li>
          <li><strong>Actuators &amp; HVAC Controllers:</strong> Belimo Modbus Damper Actuators, Trox VAV Compact, iSMA-B-4I4O I/O Module, Riello Condexa Pro Boiler, Carel pCO Controller.</li>
        </ul>

        <h4>🛠️ Custom Profiles Manager:</h4>
        <ul>
          <li><strong>Creation &amp; Editing:</strong> Define manufacturer, model, register address, data type (UInt16, Float32, etc.), scaling multiplier, and engineering units.</li>
          <li><strong>JSON Import / Export:</strong> Archive and share custom profiles in open JSON format across field teams.</li>
          <li><strong>⚡ Apply to Slave:</strong> Instantly binds the register schema to any selected Slave ID on the bus, injecting points into the active live map.</li>
        </ul>
      `,
      safemode: `
        <h3>17. Safe Mode Interlock</h3>
        <p>Active safety interlock designed to prevent inadvertent writes and accidental overrides on critical central plant machinery.</p>

        <h4>🔒 Interlocked Protection:</h4>
        <ul>
          <li><strong>Locked by Default:</strong> All field bus write commands (Modbus FC05/FC06/FC15/FC16 and BACnet Point Override) are locked with HTTP <code>403 Forbidden</code>.</li>
          <li><strong>Arming Procedure:</strong> Requires specifying Field Engineer Name, Job Order / Facility reference, and authorization window duration (15, 30, 60, or 120 minutes).</li>
          <li><strong>Auto-Disarm:</strong> Automatically locks write operations upon timer expiration or immediately when clicking <em>🔒 Disarm Now</em>.</li>
          <li><strong>Visual Header Badge:</strong> Green locked badge or red pulsating indicator with technician name and live countdown timer.</li>
        </ul>
      `,
      audit: `
        <h3>18. Crash-Proof Audit Journal (WAL &amp; SHA-256 Chaining)</h3>
        <p>Forensic tamper-evident logging of all field operations utilizing Write-Ahead Logging (WAL) and SHA-256 cryptographic chaining.</p>

        <h4>🛡️ Key Capabilities:</h4>
        <ul>
          <li><strong>Write-Ahead Intent Logging:</strong> Every write command is recorded to disk and committed with <code>os.fsync</code> before raw bytes hit the physical bus.</li>
          <li><strong>SHA-256 Cryptographic Chain:</strong> Each journal entry incorporates the previous line's hash (<code>prev_hash</code>), generating an immutable blockchain-style audit trail.</li>
          <li><strong>Automatic Crash Recovery:</strong> On startup following power cuts or abrupt disconnections, orphaned intents are detected and resolved automatically.</li>
          <li><strong>Integrity Check &amp; JSON Export:</strong> One-click forensic verification across all entries and signed JSON export for official commissioning reports.</li>
        </ul>
      `,
      standalone: `
        <h3>19. Standalone Packaging (Portable / Installed) &amp; SignPath</h3>
        <p>Dual-distribution architecture catering to portable thumb drive commissioning as well as managed enterprise workstations.</p>

        <h4>📦 Runtime Execution (<code>core/paths.py</code>):</h4>
        <ul>
          <li><strong>Portable Mode:</strong> Detects <code>portable.flag</code> to store all databases, logs, sessions, and journals strictly inside the local executable directory.</li>
          <li><strong>Installed Mode:</strong> Adheres to standard OS app data directories (<code>%LOCALAPPDATA%\\BHAM</code> on Windows and <code>~/.local/share/bham</code> on Linux).</li>
          <li><strong>Windows Code Signing (SignPath):</strong> CI/CD workflow utilizing <code>SignPath/github-action-submit-signing-request@v2</code> for trusted digital signature of Windows binaries.</li>
          <li><strong>Autonomous Linux Signing (GPG):</strong> Dedicated <code>./scripts/sign_linux.sh</code> tool to locally sign <code>.deb</code>, <code>.tar.gz</code>, and <code>SHA256SUMS.asc</code> with personal or corporate GPG keys.</li>
        </ul>
      `,
      watch_list: `
        <h3>20. Live Watch List &amp; Register Polling</h3>
        <p>The <strong>Live Watch List</strong> provides real-time periodic polling of critical Modbus registers (Holding &amp; Input Registers) during commissioning, balancing, or troubleshooting variable dynamics.</p>

        <h4>Key Capabilities:</h4>
        <ul>
          <li><strong>1-Click Watch Binding:</strong> Add points directly from the Slave Register Map or Inspector table by clicking the watch icon <code>👁️</code>.</li>
          <li><strong>Adaptive Polling Intervals:</strong> User-selectable sampling periods (<strong>500ms</strong>, <strong>1s</strong>, <strong>2s</strong>, or <strong>5s</strong>) with non-intrusive lightweight single-register queries.</li>
          <li><strong>Color-Coded Delta Highlighting:</strong> Register values that change between poll cycles flash with smooth visual transitions (green for increments, amber for decrements/updates), making subtle field fluctuations stand out immediately.</li>
          <li><strong>Hands-Free Web Audio Buzzer:</strong> An in-browser synthesized acoustic chime (Web Audio API) emits an audible click whenever a monitored register changes, allowing engineers to manipulate valves or actuators without looking at the laptop screen.</li>
          <li><strong>CSV Sampling Log Export:</strong> 1-click export of the timestamped sampling log (ISO timestamp, Slave ID, Register, and Value) for spreadsheet charting and trend analysis.</li>
        </ul>
      `,
      rs485_benchmark: `
        <h3>21. RS485 Stress Test &amp; Latency Benchmark</h3>
        <p>A physical-layer RS485 diagnostic benchmark designed to verify serial bus integrity, detect signal reflections, and evaluate baudrate stability before client handover.</p>

        <h4>Benchmark Metrics:</h4>
        <ul>
          <li><strong>Calibrated Stress Bursts:</strong> Rapid sequential query bursts (50, 100, or 200 packets) dispatched at controlled intervals towards designated slave addresses.</li>
          <li><strong>Real-Time Physical Metrics:</strong>
            <ul>
              <li><strong>Packet Error Rate (PER %):</strong> Percentage of dropped packets or timeouts relative to total requests.</li>
              <li><strong>Round-Trip Latency (RTT):</strong> Minimum, average, and maximum response times in milliseconds (ms).</li>
              <li><strong>Transmission Jitter:</strong> Statistical variation in response latency indicating line instability.</li>
              <li><strong>CRC Corruptions:</strong> Count of packets received with invalid checksums (direct indicator of electrical EMI noise).</li>
            </ul>
          </li>
          <li><strong>Automated Physical Layer Diagnostics:</strong>
            <ul>
              <li><em>High Jitter / Sporadic CRC Failures:</em> Missing 120 Ω end-of-line termination resistors causing wave reflections.</li>
              <li><em>Periodic Timeouts:</em> Inverter EMI noise or adjacent high-voltage power conduits.</li>
              <li><em>PER &gt; 50%:</em> Excessive cable length for the configured baudrate or degraded differential polarity.</li>
            </ul>
          </li>
          <li><strong>Optimal Baudrate Recommendation:</strong> Analytical algorithm recommending the maximum safe baudrate for continuous zero-error operation.</li>
        </ul>
      `,
      bms_export_mobile: `
        <h3>22. BMS/SCADA Multi-Vendor Tag Exporter &amp; Mobile QR Access</h3>
        <p>BHAM bridges the gap between field commissioning and building supervision systems by generating native import files for leading BMS/SCADA platforms and offering instant mobile access.</p>

        <h4>Multi-Vendor Tag Exporter (<code>/api/v1/export/tags/{format}</code>):</h4>
        <ul>
          <li><strong>Tridium Niagara 4:</strong> Conforming XML files ready for direct import into Niagara Workbench Modbus Async Network and BACnet Device point folders, preserving point types, addresses, and scaling factors.</li>
          <li><strong>Siemens Desigo CC:</strong> Hierarchical CSV file formatted to standard Desigo CC engineering import specifications (Identifier, DP_Type, Address, Description, Units).</li>
          <li><strong>Schneider EcoStruxure Building Operation (EBO):</strong> CSV tables optimized for bulk import into EcoStruxure WorkStation device managers.</li>
          <li><strong>Universal BACnet CSV:</strong> Tabular export containing Object Identifier, Object Name, Object Type, Present Value, Description, and Engineering Units.</li>
        </ul>

        <h4>Hands-Free Mobile Access (QR Code LAN Pairing):</h4>
        <ul>
          <li><strong>Pure SVG Vector QR Generation:</strong> Clicking the 📱 QR Code button in the status bar or Settings modal renders an instant vector QR code with zero external web dependencies.</li>
          <li><strong>Automatic Local LAN IP Resolution:</strong> The QR code embeds the live IP and port of the active network interface (e.g., <code>http://192.168.1.50:8765</code>).</li>
          <li><strong>Instant Mobile Pairing:</strong> Field engineers scan the QR code with a phone or tablet to open the complete diagnostic dashboard over local Wi-Fi without manual IP typing.</li>
          <li><strong>Zero-Asset Web Audio API:</strong> Synthesized audio notifications and tone verification enable eyes-free and hands-free testing in tight electrical panels.</li>
        </ul>
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
      { id: "api", title: "9. REST & WebSocket API" },
      { id: "topology", title: "10. Mapa Topológico & Explorer" },
      { id: "diff", title: "11. Session Diff ('Antes vs Después')" },
      { id: "bbmd", title: "12. Travesía BBMD y Routers BACnet" },
      { id: "selftest", title: "13. Auto-Prueba Hardware y Acceso LAN" },
      { id: "field_tools", title: "14. Banco de Pruebas & Override" },
      { id: "simulator", title: "15. Simulador Virtual & Resiliencia" },
      { id: "profiles", title: "16. Biblioteca Perfiles Modbus Industriales" },
      { id: "safemode", title: "17. Bloqueo de Seguridad (Safe Mode)" },
      { id: "audit", title: "18. Registro de Maniobras Certificado (WAL)" },
      { id: "standalone", title: "19. Empaquetado Standalone & SignPath" },
      { id: "watch_list", title: "20. Monitorización en Vivo (Watch List)" },
      { id: "rs485_benchmark", title: "21. Test de Estrés RS485 & Benchmark de Latencia" },
      { id: "bms_export_mobile", title: "22. Exportador BMS/SCADA & Acceso Móvil QR" }
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

        <div class="bham-callout callout-info">
          <strong>Cruce de Enrutador (BBMD) y Foreign Device:</strong> Para instalaciones multi-subred o con VLANs que bloquean el broadcast UDP, indique la IP del enrutador BBMD en la sección correspondiente. BHAM realizará un registro <em>Foreign Device</em> (Anexo J) para cursar telegramas Who-Is/I-Am a través del enrutador. Con el botón <strong>Tablas BDT/FDT</strong> puede inspeccionar la Broadcast Distribution Table y la Foreign Device Table en tiempo real.
        </div>
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
        <h3>9. Referencia REST &amp; WebSocket API</h3>
        <p>BHAM cuenta con más de 39 endpoints RESTful y un canal WebSocket de baja latencia para la automatización de puestas en marcha y la integración con BMS de terceros.</p>

        <div class="bham-callout callout-info" style="margin-bottom:14px;">
          <strong>Documentación Interactiva y Referencia Técnica:</strong><br>
          • <strong>Swagger UI:</strong> <a href="/docs" target="_blank" style="color:var(--bham-modbus); font-weight:600;">/docs</a> &nbsp;|&nbsp;
          • <strong>ReDoc:</strong> <a href="/redoc" target="_blank" style="color:var(--bham-modbus); font-weight:600;">/redoc</a> &nbsp;|&nbsp;
          • <strong>Guía Técnica:</strong> Consulta el archivo <code>API_REFERENCE.md</code> para contratos de datos JSON completos.
        </div>

        <h4>Tabla de Endpoints Principales:</h4>
        <div style="overflow-x:auto; margin-bottom:14px;">
          <table class="bham-data-table" style="font-size:12px; width:100%;">
            <thead>
              <tr><th>Método</th><th>Endpoint</th><th>Ámbito</th><th>Descripción</th></tr>
            </thead>
            <tbody>
              <tr><td><code>GET</code></td><td><code>/api/v1/health</code></td><td>Sistema</td><td>Estado del servicio, versión y clientes WS conectados</td></tr>
              <tr><td><code>GET</code></td><td><code>/api/v1/state</code></td><td>Estado</td><td>Snapshot completo de dispositivos y configuración activa</td></tr>
              <tr><td><code>GET</code></td><td><code>/api/v1/topology</code></td><td>Topología</td><td>Grafo vectorial jerárquico de la instalación</td></tr>
              <tr><td><code>GET</code></td><td><code>/api/v1/hardware/self-test</code></td><td>Hardware</td><td>Auto-prueba rápida de puertos seriales, NIC y permisos</td></tr>
              <tr><td><code>POST</code></td><td><code>/api/v1/scan/modbus/rtu</code></td><td>Escaneo</td><td>Barrido activo Modbus RTU serial (Phase Zero)</td></tr>
              <tr><td><code>POST</code></td><td><code>/api/v1/scan/modbus/tcp</code></td><td>Escaneo</td><td>Escaneo Modbus TCP multipuerto en subredes</td></tr>
              <tr><td><code>POST</code></td><td><code>/api/v1/modbus/smart-scan</code></td><td>Modbus</td><td>Escaneo inteligente heurístico de registros holding/input</td></tr>
              <tr><td><code>POST</code></td><td><code>/api/v1/scan/serial/sniff</code></td><td>Sniffer</td><td>Escucha pasiva RS485 Zero-TX y telemetría Bus Health</td></tr>
              <tr><td><code>GET</code></td><td><code>/api/v1/diag/serial/health</code></td><td>Diagnóstico</td><td>Métricas físicas RS485 (PER %, FPS, Carga de Bus %)</td></tr>
              <tr><td><code>POST</code></td><td><code>/api/v1/scan/bacnet/ip</code></td><td>Escaneo</td><td>Who-Is broadcast BACnet/IP y soporte Foreign Device</td></tr>
              <tr><td><code>GET/POST</code></td><td><code>/api/v1/bacnet/devices/{id}/objects</code></td><td>BACnet</td><td>Exploración profunda jerárquica de lista de objetos</td></tr>
              <tr><td><code>GET</code></td><td><code>/api/v1/bacnet/bbmd/tables</code></td><td>BBMD</td><td>Lectura conjunta de tablas BDT y FDT de router BBMD</td></tr>
              <tr><td><code>POST</code></td><td><code>/api/v1/scan/knx/ip</code></td><td>Scan</td><td>Descubrimiento multicast UDP KNXnet/IP</td></tr>
              <tr><td><code>POST</code></td><td><code>/api/v1/scan/arp</code></td><td>Scan</td><td>Sniffer promiscuo Layer-2 ARP</td></tr>
              <tr><td><code>POST</code></td><td><code>/api/v1/scan/abort</code></td><td>Control</td><td>Parada de emergencia inmediata de todos los escaneos</td></tr>
              <tr><td><code>POST</code></td><td><code>/api/v1/sessions/diff</code></td><td>Inteligencia</td><td>Comparación analítica Línea Base vs Sesión Activa</td></tr>
              <tr><td><code>GET</code></td><td><code>/api/v1/report/pdf</code></td><td>Reporte</td><td>Descarga de informe de ensayo en PDF vectorial</td></tr>
              <tr><td><code>GET</code></td><td><code>/api/v1/report/excel</code></td><td>Reporte</td><td>Descarga de libro as-built en Excel de 8 hojas</td></tr>
            </tbody>
          </table>
        </div>

        <h4>Ejemplos con cURL:</h4>
        <p><strong>1. Auto-Prueba de Hardware:</strong></p>
        <pre class="bham-code-block">curl -X GET http://localhost:8765/api/v1/hardware/self-test</pre>

        <p><strong>2. Iniciar Escaneo Modbus RTU:</strong></p>
        <pre class="bham-code-block">curl -X POST http://localhost:8765/api/v1/scan/modbus/rtu \\
  -H "Content-Type: application/json" \\
  -d '{"port": "/dev/ttyUSB0", "baudrates": [9600, 19200], "id_range": [1, 2, 3, 4, 5]}'</pre>

        <p><strong>3. Exportar Excel As-Built:</strong></p>
        <pre class="bham-code-block">curl -X GET http://localhost:8765/api/v1/report/excel -o reporte_as_built.xlsx</pre>

        <h4>Canal WebSocket en Vivo:</h4>
        <p>Conexión: <code>ws://&lt;host&gt;:8765/api/v1/ws</code><br>
        Eventos emitidos: <code>scan_progress</code>, <code>device_found</code>, <code>bus_health_update</code>, <code>log_record</code>.</p>
      `,
      topology: `
        <h3>10. Mapa Topológico Interactivo y Exploradores Avanzados</h3>
        <p>El <strong>Mapa Topológico</strong> (accesible desde el conmutador de vistas en la parte superior derecha del área de trabajo) convierte el inventario de dispositivos en un grafo de red vectorial SVG interactivo, mostrando la arquitectura física y lógica de la instalación BMS.</p>

        <h4>Árbol Jerárquico de la Instalación:</h4>
        <ul>
          <li><strong>Nodo Raíz (Host BHAM):</strong> Representa el puesto de comisionamiento y la sesión activa.</li>
          <li><strong>Canales Físicos:</strong> Canal serie RS485 (puerto, baudios, paridad) y Canal de red Ethernet (interfaz NIC, IP local, subred).</li>
          <li><strong>Nodos de Dispositivos:</strong> Periféricos descubiertos conectados a su canal, codificados por colores según el protocolo (Cian=Modbus, Púrpura=BACnet, Naranja=KNX, Esmeralda=ARP) con contadores integrados.</li>
        </ul>

        <h4>Controles HUD y Navegación:</h4>
        <ul>
          <li><strong>Pan y Zoom:</strong> Arrastre con el ratón para desplazar. Utilice los botones <code>+</code> y <code>-</code> del HUD o la rueda del ratón para zoom continuo.</li>
          <li><strong>Ajustar a Pantalla (Fit):</strong> Centra y escala el grafo para encajarlo perfectamente en la vista.</li>
          <li><strong>Orientación:</strong> Cambia la disposición entre árbol horizontal (izquierda a derecha) o vertical (arriba hacia abajo).</li>
          <li><strong>Filtro de Búsqueda:</strong> Resalta en tiempo real los nodos que coincidan por nombre, fabricante o IP/ID.</li>
          <li><strong>Exportar SVG:</strong> Descarga el diagrama vectorial <code>.svg</code> de alta resolución para la documentación de entrega de obra.</li>
        </ul>

        <h4>Inspector Rápido de Nodos y Exploradores:</h4>
        <p>Al hacer clic en cualquier nodo se abre el cajón lateral <em>Node Quick Inspector</em> con telemetría completa y accesos directos:</p>
        <ul>
          <li><strong>BACnet Object Explorer:</strong> Navegación jerárquica de todos los objetos (AI, AO, AV, BI, BO, BV, MSI, MSO, horarios, tendencias) con Present Value y Status Flags.</li>
          <li><strong>Modbus Smart Scan:</strong> Escaneo predictivo de registros estándar con conversión automática a entero, flotante y hexadecimal.</li>
        </ul>
      `,
      diff: `
        <h3>11. Inteligencia y Session Diff ("Antes vs Después")</h3>
        <p>El motor <strong>Session Diff</strong> compara analíticamente una sesión de línea base archivada ("Antes") contra el estado activo en vivo ("Después") o entre dos sesiones históricas.</p>

        <h4>Capacidades Principales:</h4>
        <ul>
          <li><strong>Identificación Multi-Protocolo:</strong> Seguimiento por dirección MAC en Ethernet, ID de esclavo en Modbus, Device Instance en BACnet y Dirección Física en KNX.</li>
          <li><strong>Clasificación de Cambios:</strong>
            <ul>
              <li><span class="badge" style="background:#22c55e; color:#000;">ADDED</span> Dispositivo nuevo detectado en campo no presente en la línea base.</li>
              <li><span class="badge" style="background:#ef4444; color:#fff;">REMOVED</span> Dispositivo de línea base apagado o inalcanzable.</li>
              <li><span class="badge" style="background:#eab308; color:#000;">MODIFIED</span> Dispositivo presente pero con parámetros modificados (IP, velocidad baud, firmware, latencia).</li>
              <li><span class="badge" style="background:#64748b; color:#fff;">UNCHANGED</span> Dispositivo estable e idéntico.</li>
            </ul>
          </li>
          <li><strong>Visualizador Comparativo:</strong> Modal interactivo con valores antiguos tachados en rojo y valores nuevos en verde.</li>
          <li><strong>Exportación Inmediata:</strong> Descarga directa en formatos estándar <code>.csv</code> y <code>.json</code>.</li>
        </ul>
      `,
      bbmd: `
        <h3>12. Travesía BBMD y Routers BACnet/IP</h3>
        <p>En redes BMS con segmentación VLAN o subredes de nivel 3, los paquetes de difusión Who-Is no atraviesan los enrutadores IP.</p>

        <h4>Solución BHAM:</h4>
        <ul>
          <li><strong>Registro Foreign Device:</strong> BHAM se registra como <em>Foreign Device</em> ante el router BBMD especificado con TTL configurable (por defecto 60s), enrutando paquetes Who-Is a todas las subredes conectadas.</li>
          <li><strong>Inspección de Tablas BDT y FDT:</strong>
            <ul>
              <li><strong>Broadcast Distribution Table (BDT):</strong> Lista de routers BBMD configurados para la distribución de broadcast.</li>
              <li><strong>Foreign Device Table (FDT):</strong> Lista de dispositivos remotos registrados con IP, puerto y cuenta atrás de TTL.</li>
            </ul>
          </li>
          <li><strong>Mapeo Topológico:</strong> Los dispositivos descubiertos a través de un enrutador se etiquetan con <code>BBMD</code> y se agrupan bajo el nodo router en el Mapa Topológico.</li>
        </ul>
      `,
      selftest: `
        <h3>13. Auto-Prueba Hardware y Acceso Remoto LAN</h3>
        <p>BHAM incorpora herramientas avanzadas de diagnóstico de hardware y conectividad remota en campo.</p>

        <h4>⚡ Auto-Prueba de Hardware (Self-Test):</h4>
        <p>Disponible en el Centro de Configuración (<em>Adaptadores y Puertos &gt; ⚡ Ejecutar Auto-Prueba</em>) o mediante la API <code>GET /api/v1/hardware/self-test</code>:</p>
        <ul>
          <li><strong>Puerto Serie RS485:</strong> Verificación en tiempo real de apertura/cierre y latencia en milisegundos.</li>
          <li><strong>Tarjetas de Red:</strong> Comprobación de ruta a puerta de enlace predeterminada y binding broadcast.</li>
          <li><strong>Permisos del Sistema Operativo:</strong> Comprobación de pertenencia al grupo <code>dialout</code> (Linux), privilegios de Administrador (Windows) y captura de paquetes (<code>cap_net_raw</code> o Npcap).</li>
        </ul>

        <h4>🌐 Acceso Remoto desde Tablet o Portátil en Red LAN:</h4>
        <p>Al ejecutar BHAM en una Raspberry Pi o PC industrial dentro de un cuadro eléctrico:</p>
        <ul>
          <li>El servidor escucha en <code>0.0.0.0:8765</code>, permitiendo el acceso web desde cualquier dispositivo conectado a la misma red local.</li>
          <li>Las direcciones IP LAN se muestran claramente en el modal de configuración y en la consola de inicio (ej. <code>http://192.168.1.50:8765</code>).</li>
        </ul>
      `,
      field_tools: `
        <h3>14. Herramientas Operativas de Campo ("Field Tools") &amp; Override</h3>
        <p>La suite <strong>Field Tools</strong> permite a los técnicos de puesta en marcha comandar actuadores, bombas modulantes y válvulas, o realizar lecturas y escrituras puntuales directamente desde BHAM en buses físicos o en la planta virtual.</p>
        
        <h4>⚡ Modbus Quick Commander:</h4>
        <ul>
          <li><strong>Funciones de Lectura:</strong> FC01 (Coils), FC02 (Discrete Inputs), FC03 (Holding Registers), FC04 (Input Registers).</li>
          <li><strong>Funciones de Escritura:</strong> FC05 (Single Coil), FC06 (Single Register), FC15 (Multiple Coils), FC16 (Multiple Registers).</li>
          <li><strong>Formatos de Datos:</strong> UInt16, Int16 (con signo), Float32 Big-Endian (MSW:LSW), Float32 Little-Endian (LSW:MSW), Hex bruto, Booleanos.</li>
          <li><strong>Acceso:</strong> Botón <em>⚡ Herramientas de Campo</em> en cabecera o pestaña <em>⚡ Comando Rápido</em> en el inspector de esclavo Modbus.</li>
        </ul>

        <h4>⚡ BACnet Point Commander &amp; Priority Array:</h4>
        <ul>
          <li><strong>Override Manual:</strong> Comando en objetos <code>analogOutput</code>, <code>analogValue</code>, <code>binaryOutput</code>, <code>binaryValue</code> al nivel de prioridad seleccionado (predeterminado <strong>Prioridad 8 – Operador Manual</strong>).</li>
          <li><strong>Comando Relinquish:</strong> Liberación inmediata de la prioridad establecida devolviendo el control al controlador local.</li>
          <li><strong>Acceso:</strong> Botón <em>⚡ Override</em> junto a cada objeto en el Explorador de Objetos BACnet.</li>
        </ul>
      `,
      simulator: `
        <h3>15. Simulador de Planta Virtual (Modo Demo) &amp; Resiliencia</h3>
        <p>BHAM integra un motor de simulación virtual completo para pruebas offline, capacitación y demostraciones sin hardware físico conectado.</p>

        <h4>🌱 Motor de Planta Virtual (Modo Demo):</h4>
        <ul>
          <li><strong>Activación:</strong> Interruptor <em>MODO DEMO</em> en cabecera, flag CLI <code>--demo</code>, variable <code>BHAM_DEMO=1</code> o endpoint REST <code>/api/v1/demo/toggle</code>.</li>
          <li><strong>Equipos Simulados:</strong> Chiller Climaveneta Modbus RTU, Bomba Inverter Grundfos Modbus RTU, Medidor Schneider PM5350 Modbus TCP, Climatizador UTA 01 BACnet/IP (12 objetos), VAV BACnet/IP (4 objetos), pasarela y sensores KNX, y hosts ARP de red.</li>
          <li><strong>Telemetría Dinámica:</strong> Variación sinusoidal en tiempo real de temperaturas, caudales, potencias y frecuencias transmitidas vía WebSocket.</li>
        </ul>

        <h4>🛡️ Resiliencia Serie &amp; Auto-Recuperación Hot-Plug:</h4>
        <ul>
          <li><strong>Tollerancia a Desconexiones:</strong> Manejo transparente de desconexiones accidentales de adaptadores USB↔RS485 sin caída del servidor ni pérdida de datos.</li>
          <li><strong>Auto-Recuperación:</strong> Reconexión automática en cuanto se reconecta el puerto serie con notificaciones toast no intrusivas.</li>
          <li><strong>Visor de Logs Mejorado:</strong> Filtrado por niveles de severidad (<code>ALL</code>, <code>DEBUG</code>, <code>INFO</code>, <code>WARN</code>, <code>ERROR</code>) y cuadro de búsqueda en tiempo real.</li>
        </ul>
      `,
      profiles: `
        <h3>16. Biblioteca de Perfiles Modbus Industriales &amp; Gestor Custom</h3>
        <p>BHAM integra una amplia biblioteca de perfiles Modbus estándar para evitar la consulta de manuales en papel durante las pruebas de campo.</p>

        <h4>📚 Perfiles Industriales Integrados:</h4>
        <ul>
          <li><strong>Medidores Eléctricos:</strong> ABB B23, Carlo Gavazzi EM24 y EM111, IME Nemo 96, Schneider Acti9 iEM3150 y PM5350, Siemens SENTRON PAC3200.</li>
          <li><strong>Contabilizadores de Energía y Caudal:</strong> Belimo Energy Valve (EV), Isoil ISOMAG, Diehl/Hydrometer Sharky 775, Emerson Rosemount 8712.</li>
          <li><strong>Actuadores y Controladores HVAC:</strong> Actuadores Modbus Belimo, Trox VAV Compact, Módulo I/O iSMA-B-4I4O, Caldera Riello Condexa Pro, Controlador Carel pCO.</li>
        </ul>

        <h4>🛠️ Gestión de Perfiles Personalizados:</h4>
        <ul>
          <li><strong>Creación y Modificación:</strong> Definición de fabricante, modelo, direcciones de registro, tipo de dato (UInt16, Float32, etc.), factor de escala y unidades.</li>
          <li><strong>Importación / Exportación JSON:</strong> Comparta y guarde perfiles personalizados en formato JSON estándar.</li>
          <li><strong>⚡ Aplicar a Esclavo:</strong> Asignación inmediata del perfil al Slave ID seleccionado con inyección automática en el mapa de registros en vivo.</li>
        </ul>
      `,
      safemode: `
        <h3>17. Bloqueo de Seguridad para Maniobras (Safe Mode Interlock)</h3>
        <p>Sistema de protección activa para prevenir escrituras accidentales y maniobras no deseadas en equipos críticos de planta.</p>

        <h4>🔒 Protección Enclavada:</h4>
        <ul>
          <li><strong>Bloqueo Predeterminado:</strong> Al iniciar el sistema, todas las órdenes de escritura (Modbus FC05/FC06/FC15/FC16 y BACnet Point Override) están bloqueadas con código <code>403 Forbidden</code>.</li>
          <li><strong>Procedimiento de Desbloqueo ("Arm"):</strong> Requiere indicar Nombre del Técnico, Orden de Trabajo / Referencia de Obra y duración de la ventana temporal (15, 30, 60 o 120 minutos).</li>
          <li><strong>Bloqueo Automático:</strong> Al expirar el temporizador o pulsar <em>🔒 Bloquear Inmediatamente</em>, el sistema restablece la protección sin canales abiertos.</li>
          <li><strong>Distintivo Visual:</strong> Indicador verde bloqueado o rojo parpadeante con nombre del técnico y cuenta atrás en tiempo real.</li>
        </ul>
      `,
      audit: `
        <h3>18. Registro de Maniobras Certificado (WAL &amp; Cadenas SHA-256)</h3>
        <p>Trazabilidad forense inmutable de todas las intervenciones en campo con tecnología Write-Ahead Log (WAL) y firma criptográfica SHA-256.</p>

        <h4>🛡️ Características Principales:</h4>
        <ul>
          <li><strong>Registro Previo (Write-Ahead):</strong> Cada orden de escritura se guarda en disco con <code>os.fsync</code> antes de emitir los bytes por la línea física.</li>
          <li><strong>Cadena Criptográfica SHA-256:</strong> Cada entrada incluye el hash del registro anterior (<code>prev_hash</code>), creando una cadena inalterable estilo blockchain.</li>
          <li><strong>Recuperación tras Caídas de Tensión:</strong> Al reiniciar el sistema tras un apagón o desconexión brusca, los intentos huérfanos se detectan y resuelven automáticamente.</li>
          <li><strong>Verificación de Integridad y Exportación:</strong> Comprobación forense línea por línea y exportación del registro en JSON firmado para actas de recepción.</li>
        </ul>
      `,
      standalone: `
        <h3>19. Empaquetado Standalone (Portable / Instalador) &amp; SignPath</h3>
        <p>Distribución dual adaptada tanto a la ejecución directa desde memoria USB como a la instalación gestionada en ordenadores de empresa.</p>

        <h4>📦 Modos de Ejecución (<code>core/paths.py</code>):</h4>
        <ul>
          <li><strong>Modo Portable:</strong> Reconoce el archivo <code>portable.flag</code> y guarda sesiones, registros y perfiles directamente en la carpeta del ejecutable.</li>
          <li><strong>Modo Instalado:</strong> Emplea directorios estándar del sistema operativo (<code>%LOCALAPPDATA%\\BHAM</code> en Windows y <code>~/.local/share/bham</code> en Linux).</li>
          <li><strong>Firma Digital Windows (SignPath):</strong> Integración en GitHub Actions con <code>SignPath/github-action-submit-signing-request@v2</code> para firma autenticada de binarios.</li>
          <li><strong>Firma Digital Autónoma Linux (GPG):</strong> Herramienta <code>./scripts/sign_linux.sh</code> para firmar localmente los paquetes <code>.deb</code>, <code>.tar.gz</code> y <code>SHA256SUMS.asc</code> con su clave GPG.</li>
        </ul>
      `,
      watch_list: `
        <h3>20. Monitorización en Vivo (Watch List) &amp; Polling</h3>
        <p>La <strong>Watch List en Vivo</strong> permite la supervisión continua y en tiempo real de registros Modbus seleccionados (Holding e Input Registers) durante tareas de equilibrado hidráulico, calibración de sensores o diagnóstico de transitorios.</p>

        <h4>Funcionalidades Principales:</h4>
        <ul>
          <li><strong>Asignación en 1-Clic:</strong> Agregue puntos directamente desde el mapa de registros del esclavo o inspector pulsando el icono del ojo <code>👁️</code>.</li>
          <li><strong>Intervalos de Muestreo Adaptativos:</strong> Periodos seleccionables de <strong>500ms</strong>, <strong>1s</strong>, <strong>2s</strong> o <strong>5s</strong> con consultas ligeras no invasivas sobre el bus.</li>
          <li><strong>Resaltado Cromático de Deltas:</strong> Los valores que sufren cambios se iluminan dinámicamente (verde para incrementos, naranja para variaciones), facilitando la detección de oscilaciones.</li>
          <li><strong>Avisador Acústico (Web Audio API):</strong> Tono sonoro generado por el navegador cada vez que cambia un registro vigilado, permitiendo trabajar en el cuadro eléctrico sin mirar la pantalla.</li>
          <li><strong>Exportación de Muestras a CSV:</strong> Descarga inmediata del registro cronológico con marcas temporales en milisegundos para gráficos y tendencias.</li>
        </ul>
      `,
      rs485_benchmark: `
        <h3>21. Test de Estrés RS485 &amp; Benchmark de Latencia</h3>
        <p>Herramienta de diagnóstico de capa física para verificar la integridad del bus serie RS485, detectar reflexiones de onda y evaluar la estabilidad de la velocidad antes de la entrega final.</p>

        <h4>Parámetros de Medición:</h4>
        <ul>
          <li><strong>Ráfagas de Estrés Calibradas:</strong> Envío de secuencias continuas de peticiones Modbus (50, 100 o 200 tramas) a frecuencia controlada sobre esclavos activos.</li>
          <li><strong>Métricas Físicas en Tiempo Real:</strong>
            <ul>
              <li><strong>Packet Error Rate (PER %):</strong> Porcentaje de paquetes perdidos o con timeout sobre el total.</li>
              <li><strong>Tiempo de Ida y Vuelta (RTT):</strong> Latencia mínima, media y máxima en milisegundos (ms).</li>
              <li><strong>Jitter de Línea:</strong> Variación temporal de la respuesta que evidencia ruido o inestabilidad.</li>
              <li><strong>Fallos CRC:</strong> Tramas descartadas por suma de comprobación errónea (indicio directo de EMI o cables sin apantallar).</li>
            </ul>
          </li>
          <li><strong>Diagnóstico Físico Guiado:</strong>
            <ul>
              <li><em>Jitter elevado / Fallos CRC esporádicos:</em> Ausencia de resistencias de terminación de 120 Ω en los extremos del bus.</li>
              <li><em>Timeouts frecuentes:</em> Interferencias por variadores de frecuencia o cables de potencia adyacentes.</li>
              <li><em>PER &gt; 50%:</em> Longitud excesiva de cable para el baudrate fijado o polaridad A/B defectuosa.</li>
            </ul>
          </li>
          <li><strong>Recomendación de Baudrate Óptimo:</strong> Algoritmo analítico que indica la velocidad máxima aconsejada para operación continua sin errores.</li>
        </ul>
      `,
      bms_export_mobile: `
        <h3>22. Exportador BMS/SCADA Multi-Fabricante &amp; Acceso Móvil QR</h3>
        <p>BHAM agiliza la integración en sistemas de supervisión exportando el inventario de puntos a los formatos nativos de las plataformas líderes BMS y ofreciendo acceso móvil en campo.</p>

        <h4>Exportador de Puntos BMS (<code>/api/v1/export/tags/{format}</code>):</h4>
        <ul>
          <li><strong>Tridium Niagara 4:</strong> Archivo XML compatible para importación en controladores Niagara Workbench (Modbus Async Network y BACnet Device Points).</li>
          <li><strong>Siemens Desigo CC:</strong> Archivo CSV formateado según la jerarquía estándar de importación de ingeniería Desigo CC.</li>
          <li><strong>Schneider EcoStruxure Building Operation (EBO):</strong> Tablas CSV optimizadas para la creación masiva de dispositivos y puntos en EcoStruxure WorkStation.</li>
          <li><strong>BACnet CSV Estándar:</strong> Tabla universal con Object Identifier, Object Name, Object Type, Present Value, Description y Unidades de Ingeniería.</li>
        </ul>

        <h4>Acceso Móvil en Obra con Código QR (LAN Pairing):</h4>
        <ul>
          <li><strong>Generación Vectorial SVG:</strong> Al pulsar el icono 📱 QR Code en la barra de estado o Ajustes, se genera de forma instantánea un código QR vectorial sin depender de servicios web externos.</li>
          <li><strong>Detección Automática de IP Local:</strong> El código QR codifica la dirección IP real de la tarjeta de red seleccionada (ej. <code>http://192.168.1.50:8765</code>).</li>
          <li><strong>Emparejamiento Instantáneo:</strong> El técnico escanea el código con su teléfono o tableta y accede a la interfaz completa por Wi-Fi sin escribir la IP a mano.</li>
          <li><strong>Síntesis Sonora Web Audio API:</strong> Notificaciones y confirmaciones acústicas generadas en el navegador para pruebas a manos libres.</li>
        </ul>
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
