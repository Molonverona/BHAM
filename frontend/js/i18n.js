/**
 * BHAM – Internationalization System (i18n)
 * Full multi-language dictionary and reactive translator supporting:
 * - it: Italiano (predefinito)
 * - en: English
 * - es: Español
 */

"use strict";

const I18N = {
  currentLang: "it",

  translations: {
    it: {
      // Header & Brand
      brand_sub: "BACS Help Auto Mapper v0.6.0",
      rapid_scan: "AVVIA SCAN RAPIDO",
      rapid_scan_title: "Avvia scansione sequenziale RTU + BACnet + KNX + ARP",
      abort_scan: "ABORT SCAN",
      abort_scan_title: "Arresta immediatamente tutte le scansioni attive",
      save: "Salva",
      sessions: "Sessioni",
      settings: "Impostazioni",
      help: "Manuale & Guida",
      api_docs: "API / Docs",
      theme_light: "Chiaro",
      theme_dark: "Scuro",

      // Telemetry Strip
      status_ready: "Pronto – {n} dispositivi attivi su campo",
      status_running: "Scansione in corso ({proto}) – {n} catalogati",
      status_completed: "Completata – {n} trovati ({pct}%)",
      status_aborted: "Scansione arrestata da operatore (Abort)",
      scan_duration: "Tempo scansione:",
      active_tag: "ATTIVO:",
      active_site_lbl: "Impianto:",
      active_rs485_lbl: "RS485:",
      active_nic_lbl: "NIC:",
      edit_params_hint: "Clicca per aprire la configurazione",

      // Sidebar Cards
      site_plant_lbl: "Sito / Impianto:",
      modbus_rtu_title: "Modbus RTU (RS485)",
      slave_id_range: "Slave ID Range",
      timeout_ms: "Timeout (ms)",
      btn_start_rtu: "Avvia RTU",
      modbus_tcp_title: "Modbus TCP",
      tcp_hosts_label: "Host (uno per riga o CIDR)",
      tcp_port_label: "Porta TCP (o elenco)",
      btn_start_tcp: "Avvia TCP",
      bacnet_title: "BACnet/IP",
      iface_label: "Interfaccia",
      udp_port_label: "Porta UDP",
      bacnet_port_label: "Porta / Simbolo",
      btn_start_bacnet: "Who-Is Broadcast",
      knx_title: "KNXnet/IP Discovery",
      btn_start_knx: "Avvia KNX Discovery",
      arp_title: "ARP Sniffer",
      duration_sec: "Durata (sec)",
      btn_start_arp: "Avvia Sniffing",
      fc43_title: "FC43 Device ID (Modbus MEI)",
      serial_port_label: "Porta Seriale",
      slave_id_label: "Slave ID",
      btn_run_fc43: "Leggi FC43",
      serial_sniff_title: "Sniffer Passivo (RS485)",
      zero_tx_badge: "Zero-TX Stealth",
      protocol_label: "Protocollo",
      baud_label: "Baudrate",
      duration_label: "Durata",
      opt_proto_auto: "Auto-Detect",
      opt_baud_auto: "Auto-Baud",
      opt_parity_auto: "Auto",
      opt_dur_continuous: "Continuo (∞)",
      btn_start_sniff: "Avvia Ascolto (RS485)",
      btn_open_inspector: "Mostra Frame RS485",
      console_tab_log: "Live Log",
      console_tab_inspector: "RS485 Inspector",
      console_reduce: "Riduci",
      console_expand: "Console",
      btn_toggle_console: "Console & Sniffer",
      btn_clear_cache: "Pulisci Cache",
      btn_bacs_maps: "Mappe BACS",

      // View Switcher & Topology Map
      view_table: "Tabelle",
      view_topology: "Mappa Topologica",
      view_table_title: "Visualizza vista tabellare dispositivi",
      view_topology_title: "Visualizza mappa topologica interattiva impianto",
      topo_zoom_in: "Zoom In (+)",
      topo_zoom_out: "Zoom Out (-)",
      topo_fit: "Adatta a Schermo",
      topo_layout_h: "Albero Orizzontale",
      topo_layout_v: "Albero Verticale",
      topo_export_svg: "Esporta SVG",
      topo_legend_host: "Host / Gateway",
      topo_legend_interface: "Interfaccia",
      topo_legend_bus: "Bus di Protocollo",
      topo_legend_device: "Dispositivo / Nodo",
      topo_inspector_title: "Dettaglio Nodo",
      topo_inspector_close: "Chiudi",
      topo_node_type: "Tipo:",
      topo_node_proto: "Protocollo:",
      topo_node_parent: "Collegato a:",
      topo_node_status: "Stato:",
      topo_btn_modbus_details: "🔍 Dettagli Slave / Mappa",
      topo_btn_smart_scan: "⚡ Auto-Scan Registri",
      topo_btn_bacnet_objects: "🔍 Esplora Oggetti",
      topo_btn_show_table: "📋 Mostra in Tabella",
      topo_filter_all: "Tutti i Canali",
      topo_empty_title: "Mappa Pronta al Collaudo",
      topo_empty_desc: "L'host BHAM e le interfacce hardware sono pronte. Avvia una scansione per visualizzare i dispositivi sul grafo topologico.",

      // Center Tabs & Tables
      tab_all: "Tutti",
      tab_modbus: "Modbus",
      tab_bacnet: "BACnet",
      tab_knx: "KNX",
      tab_hosts: "ARP Hosts",
      export_csv: "CSV",
      export_excel: "Excel",
      export_pdf: "PDF",
      search_placeholder: "Filtra per IP, Vendor, Modello, Indirizzo registro/KNX...",

      // Table Headers
      th_id: "ID",
      th_protocol: "PROTOCOLLO",
      th_endpoint: "ENDPOINT",
      th_latency: "MS",
      th_vendor_model: "VENDOR / MODELLO",
      th_status: "STATO",
      th_actions: "AZIONI",
      th_dev_id: "DEV ID",
      th_mac_address: "MAC / INDIRIZZO",
      th_vendor: "VENDOR",
      th_model: "MODELLO",
      th_fw_rev: "REV FW",
      th_obj_count: "CONTEGGIO OBJ",
      th_indiv_addr: "INDIV ADDR",
      th_dev_name: "NOME DISPOSITIVO",
      th_serial: "NUMERO SERIE",
      th_medium: "MEDIUM",
      th_ip_addr: "INDIRIZZO IP",
      th_hostname: "HOSTNAME / NETBIOS",
      th_first_seen: "PRIMO RILEVAMENTO",
      th_oui_vendor: "OUI VENDOR",
      btn_details: "Dettagli",

      // Live Console
      console_title: "Live Log",
      console_scroll: "Scroll",
      console_clear: "Pulisci",
      console_export: "export.txt",
      console_waiting: "In attesa di nuovi eventi o scansione periodica…",
      console_prompt_placeholder: "Invia comando rapido (es: ping 192.168.1.1, status, clear)",

      // Unified Settings Modal
      settings_title: "Centro Impostazioni & Configurazione",
      settings_sub: "Gestione centralizzata hardware, motori di scansione, lingua, sessioni salvate e mappe.",
      tab_hw: "Hardware & Porte",
      tab_scan: "Parametri Scansione",
      tab_appearance: "Aspetto & Lingua",
      tab_sessions: "Sessioni Salvate",
      tab_maps: "Mappe BACS Help",
      site_name_label: "Nome Sito / Impianto",
      rs485_box_title: "Porta Seriale RS485",
      btn_scan_ports: "Scansiona Porte",
      selected_port: "Porta selezionata",
      baudrate_label: "Baudrate",
      parity_label: "Parità",
      stopbits_label: "Stop Bit",
      net_box_title: "Interfacce di Rete (NIC)",
      btn_scan_nics: "Scansiona NIC",
      scan_nic_label: "NIC Scansione",
      client_nic_label: "NIC Client",
      btn_apply_config: "Applica Configurazione",
      btn_close: "Chiudi",
      btn_cancel: "Annulla",

      // Scan Parameters Tab
      rtu_timeout_slow: "Timeout Iniziale Modbus RTU (s)",
      rtu_timeout_fast: "Fast Timeout dopo LOCK (s)",
      spy_ids_label: "Spy IDs per Early Exit (separati da virgola)",
      cfg_tcp_port_default: "Porta default Modbus TCP (es. 502)",
      cfg_bacnet_port_default: "Porta default BACnet/IP (es. BAC0 o 47808)",
      cfg_knx_port_default: "Porta default KNXnet/IP (es. 3671)",
      knx_multicast_label: "Gruppo Multicast KNX",
      knx_timeout_label: "Finestra di Ascolto KNX (s)",
      arp_duration_default: "Durata default Sniffer ARP (s)",

      // Appearance & Language Tab
      lang_selection_label: "Lingua dell'Interfaccia",
      theme_selection_label: "Tema Grafico",
      console_buffer_label: "Buffer Retention Console (righe massime)",

      // Saved Sessions Tab
      save_current_btn: "Salva Sessione Corrente",
      session_name_placeholder: "Nome sessione (es. Cliente Rossi - Imp. 3)",
      saved_sessions_list_title: "Archivio Sessioni di Collaudo",
      col_session_name: "Nome Sessione",
      col_date: "Data Salvataggio",
      col_devices: "Dispositivi",
      col_actions: "Azioni",
      btn_restore: "Ripristina",
      btn_download_json: "JSON",
      btn_delete: "Elimina",
      no_saved_sessions: "Nessuna sessione salvata presente in archivio.",

      // Point Maps Tab
      maps_title: "Definizioni Registri & Mappe BACS Help",
      maps_sub: "Importa ed esporta tabelle di punti registri per arricchire i dispositivi Modbus.",
      btn_import_maps: "Importa JSON",
      btn_export_maps: "Esporta JSON",
      btn_clear_maps: "Svuota Mappe",
      loaded_maps_count: "Mappe caricate per {n} slave ID.",
      no_maps_loaded: "Nessuna mappa BACS Help caricata. Importa un file JSON per visualizzare i punti.",

      // Slave Details Modal
      slave_details_title: "Dettagli Dispositivo Modbus Slave #{id}",
      protocol_lbl: "Protocollo:",
      endpoint_lbl: "Endpoint:",
      response_time_lbl: "Tempo di risposta:",
      vendor_lbl: "Costruttore:",
      model_lbl: "Modello:",
      registers_mapped_title: "Registri Mappati (BACS Help)",
      no_registers_mapped: "Nessun registro associato a questo Slave ID nella mappa BACS Help attiva.",

      // Help Modal
      help_title: "Manuale Tecnico & Guida di Campo BHAM",
      help_sub: "Manuale operativo completo per il collaudo e la diagnosi di reti BACS.",

      // Session Diff
      btn_diff: "Diff Impianto",
      diff_modal_title: "Intelligence & Session Diff (\"Prima vs Dopo\")",
      diff_baseline_label: "Baseline (Sessione Storica / Prima):",
      diff_target_label: "Target (Sessione Attuale / Dopo):",
      diff_run_btn: "Calcola Differenze",
      diff_stat_added: "Nuovi / Aggiunti",
      diff_stat_removed: "Assenti / Scomparsi",
      diff_stat_modified: "Modificati / Variazioni",
      diff_stat_unchanged: "Invariati",
      diff_select_prompt: "Seleziona la sessione di Baseline e clicca su \"Calcola Differenze\" per confrontare l'impianto.",
      diff_col_device: "Dispositivo",
      diff_col_status: "Stato Variazione",
      diff_col_details: "Dettaglio Parametri / Modifiche Rilevate",
      diff_export_csv: "Esporta Diff CSV",
      diff_export_json: "Esporta Diff JSON",

      // BBMD & Foreign Device
      bbmd_traversal_title: "Router BBMD (Foreign Dev)",
      bbmd_ip_label: "IP Router BBMD",
      bbmd_port_label: "Porta",
      bbmd_ttl_label: "TTL Registrazione (s)",
      btn_inspect_bbmd: "Tabelle BDT/FDT",
      bbmd_modal_title: "Diagnostica Router BBMD (BACnet/IP)",
      bbmd_query_btn: "Interroga Tabelle BBMD",
      bbmd_bdt_title: "Broadcast Distribution Table (BDT)",
      bbmd_fdt_title: "Foreign Device Table (FDT)",
      bbmd_bdt_desc: "Elenco router BBMD peer per inoltro broadcast tra subnet IP.",
      bbmd_fdt_desc: "Dispositivi e workstation temporaneamente registrati come Foreign Device.",
      bbmd_col_mask: "Maschera Broadcast",
      bbmd_col_ttl: "TTL (s)",
      bbmd_col_remaining: "Rimanente (s)",
      bbmd_missing_ip_alert: "Inserisci un indirizzo IP valido per il router BBMD.",
    },

    en: {
      // Header & Brand
      brand_sub: "BACS Help Auto Mapper v0.6.0",
      rapid_scan: "START RAPID SCAN",
      rapid_scan_title: "Start automated sequential scan RTU + BACnet + KNX + ARP",
      abort_scan: "ABORT SCAN",
      abort_scan_title: "Immediately halt all active discovery scans",
      save: "Save",
      sessions: "Sessions",
      settings: "Settings",
      help: "Manual & Help",
      api_docs: "API / Docs",
      theme_light: "Light",
      theme_dark: "Dark",

      // Telemetry Strip
      status_ready: "Ready – {n} active devices on field",
      status_running: "Scan in progress ({proto}) – {n} cataloged",
      status_completed: "Completed – {n} found ({pct}%)",
      status_aborted: "Scan halted by operator (Abort)",
      scan_duration: "Scan duration:",
      active_tag: "ACTIVE:",
      active_site_lbl: "Site:",
      active_rs485_lbl: "RS485:",
      active_nic_lbl: "NIC:",
      edit_params_hint: "Click to open configuration",

      // Sidebar Cards
      site_plant_lbl: "Site / Plant:",
      modbus_rtu_title: "Modbus RTU (RS485)",
      slave_id_range: "Slave ID Range",
      timeout_ms: "Timeout (ms)",
      btn_start_rtu: "Start RTU",
      modbus_tcp_title: "Modbus TCP",
      tcp_hosts_label: "Hosts (one per line or CIDR)",
      tcp_port_label: "TCP Port (or list)",
      btn_start_tcp: "Start TCP",
      bacnet_title: "BACnet/IP",
      iface_label: "Interface",
      udp_port_label: "UDP Port",
      bacnet_port_label: "Port / Symbol",
      btn_start_bacnet: "Who-Is Broadcast",
      knx_title: "KNXnet/IP Discovery",
      btn_start_knx: "Start KNX Discovery",
      arp_title: "ARP Sniffer",
      duration_sec: "Duration (sec)",
      btn_start_arp: "Start Sniffing",
      fc43_title: "FC43 Device ID (Modbus MEI)",
      serial_port_label: "Serial Port",
      slave_id_label: "Slave ID",
      btn_run_fc43: "Read FC43",
      serial_sniff_title: "Passive Sniffer (RS485)",
      zero_tx_badge: "Zero-TX Stealth",
      protocol_label: "Protocol",
      baud_label: "Baudrate",
      duration_label: "Duration",
      opt_proto_auto: "Auto-Detect",
      opt_baud_auto: "Auto-Baud",
      opt_parity_auto: "Auto",
      opt_dur_continuous: "Continuous (∞)",
      btn_start_sniff: "Start Passive Sniff (RS485)",
      btn_open_inspector: "Show RS485 Frames",
      console_tab_log: "Live Log",
      console_tab_inspector: "RS485 Inspector",
      console_reduce: "Collapse",
      console_expand: "Console",
      btn_toggle_console: "Console & Sniffer",
      btn_clear_cache: "Clear Cache",
      btn_bacs_maps: "BACS Maps",

      // View Switcher & Topology Map
      view_table: "Tables",
      view_topology: "Topology Map",
      view_table_title: "Switch to device tables view",
      view_topology_title: "Switch to interactive network topology map",
      topo_zoom_in: "Zoom In (+)",
      topo_zoom_out: "Zoom Out (-)",
      topo_fit: "Fit to Screen",
      topo_layout_h: "Horizontal Tree",
      topo_layout_v: "Vertical Tree",
      topo_export_svg: "Export SVG",
      topo_legend_host: "Host / Gateway",
      topo_legend_interface: "Interface",
      topo_legend_bus: "Protocol Bus",
      topo_legend_device: "Device / Node",
      topo_inspector_title: "Node Details",
      topo_inspector_close: "Close",
      topo_node_type: "Type:",
      topo_node_proto: "Protocol:",
      topo_node_parent: "Connected to:",
      topo_node_status: "Status:",
      topo_btn_modbus_details: "🔍 Slave Details / Map",
      topo_btn_smart_scan: "⚡ Register Auto-Scan",
      topo_btn_bacnet_objects: "🔍 Explore Objects",
      topo_btn_show_table: "📋 Show in Table",
      topo_filter_all: "All Channels",
      topo_empty_title: "Topology Ready for Commissioning",
      topo_empty_desc: "BHAM host and hardware interfaces are standby. Launch a scan to visualize discovered devices on the network graph.",

      // Center Tabs & Tables
      tab_all: "All",
      tab_modbus: "Modbus",
      tab_bacnet: "BACnet",
      tab_knx: "KNX",
      tab_hosts: "ARP Hosts",
      export_csv: "CSV",
      export_excel: "Excel",
      export_pdf: "PDF",
      search_placeholder: "Filter by IP, Vendor, Model, Register/KNX address...",

      // Table Headers
      th_id: "ID",
      th_protocol: "PROTOCOL",
      th_endpoint: "ENDPOINT",
      th_latency: "MS",
      th_vendor_model: "VENDOR / MODEL",
      th_status: "STATUS",
      th_actions: "ACTIONS",
      th_dev_id: "DEV ID",
      th_mac_address: "MAC / ADDRESS",
      th_vendor: "VENDOR",
      th_model: "MODEL",
      th_fw_rev: "FW REV",
      th_obj_count: "OBJ COUNT",
      th_indiv_addr: "INDIV ADDR",
      th_dev_name: "DEVICE NAME",
      th_serial: "SERIAL NUMBER",
      th_medium: "MEDIUM",
      th_ip_addr: "IP ADDRESS",
      th_hostname: "HOSTNAME / NETBIOS",
      th_first_seen: "FIRST SEEN",
      th_oui_vendor: "OUI VENDOR",
      btn_details: "Details",

      // Live Console
      console_title: "Live Log",
      console_scroll: "Scroll",
      console_clear: "Clear",
      console_export: "export.txt",
      console_waiting: "Waiting for events or periodic scans…",
      console_prompt_placeholder: "Enter quick command (e.g. ping 192.168.1.1, status, clear)",

      // Unified Settings Modal
      settings_title: "Settings & Configuration Center",
      settings_sub: "Centralized management of hardware, scan engines, language, saved sessions and maps.",
      tab_hw: "Hardware & Ports",
      tab_scan: "Scan Parameters",
      tab_appearance: "Appearance & Language",
      tab_sessions: "Saved Sessions",
      tab_maps: "BACS Help Maps",
      site_name_label: "Site / Plant Name",
      rs485_box_title: "RS485 Serial Port",
      btn_scan_ports: "Scan Ports",
      selected_port: "Selected Port",
      baudrate_label: "Baudrate",
      parity_label: "Parity",
      stopbits_label: "Stop Bits",
      net_box_title: "Network Interfaces (NIC)",
      btn_scan_nics: "Scan NICs",
      scan_nic_label: "Scan NIC",
      client_nic_label: "Client NIC",
      btn_apply_config: "Apply Configuration",
      btn_close: "Close",
      btn_cancel: "Cancel",

      // Scan Parameters Tab
      rtu_timeout_slow: "Modbus RTU Initial Timeout (s)",
      rtu_timeout_fast: "Fast Timeout after LOCK (s)",
      spy_ids_label: "Early Exit Spy IDs (comma-separated)",
      cfg_tcp_port_default: "Default Modbus TCP Port (e.g. 502)",
      cfg_bacnet_port_default: "Default BACnet/IP Port (e.g. BAC0 or 47808)",
      cfg_knx_port_default: "Default KNXnet/IP Port (e.g. 3671)",
      knx_multicast_label: "KNX Multicast Group",
      knx_timeout_label: "KNX Listening Window (s)",
      arp_duration_default: "Default ARP Sniff Duration (s)",

      // Appearance & Language Tab
      lang_selection_label: "Interface Language",
      theme_selection_label: "Visual Theme",
      console_buffer_label: "Console Max Buffer Lines",

      // Saved Sessions Tab
      save_current_btn: "Save Current Session",
      session_name_placeholder: "Session name (e.g. Acme Corp - Bldg 3)",
      saved_sessions_list_title: "Commissioning Session Archive",
      col_session_name: "Session Name",
      col_date: "Saved Date",
      col_devices: "Devices",
      col_actions: "Actions",
      btn_restore: "Restore",
      btn_download_json: "JSON",
      btn_delete: "Delete",
      no_saved_sessions: "No saved sessions found in archive.",

      // Point Maps Tab
      maps_title: "Register Definitions & BACS Help Maps",
      maps_sub: "Import and export register point tables to enrich Modbus device telemetry.",
      btn_import_maps: "Import JSON",
      btn_export_maps: "Export JSON",
      btn_clear_maps: "Clear Maps",
      loaded_maps_count: "Point maps loaded for {n} slave IDs.",
      no_maps_loaded: "No point maps currently loaded in memory. Import a JSON file to see points.",

      // Slave Details Modal
      slave_details_title: "Modbus Slave #{id} Device Details",
      protocol_lbl: "Protocol:",
      endpoint_lbl: "Endpoint:",
      response_time_lbl: "Response time:",
      vendor_lbl: "Vendor:",
      model_lbl: "Model:",
      registers_mapped_title: "Mapped Registers (BACS Help)",
      no_registers_mapped: "No registers mapped for this Slave ID in active BACS Help map.",

      // Help Modal
      help_title: "BHAM Technical Manual & Field Guide",
      help_sub: "Comprehensive field operations handbook for BACS network commissioning and diagnosis.",

      // Session Diff
      btn_diff: "Plant Diff",
      diff_modal_title: "Intelligence & Session Diff (\"Before vs After\")",
      diff_baseline_label: "Baseline (Historical Session / Before):",
      diff_target_label: "Target (Current Session / After):",
      diff_run_btn: "Calculate Differences",
      diff_stat_added: "New / Added",
      diff_stat_removed: "Missing / Offline",
      diff_stat_modified: "Modified / Changes",
      diff_stat_unchanged: "Unchanged",
      diff_select_prompt: "Select Baseline session and click \"Calculate Differences\" to compare plant.",
      diff_col_device: "Device",
      diff_col_status: "Diff Status",
      diff_col_details: "Parameter Details / Detected Changes",
      diff_export_csv: "Export Diff CSV",
      diff_export_json: "Export Diff JSON",

      // BBMD & Foreign Device
      bbmd_traversal_title: "BBMD Router (Foreign Dev)",
      bbmd_ip_label: "BBMD Router IP",
      bbmd_port_label: "Port",
      bbmd_ttl_label: "Registration TTL (s)",
      btn_inspect_bbmd: "BDT/FDT Tables",
      bbmd_modal_title: "BBMD Router Diagnostics (BACnet/IP)",
      bbmd_query_btn: "Query BBMD Tables",
      bbmd_bdt_title: "Broadcast Distribution Table (BDT)",
      bbmd_fdt_title: "Foreign Device Table (FDT)",
      bbmd_bdt_desc: "List of peer BBMD routers for broadcast forwarding between IP subnets.",
      bbmd_fdt_desc: "Devices and workstations temporarily registered as Foreign Devices.",
      bbmd_col_mask: "Broadcast Mask",
      bbmd_col_ttl: "TTL (s)",
      bbmd_col_remaining: "Remaining (s)",
      bbmd_missing_ip_alert: "Enter a valid IP address for the BBMD router.",
    },

    es: {
      // Header & Brand
      brand_sub: "BACS Help Auto Mapper v0.6.0",
      rapid_scan: "INICIAR ESCANEO RÁPIDO",
      rapid_scan_title: "Iniciar escaneo secuencial RTU + BACnet + KNX + ARP",
      abort_scan: "ABORT SCAN",
      abort_scan_title: "Detener de inmediato todos los escaneos activos",
      save: "Guardar",
      sessions: "Sesiones",
      settings: "Configuración",
      help: "Manual y Ayuda",
      api_docs: "API / Docs",
      theme_light: "Claro",
      theme_dark: "Oscuro",

      // Telemetry Strip
      status_ready: "Listo – {n} dispositivos activos en campo",
      status_running: "Escaneo en curso ({proto}) – {n} catalogados",
      status_completed: "Completado – {n} encontrados ({pct}%)",
      status_aborted: "Escaneo detenido por el operador (Abort)",
      scan_duration: "Tiempo escaneo:",
      active_tag: "ACTIVO:",
      active_site_lbl: "Instalación:",
      active_rs485_lbl: "RS485:",
      active_nic_lbl: "NIC:",
      edit_params_hint: "Haga clic para abrir la configuración",

      // Sidebar Cards
      site_plant_lbl: "Sitio / Instalación:",
      modbus_rtu_title: "Modbus RTU (RS485)",
      slave_id_range: "Rango ID Slave",
      timeout_ms: "Timeout (ms)",
      btn_start_rtu: "Iniciar RTU",
      modbus_tcp_title: "Modbus TCP",
      tcp_hosts_label: "Hosts (uno por línea o CIDR)",
      tcp_port_label: "Puerto TCP (o lista)",
      btn_start_tcp: "Iniciar TCP",
      bacnet_title: "BACnet/IP",
      iface_label: "Interfaz",
      udp_port_label: "Puerto UDP",
      bacnet_port_label: "Puerto / Símbolo",
      btn_start_bacnet: "Who-Is Difusión",
      knx_title: "KNXnet/IP Discovery",
      btn_start_knx: "Iniciar KNX Discovery",
      arp_title: "Sniffer ARP",
      duration_sec: "Duración (seg)",
      btn_start_arp: "Iniciar Sniffing",
      fc43_title: "FC43 ID Dispositivo (Modbus MEI)",
      serial_port_label: "Puerto Serie",
      slave_id_label: "ID Slave",
      btn_run_fc43: "Leer FC43",
      serial_sniff_title: "Sniffer Pasivo (RS485)",
      zero_tx_badge: "Zero-TX Stealth",
      protocol_label: "Protocolo",
      baud_label: "Velocidad Baud",
      duration_label: "Duración",
      opt_proto_auto: "Auto-Detectar",
      opt_baud_auto: "Auto-Baud",
      opt_parity_auto: "Auto",
      opt_dur_continuous: "Continuo (∞)",
      btn_start_sniff: "Iniciar Escucha (RS485)",
      btn_open_inspector: "Ver Tramas RS485",
      console_tab_log: "Registro en Vivo",
      console_tab_inspector: "Inspector RS485",
      console_reduce: "Reducir",
      console_expand: "Consola",
      btn_toggle_console: "Consola y Sniffer",
      btn_clear_cache: "Limpiar Caché",
      btn_bacs_maps: "Mapas BACS",

      // View Switcher & Topology Map
      view_table: "Tablas",
      view_topology: "Mapa Topológico",
      view_table_title: "Ver vista de tablas de dispositivos",
      view_topology_title: "Ver mapa topológico interactivo de la planta",
      topo_zoom_in: "Acercar (+)",
      topo_zoom_out: "Alejar (-)",
      topo_fit: "Ajustar a Pantalla",
      topo_layout_h: "Árbol Horizontal",
      topo_layout_v: "Árbol Vertical",
      topo_export_svg: "Exportar SVG",
      topo_legend_host: "Host / Pasarela",
      topo_legend_interface: "Interfaz",
      topo_legend_bus: "Bus de Protocolo",
      topo_legend_device: "Dispositivo / Nodo",
      topo_inspector_title: "Detalle del Nodo",
      topo_inspector_close: "Cerrar",
      topo_node_type: "Tipo:",
      topo_node_proto: "Protocolo:",
      topo_node_parent: "Conectado a:",
      topo_node_status: "Estado:",
      topo_btn_modbus_details: "🔍 Detalles Slave / Mapa",
      topo_btn_smart_scan: "⚡ Auto-Scan Registros",
      topo_btn_bacnet_objects: "🔍 Explorar Objetos",
      topo_btn_show_table: "📋 Mostrar en Tabla",
      topo_filter_all: "Todos los Canales",
      topo_empty_title: "Topología Lista para Comisionamiento",
      topo_empty_desc: "El host BHAM y las interfaces de hardware están listos. Inicie un escaneo para visualizar los dispositivos en el mapa topológico.",

      // Center Tabs & Tables
      tab_all: "Todos",
      tab_modbus: "Modbus",
      tab_bacnet: "BACnet",
      tab_knx: "KNX",
      tab_hosts: "Hosts ARP",
      export_csv: "CSV",
      export_excel: "Excel",
      export_pdf: "PDF",
      search_placeholder: "Filtrar por IP, Fabricante, Modelo, Dirección registro/KNX...",

      // Table Headers
      th_id: "ID",
      th_protocol: "PROTOCOLO",
      th_endpoint: "ENDPOINT",
      th_latency: "MS",
      th_vendor_model: "FABRICANTE / MODELO",
      th_status: "ESTADO",
      th_actions: "ACCIONES",
      th_dev_id: "ID DEV",
      th_mac_address: "MAC / DIRECCIÓN",
      th_vendor: "FABRICANTE",
      th_model: "MODELO",
      th_fw_rev: "REV FW",
      th_obj_count: "CONTEO OBJ",
      th_indiv_addr: "DIR INDIV",
      th_dev_name: "NOMBRE DISPOSITIVO",
      th_serial: "NÚMERO SERIE",
      th_medium: "MEDIO",
      th_ip_addr: "DIRECCIÓN IP",
      th_hostname: "HOSTNAME / NETBIOS",
      th_first_seen: "PRIMER DETECCIÓN",
      th_oui_vendor: "FABRICANTE OUI",
      btn_details: "Detalles",

      // Live Console
      console_title: "Live Log",
      console_scroll: "Scroll",
      console_clear: "Limpiar",
      console_export: "export.txt",
      console_waiting: "Esperando eventos o escaneo periódico…",
      console_prompt_placeholder: "Comando rápido (ej: ping 192.168.1.1, status, clear)",

      // Unified Settings Modal
      settings_title: "Centro de Configuración & Ajustes",
      settings_sub: "Gestión centralizada de hardware, motores de escaneo, idioma, sesiones y mapas.",
      tab_hw: "Hardware y Puertos",
      tab_scan: "Parámetros de Escaneo",
      tab_appearance: "Apariencia e Idioma",
      tab_sessions: "Sesiones Guardadas",
      tab_maps: "Mapas BACS Help",
      site_name_label: "Nombre Sitio / Instalación",
      rs485_box_title: "Puerto Serie RS485",
      btn_scan_ports: "Escanear Puertos",
      selected_port: "Puerto seleccionado",
      baudrate_label: "Baudrate",
      parity_label: "Paridad",
      stopbits_label: "Bits de Parada",
      net_box_title: "Interfaces de Red (NIC)",
      btn_scan_nics: "Escanear NICs",
      scan_nic_label: "NIC de Escaneo",
      client_nic_label: "NIC de Cliente",
      btn_apply_config: "Aplicar Configuración",
      btn_close: "Cerrar",
      btn_cancel: "Cancelar",

      // Scan Parameters Tab
      rtu_timeout_slow: "Timeout Inicial Modbus RTU (s)",
      rtu_timeout_fast: "Fast Timeout tras LOCK (s)",
      spy_ids_label: "Spy IDs para Early Exit (separados por coma)",
      cfg_tcp_port_default: "Puerto predeterminado Modbus TCP (ej. 502)",
      cfg_bacnet_port_default: "Puerto predeterminado BACnet/IP (ej. BAC0 o 47808)",
      cfg_knx_port_default: "Puerto predeterminado KNXnet/IP (ej. 3671)",
      knx_multicast_label: "Grupo Multicast KNX",
      knx_timeout_label: "Ventana de Escucha KNX (s)",
      arp_duration_default: "Duración default Sniffer ARP (s)",

      // Appearance & Language Tab
      lang_selection_label: "Idioma de la Interfaz",
      theme_selection_label: "Tema Visual",
      console_buffer_label: "Líneas Máximas Buffer Consola",

      // Saved Sessions Tab
      save_current_btn: "Guardar Sesión Actual",
      session_name_placeholder: "Nombre de sesión (ej. Cliente García - Planta 2)",
      saved_sessions_list_title: "Archivo de Sesiones de Puesta en Marcha",
      col_session_name: "Nombre Sesión",
      col_date: "Fecha Guardado",
      col_devices: "Dispositivos",
      col_actions: "Acciones",
      btn_restore: "Restaurar",
      btn_download_json: "JSON",
      btn_delete: "Eliminar",
      no_saved_sessions: "No hay sesiones guardadas en el archivo.",

      // Point Maps Tab
      maps_title: "Definición de Registros y Mapas BACS Help",
      maps_sub: "Importe y exporte tablas de puntos de registros para enriquecer dispositivos Modbus.",
      btn_import_maps: "Importar JSON",
      btn_export_maps: "Exportar JSON",
      btn_clear_maps: "Vaciar Mapas",
      loaded_maps_count: "Mapas cargados para {n} slave IDs.",
      no_maps_loaded: "No hay mapas BACS Help cargados en memoria. Importe un archivo JSON para ver puntos.",

      // Slave Details Modal
      slave_details_title: "Detalles Dispositivo Modbus Slave #{id}",
      protocol_lbl: "Protocolo:",
      endpoint_lbl: "Endpoint:",
      response_time_lbl: "Tiempo de respuesta:",
      vendor_lbl: "Fabricante:",
      model_lbl: "Modelo:",
      registers_mapped_title: "Registros Mapeados (BACS Help)",
      no_registers_mapped: "No hay registros asociados a este Slave ID en el mapa BACS Help activo.",

      // Help Modal
      help_title: "Manual Técnico y Guía de Campo BHAM",
      help_sub: "Manual operativo completo para la puesta en marcha y diagnóstico de redes BACS.",

      // Session Diff
      btn_diff: "Diff Instalación",
      diff_modal_title: "Intelligence & Session Diff (\"Antes vs Después\")",
      diff_baseline_label: "Línea Base (Sesión Histórica / Antes):",
      diff_target_label: "Destino (Sesión Actual / Después):",
      diff_run_btn: "Calcular Diferencias",
      diff_stat_added: "Nuevos / Añadidos",
      diff_stat_removed: "Ausentes / Desconectados",
      diff_stat_modified: "Modificados / Variaciones",
      diff_stat_unchanged: "Sin cambios",
      diff_select_prompt: "Seleccione la sesión de Línea Base y haga clic en \"Calcular Diferencias\" para comparar la instalación.",
      diff_col_device: "Dispositivo",
      diff_col_status: "Estado Variación",
      diff_col_details: "Detalle Parámetros / Cambios Detectados",
      diff_export_csv: "Exportar Diff CSV",
      diff_export_json: "Exportar Diff JSON",

      // BBMD & Foreign Device
      bbmd_traversal_title: "Enrutador BBMD (Foreign Dev)",
      bbmd_ip_label: "IP Enrutador BBMD",
      bbmd_port_label: "Puerto",
      bbmd_ttl_label: "TTL Registro (s)",
      btn_inspect_bbmd: "Tablas BDT/FDT",
      bbmd_modal_title: "Diagnóstico de Enrutador BBMD (BACnet/IP)",
      bbmd_query_btn: "Consultar Tablas BBMD",
      bbmd_bdt_title: "Tabla de Distribución Broadcast (BDT)",
      bbmd_fdt_title: "Tabla de Dispositivos Externos (FDT)",
      bbmd_bdt_desc: "Lista de enrutadores BBMD pares para reenvío broadcast entre subredes IP.",
      bbmd_fdt_desc: "Dispositivos y estaciones registrados temporalmente como Foreign Device.",
      bbmd_col_mask: "Máscara Broadcast",
      bbmd_col_ttl: "TTL (s)",
      bbmd_col_remaining: "Restante (s)",
      bbmd_missing_ip_alert: "Ingrese una dirección IP válida para el enrutador BBMD.",
    }
  },

  /**
   * Traduce una chiave data per la lingua corrente, con interpolazione opzionale.
   */
  t(key, params = {}) {
    const dict = this.translations[this.currentLang] || this.translations.it;
    let str = dict[key] || this.translations.it[key] || key;
    for (const [k, v] of Object.entries(params)) {
      str = str.replace(new RegExp(`\\{${k}\\}`, "g"), v);
    }
    return str;
  },

  /**
   * Imposta la lingua corrente e applica le traduzioni al DOM.
   */
  setLanguage(lang) {
    if (!this.translations[lang]) lang = "it";
    this.currentLang = lang;
    localStorage.setItem("bham-lang", lang);
    document.documentElement.setAttribute("lang", lang);

    // Aggiorna lo stato visivo dei pulsanti del selettore
    document.querySelectorAll(".bham-lang-btn").forEach(btn => {
      const targetLang = btn.getAttribute("data-lang");
      if (targetLang === lang) {
        btn.classList.add("active");
      } else {
        btn.classList.remove("active");
      }
    });

    this.applyTranslations();

    // Aggiorna capitoli help se aperto
    if (typeof renderManualContent === "function") {
      renderManualContent();
    }
  },

  /**
   * Scansiona ed applica le traduzioni a tutti gli elementi marcati nel DOM.
   */
  applyTranslations() {
    // Testo interno
    document.querySelectorAll("[data-i18n]").forEach(el => {
      const key = el.getAttribute("data-i18n");
      const trans = this.t(key);
      if (trans) el.textContent = trans;
    });

    // Placeholders
    document.querySelectorAll("[data-i18n-placeholder]").forEach(el => {
      const key = el.getAttribute("data-i18n-placeholder");
      const trans = this.t(key);
      if (trans) el.setAttribute("placeholder", trans);
    });

    // Titles / Tooltips
    document.querySelectorAll("[data-i18n-title]").forEach(el => {
      const key = el.getAttribute("data-i18n-title");
      const trans = this.t(key);
      if (trans) el.setAttribute("title", trans);
    });
  },

  init() {
    const saved = localStorage.getItem("bham-lang") || "it";
    this.setLanguage(saved);
  }
};

window.I18N = I18N;
window.t = (key, params) => I18N.t(key, params);
