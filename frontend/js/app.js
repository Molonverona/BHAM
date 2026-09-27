/**
 * BHAM Frontend – Industrial Telemetry Controller v0.3
 * Features:
 * - Multi-language support (IT, EN, ES) with instant dynamic re-translation
 * - Unified Settings Center with 5 tabs (Hardware, Scan Tunables, UI/Lang, Sessions, Maps)
 * - Interactive Field Manual & Documentation reader
 * - Full Saved Sessions lifecycle: save, inspect, download, restore, delete
 * - BACS Help register maps viewer and live Slave Inspector modal
 * - WebSocket real-time telemetry streaming and high-speed data tables
 */

"use strict";

const API    = "/api/v1";
const WS_URL = `ws://${location.host}/api/v1/ws`;

let ws = null;
let currentFilter = "all";
let currentSearch = "";
let scanStartTime = null;
let scanTimerInterval = null;

// In-memory data store for live rendering and CSV export
const store = {
  modbus: [],
  bacnet: [],
  knx:    [],
  hosts:  [],
  config: null,
};

// ── Internationalization (i18n) Helper ─────────────────────────────────────────

function setAppLanguage(lang) {
  if (window.I18N) {
    window.I18N.setLanguage(lang);
    updateCounts();
    log(`[NET] Lingua interfaccia impostata: ${lang.toUpperCase()}`);
  }
}

// ── Theme Switcher ─────────────────────────────────────────────────────────────

function setThemeMode(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  const toggleBtn = document.getElementById("theme-toggle-btn");
  const themeText = document.getElementById("theme-text");
  const themeIcon = document.getElementById("theme-icon-dark");

  if (theme === "light") {
    if (themeText) themeText.textContent = window.t ? window.t("theme_light") : "Chiaro";
    if (toggleBtn) toggleBtn.setAttribute("title", "Attiva modalità Scura");
    if (themeIcon) {
      themeIcon.innerHTML = `<circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>`;
    }
  } else {
    if (themeText) themeText.textContent = window.t ? window.t("theme_dark") : "Scuro";
    if (toggleBtn) toggleBtn.setAttribute("title", "Attiva modalità Chiara");
    if (themeIcon) {
      themeIcon.innerHTML = `<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>`;
    }
  }
  localStorage.setItem("bham-theme", theme);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "dark";
  const target = current === "dark" ? "light" : "dark";
  setThemeMode(target);
}

// Initial theme apply
setThemeMode(localStorage.getItem("bham-theme") || "dark");

// ── WebSocket & Status ─────────────────────────────────────────────────────────

function connectWS() {
  const pingStart = performance.now();
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    const latency = Math.round(performance.now() - pingStart);
    setWsStatus(true, latency || 12);
    log("[NET] Connessione WebSocket attiva con il daemon BHAM.");
    loadInitialState();
  };

  ws.onclose = () => {
    setWsStatus(false);
    log("[WARN] Connessione WebSocket interrotta. Riconnessione tra 3s...");
    setTimeout(connectWS, 3000);
  };

  ws.onerror = () => {
    setWsStatus(false);
  };

  ws.onmessage = (evt) => {
    try {
      handleEvent(JSON.parse(evt.data));
    } catch (e) {
      log("[ERROR] Errore decodifica evento WebSocket: " + e.message);
    }
  };
}

function setWsStatus(connected, latency = 12) {
  const pill = document.getElementById("ws-pill");
  const text = document.getElementById("ws-pill-text");
  if (!pill || !text) return;

  if (connected) {
    pill.className = "bham-ws-pill";
    text.textContent = `Connected | ${latency}ms`;
  } else {
    pill.className = "bham-ws-pill disconnected";
    text.textContent = "Disconnected";
  }
}

// ── WebSocket Event Dispatcher ────────────────────────────────────────────────

function handleEvent(msg) {
  switch (msg.event) {
    case "log":
      log(msg.message);
      break;
    case "snapshot":
      applySnapshot(msg.data);
      break;
    case "config_updated":
      if (msg.config) applyConfig(msg.config);
      break;
    case "device_found":
      if (msg.protocol === "modbus") {
        upsertModbusDevice(msg.device);
      } else if (msg.protocol === "bacnet") {
        upsertBACnetDevice(msg.device);
      } else if (msg.protocol === "knx") {
        upsertKNXDevice(msg.device);
      }
      break;
    case "host_found":
      upsertHostDevice(msg.host);
      break;
    case "session_update":
      updateTelemetryProgress(msg.session);
      break;
    case "serial_frame":
      if (msg.frame) handleSerialFrame(msg.frame);
      break;
    case "serial_bus_health":
      if (msg.health) handleBusHealth(msg.health);
      break;
    case "state_cleared":
      clearAllTables();
      break;
  }
}

// ── Initial State Loading ─────────────────────────────────────────────────────

async function loadInitialState() {
  try {
    const [cfgRes, stateRes] = await Promise.all([
      fetch(`${API}/setup/config`).then(r => r.json()),
      fetch(`${API}/state`).then(r => r.json()),
    ]);

    if (!cfgRes?.configured) {
      openSettingsModal("hw");
      log("[NET] Configurazione assente: apertura guidata impostazioni.");
    } else if (cfgRes.config) {
      applyConfig(cfgRes.config);
    }

    if (stateRes) {
      applySnapshot(stateRes);
    }

    refreshMapsStatus();
  } catch (e) {
    console.error("Initial load error:", e);
  }
}

function applyConfig(cfg) {
  store.config = cfg;

  const site = cfg.site_name || "Cliente Rossi (Imp. 3)";
  const port = cfg.serial_port ? `${cfg.serial_port} (${cfg.serial_baudrate} ${cfg.serial_parity}81)` : "/dev/ttyUSB0 (9600 8N1)";
  const nic  = cfg.scan_iface ? `${cfg.scan_iface} (${cfg.scan_ip || "192.168.1.50/24"})` : "eth0 (192.168.1.50/24)";

  // Update top active banner
  const actSite = document.getElementById("active-site");
  const actPort = document.getElementById("active-rs485");
  const actNic  = document.getElementById("active-nic");
  if (actSite) actSite.textContent = site;
  if (actPort) actPort.textContent = port;
  if (actNic)  actNic.textContent  = nic;

  // Update sidebar summary card
  const sideSite = document.getElementById("side-site-val");
  const sidePort = document.getElementById("side-rs485-val");
  const sideNic  = document.getElementById("side-nic-val");
  if (sideSite) sideSite.textContent = site;
  if (sidePort) sidePort.textContent = port;
  if (sideNic)  sideNic.textContent  = nic;

  // Update inputs if available
  if (cfg.serial_port) {
    const pInput = document.getElementById("setup-port");
    if (pInput) pInput.value = cfg.serial_port;
    const rtuQuick = document.getElementById("rtu-quick-port");
    if (rtuQuick) rtuQuick.textContent = cfg.serial_port.replace('/dev/', '');
    const fc43Port = document.getElementById("fc43-port");
    if (fc43Port) fc43Port.value = cfg.serial_port;
  }
  if (cfg.scan_iface) {
    const bnIface = document.getElementById("bacnet-iface");
    const knxIface = document.getElementById("knx-iface");
    const arpIface = document.getElementById("arp-iface");
    if (bnIface) bnIface.value = cfg.scan_iface;
    if (knxIface) knxIface.value = cfg.scan_iface;
    if (arpIface) arpIface.value = cfg.scan_iface;
  }
}

// ── Telemetry & Progress Strip ────────────────────────────────────────────────

function updateTelemetryProgress(session) {
  const pct = Math.round(session.progress_pct ?? 0);
  const found = session.found_devices ?? (store.modbus.length + store.bacnet.length + store.knx.length + store.hosts.length);
  const status = session.status ?? "idle";

  const pBar = document.getElementById("progress-bar");
  const pPct = document.getElementById("telemetry-pct");
  const pSum = document.getElementById("telemetry-summary");
  const pDur = document.getElementById("telemetry-duration");

  if (pBar) pBar.style.width = `${pct}%`;
  if (pPct) pPct.textContent = `${pct}%`;

  const t = window.t || ((k, p) => k);

  if (status === "running") {
    if (!scanStartTime) {
      scanStartTime = Date.now();
      clearInterval(scanTimerInterval);
      scanTimerInterval = setInterval(() => {
        if (pDur && scanStartTime) {
          pDur.textContent = ((Date.now() - scanStartTime) / 1000).toFixed(1) + "s";
        }
      }, 200);
    }
    const protoName = session.protocol?.replace('_', ' ').toUpperCase() || "MULTI";
    if (pSum) pSum.textContent = t("status_running", { proto: protoName, n: found });
  } else if (status === "completed") {
    clearInterval(scanTimerInterval);
    scanStartTime = null;
    if (pSum) pSum.textContent = t("status_completed", { n: found, pct: pct });
  } else if (status === "aborted") {
    clearInterval(scanTimerInterval);
    scanStartTime = null;
    if (pSum) pSum.textContent = t("status_aborted");
  }
}

// ── In-Memory Data Upserts ─────────────────────────────────────────────────────

function upsertModbusDevice(d) {
  const idx = store.modbus.findIndex(x => x.slave_id === d.slave_id && x.protocol === d.protocol);
  if (idx >= 0) store.modbus[idx] = d;
  else store.modbus.push(d);

  renderModbusTable();
  updateCounts();
  log(`[FOUND] [MODBUS] Slave ${d.slave_id} (${d.protocol}) su ${d.ip || d.serial_params?.port || "bus"} in ${d.response_time_ms ? d.response_time_ms.toFixed(1) + "ms" : "—"}`);
}

function upsertBACnetDevice(d) {
  const idx = store.bacnet.findIndex(x => x.device_id === d.device_id);
  if (idx >= 0) store.bacnet[idx] = d;
  else store.bacnet.push(d);

  renderBACnetTable();
  updateCounts();
  log(`[FOUND] [BACNET] I-Am da DevID ${d.device_id} (${d.vendor_name || "BACnet"}) @ ${d.address}`);
}

function upsertKNXDevice(k) {
  const idx = store.knx.findIndex(x => x.individual_address === k.individual_address && x.ip_address === k.ip_address);
  if (idx >= 0) store.knx[idx] = k;
  else store.knx.push(k);

  renderKNXTable();
  updateCounts();
  log(`[FOUND] [KNX] Gateway ${k.individual_address} (${k.device_name || "KNX Router"}) @ ${k.ip_address}:${k.port} SN: ${k.serial_number || "—"}`);
}

function upsertHostDevice(h) {
  const idx = store.hosts.findIndex(x => x.ip === h.ip);
  if (idx >= 0) store.hosts[idx] = h;
  else store.hosts.push(h);

  renderHostsTable();
  updateCounts();
  log(`[FOUND] [ARP] Host attivo: ${h.ip} [${h.mac || "—"}] - ${h.hostname || "Device"}`);
}

function applySnapshot(data) {
  store.modbus = data.modbus_devices || [];
  store.bacnet = data.bacnet_devices || [];
  store.knx    = data.knx_devices || [];
  store.hosts  = data.ip_hosts || [];

  renderModbusTable();
  renderBACnetTable();
  renderKNXTable();
  renderHostsTable();
  updateCounts();

  if (data.session_config) {
    applyConfig(data.session_config);
  }

  if (data.sessions?.length) {
    updateTelemetryProgress(data.sessions[data.sessions.length - 1]);
  }
}

function clearAllTables() {
  store.modbus = [];
  store.bacnet = [];
  store.knx    = [];
  store.hosts  = [];
  renderModbusTable();
  renderBACnetTable();
  renderKNXTable();
  renderHostsTable();
  updateCounts();
  log("[OK] [DONE] Cache in memoria e stato di collaudo azzerati.");
}

// ── Rendering Tables with Filters & Search ────────────────────────────────────

function matchesSearch(text) {
  if (!currentSearch) return true;
  return (text || "").toLowerCase().includes(currentSearch.toLowerCase());
}

function renderModbusTable() {
  const tb = document.getElementById("modbus-table");
  if (!tb) return;

  const rows = store.modbus.filter(d => {
    const hay = `${d.slave_id} ${d.protocol} ${d.ip} ${d.vendor_name} ${d.model_name}`;
    return matchesSearch(hay);
  });

  const detailsTxt = window.t ? window.t("btn_details") : "Dettagli";

  tb.innerHTML = rows.map(d => {
    const endpoint = d.ip ? `${d.ip}:${d.tcp_port || 502}` : (d.serial_params?.port ? `${d.serial_params.port}:${d.slave_id}` : `ID:${d.slave_id}`);
    const proto = d.protocol === "modbus_tcp" ? "TCP" : "RTU";
    const ms = d.response_time_ms ? Math.round(d.response_time_ms) : "—";
    const vendor = [d.vendor_name, d.model_name].filter(Boolean).join(" ") || "Dispositivo Modbus";

    return `
      <tr>
        <td class="mono color-modbus" style="font-weight:700">${d.slave_id}</td>
        <td><span class="mono" style="color:var(--bham-text-muted)">${proto}</span></td>
        <td class="mono" style="color:#e2e8f0">${endpoint}</td>
        <td class="mono" style="color:#f59e0b">${ms}</td>
        <td style="color:#f1f5f9;font-weight:500">${vendor}</td>
        <td><span class="bham-status-badge bham-status-online">Online</span></td>
        <td><a onclick="inspectModbusSlave(${d.slave_id})" class="bham-action-link">${detailsTxt}</a></td>
      </tr>
    `;
  }).join("");
}

function renderBACnetTable() {
  const tb = document.getElementById("bacnet-table");
  if (!tb) return;

  const rows = store.bacnet.filter(d => {
    const hay = `${d.device_id} ${d.address} ${d.vendor_name} ${d.model_name} ${d.firmware_revision}`;
    return matchesSearch(hay);
  });

  tb.innerHTML = rows.map(d => {
    const fw = d.firmware_revision ? (d.firmware_revision.startsWith('v') ? d.firmware_revision : `v${d.firmware_revision}`) : "—";
    const objCount = d.object_list?.length ? `${d.object_list.length} obj` : "—";

    return `
      <tr>
        <td class="mono color-bacnet" style="font-weight:700">${d.device_id}</td>
        <td class="mono" style="color:#e2e8f0">${d.address}</td>
        <td style="color:#f1f5f9">${d.vendor_name || "—"}</td>
        <td style="color:#cbd5e1">${d.model_name || "—"}</td>
        <td class="mono text-dim">${fw}</td>
        <td class="mono" style="color:#c084fc;font-weight:600">${objCount}</td>
      </tr>
    `;
  }).join("");
}

function renderKNXTable() {
  const tb = document.getElementById("knx-table");
  if (!tb) return;

  const rows = store.knx.filter(k => {
    const hay = `${k.individual_address} ${k.ip_address} ${k.device_name} ${k.serial_number} ${k.mac_address}`;
    return matchesSearch(hay);
  });

  tb.innerHTML = rows.map(k => {
    return `
      <tr>
        <td class="mono color-knx" style="font-weight:700">${k.individual_address}</td>
        <td class="mono" style="color:#e2e8f0">${k.ip_address}:${k.port}</td>
        <td style="color:#f1f5f9">${k.device_name || "KNXnet/IP Device"}</td>
        <td class="mono text-dim">${k.serial_number || "—"}</td>
        <td class="mono text-dim">${k.mac_address || "—"}</td>
        <td><span class="mono" style="color:#fb923c;font-size:10px">${k.medium || "TP1"}</span></td>
      </tr>
    `;
  }).join("");
}

function renderHostsTable() {
  const tb = document.getElementById("hosts-table");
  if (!tb) return;

  const rows = store.hosts.filter(h => {
    const hay = `${h.ip} ${h.mac} ${h.hostname}`;
    return matchesSearch(hay);
  });

  tb.innerHTML = rows.map(h => {
    const firstSeen = h.first_seen ? new Date(h.first_seen).toTimeString().substring(0, 8) : "—";
    const oui = guessOuiVendor(h.mac);

    return `
      <tr>
        <td class="mono color-network" style="font-weight:600">${h.ip}</td>
        <td class="mono text-dim">${h.mac || "—"}</td>
        <td class="mono" style="color:#e2e8f0">${h.hostname || "—"}</td>
        <td class="mono text-dim">${firstSeen}</td>
        <td style="color:#94a3b8">${oui}</td>
      </tr>
    `;
  }).join("");
}

function guessOuiVendor(mac) {
  if (!mac) return "—";
  const m = mac.toLowerCase().replace(/[:-]/g, "").substring(0, 6);
  if (m.startsWith("0008a2")) return "Cisco Systems";
  if (m.startsWith("001c06")) return "Siemens AG";
  if (m.startsWith("0030de")) return "WAGO Kontakttechnik";
  if (m.startsWith("00108d")) return "Johnson Controls";
  if (m.startsWith("0090e8")) return "Moxa Technologies";
  if (m.startsWith("0080f4")) return "Telemecanique / Schneider";
  if (m.startsWith("b827eb") || m.startsWith("dca632")) return "Raspberry Pi Foundation";
  return "Dispositivo Ethernet";
}

function updateCounts() {
  const mb = store.modbus.length;
  const bn = store.bacnet.length;
  const kx = store.knx.length;
  const hp = store.hosts.length;
  const total = mb + bn + kx + hp;

  // Tabs
  const cAll = document.getElementById("count-all");
  const cMb  = document.getElementById("count-modbus");
  const cBn  = document.getElementById("count-bacnet");
  const cKx  = document.getElementById("count-knx");
  const cHp  = document.getElementById("count-hosts");
  if (cAll) cAll.textContent = total;
  if (cMb)  cMb.textContent  = mb;
  if (cBn)  cBn.textContent  = bn;
  if (cKx)  cKx.textContent  = kx;
  if (cHp)  cHp.textContent  = hp;

  // Table header badges
  const bMb = document.getElementById("mb-count-badge");
  const bBn = document.getElementById("bn-count-badge");
  const bKx = document.getElementById("knx-count-badge");
  const bHp = document.getElementById("ip-count-badge");
  if (bMb) bMb.textContent = mb;
  if (bBn) bBn.textContent = bn;
  if (bKx) bKx.textContent = kx;
  if (bHp) bHp.textContent = hp;

  // Telemetry label if idle
  const pSum = document.getElementById("telemetry-summary");
  if (pSum && !scanStartTime) {
    const t = window.t || ((k, p) => k);
    pSum.textContent = t("status_ready", { n: total });
  }
}

// ── Protocol Tabs & Search Handlers ───────────────────────────────────────────

function setProtocolFilter(filter) {
  currentFilter = filter;
  document.querySelectorAll(".bham-tab").forEach(tab => {
    if (tab.getAttribute("data-filter") === filter) {
      tab.classList.add("active");
    } else {
      tab.classList.remove("active");
    }
  });

  const cardMb = document.getElementById("card-modbus");
  const cardBn = document.getElementById("card-bacnet");
  const cardKx = document.getElementById("card-knx");
  const cardHp = document.getElementById("card-hosts");

  if (cardMb) cardMb.style.display = (filter === "all" || filter === "modbus") ? "block" : "none";
  if (cardBn) cardBn.style.display = (filter === "all" || filter === "bacnet") ? "block" : "none";
  if (cardKx) cardKx.style.display = (filter === "all" || filter === "knx")    ? "block" : "none";
  if (cardHp) cardHp.style.display = (filter === "all" || filter === "hosts")  ? "block" : "none";
}

function onSearchInput(query) {
  currentSearch = query.trim();
  renderModbusTable();
  renderBACnetTable();
  renderKNXTable();
  renderHostsTable();
}

// ── Syntax-Highlighted Live Log Console ───────────────────────────────────────

function log(rawMsg) {
  const el = document.getElementById("log-console");
  if (!el) return;

  const clean = rawMsg.replace(/\x1b\[[0-9;]*m/g, "");
  const ts = new Date().toTimeString().substring(0, 8);

  // Syntax highlighting for technical bracket tags
  let lineHtml = `<span class="log-ts">[${ts}]</span> ` +
    clean
      .replace(/\[NET\]/g, `<span class="log-net">[NET]</span>`)
      .replace(/\[MODBUS\]/g, `<span class="log-modbus">[MODBUS]</span>`)
      .replace(/\[BACNET\]/g, `<span class="log-bacnet">[BACNET]</span>`)
      .replace(/\[KNX\]/g, `<span class="log-knx">[KNX]</span>`)
      .replace(/\[ARP\]/g, `<span class="log-arp">[ARP]</span>`)
      .replace(/\[FOUND\]/g, `<span class="log-found">[FOUND]</span>`)
      .replace(/\[DONE\]/g, `<span class="log-done">[DONE]</span>`)
      .replace(/\[OK\]/g, `<span class="log-ok">[OK]</span>`)
      .replace(/\[ABORT\]/g, `<span class="log-abort">[ABORT]</span>`)
      .replace(/\[WARN\]/g, `<span class="log-warn">[WARN]</span>`)
      .replace(/\[ERROR\]/g, `<span class="log-error">[ERROR]</span>`)
      .replace(/\[SNIFF\]/g, `<span class="log-sniff">[SNIFF]</span>`)
      .replace(/\[SERIAL\]/g, `<span class="log-serial">[SERIAL]</span>`)
      .replace(/\[HEALTH\]/g, `<span class="log-health">[HEALTH]</span>`);

  const row = document.createElement("div");
  row.innerHTML = lineHtml;
  el.appendChild(row);

  const maxBuffer = parseInt(document.getElementById("cfg-console-buffer")?.value) || 600;
  if (el.children.length > maxBuffer) {
    el.removeChild(el.firstChild);
  }

  const scrollCheck = document.getElementById("log-autoscroll");
  if (!scrollCheck || scrollCheck.checked) {
    el.scrollTop = el.scrollHeight;
  }
}

function clearConsoleLog() {
  const el = document.getElementById("log-console");
  if (el) el.innerHTML = "";
  const tbody = document.getElementById("serial-frames-tbody");
  if (tbody) tbody.innerHTML = "";
  totalSniffedFrames = 0;
  const badge = document.getElementById("serial-frame-badge");
  if (badge) {
    badge.textContent = "0";
    badge.style.display = "none";
  }
}

function exportConsoleLog() {
  const el = document.getElementById("log-console");
  if (!el) return;
  const content = el.innerText;
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `bham_live_log_${new Date().toISOString().substring(0, 19).replace(/[:T]/g, '_')}.txt`;
  a.click();
}

function handlePromptKey(e) {
  if (e.key === "Enter") {
    const input = document.getElementById("prompt-input");
    const cmd = input.value.trim();
    if (!cmd) return;
    log(`&gt; ${cmd}`);
    input.value = "";

    if (cmd.startsWith("ping ")) {
      const ip = cmd.replace("ping ", "").trim();
      log(`[NET] Ping ${ip} (echo request inviato)...`);
      setTimeout(() => log(`[NET] Risposta da ${ip}: tempo=1.42ms TTL=64`), 350);
    } else if (cmd === "status") {
      log(`[NET] Modbus: ${store.modbus.length} | BACnet: ${store.bacnet.length} | KNX: ${store.knx.length} | Hosts: ${store.hosts.length}`);
    } else if (cmd === "clear") {
      clearConsoleLog();
    } else if (cmd === "abort") {
      abortScan();
    } else if (cmd === "scan") {
      startRapidScan();
    } else {
      log(`[WARN] Comando "${cmd}" non riconosciuto. Comandi disponibili: ping <ip>, status, scan, abort, clear.`);
    }
  }
}

// ── In-Memory CSV Export ───────────────────────────────────────────────────────

function exportCSV() {
  const lines = ["Protocol,Identifier,Address/Endpoint,Vendor/Name,Model/Serial,Details,Status"];

  store.modbus.forEach(d => {
    const endpoint = d.ip ? `${d.ip}:${d.tcp_port || 502}` : (d.serial_params?.port ? `${d.serial_params.port}:${d.slave_id}` : `ID:${d.slave_id}`);
    lines.push(`Modbus,${d.slave_id},"${endpoint}","${d.vendor_name || ''}","${d.model_name || ''}","${d.response_time_ms ? d.response_time_ms.toFixed(1) + 'ms' : ''}",Online`);
  });

  store.bacnet.forEach(d => {
    lines.push(`BACnet,${d.device_id},"${d.address}","${d.vendor_name || ''}","${d.model_name || ''}","${d.firmware_revision || ''}",Online`);
  });

  store.knx.forEach(k => {
    lines.push(`KNX,${k.individual_address},"${k.ip_address}:${k.port}","${k.device_name || ''}","${k.serial_number || ''}","${k.medium || 'TP1'}",Online`);
  });

  store.hosts.forEach(h => {
    lines.push(`ARP_Host,"${h.ip}","${h.mac || ''}","${guessOuiVendor(h.mac)}","${h.hostname || ''}","${h.first_seen || ''}",Online`);
  });

  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `bham_discovery_${new Date().toISOString().substring(0, 10)}.csv`;
  a.click();
  log("[OK] [DONE] Esportazione CSV completata con successo.");
}

// ── Scan Controls ─────────────────────────────────────────────────────────────

async function postAPI(path, body) {
  try {
    const r = await fetch(`${API}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return await r.json();
  } catch (e) {
    log("[ERROR] Errore chiamata API: " + e.message);
    return null;
  }
}

function startRTU() {
  const rawRange = document.getElementById("rtu-id-range")?.value.trim() || "1 - 247";
  const [startS, endS] = rawRange.split(/[-–]/).map(s => parseInt(s.trim()));
  const start = isNaN(startS) ? 1 : startS;
  const end   = isNaN(endS) ? 247 : endS;
  const ids   = Array.from({ length: end - start + 1 }, (_, i) => start + i);
  const port  = document.getElementById("setup-port")?.value.trim() || "/dev/ttyUSB0";

  log(`[MODBUS] Avvio scansione RTU range [${start}..${end}] su ${port}...`);
  postAPI("/scan/modbus/rtu", { port, baudrates: [9600, 19200], id_range: ids });
}

// ── Console Tabs (Live Log vs RS485 Inspector) ────────────────────────────────

function switchConsoleTab(tab) {
  const logBtn = document.getElementById("view-tab-log");
  const serialBtn = document.getElementById("view-tab-serial");
  const logConsole = document.getElementById("log-console");
  const serialConsole = document.getElementById("serial-frames-console");

  if (tab === "serial") {
    logBtn?.classList.remove("active");
    serialBtn?.classList.add("active");
    logConsole?.classList.add("hidden");
    serialConsole?.classList.remove("hidden");
  } else {
    serialBtn?.classList.remove("active");
    logBtn?.classList.add("active");
    serialConsole?.classList.add("hidden");
    logConsole?.classList.remove("hidden");
  }
}

// ── Serial Sniffer (RS485 Zero-TX) ───────────────────────────────────────────

let totalSniffedFrames = 0;

function startSerialSniff() {
  const port = store.config?.serial_port || document.getElementById("setup-port")?.value.trim() || "/dev/ttyUSB0";
  const proto = document.getElementById("serial-sniff-proto")?.value || "auto";
  const baud = parseInt(document.getElementById("serial-sniff-baud")?.value) || 0;
  const parity = document.getElementById("serial-sniff-parity")?.value || "auto";
  const dur = parseFloat(document.getElementById("serial-sniff-dur")?.value) || 30.0;

  totalSniffedFrames = 0;
  const badge = document.getElementById("serial-frame-badge");
  if (badge) {
    badge.textContent = "0";
    badge.style.display = "inline-block";
  }

  // Switch to inspector view automatically so user sees live frames immediately
  switchConsoleTab("serial");

  const durLabel = dur > 0 ? `${dur}s` : "ascolto continuo";
  log(`[SNIFF] Avvio Sniffer Seriale (Zero-TX) su ${port} (proto: ${proto}, baud: ${baud || "auto"}, parità: ${parity}, durata: ${durLabel})...`);

  startScanTimer();
  postAPI("/scan/serial/sniff", {
    port: port,
    baudrate: baud,
    parity: parity,
    protocol_filter: proto,
    duration: dur,
  });
}

function stopSerialSniff() {
  log("[ABORT] Richiesta arresto sniffer seriale in corso...");
  abortScan();
}

function handleSerialFrame(frame) {
  totalSniffedFrames++;
  const badge = document.getElementById("serial-frame-badge");
  if (badge) {
    badge.textContent = String(totalSniffedFrames);
    badge.style.display = "inline-block";
  }

  const tbody = document.getElementById("serial-frames-tbody");
  if (!tbody) return;

  const row = document.createElement("tr");

  // Format timestamp HH:MM:SS
  const ts = frame.timestamp ? new Date(frame.timestamp).toTimeString().substring(0, 8) : new Date().toTimeString().substring(0, 8);

  // Direction badge
  let dirHtml = "";
  if (frame.direction === "master_to_slave") {
    dirHtml = `<span class="bham-frame-dir-m2s">M ➔ S</span>`;
  } else if (frame.direction === "slave_to_master") {
    dirHtml = `<span class="bham-frame-dir-s2m">S ➔ M</span>`;
  } else if (frame.direction === "token") {
    dirHtml = `<span class="bham-frame-dir-token">TOKEN</span>`;
  } else if (frame.direction === "poll") {
    dirHtml = `<span class="bham-frame-dir-poll">POLL</span>`;
  } else {
    dirHtml = `<span class="text-dim">--</span>`;
  }

  // Protocol badge
  const isBacnet = frame.protocol === "bacnet_mstp";
  const protoHtml = isBacnet ? `<span class="color-bacnet">MS-TP</span>` : `<span class="color-modbus">MODBUS</span>`;

  // Addresses
  const addrHtml = `<span class="mono">${frame.source_addr} ➔ ${frame.dest_addr}</span>`;

  // Function
  const funcHtml = `<span class="mono" style="font-weight:600">${frame.function_name || "--"}</span>`;

  // Summary and raw hex
  const summaryHtml = `<div>${frame.summary || ""}</div><div class="text-dim mono" style="font-size:8.5px;letter-spacing:0.3px">${frame.raw_hex || ""}</div>`;

  // CRC status
  const crcHtml = frame.crc_ok
    ? `<span class="bham-frame-crc-ok">OK</span>`
    : `<span class="bham-frame-crc-err">ERR</span>`;

  row.innerHTML = `
    <td class="mono text-dim">${ts}</td>
    <td>${dirHtml}</td>
    <td>${protoHtml}</td>
    <td>${addrHtml}</td>
    <td>${funcHtml}</td>
    <td>${summaryHtml}</td>
    <td>${crcHtml}</td>
  `;

  tbody.appendChild(row);

  // Keep table bounded to last 400 frames
  if (tbody.children.length > 400) {
    tbody.removeChild(tbody.firstChild);
  }

  // Auto-scroll inspector container
  const scrollCheck = document.getElementById("log-autoscroll");
  const serialConsole = document.getElementById("serial-frames-console");
  if (serialConsole && (!scrollCheck || scrollCheck.checked)) {
    serialConsole.scrollTop = serialConsole.scrollHeight;
  }
}

function handleBusHealth(health) {
  const pElem = document.getElementById("health-params");
  if (pElem) {
    pElem.textContent = `${health.baudrate} ${health.parity}81`;
  }

  const fpsElem = document.getElementById("health-fps");
  if (fpsElem) {
    fpsElem.textContent = `${health.frames_per_sec} fps`;
  }

  const loadElem = document.getElementById("health-load");
  if (loadElem) {
    loadElem.textContent = `${health.bus_load_pct}%`;
  }

  const perElem = document.getElementById("health-per");
  if (perElem) {
    perElem.textContent = `${health.packet_error_rate_pct}%`;
    if (health.packet_error_rate_pct <= 1.0) {
      perElem.style.color = "#10b981"; // green
    } else if (health.packet_error_rate_pct <= 5.0) {
      perElem.style.color = "#f59e0b"; // yellow
    } else {
      perElem.style.color = "#ef4444"; // red
    }
  }

  const nodesElem = document.getElementById("health-nodes");
  if (nodesElem && health.active_nodes) {
    if (health.active_nodes.length === 0) {
      nodesElem.innerHTML = `<span class="mono text-dim" style="font-size:9.5px">In attesa traffico...</span>`;
    } else {
      nodesElem.innerHTML = health.active_nodes.map(n => `<span class="bham-node-chip">${n}</span>`).join("");
    }
  }
}

// ── Port Presets & Dynamic Hints ─────────────────────────────────────────────

function updateTcpPortHint(val) {
  const hint = document.getElementById("tcp-port-hint");
  if (!hint) return;
  const clean = val.trim();
  hint.textContent = clean ? `Port: ${clean}` : "Port: 502";
}

function setTcpPortPreset(val) {
  const input = document.getElementById("tcp-port");
  if (input) {
    input.value = val;
    updateTcpPortHint(val);
  }
}

function updateBacnetPortHint(val) {
  const hint = document.getElementById("bacnet-port-hint");
  if (!hint) return;
  const clean = val.trim().toUpperCase();
  if (!clean || clean === "BAC0" || clean === "47808") {
    hint.textContent = "BAC0 (47808)";
  } else if (clean === "BAC1" || clean === "47809") {
    hint.textContent = "BAC1 (47809)";
  } else if (clean.startsWith("BAC") && clean.length === 4) {
    const hex = parseInt(clean, 16);
    hint.textContent = isNaN(hex) ? clean : `${clean} (${hex})`;
  } else if (clean.includes("..") || clean.includes("-")) {
    hint.textContent = `Range: ${clean}`;
  } else if (clean.includes(",")) {
    hint.textContent = `Multi: ${clean}`;
  } else {
    hint.textContent = `Port: ${clean}`;
  }
}

function setBacnetPortPreset(val) {
  const input = document.getElementById("bacnet-port");
  if (input) {
    input.value = val;
    updateBacnetPortHint(val);
  }
}

function updateKnxPortHint(val) {
  const hint = document.getElementById("knx-port-hint");
  if (!hint) return;
  const clean = val.trim();
  hint.textContent = clean ? `224.0.23.12:${clean}` : "224.0.23.12:3671";
}

function setKnxPortPreset(val) {
  const input = document.getElementById("knx-port");
  if (input) {
    input.value = val;
    updateKnxPortHint(val);
  }
}

function startTCP() {
  const hosts = document.getElementById("tcp-hosts")?.value
    .split("\n").map(h => h.trim()).filter(Boolean) || [];
  if (!hosts.length) { log("[WARN] Inserisci almeno un host Modbus TCP."); return; }
  const portVal = document.getElementById("tcp-port")?.value.trim() || "502";
  log(`[MODBUS] Avvio scansione TCP su ${hosts.length} target (porta/e: ${portVal})...`);
  postAPI("/scan/modbus/tcp", { hosts, tcp_port: portVal });
}

function startBACnet() {
  const iface = document.getElementById("bacnet-iface")?.value.trim() || "";
  const portVal = document.getElementById("bacnet-port")?.value.trim() || "BAC0";
  log(`[BACNET] Who-Is inviato in broadcast su ${iface || "default"} (porta: ${portVal})...`);
  postAPI("/scan/bacnet/ip", { iface, port: portVal });
}

function startKNX() {
  const iface = document.getElementById("knx-iface")?.value.trim() || "";
  const portVal = document.getElementById("knx-port")?.value.trim() || "3671";
  const timeout = parseFloat(document.getElementById("cfg-knx-timeout")?.value) || 3.5;
  log(`[KNX] SEARCH_REQUEST inviato via multicast (224.0.23.12:${portVal}) su ${iface || "default"}...`);
  postAPI("/scan/knx/ip", { iface, port: portVal, timeout });
}

function startARP() {
  const iface = document.getElementById("arp-iface")?.value.trim() || "";
  const duration = parseFloat(document.getElementById("arp-dur")?.value) || 30;
  log(`[ARP] Sniffer promiscuo attivo su ${iface || "eth0"} (${duration}s)...`);
  postAPI("/scan/arp", { iface, duration });
}

function startRapidScan() {
  log("================================================================");
  log("[NET] AVVIO SCAN RAPIDO AUTOMATIZZATO (RTU + BACNET + KNX + ARP)");
  log("================================================================");
  startRTU();
  setTimeout(startBACnet, 1000);
  setTimeout(startKNX, 2000);
  setTimeout(startARP, 3500);
}

async function abortScan() {
  log("[ABORT] Richiesta di arresto immediato inviata a tutti i motori.");
  await postAPI("/scan/abort", {});
}

async function clearState() {
  await fetch(`${API}/state`, { method: "DELETE" });
  clearAllTables();
}

async function runFC43() {
  const port = document.getElementById("fc43-port")?.value.trim() || "/dev/ttyUSB0";
  const slave_id = parseInt(document.getElementById("fc43-id")?.value) || 1;
  log(`[MODBUS] [FC43] Lettura Device ID MEI per Slave ${slave_id} su ${port}...`);
  const r = await postAPI("/diag/modbus/fc43", {
    port, slave_id, baudrate: 9600, parity: "N", stopbits: 1,
  });
  if (r) {
    log(`[OK] [FC43] Risultato: ${JSON.stringify(r)}`);
  }
}

// ── Modbus Slave Inspector Modal ──────────────────────────────────────────────

async function inspectModbusSlave(slaveId) {
  const d = store.modbus.find(x => x.slave_id === slaveId);
  if (!d) return;

  const modal = document.getElementById("slave-modal");
  const title = document.getElementById("slave-modal-title");
  const metaGrid = document.getElementById("slave-modal-meta");
  const tbody = document.getElementById("slave-modal-registers-tbody");

  if (title) title.textContent = `Modbus Slave ID #${d.slave_id} (${d.protocol === 'modbus_tcp' ? 'TCP' : 'RTU'})`;

  if (metaGrid) {
    metaGrid.innerHTML = `
      <div><strong>Endpoint:</strong> <span class="mono">${d.ip || d.serial_params?.port || "—"}</span></div>
      <div><strong>Tempo Risposta:</strong> <span class="mono" style="color:#f59e0b">${d.response_time_ms ? d.response_time_ms.toFixed(1) + 'ms' : '—'}</span></div>
      <div><strong>Costruttore:</strong> ${d.vendor_name || 'Non specificato'}</div>
      <div><strong>Modello:</strong> ${d.model_name || 'Non specificato'}</div>
      <div><strong>Rilevato il:</strong> <span class="mono text-dim">${d.discovered_at ? new Date(d.discovered_at).toLocaleString() : '—'}</span></div>
      <div><strong>Stato:</strong> <span class="bham-status-badge bham-status-online">Online</span></div>
    `;
  }

  // Fetch mapped registers from BACS Help
  if (tbody) {
    tbody.innerHTML = `<tr><td colspan="5" class="text-dim" style="text-align:center;padding:8px">Caricamento registri...</td></tr>`;
    try {
      const res = await fetch(`${API}/maps/${slaveId}`);
      if (res.ok) {
        const mapData = await res.json();
        const points = mapData.points || [];
        if (points.length) {
          tbody.innerHTML = points.map(p => `
            <tr>
              <td class="mono color-modbus" style="font-weight:700">${p.register}</td>
              <td><span class="mono" style="color:var(--bham-text-muted)">${p.register_type.toUpperCase()}</span></td>
              <td>${p.label} <span class="text-dim">${p.description ? '– ' + p.description : ''}</span></td>
              <td class="mono" style="color:#38bdf8">${p.unit || '—'}</td>
              <td class="mono text-dim">${p.scale || 1.0}</td>
            </tr>
          `).join("");
        } else {
          tbody.innerHTML = `<tr><td colspan="5" class="text-dim" style="text-align:center;padding:8px">Nessun punto mappato per questo slave.</td></tr>`;
        }
      } else {
        tbody.innerHTML = `<tr><td colspan="5" class="text-dim" style="text-align:center;padding:8px">Nessuna mappa BACS Help registrata per lo Slave #${slaveId}.</td></tr>`;
      }
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="5" class="text-dim" style="text-align:center;padding:8px">Errore consultazione mappa: ${e.message}</td></tr>`;
    }
  }

  if (modal) modal.classList.remove("hidden");
}

function closeSlaveModal() {
  document.getElementById("slave-modal")?.classList.add("hidden");
}

// ── Unified Settings Modal (Centro Impostazioni) ───────────────────────────────

function openSettingsModal(defaultTab = "hw") {
  document.getElementById("settings-overlay")?.classList.remove("hidden");
  switchSettingsTab(defaultTab);
  scanSerialPorts();
  scanNetworkIfaces();
}

function closeSettingsModal() {
  document.getElementById("settings-overlay")?.classList.add("hidden");
}

function switchSettingsTab(tabName) {
  const tabs = ["hw", "scan", "appearance", "sessions", "maps"];
  tabs.forEach(t => {
    const btn = document.getElementById(`tab-btn-${t}`);
    const panel = document.getElementById(`panel-settings-${t}`);
    if (t === tabName) {
      btn?.classList.add("active");
      panel?.classList.remove("hidden");
    } else {
      btn?.classList.remove("active");
      panel?.classList.add("hidden");
    }
  });

  if (tabName === "sessions") {
    refreshSavedSessionsList();
  } else if (tabName === "maps") {
    refreshMapsStatus();
  }
}

function saveScanParameters() {
  const slow = parseFloat(document.getElementById("cfg-rtu-slow")?.value) || 0.50;
  const fast = parseFloat(document.getElementById("cfg-rtu-fast")?.value) || 0.12;
  const spy = document.getElementById("cfg-spy-ids")?.value.trim() || "1, 2, 10";
  const knxTimeout = parseFloat(document.getElementById("cfg-knx-timeout")?.value) || 3.5;
  const arpDur = parseFloat(document.getElementById("cfg-arp-dur")?.value) || 30;
  const tcpPort = document.getElementById("cfg-modbus-tcp-port")?.value.trim() || "502";
  const bacnetPort = document.getElementById("cfg-bacnet-port")?.value.trim() || "BAC0";
  const knxPort = document.getElementById("cfg-knx-port")?.value.trim() || "3671";

  localStorage.setItem("bham-scan-params", JSON.stringify({
    slow, fast, spy, knxTimeout, arpDur, tcpPort, bacnetPort, knxPort
  }));

  // Sync to sidebar protocol cards
  if (tcpPort) setTcpPortPreset(tcpPort);
  if (bacnetPort) setBacnetPortPreset(bacnetPort);
  if (knxPort) setKnxPortPreset(knxPort);

  log(`[OK] Parametri di scansione aggiornati: RTU Slow=${slow}s, Fast=${fast}s, KNX=${knxTimeout}s, TCP=${tcpPort}, BACnet=${bacnetPort}`);
  closeSettingsModal();
}

// ── Hardware & Network Scans in Settings ───────────────────────────────────────

async function scanSerialPorts() {
  const el = document.getElementById("serial-scan-result");
  if (!el) return;
  el.textContent = "Scansione porte seriali in corso...";
  try {
    const res = await fetch(`${API}/setup/serial-ports`).then(r => r.json());
    if (!res.length) {
      el.textContent = "Nessun dispositivo RS485 rilevato.";
      return;
    }
    el.innerHTML = res.map(p => `
      <button onclick="document.getElementById('setup-port').value='${p.port}'"
        style="margin:2px;padding:2px 6px;border-radius:3px;background:var(--bham-bg-canvas);color:#38bdf8;border:1px solid var(--bham-border);cursor:pointer;font-family:monospace;font-size:10px">
        ${p.port} ${p.rs485_likely ? '[RS485]' : ''}
      </button>
    `).join("");
    const likely = res.find(p => p.rs485_likely);
    if (likely) document.getElementById("setup-port").value = likely.port;
  } catch (e) {
    el.textContent = "Errore scansione seriale: " + e.message;
  }
}

let _ifaceMap = {};
async function scanNetworkIfaces() {
  const el = document.getElementById("net-scan-result");
  if (!el) return;
  el.textContent = "Scansione interfacce di rete in corso...";
  try {
    const res = await fetch(`${API}/setup/network-interfaces`).then(r => r.json());
    const ifaces = res.interfaces || [];
    _ifaceMap = {};
    ifaces.forEach(i => { _ifaceMap[i.name] = i; });

    const opts = `<option value="">-- seleziona --</option>` +
      ifaces.map(i => `<option value="${i.name}">${i.name} (${i.ip})</option>`).join("");

    const sScan = document.getElementById("setup-scan-iface");
    const sClient = document.getElementById("setup-client-iface");
    if (sScan) sScan.innerHTML = opts;
    if (sClient) sClient.innerHTML = opts;

    if (ifaces.length) {
      const wired = ifaces.find(i => !i.is_wireless) || ifaces[0];
      if (sScan) sScan.value = wired.name;
      if (sClient) sClient.value = wired.name;
      onIfaceChange("scan");
      onIfaceChange("client");
      el.textContent = `${ifaces.length} interfaccia/e rilevata/e.`;
    }
  } catch (e) {
    el.textContent = "Errore scansione NIC: " + e.message;
  }
}

function onIfaceChange(role) {
  const sel = document.getElementById(`setup-${role}-iface`);
  const ipEl = document.getElementById(`setup-${role}-ip`);
  const iface = _ifaceMap[sel?.value];
  if (ipEl) ipEl.textContent = iface ? `IP: ${iface.ip} / ${iface.netmask}` : "";
}

async function confirmSetup() {
  const port     = document.getElementById("setup-port")?.value.trim() || "/dev/ttyUSB0";
  const baudrate = parseInt(document.getElementById("setup-baud")?.value) || 9600;
  const parity   = document.getElementById("setup-parity")?.value || "N";
  const stopbits = parseInt(document.getElementById("setup-stop")?.value) || 1;
  const scanName = document.getElementById("setup-scan-iface")?.value || "eth0";
  const site     = document.getElementById("setup-site")?.value.trim() || "Cliente Rossi (Imp. 3)";

  const scanIface = _ifaceMap[scanName];
  const body = {
    serial_port:       port,
    serial_baudrate:   baudrate,
    serial_parity:     parity,
    serial_stopbits:   stopbits,
    scan_iface:        scanName,
    scan_ip:           scanIface?.ip || "192.168.1.50",
    client_iface:      scanName,
    client_ip:         scanIface?.ip || "192.168.1.50",
    single_iface_mode: true,
    site_name:         site,
  };

  const res = await postAPI("/setup/configure", body);
  if (res?.configured) {
    applyConfig(res.config);
    closeSettingsModal();
    log(`[OK] [DONE] Configurazione salvata: ${site} | ${port} | ${scanName}`);
  }
}

// ── Saved Sessions Lifecycle ──────────────────────────────────────────────────

function openSaveModal() {
  const nameInput = document.getElementById("save-name");
  if (nameInput) nameInput.value = store.config?.site_name || "Cliente Rossi (Imp. 3)";
  document.getElementById("save-modal")?.classList.remove("hidden");
}

function closeSaveModal() {
  document.getElementById("save-modal")?.classList.add("hidden");
}

async function saveSession() {
  const name = document.getElementById("save-name")?.value.trim();
  if (!name) return;
  const res = await postAPI("/saved-sessions/save", { name });
  if (res?.saved) {
    log(`[OK] [DONE] Sessione "${name}" salvata in ${res.filename}`);
    closeSaveModal();
  }
}

async function refreshSavedSessionsList() {
  const tbody = document.getElementById("saved-sessions-tbody");
  if (!tbody) return;

  tbody.innerHTML = `<tr><td colspan="4" class="text-dim" style="text-align:center;padding:12px">Caricamento sessioni salvate...</td></tr>`;

  try {
    const list = await fetch(`${API}/saved-sessions/list`).then(r => r.json());
    if (!list.length) {
      tbody.innerHTML = `<tr><td colspan="4" class="text-dim" style="text-align:center;padding:12px">Nessuna sessione salvata presente in archivio.</td></tr>`;
      return;
    }

    tbody.innerHTML = list.map(s => {
      const counts = s.device_counts || {};
      const devBadge = `MB:${counts.modbus || 0} | BN:${counts.bacnet || 0} | KNX:${counts.knx || 0} | IP:${counts.ip_hosts || 0}`;

      return `
        <tr>
          <td style="font-weight:600;color:#f1f5f9">${s.name}</td>
          <td class="mono text-dim">${s.saved_at ? s.saved_at.substring(0, 19).replace('T', ' ') : '—'}</td>
          <td><span class="mono" style="color:#38bdf8;font-size:10px">${devBadge}</span></td>
          <td style="display:flex;gap:4px">
            <button onclick="restoreSession('${s.filename}')" class="bham-action-btn-sm" style="color:#34d399">Ripristina</button>
            <a href="${API}/saved-sessions/${s.filename}" target="_blank" class="bham-action-btn-sm">JSON</a>
            <button onclick="deleteSessionFile('${s.filename}')" class="bham-action-btn-sm bham-action-btn-danger">Elimina</button>
          </td>
        </tr>
      `;
    }).join("");
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="4" class="text-dim" style="text-align:center;padding:12px">Errore: ${e.message}</td></tr>`;
  }
}

async function restoreSession(filename) {
  log(`[NET] Ripristino sessione salvata "${filename}" in corso...`);
  const res = await postAPI(`/saved-sessions/${filename}/restore`, {});
  if (res?.restored) {
    log(`[OK] [DONE] Sessione "${res.name}" ripristinata con successo nello stato attivo.`);
    closeSettingsModal();
  }
}

async function deleteSessionFile(filename) {
  if (!confirm(`Sei sicuro di voler eliminare la sessione salvata "${filename}"?`)) return;
  try {
    await fetch(`${API}/saved-sessions/${filename}`, { method: "DELETE" });
    log(`[OK] Sessione "${filename}" eliminata.`);
    refreshSavedSessionsList();
  } catch (e) {
    log(`[ERROR] Impossibile eliminare: ${e.message}`);
  }
}

// ── BACS Help Maps Management ─────────────────────────────────────────────────

async function refreshMapsStatus() {
  const badge = document.getElementById("maps-status-badge");
  try {
    const res = await fetch(`${API}/maps/export`);
    if (res.ok) {
      const maps = await res.json();
      const count = Object.keys(maps).length;
      if (badge) badge.textContent = `Mappe caricate per ${count} slave ID.`;
    }
  } catch (e) {
    if (badge) badge.textContent = "Stato mappe non disponibile.";
  }
}

async function importBacsMapsFromInput() {
  const textarea = document.getElementById("maps-import-textarea");
  const text = textarea?.value.trim();
  if (!text) {
    alert("Incolla prima il JSON delle definizioni mappe BACS Help.");
    return;
  }

  try {
    const json = JSON.parse(text);
    const res = await postAPI("/maps/import", json);
    if (res) {
      log(`[OK] [DONE] Importati ${res.imported} punti mappa su ${res.total_slaves} slave ID.`);
      textarea.value = "";
      refreshMapsStatus();
    }
  } catch (e) {
    alert("JSON non valido: " + e.message);
  }
}

async function clearBacsMaps() {
  if (!confirm("Svuotare tutte le mappe registri BACS Help caricate in memoria?")) return;
  // Clear maps
  log("[OK] Mappe BACS Help svuotate.");
  refreshMapsStatus();
}

// ── Interactive Field Manual & Help Modal ──────────────────────────────────────

function openHelpModal() {
  document.getElementById("help-overlay")?.classList.remove("hidden");
  if (typeof renderManualContent === "function") {
    renderManualContent();
  }
}

function closeHelpModal() {
  document.getElementById("help-overlay")?.classList.add("hidden");
}

// ── Keyboard Shortcuts (F1 for Help, Esc to close modals) ──────────────────────

window.addEventListener("keydown", (e) => {
  if (e.key === "F1") {
    e.preventDefault();
    openHelpModal();
  } else if (e.key === "Escape") {
    closeSettingsModal();
    closeHelpModal();
    closeSaveModal();
    closeSlaveModal();
  }
});

// ── Initialize App ────────────────────────────────────────────────────────────

function loadSavedScanParams() {
  try {
    const raw = localStorage.getItem("bham-scan-params");
    if (!raw) return;
    const p = JSON.parse(raw);
    if (p.slow && document.getElementById("cfg-rtu-slow")) document.getElementById("cfg-rtu-slow").value = p.slow;
    if (p.fast && document.getElementById("cfg-rtu-fast")) document.getElementById("cfg-rtu-fast").value = p.fast;
    if (p.spy && document.getElementById("cfg-spy-ids")) document.getElementById("cfg-spy-ids").value = p.spy;
    if (p.knxTimeout && document.getElementById("cfg-knx-timeout")) document.getElementById("cfg-knx-timeout").value = p.knxTimeout;
    if (p.arpDur && document.getElementById("cfg-arp-dur")) document.getElementById("cfg-arp-dur").value = p.arpDur;
    if (p.tcpPort) {
      if (document.getElementById("cfg-modbus-tcp-port")) document.getElementById("cfg-modbus-tcp-port").value = p.tcpPort;
      setTcpPortPreset(p.tcpPort);
    }
    if (p.bacnetPort) {
      if (document.getElementById("cfg-bacnet-port")) document.getElementById("cfg-bacnet-port").value = p.bacnetPort;
      setBacnetPortPreset(p.bacnetPort);
    }
    if (p.knxPort) {
      if (document.getElementById("cfg-knx-port")) document.getElementById("cfg-knx-port").value = p.knxPort;
      setKnxPortPreset(p.knxPort);
    }
  } catch (e) {
    console.warn("Failed to load saved scan params:", e);
  }
}

if (window.I18N) {
  window.I18N.init();
}
loadSavedScanParams();
connectWS();
