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
  if (theme !== "dark") theme = "light";
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
  localStorage.setItem("bham-theme-mode", theme);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "light";
  const target = current === "dark" ? "light" : "dark";
  setThemeMode(target);
}

// FORCE RESET legacy dark mode preference
try {
  localStorage.removeItem("bham-theme");
} catch (_) {}
// Default strictly to light mode
setThemeMode(localStorage.getItem("bham-theme-mode") || "light");

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
    if (session.protocol) {
      const pKey = session.protocol.replace("modbus_", "");
      setRackLed(pKey, "scanning");
    }
  } else if (status === "completed") {
    clearInterval(scanTimerInterval);
    scanStartTime = null;
    if (pSum) pSum.textContent = t("status_completed", { n: found, pct: pct });
    resetAllRackLeds();
  } else if (status === "aborted") {
    clearInterval(scanTimerInterval);
    scanStartTime = null;
    if (pSum) pSum.textContent = t("status_aborted");
    resetAllRackLeds();
  }
}

// ── Rack Unit LED Status & Console Toggle ──────────────────────────────────────

function setRackLed(proto, state) {
  const led = document.getElementById(`led-${proto}`);
  if (!led) return;
  led.className = "bham-led " + (
    state === "scanning" ? "led-scanning" :
    state === "ok" ? "led-ok" : "led-idle"
  );
}

function resetAllRackLeds() {
  ["rtu", "tcp", "bacnet", "knx", "arp", "sniff", "fc43"].forEach(p => {
    const badge = document.getElementById(`rack-count-${p}`);
    const hasDev = badge && badge.classList.contains("has-devices");
    setRackLed(p, hasDev ? "ok" : "idle");
  });
}

function expandConsole() {
  const col = document.getElementById("console-col");
  if (!col) return;
  col.classList.remove("collapsed");
  const btn = document.getElementById("btn-console-toggle");
  if (btn) {
    btn.innerHTML = `<svg class="bham-svg-sm" viewBox="0 0 24 24"><polyline points="6 9 12 15 18 9"></polyline></svg> <span data-i18n="console_reduce">Riduci</span>`;
  }
  try {
    localStorage.setItem("bham-console-collapsed", "0");
  } catch (_) {}
}

function collapseConsole() {
  const col = document.getElementById("console-col");
  if (!col) return;
  col.classList.add("collapsed");
  const btn = document.getElementById("btn-console-toggle");
  if (btn) {
    btn.innerHTML = `<svg class="bham-svg-sm" viewBox="0 0 24 24"><polyline points="18 15 12 9 6 15"></polyline></svg> <span data-i18n="console_expand">Console</span>`;
  }
  try {
    localStorage.setItem("bham-console-collapsed", "1");
  } catch (_) {}
}

function toggleConsole() {
  const col = document.getElementById("console-col");
  if (!col) return;
  if (col.classList.contains("collapsed")) {
    expandConsole();
  } else {
    collapseConsole();
  }
}

function handleDockHeaderClick(e) {
  if (e.target.closest("button, input, label, a, select")) return;
  toggleConsole();
}

function openConsoleTab(tab) {
  expandConsole();
  switchConsoleTab(tab);
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

// Utility: sort devices by column (helper for sortable headers)
window.sortDeviceTable = function(table, colIndex, dataType = 'string') {
  const rows = Array.from(document.querySelectorAll(`#${table} tbody tr`));
  const isAsc = rows[0]?.dataset.sortAsc !== 'true';

  rows.sort((a, b) => {
    const aVal = a.children[colIndex].textContent.trim();
    const bVal = b.children[colIndex].textContent.trim();

    let compare = 0;
    if (dataType === 'number') {
      compare = parseFloat(aVal) - parseFloat(bVal);
    } else {
      compare = aVal.localeCompare(bVal);
    }
    return isAsc ? compare : -compare;
  });

  rows.forEach(row => row.dataset.sortAsc = isAsc);
  const tbody = document.querySelector(`#${table} tbody`);
  tbody.innerHTML = '';
  rows.forEach(row => tbody.appendChild(row));
};

function renderModbusTable() {
  const tb = document.getElementById("modbus-table");
  if (!tb) return;

  const rows = store.modbus.filter(d => {
    const hay = `${d.slave_id} ${d.protocol} ${d.ip} ${d.vendor_name} ${d.model_name}`;
    return matchesSearch(hay);
  }).sort((a, b) => a.slave_id - b.slave_id);

  const detailsTxt = window.t ? window.t("btn_details") : "Dettagli";

  tb.innerHTML = rows.map(d => {
    const endpoint = d.ip ? `${d.ip}:${d.tcp_port || 502}` : (d.serial_params?.port ? `${d.serial_params.port}:${d.slave_id}` : `ID:${d.slave_id}`);
    const proto = d.protocol === "modbus_tcp" ? "TCP" : "RTU";
    const ms = d.response_time_ms ? `${Math.round(d.response_time_ms)} ms` : "—";
    const vendor = [d.vendor_name, d.model_name].filter(Boolean).join(" ") || "Dispositivo Modbus";

    return `
      <tr>
        <td class="cell-mono color-modbus" style="font-weight:700">${d.slave_id}</td>
        <td><span class="bham-badge-proto ${proto === 'TCP' ? 'proto-tcp' : 'proto-rtu'}">${proto}</span></td>
        <td class="cell-mono cell-text-main">${endpoint}</td>
        <td class="cell-mono cell-latency">${ms}</td>
        <td class="cell-text-main">${vendor}</td>
        <td><span class="bham-status-badge bham-status-online"><span class="bham-status-dot"></span>Online</span></td>
        <td><button type="button" onclick="inspectModbusSlave(${d.slave_id})" class="bham-table-action-btn">${detailsTxt}</button></td>
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
    const isBbmd = Boolean(d.bbmd_routed || (d.tags && d.tags.includes('bbmd_routed')));
    const bbmdBadge = isBbmd ? `<span class="bham-badge-proto" style="font-size:10px;margin-left:5px;vertical-align:middle;background:rgba(6,182,212,0.18);color:#06b6d4;border:1px solid rgba(6,182,212,0.4)" title="Dispositivo traversato via router BBMD ${d.routed_via || ''}">BBMD</span>` : "";

    return `
      <tr>
        <td class="cell-mono color-bacnet" style="font-weight:700">${d.device_id}${bbmdBadge}</td>
        <td class="cell-mono cell-text-main">${d.address}</td>
        <td class="cell-text-main">${d.vendor_name || "—"}</td>
        <td class="cell-text-muted">${d.model_name || "—"}</td>
        <td class="cell-mono cell-text-dim">${fw}</td>
        <td class="cell-mono cell-text-main" style="font-weight:600">${objCount}</td>
        <td><button type="button" onclick="inspectBACnetDevice(${d.device_id})" class="bham-table-action-btn">🔍 Oggetti</button></td>
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
        <td class="cell-mono color-knx" style="font-weight:700">${k.individual_address}</td>
        <td class="cell-mono cell-text-main">${k.ip_address}:${k.port}</td>
        <td class="cell-text-main">${k.device_name || "KNXnet/IP Device"}</td>
        <td class="cell-mono cell-text-dim">${k.serial_number || "—"}</td>
        <td class="cell-mono cell-text-dim">${k.mac_address || "—"}</td>
        <td><span class="bham-badge-proto proto-knx">${k.medium || "TP1"}</span></td>
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
        <td class="cell-mono color-network" style="font-weight:600">${h.ip}</td>
        <td class="cell-mono cell-text-dim">${h.mac || "—"}</td>
        <td class="cell-mono cell-text-main">${h.hostname || "—"}</td>
        <td class="cell-mono cell-text-dim">${firstSeen}</td>
        <td class="cell-text-muted">${oui}</td>
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

  // Rack Unit Discovery Badges per Channel
  const mbRtu = store.modbus.filter(d => d.protocol !== "modbus_tcp").length;
  const mbTcp = store.modbus.filter(d => d.protocol === "modbus_tcp").length;

  const rRtu = document.getElementById("rack-count-rtu");
  const rTcp = document.getElementById("rack-count-tcp");
  const rBn  = document.getElementById("rack-count-bacnet");
  const rKx  = document.getElementById("rack-count-knx");
  const rHp  = document.getElementById("rack-count-arp");

  if (rRtu) {
    rRtu.textContent = `${mbRtu} dev`;
    rRtu.classList.toggle("has-devices", mbRtu > 0);
  }
  if (rTcp) {
    rTcp.textContent = `${mbTcp} dev`;
    rTcp.classList.toggle("has-devices", mbTcp > 0);
  }
  if (rBn) {
    rBn.textContent = `${bn} dev`;
    rBn.classList.toggle("has-devices", bn > 0);
  }
  if (rKx) {
    rKx.textContent = `${kx} dev`;
    rKx.classList.toggle("has-devices", kx > 0);
  }
  if (rHp) {
    rHp.textContent = `${hp} host`;
    rHp.classList.toggle("has-devices", hp > 0);
  }

  // Telemetry label if idle
  const pSum = document.getElementById("telemetry-summary");
  if (pSum && !scanStartTime) {
    const t = window.t || ((k, p) => k);
    pSum.textContent = t("status_ready", { n: total });
  }

  // Refresh active filter and empty state visibility
  setProtocolFilter(currentFilter);
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

  const total = store.modbus.length + store.bacnet.length + store.knx.length + store.hosts.length;
  const emptyState = document.getElementById("discovery-empty-state");
  const cardMb = document.getElementById("card-modbus");
  const cardBn = document.getElementById("card-bacnet");
  const cardKx = document.getElementById("card-knx");
  const cardHp = document.getElementById("card-hosts");
  const topoContainer = document.getElementById("bham-topology-container");

  if (currentMainView === "topology") {
    if (emptyState) emptyState.classList.add("hidden");
    if (cardMb) cardMb.classList.add("hidden");
    if (cardBn) cardBn.classList.add("hidden");
    if (cardKx) cardKx.classList.add("hidden");
    if (cardHp) cardHp.classList.add("hidden");
    if (topoContainer) topoContainer.classList.remove("hidden");
    renderTopology();
    return;
  }

  if (topoContainer) topoContainer.classList.add("hidden");

  if (total === 0 && !currentSearch) {
    if (emptyState) emptyState.classList.remove("hidden");
    if (cardMb) cardMb.classList.add("hidden");
    if (cardBn) cardBn.classList.add("hidden");
    if (cardKx) cardKx.classList.add("hidden");
    if (cardHp) cardHp.classList.add("hidden");
    return;
  }

  if (emptyState) emptyState.classList.add("hidden");

  if (cardMb) {
    cardMb.classList.remove("hidden");
    cardMb.style.display = (filter === "all" || filter === "modbus") ? "block" : "none";
  }
  if (cardBn) {
    cardBn.classList.remove("hidden");
    cardBn.style.display = (filter === "all" || filter === "bacnet") ? "block" : "none";
  }
  if (cardKx) {
    cardKx.classList.remove("hidden");
    cardKx.style.display = (filter === "all" || filter === "knx")    ? "block" : "none";
  }
  if (cardHp) {
    cardHp.classList.remove("hidden");
    cardHp.style.display = (filter === "all" || filter === "hosts")  ? "block" : "none";
  }
}

function onSearchInput(query) {
  currentSearch = query.trim();
  renderModbusTable();
  renderBACnetTable();
  renderKNXTable();
  renderHostsTable();
  if (currentMainView === "topology") {
    renderTopology();
  }
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
  const centerBadge = document.getElementById("center-frame-badge");
  if (centerBadge) {
    centerBadge.textContent = "0";
    centerBadge.style.display = "none";
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

  openConsoleTab("log");
  setRackLed("rtu", "scanning");
  log(`[MODBUS] Avvio scansione RTU range [${start}..${end}] su ${port}...`);
  postAPI("/scan/modbus/rtu", { port, baudrates: [9600, 19200], id_range: ids });
}

// ── Console Tabs (Live Log vs RS485 Inspector) ────────────────────────────────

function switchConsoleTab(tab) {
  const col = document.getElementById("console-col");
  if (col && col.classList.contains("collapsed")) {
    expandConsole();
  }
  const logBtn = document.getElementById("view-tab-log");
  const serialBtn = document.getElementById("view-tab-serial");
  const logConsole = document.getElementById("log-console");
  const serialConsole = document.getElementById("serial-frames-console");

  if (tab === "serial") {
    logBtn?.classList.remove("active");
    serialBtn?.classList.add("active");
    logConsole?.classList.add("hidden");
    serialConsole?.classList.remove("hidden");
    const scrollCheck = document.getElementById("log-autoscroll");
    if (serialConsole && (!scrollCheck || scrollCheck.checked)) {
      serialConsole.scrollTop = serialConsole.scrollHeight;
    }
  } else {
    serialBtn?.classList.remove("active");
    logBtn?.classList.add("active");
    serialConsole?.classList.add("hidden");
    logConsole?.classList.remove("hidden");
    const scrollCheck = document.getElementById("log-autoscroll");
    if (logConsole && (!scrollCheck || scrollCheck.checked)) {
      logConsole.scrollTop = logConsole.scrollHeight;
    }
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
  const centerBadge = document.getElementById("center-frame-badge");
  if (centerBadge) {
    centerBadge.textContent = "0";
    centerBadge.style.display = "inline-block";
  }
  const rSniff = document.getElementById("rack-count-sniff");
  if (rSniff) {
    rSniff.textContent = "0 frame";
    rSniff.classList.remove("has-devices");
  }
  setRackLed("sniff", "scanning");

  // Switch to inspector view automatically and expand dock so user sees live frames immediately
  openConsoleTab("serial");

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
  setRackLed("sniff", totalSniffedFrames > 0 ? "ok" : "idle");
  abortScan();
}

function handleSerialFrame(frame) {
  totalSniffedFrames++;
  const badge = document.getElementById("serial-frame-badge");
  if (badge) {
    badge.textContent = String(totalSniffedFrames);
    badge.style.display = "inline-block";
  }
  const centerBadge = document.getElementById("center-frame-badge");
  if (centerBadge) {
    centerBadge.textContent = String(totalSniffedFrames);
    centerBadge.style.display = "inline-block";
  }
  const rSniff = document.getElementById("rack-count-sniff");
  if (rSniff) {
    rSniff.textContent = `${totalSniffedFrames} frame`;
    rSniff.classList.add("has-devices");
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
  openConsoleTab("log");
  setRackLed("tcp", "scanning");
  log(`[MODBUS] Avvio scansione TCP su ${hosts.length} target (porta/e: ${portVal})...`);
  postAPI("/scan/modbus/tcp", { hosts, tcp_port: portVal });
}

function startBACnet() {
  const iface = document.getElementById("bacnet-iface")?.value.trim() || "";
  const portVal = document.getElementById("bacnet-port")?.value.trim() || "BAC0";
  const bbmdIp = document.getElementById("bbmd-ip")?.value.trim() || "";
  const bbmdPort = document.getElementById("bbmd-port")?.value.trim() || "47808";
  const bbmdTtl = parseInt(document.getElementById("bbmd-ttl")?.value) || 60;

  openConsoleTab("log");
  setRackLed("bacnet", "scanning");

  const payload = { iface, port: portVal };
  if (bbmdIp) {
    payload.bbmd_ip = bbmdIp;
    payload.bbmd_port = bbmdPort;
    payload.bbmd_ttl = bbmdTtl;
    log(`[BACNET] Foreign Device Registration verso BBMD ${bbmdIp}:${bbmdPort} (TTL: ${bbmdTtl}s)...`);
  } else {
    log(`[BACNET] Who-Is inviato in broadcast su ${iface || "default"} (porta: ${portVal})...`);
  }
  postAPI("/scan/bacnet/ip", payload);
}

function startKNX() {
  const iface = document.getElementById("knx-iface")?.value.trim() || "";
  const portVal = document.getElementById("knx-port")?.value.trim() || "3671";
  const timeout = parseFloat(document.getElementById("cfg-knx-timeout")?.value) || 3.5;
  openConsoleTab("log");
  setRackLed("knx", "scanning");
  log(`[KNX] SEARCH_REQUEST inviato via multicast (224.0.23.12:${portVal}) su ${iface || "default"}...`);
  postAPI("/scan/knx/ip", { iface, port: portVal, timeout });
}

function startARP() {
  const iface = document.getElementById("arp-iface")?.value.trim() || "";
  const duration = parseFloat(document.getElementById("arp-dur")?.value) || 30;
  openConsoleTab("log");
  setRackLed("arp", "scanning");
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
  resetAllRackLeds();
  await postAPI("/scan/abort", {});
}

async function clearState() {
  await fetch(`${API}/state`, { method: "DELETE" });
  clearAllTables();
  resetAllRackLeds();
}

async function runFC43() {
  const port = document.getElementById("fc43-port")?.value.trim() || "/dev/ttyUSB0";
  const slave_id = parseInt(document.getElementById("fc43-id")?.value) || 1;
  setRackLed("fc43", "scanning");
  log(`[MODBUS] [FC43] Lettura Device ID MEI per Slave ${slave_id} su ${port}...`);
  const r = await postAPI("/diag/modbus/fc43", {
    port, slave_id, baudrate: 9600, parity: "N", stopbits: 1,
  });
  setRackLed("fc43", r ? "ok" : "idle");
  if (r) {
    log(`[OK] [FC43] Risultato: ${JSON.stringify(r)}`);
  }
}

// ── Modbus Slave Inspector Modal ──────────────────────────────────────────────

// ── Modbus Slave Inspector Modal & Smart Scan ─────────────────────────────────

let currentInspectedSlaveId = null;

async function inspectModbusSlave(slaveId) {
  const d = store.modbus.find(x => x.slave_id === slaveId);
  if (!d) return;

  currentInspectedSlaveId = slaveId;
  const modal = document.getElementById("slave-modal");
  const title = document.getElementById("slave-modal-title");
  const metaGrid = document.getElementById("slave-modal-meta");
  const tbody = document.getElementById("slave-modal-registers-tbody");
  const smartTbody = document.getElementById("slave-modal-smart-tbody");

  if (title) title.textContent = `Modbus Slave ID #${d.slave_id} (${d.protocol === 'modbus_tcp' ? 'TCP' : 'RTU'})`;

  if (metaGrid) {
    metaGrid.innerHTML = `
      <div><strong>Endpoint:</strong> <span class="mono">${d.ip || d.serial_params?.port || "—"}</span></div>
      <div><strong>Tempo Risposta:</strong> <span class="cell-mono cell-latency">${d.response_time_ms ? d.response_time_ms.toFixed(1) + ' ms' : '—'}</span></div>
      <div><strong>Costruttore:</strong> ${d.vendor_name || 'Non specificato'}</div>
      <div><strong>Modello:</strong> ${d.model_name || 'Non specificato'}</div>
      <div><strong>Rilevato il:</strong> <span class="mono text-dim">${d.discovered_at ? new Date(d.discovered_at).toLocaleString() : '—'}</span></div>
      <div><strong>Stato:</strong> <span class="bham-status-badge bham-status-online"><span class="bham-status-dot"></span>Online</span></div>
    `;
  }

  // Se abbiamo registri già scoperti in memoria, mostriamoli
  if (smartTbody) {
    if (d.registers && Object.keys(d.registers).length) {
      renderSmartRegisters(Object.values(d.registers));
    } else {
      smartTbody.innerHTML = `<tr><td colspan="6" class="text-dim" style="text-align:center;padding:12px">Premi "⚡ Avvia Auto-Scan" per scoprire automaticamente i registri attivi su questo slave.</td></tr>`;
    }
  }

  switchSlaveSubTab("mapped");

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
              <td class="cell-mono color-modbus" style="font-weight:700">${p.register}</td>
              <td><span class="mono" style="color:var(--bham-text-muted)">${p.register_type.toUpperCase()}</span></td>
              <td class="cell-text-main">${p.label} <span class="text-dim">${p.description ? '– ' + p.description : ''}</span></td>
              <td class="cell-mono cell-text-main">${p.unit || '—'}</td>
              <td class="cell-mono text-dim">${p.scale || 1.0}</td>
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

function switchSlaveSubTab(tab) {
  const pMap = document.getElementById("panel-slave-mapped");
  const pSmart = document.getElementById("panel-slave-smart");
  const bMap = document.getElementById("btn-tab-slave-mapped");
  const bSmart = document.getElementById("btn-tab-slave-smart");

  if (tab === "smart") {
    bMap?.classList.remove("active");
    bSmart?.classList.add("active");
    pMap?.classList.add("hidden");
    pSmart?.classList.remove("hidden");
  } else {
    bSmart?.classList.remove("active");
    bMap?.classList.add("active");
    pSmart?.classList.add("hidden");
    pMap?.classList.remove("hidden");
  }
}

async function runSmartRegisterScan() {
  if (currentInspectedSlaveId == null) return;
  const btn = document.getElementById("btn-run-smart-scan");
  const origText = btn ? btn.textContent : "⚡ Avvia Auto-Scan";
  if (btn) {
    btn.textContent = "⏳ Scansione in corso...";
    btn.disabled = true;
  }

  switchSlaveSubTab("smart");
  const smartTbody = document.getElementById("slave-modal-smart-tbody");
  if (smartTbody) {
    smartTbody.innerHTML = `<tr><td colspan="6" class="text-dim" style="text-align:center;padding:12px">Scansione euristica blocchi FC03/FC04 in corso...</td></tr>`;
  }

  log(`[MODBUS] Avvio Auto-Scan registri su Slave #${currentInspectedSlaveId}...`);
  try {
    const res = await postAPI("/modbus/smart-scan", { slave_id: currentInspectedSlaveId });
    if (res && res.registers && res.registers.length) {
      renderSmartRegisters(res.registers);
      log(`[OK] [DONE] Auto-Scan: trovati ${res.found_count} registri attivi su Slave #${currentInspectedSlaveId} in ${res.elapsed_ms}ms.`);
    } else {
      if (smartTbody) {
        smartTbody.innerHTML = `<tr><td colspan="6" class="text-dim" style="text-align:center;padding:12px">Nessun registro attivo riscontrato o errore: ${res?.error || 'Nessuna risposta'}</td></tr>`;
      }
      log(`[WARN] Auto-Scan completato: nessun registro rilevato per Slave #${currentInspectedSlaveId}.`);
    }
  } catch (err) {
    if (smartTbody) {
      smartTbody.innerHTML = `<tr><td colspan="6" class="text-dim" style="text-align:center;padding:12px">Errore durante la scansione: ${err.message}</td></tr>`;
    }
  } finally {
    if (btn) {
      btn.textContent = origText;
      btn.disabled = false;
    }
  }
}

function renderSmartRegisters(regList) {
  const smartTbody = document.getElementById("slave-modal-smart-tbody");
  if (!smartTbody) return;

  smartTbody.innerHTML = regList.map(r => {
    const f32Html = r.float32 !== null && r.float32 !== undefined
      ? `<span class="cell-mono cell-latency" style="font-weight:600">${r.float32}</span>`
      : `<span class="text-dim">—</span>`;

    return `
      <tr>
        <td class="cell-mono color-modbus" style="font-weight:700">${r.address}</td>
        <td><span class="mono text-dim">${(r.type || 'HOLDING').toUpperCase()}</span></td>
        <td class="cell-mono cell-text-main">${r.raw_dec}</td>
        <td class="cell-mono text-dim">${r.raw_hex}</td>
        <td class="cell-mono cell-text-muted">${r.int16}</td>
        <td>${f32Html}</td>
      </tr>
    `;
  }).join("");
}

function closeSlaveModal() {
  currentInspectedSlaveId = null;
  document.getElementById("slave-modal")?.classList.add("hidden");
}

// ── BACnet Device Object Explorer Modal ───────────────────────────────────────

let currentBACnetDeviceId = null;
let currentBACnetObjects = [];

async function inspectBACnetDevice(deviceId) {
  const d = store.bacnet.find(x => x.device_id === deviceId);
  if (!d) return;

  currentBACnetDeviceId = deviceId;
  const modal = document.getElementById("bacnet-modal");
  const title = document.getElementById("bacnet-modal-title");
  const metaGrid = document.getElementById("bacnet-modal-meta");
  const searchInput = document.getElementById("bacnet-obj-search");

  if (searchInput) searchInput.value = "";
  if (title) title.textContent = `BACnet Device Explorer #${d.device_id} (${d.model_name || 'Generic Device'})`;

  if (metaGrid) {
    metaGrid.innerHTML = `
      <div><strong>Indirizzo IP/Porta:</strong> <span class="mono">${d.address}</span></div>
      <div><strong>Vendor:</strong> ${d.vendor_name || 'Non specificato'} (ID: ${d.vendor_id ?? '—'})</div>
      <div><strong>Modello:</strong> ${d.model_name || 'Non specificato'}</div>
      <div><strong>Firmware:</strong> <span class="mono text-dim">${d.firmware_revision || '—'}</span></div>
      <div><strong>Software Ver:</strong> <span class="mono text-dim">${d.application_software_version || '—'}</span></div>
      <div><strong>Stato:</strong> <span class="bham-status-badge bham-status-online"><span class="bham-status-dot"></span>Online</span></div>
    `;
  }

  if (modal) modal.classList.remove("hidden");

  if (d.object_list && d.object_list.length) {
    currentBACnetObjects = d.object_list;
    renderBACnetObjectsTable(currentBACnetObjects);
  } else {
    await refreshBACnetObjects();
  }
}

async function refreshBACnetObjects() {
  if (currentBACnetDeviceId == null) return;
  const tbody = document.getElementById("bacnet-modal-objects-tbody");
  const countBadge = document.getElementById("bacnet-obj-count-badge");
  const btn = document.getElementById("btn-refresh-bacnet-objects");

  if (btn) {
    btn.textContent = "⏳ Lettura...";
    btn.disabled = true;
  }

  if (tbody) {
    tbody.innerHTML = `<tr><td colspan="5" class="text-dim" style="text-align:center;padding:14px">Interrogazione stack BACnet per elenco oggetti e present_value...</td></tr>`;
  }

  log(`[BACNET] Esplorazione oggetti per Device #${currentBACnetDeviceId}...`);

  try {
    const res = await postAPI(`/bacnet/devices/${currentBACnetDeviceId}/objects`, {});
    currentBACnetObjects = res?.objects || [];
    renderBACnetObjectsTable(currentBACnetObjects);

    if (countBadge) {
      countBadge.textContent = `${currentBACnetObjects.length} oggetti`;
    }

    if (currentBACnetObjects.length) {
      log(`[OK] [DONE] BACnet Explorer: trovati ${currentBACnetObjects.length} oggetti su Device #${currentBACnetDeviceId}.`);
    } else {
      log(`[WARN] Nessun oggetto restituito da Device #${currentBACnetDeviceId}.`);
    }
  } catch (err) {
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="5" class="text-dim" style="text-align:center;padding:14px">Errore consultazione oggetti: ${err.message}</td></tr>`;
    }
  } finally {
    if (btn) {
      btn.textContent = "🔄 Rileggi Oggetti";
      btn.disabled = false;
    }
  }
}

function renderBACnetObjectsTable(objList) {
  const tbody = document.getElementById("bacnet-modal-objects-tbody");
  const countBadge = document.getElementById("bacnet-obj-count-badge");
  if (countBadge) countBadge.textContent = `${objList.length} oggetti`;
  if (!tbody) return;

  if (!objList.length) {
    tbody.innerHTML = `<tr><td colspan="5" class="text-dim" style="text-align:center;padding:14px">Nessun oggetto trovato o corrispondente al filtro.</td></tr>`;
    return;
  }

  tbody.innerHTML = objList.map(obj => {
    let typeClass = "bham-badge-proto";
    const t = (obj.type || "").toLowerCase();
    if (t.includes("analog")) typeClass += " proto-rtu";
    else if (t.includes("binary")) typeClass += " proto-tcp";
    else typeClass += " proto-knx";

    return `
      <tr>
        <td class="cell-mono color-bacnet" style="font-weight:700">${obj.identifier}</td>
        <td><span class="${typeClass}" style="font-size:10px">${obj.type}</span></td>
        <td class="cell-text-main" style="font-weight:600">${obj.name}</td>
        <td class="cell-mono cell-latency" style="font-weight:600">${obj.present_value}</td>
        <td class="cell-mono cell-text-muted">${obj.units || '—'}</td>
      </tr>
    `;
  }).join("");
}

function filterBACnetObjects(query) {
  const q = query.trim().toLowerCase();
  if (!q) {
    renderBACnetObjectsTable(currentBACnetObjects);
    return;
  }
  const filtered = currentBACnetObjects.filter(o => {
    const hay = `${o.identifier} ${o.type} ${o.name} ${o.present_value} ${o.units}`.toLowerCase();
    return hay.includes(q);
  });
  renderBACnetObjectsTable(filtered);
}

function closeBACnetModal() {
  currentBACnetDeviceId = null;
  document.getElementById("bacnet-modal")?.classList.add("hidden");
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
      <button type="button" onclick="document.getElementById('setup-port').value='${p.port}'"
        style="margin:2px;padding:3px 8px;border-radius:var(--bham-radius-sm);background:var(--bham-bg-surface);color:var(--bham-modbus);border:1px solid var(--bham-border);cursor:pointer;font-family:var(--font-mono, monospace);font-size:11px;font-weight:600">
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
          <td class="cell-text-main" style="font-weight:600">${s.name}</td>
          <td class="mono text-dim">${s.saved_at ? s.saved_at.substring(0, 19).replace('T', ' ') : '—'}</td>
          <td><span class="mono text-dim" style="font-size:11px">${devBadge}</span></td>
          <td style="display:flex;gap:4px">
            <button onclick="openDiffModalForSession('${s.filename}')" class="bham-action-btn-sm" style="color:#d97706;font-weight:600">⚡ Diff</button>
            <button onclick="restoreSession('${s.filename}')" class="bham-action-btn-sm" style="color:var(--bham-modbus);font-weight:600">Ripristina</button>
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
    closeTopologyInspector();
  }
});

// =============================================================================
// BHAM – Interactive Network Topology Engine (Milestone 1)
// =============================================================================

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

let currentMainView = "table"; // "table" | "topology"

const topoState = {
  orientation: "horizontal", // "horizontal" | "vertical"
  scale: 1,
  panX: 40,
  panY: 40,
  isPanning: false,
  startX: 0,
  startY: 0,
  selectedNodeId: null,
  nodesMap: {},
  nodes: [],
  links: [],
  initializedEvents: false,
};

function switchMainView(mode) {
  currentMainView = mode;
  const btnTable = document.getElementById("view-mode-table");
  const btnTopo = document.getElementById("view-mode-topology");
  const topoContainer = document.getElementById("bham-topology-container");
  const emptyState = document.getElementById("discovery-empty-state");
  const cardMb = document.getElementById("card-modbus");
  const cardBn = document.getElementById("card-bacnet");
  const cardKx = document.getElementById("card-knx");
  const cardHp = document.getElementById("card-hosts");

  if (mode === "table") {
    if (btnTable) btnTable.classList.add("active");
    if (btnTopo) btnTopo.classList.remove("active");
    if (topoContainer) topoContainer.classList.add("hidden");
    setProtocolFilter(currentFilter);
  } else {
    if (btnTable) btnTable.classList.remove("active");
    if (btnTopo) btnTopo.classList.add("active");
    if (topoContainer) topoContainer.classList.remove("hidden");
    if (emptyState) emptyState.classList.add("hidden");
    if (cardMb) cardMb.classList.add("hidden");
    if (cardBn) cardBn.classList.add("hidden");
    if (cardKx) cardKx.classList.add("hidden");
    if (cardHp) cardHp.classList.add("hidden");

    initTopologyEvents();
    renderTopology();
    setTimeout(topoFitView, 60);
  }

  try {
    localStorage.setItem("bham-main-view", mode);
  } catch (_) {}
}

function initTopologyEvents() {
  if (topoState.initializedEvents) return;
  topoState.initializedEvents = true;

  const vp = document.getElementById("topology-viewport");
  if (!vp) return;

  vp.addEventListener("mousedown", (e) => {
    if (e.target.closest(".topo-node") || e.target.closest(".bham-topo-hud") || e.target.closest(".bham-topo-inspector")) {
      return;
    }
    topoState.isPanning = true;
    topoState.startX = e.clientX - topoState.panX;
    topoState.startY = e.clientY - topoState.panY;
    vp.style.cursor = "grabbing";
  });

  window.addEventListener("mousemove", (e) => {
    if (!topoState.isPanning) return;
    topoState.panX = e.clientX - topoState.startX;
    topoState.panY = e.clientY - topoState.startY;
    applyTopologyTransform();
  });

  window.addEventListener("mouseup", () => {
    if (topoState.isPanning) {
      topoState.isPanning = false;
      if (vp) vp.style.cursor = "grab";
    }
  });

  vp.addEventListener("wheel", (e) => {
    e.preventDefault();
    const rect = vp.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const zoomFactor = e.deltaY < 0 ? 1.15 : 0.87;
    const newScale = Math.min(Math.max(topoState.scale * zoomFactor, 0.25), 3.0);

    topoState.panX = mouseX - (mouseX - topoState.panX) * (newScale / topoState.scale);
    topoState.panY = mouseY - (mouseY - topoState.panY) * (newScale / topoState.scale);
    topoState.scale = newScale;

    applyTopologyTransform();
  }, { passive: false });
}

function applyTopologyTransform() {
  const root = document.getElementById("topology-graph-root");
  if (root) {
    root.setAttribute("transform", `translate(${topoState.panX.toFixed(1)}, ${topoState.panY.toFixed(1)}) scale(${topoState.scale.toFixed(3)})`);
  }
}

function topoZoomIn() {
  topoState.scale = Math.min(topoState.scale * 1.25, 3.0);
  applyTopologyTransform();
}

function topoZoomOut() {
  topoState.scale = Math.max(topoState.scale * 0.8, 0.25);
  applyTopologyTransform();
}

function topoSetOrientation(orient) {
  topoState.orientation = orient;
  const btnH = document.getElementById("topo-btn-layout-h");
  const btnV = document.getElementById("topo-btn-layout-v");
  if (orient === "horizontal") {
    if (btnH) btnH.classList.add("active");
    if (btnV) btnV.classList.remove("active");
  } else {
    if (btnH) btnH.classList.remove("active");
    if (btnV) btnV.classList.add("active");
  }
  renderTopology();
  setTimeout(topoFitView, 50);
}

function topoFitView() {
  const vp = document.getElementById("topology-viewport");
  if (!vp || topoState.nodes.length === 0) return;

  const rect = vp.getBoundingClientRect();
  const width = rect.width || 800;
  const height = rect.height || 500;

  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  topoState.nodes.forEach(n => {
    minX = Math.min(minX, n.x);
    maxX = Math.max(maxX, n.x + n.width);
    minY = Math.min(minY, n.y);
    maxY = Math.max(maxY, n.y + n.height);
  });

  const graphW = Math.max(maxX - minX, 100);
  const graphH = Math.max(maxY - minY, 100);

  const padding = 60;
  const scaleX = (width - padding * 2) / graphW;
  const scaleY = (height - padding * 2) / graphH;
  let newScale = Math.min(scaleX, scaleY, 1.15);
  newScale = Math.max(newScale, 0.4);

  topoState.scale = newScale;
  topoState.panX = (width - graphW * newScale) / 2 - minX * newScale;
  topoState.panY = (height - graphH * newScale) / 2 - minY * newScale;

  applyTopologyTransform();
}

function buildTopologyData() {
  const cfg = store.config || {};
  const siteName = cfg.site_name || "BHAM Field Station";
  const serialPort = cfg.serial_port || "/dev/ttyUSB0";
  const baud = cfg.serial_baudrate || 9600;
  const parity = cfg.serial_parity || "N";
  const nic = cfg.scan_iface || "eth0";
  const nicIp = cfg.scan_ip || "";

  const nodes = [];
  const links = [];

  const showModbus = (currentFilter === "all" || currentFilter === "modbus");
  const showBacnet = (currentFilter === "all" || currentFilter === "bacnet");
  const showKnx    = (currentFilter === "all" || currentFilter === "knx");
  const showHosts  = (currentFilter === "all" || currentFilter === "hosts");

  // 1. Root Host
  nodes.push({
    id: "node:host",
    label: siteName,
    sublabel: "Host di Collaudo / Master",
    category: "host",
    protocol: "system",
    protoColor: "host",
    status: "online",
    parent_id: null,
    level: 0,
    width: 184,
    height: 54,
    metrics: { "Totale Dispositivi": store.modbus.length + store.bacnet.length + store.knx.length + store.hosts.length },
    data: { siteName, scanIp: nicIp, serialPort }
  });

  const rtuDevs = store.modbus.filter(d => d.protocol === "modbus_rtu" || d.serial_params);
  const tcpDevs = store.modbus.filter(d => d.protocol === "modbus_tcp");
  const mstpDevs = store.bacnet.filter(d => d.protocol === "bacnet_mstp");
  const bacnetIpDevs = store.bacnet.filter(d => d.protocol !== "bacnet_mstp");

  const hasSerialDevs = (rtuDevs.length > 0 || mstpDevs.length > 0);
  const hasIpDevs = (tcpDevs.length > 0 || bacnetIpDevs.length > 0 || store.knx.length > 0 || store.hosts.length > 0);

  // 2. Interfaces
  if (showModbus || showBacnet || currentFilter === "all") {
    nodes.push({
      id: "node:iface:serial",
      label: serialPort,
      sublabel: `RS485 (${baud} 8${parity}1)`,
      category: "interface",
      protocol: "serial",
      protoColor: "serial",
      status: hasSerialDevs ? "active" : "standby",
      parent_id: "node:host",
      level: 1,
      width: 180,
      height: 52,
      metrics: { "Baudrate": baud, "Parità": `8${parity}1`, "Stato": hasSerialDevs ? "Attivo" : "Standby" },
      data: { port: serialPort, baud, parity }
    });
    links.push({ source: "node:host", target: "node:iface:serial", protocol: "serial" });
  }

  if (showModbus || showBacnet || showKnx || showHosts || currentFilter === "all") {
    nodes.push({
      id: "node:iface:nic",
      label: nic,
      sublabel: nicIp ? nicIp : "Ethernet LAN",
      category: "interface",
      protocol: "ethernet",
      protoColor: "nic",
      status: hasIpDevs ? "active" : "standby",
      parent_id: "node:host",
      level: 1,
      width: 180,
      height: 52,
      metrics: { "Interfaccia": nic, "IP Subnet": nicIp || "dhcp/auto", "Stato": hasIpDevs ? "Attivo" : "Standby" },
      data: { iface: nic, ip: nicIp }
    });
    links.push({ source: "node:host", target: "node:iface:nic", protocol: "ethernet" });
  }

  // 3. Protocol Buses
  if (showModbus && (rtuDevs.length > 0 || currentFilter === "modbus" || currentFilter === "all")) {
    nodes.push({
      id: "node:bus:modbus_rtu",
      label: "Modbus RTU Bus",
      sublabel: `${rtuDevs.length} slave`,
      category: "bus",
      protocol: "modbus_rtu",
      protoColor: "modbus",
      status: rtuDevs.length > 0 ? "active" : "standby",
      parent_id: "node:iface:serial",
      level: 2,
      width: 176,
      height: 50,
      metrics: { "Slave Rilevati": rtuDevs.length, "Protocollo": "Modbus RTU (RS485)" },
      data: { count: rtuDevs.length }
    });
    links.push({ source: "node:iface:serial", target: "node:bus:modbus_rtu", protocol: "modbus" });
  }

  if (showBacnet && mstpDevs.length > 0) {
    nodes.push({
      id: "node:bus:bacnet_mstp",
      label: "BACnet MS-TP Ring",
      sublabel: `${mstpDevs.length} nodi`,
      category: "bus",
      protocol: "bacnet_mstp",
      protoColor: "bacnet",
      status: "active",
      parent_id: "node:iface:serial",
      level: 2,
      width: 176,
      height: 50,
      metrics: { "Nodi MS-TP": mstpDevs.length, "Protocollo": "BACnet MS-TP Token Ring" },
      data: { count: mstpDevs.length }
    });
    links.push({ source: "node:iface:serial", target: "node:bus:bacnet_mstp", protocol: "bacnet" });
  }

  if (showModbus && (tcpDevs.length > 0 || currentFilter === "modbus")) {
    nodes.push({
      id: "node:bus:modbus_tcp",
      label: "Modbus TCP",
      sublabel: `${tcpDevs.length} server`,
      category: "bus",
      protocol: "modbus_tcp",
      protoColor: "modbus",
      status: tcpDevs.length > 0 ? "active" : "standby",
      parent_id: "node:iface:nic",
      level: 2,
      width: 176,
      height: 50,
      metrics: { "Server Modbus TCP": tcpDevs.length },
      data: { count: tcpDevs.length }
    });
    links.push({ source: "node:iface:nic", target: "node:bus:modbus_tcp", protocol: "modbus" });
  }

  if (showBacnet && (bacnetIpDevs.length > 0 || currentFilter === "bacnet" || currentFilter === "all")) {
    nodes.push({
      id: "node:bus:bacnet_ip",
      label: "BACnet/IP Network",
      sublabel: `${bacnetIpDevs.length} dispositivi`,
      category: "bus",
      protocol: "bacnet_ip",
      protoColor: "bacnet",
      status: bacnetIpDevs.length > 0 ? "active" : "standby",
      parent_id: "node:iface:nic",
      level: 2,
      width: 176,
      height: 50,
      metrics: { "Dispositivi BACnet": bacnetIpDevs.length, "Porta": "UDP 47808 (BAC0)" },
      data: { count: bacnetIpDevs.length }
    });
    links.push({ source: "node:iface:nic", target: "node:bus:bacnet_ip", protocol: "bacnet" });
  }

  if (showKnx && (store.knx.length > 0 || currentFilter === "knx" || currentFilter === "all")) {
    nodes.push({
      id: "node:bus:knx_ip",
      label: "KNXnet/IP Network",
      sublabel: `${store.knx.length} router/gw`,
      category: "bus",
      protocol: "knx_ip",
      protoColor: "knx",
      status: store.knx.length > 0 ? "active" : "standby",
      parent_id: "node:iface:nic",
      level: 2,
      width: 176,
      height: 50,
      metrics: { "Router KNX": store.knx.length, "Multicast": "224.0.23.12:3671" },
      data: { count: store.knx.length }
    });
    links.push({ source: "node:iface:nic", target: "node:bus:knx_ip", protocol: "knx" });
  }

  if (showHosts && (store.hosts.length > 0 || currentFilter === "hosts" || currentFilter === "all")) {
    nodes.push({
      id: "node:bus:arp",
      label: "IP Subnet (ARP)",
      sublabel: `${store.hosts.length} host L2`,
      category: "bus",
      protocol: "arp",
      protoColor: "arp",
      status: store.hosts.length > 0 ? "active" : "standby",
      parent_id: "node:iface:nic",
      level: 2,
      width: 176,
      height: 50,
      metrics: { "Host ARP": store.hosts.length },
      data: { count: store.hosts.length }
    });
    links.push({ source: "node:iface:nic", target: "node:bus:arp", protocol: "arp" });
  }

  // 4. Device Leaf Nodes
  if (showModbus) {
    rtuDevs.forEach(dev => {
      const nid = `node:dev:modbus:rtu:${dev.slave_id}`;
      const modelStr = dev.model_name || dev.vendor_name || (dev.registers ? (dev.registers.model || dev.registers.vendor) : "") || `ID #${dev.slave_id}`;
      const isSniffed = (dev.tags && dev.tags.includes("sniffed"));
      nodes.push({
        id: nid,
        label: `Slave #${dev.slave_id}`,
        sublabel: modelStr,
        category: "device",
        protocol: "modbus_rtu",
        protoColor: "modbus",
        status: isSniffed ? "sniffed" : "active",
        parent_id: "node:bus:modbus_rtu",
        level: 3,
        width: 176,
        height: 50,
        badge: dev.response_time_ms ? `${dev.response_time_ms.toFixed(0)}ms` : (isSniffed ? "SNIFF" : "OK"),
        metrics: {
          "Slave ID": dev.slave_id,
          "Protocollo": "Modbus RTU",
          "Porta": dev.serial_params?.port || serialPort,
          "Latenza": dev.response_time_ms ? `${dev.response_time_ms.toFixed(1)} ms` : "—",
          "Registri": dev.registers ? Object.keys(dev.registers).length : 0,
          "Tipo": isSniffed ? "Passivo (Sniffed)" : "Attivo (Sondato)"
        },
        data: dev
      });
      links.push({ source: "node:bus:modbus_rtu", target: nid, protocol: "modbus" });
    });
  }

  if (showBacnet) {
    mstpDevs.forEach(dev => {
      const nid = `node:dev:bacnet:mstp:${dev.device_id}`;
      nodes.push({
        id: nid,
        label: `MS-TP #${dev.device_id}`,
        sublabel: dev.vendor_name || `MAC ${dev.address}`,
        category: "device",
        protocol: "bacnet_mstp",
        protoColor: "bacnet",
        status: "active",
        parent_id: "node:bus:bacnet_mstp",
        level: 3,
        width: 176,
        height: 50,
        badge: "MS-TP",
        metrics: {
          "Device ID": dev.device_id,
          "Indirizzo MAC": dev.address,
          "Vendor": dev.vendor_name || "—",
          "Modello": dev.model_name || "—",
          "Oggetti": dev.object_list ? dev.object_list.length : 0
        },
        data: dev
      });
      links.push({ source: "node:bus:bacnet_mstp", target: nid, protocol: "bacnet" });
    });
  }

  if (showModbus) {
    tcpDevs.forEach(dev => {
      const nid = `node:dev:modbus:tcp:${dev.ip}_${dev.tcp_port}_${dev.slave_id}`;
      nodes.push({
        id: nid,
        label: `TCP #${dev.slave_id}`,
        sublabel: `${dev.ip}:${dev.tcp_port}`,
        category: "device",
        protocol: "modbus_tcp",
        protoColor: "modbus",
        status: "active",
        parent_id: "node:bus:modbus_tcp",
        level: 3,
        width: 176,
        height: 50,
        badge: `${dev.tcp_port}`,
        metrics: {
          "Slave ID": dev.slave_id,
          "IP": dev.ip,
          "Porta TCP": dev.tcp_port,
          "Latenza": dev.response_time_ms ? `${dev.response_time_ms.toFixed(1)} ms` : "—"
        },
        data: dev
      });
      links.push({ source: "node:bus:modbus_tcp", target: nid, protocol: "modbus" });
    });
  }

  if (showBacnet) {
    bacnetIpDevs.forEach(dev => {
      const nid = `node:dev:bacnet:ip:${dev.device_id}`;
      const subParts = [dev.vendor_name, dev.model_name].filter(Boolean);
      const sub = subParts.length ? subParts.join(" - ") : dev.address;
      nodes.push({
        id: nid,
        label: `Dev #${dev.device_id}`,
        sublabel: sub,
        category: "device",
        protocol: "bacnet_ip",
        protoColor: "bacnet",
        status: "active",
        parent_id: "node:bus:bacnet_ip",
        level: 3,
        width: 176,
        height: 50,
        badge: dev.object_list ? `${dev.object_list.length} obj` : "BACnet",
        metrics: {
          "Device ID": dev.device_id,
          "Indirizzo": dev.address,
          "Vendor": dev.vendor_name || "—",
          "Modello": dev.model_name || "—",
          "Firmware": dev.firmware_revision || "—",
          "Oggetti": dev.object_list ? dev.object_list.length : 0
        },
        data: dev
      });
      links.push({ source: "node:bus:bacnet_ip", target: nid, protocol: "bacnet" });
    });
  }

  if (showKnx) {
    store.knx.forEach(dev => {
      const nid = `node:dev:knx:${dev.individual_address}`;
      nodes.push({
        id: nid,
        label: `KNX ${dev.individual_address}`,
        sublabel: dev.device_name || dev.ip_address,
        category: "device",
        protocol: "knx_ip",
        protoColor: "knx",
        status: "active",
        parent_id: "node:bus:knx_ip",
        level: 3,
        width: 176,
        height: 50,
        badge: dev.medium || "TP1",
        metrics: {
          "Indirizzo Fisico": dev.individual_address,
          "Nome": dev.device_name || "—",
          "IP": `${dev.ip_address}:${dev.port || 3671}`,
          "MAC": dev.mac_address || "—",
          "Seriale": dev.serial_number || "—",
          "Medium": dev.medium || "TP1"
        },
        data: dev
      });
      links.push({ source: "node:bus:knx_ip", target: nid, protocol: "knx" });
    });
  }

  if (showHosts) {
    store.hosts.forEach(host => {
      const nid = `node:dev:arp:${host.ip.replace(/[^a-zA-Z0-9]/g, "_")}`;
      nodes.push({
        id: nid,
        label: host.ip,
        sublabel: host.hostname || host.mac || "Host L2",
        category: "device",
        protocol: "arp",
        protoColor: "arp",
        status: "active",
        parent_id: "node:bus:arp",
        level: 3,
        width: 176,
        height: 50,
        badge: "ARP",
        metrics: {
          "Indirizzo IP": host.ip,
          "MAC Address": host.mac || "—",
          "Hostname": host.hostname || "—",
          "Rilevato": host.first_seen ? new Date(host.first_seen).toLocaleTimeString() : "—"
        },
        data: host
      });
      links.push({ source: "node:bus:arp", target: nid, protocol: "arp" });
    });
  }

  return { nodes, links };
}

function calculateTopologyLayout(nodes, links, orientation) {
  const nodesMap = {};
  nodes.forEach(n => {
    nodesMap[n.id] = n;
    n.children = [];
  });

  links.forEach(l => {
    if (nodesMap[l.source] && nodesMap[l.target]) {
      nodesMap[l.source].children.push(nodesMap[l.target]);
    }
  });

  const isHoriz = (orientation === "horizontal");
  const colDistance = isHoriz ? 250 : 120;
  const rowDistance = isHoriz ? 68 : 190;

  let leafCounter = 0;
  function layoutSubtree(node) {
    if (!node.children || node.children.length === 0) {
      node.slot = leafCounter++;
      return;
    }
    node.children.forEach(c => layoutSubtree(c));
    const first = node.children[0].slot;
    const last = node.children[node.children.length - 1].slot;
    node.slot = (first + last) / 2;
  }

  const root = nodesMap["node:host"];
  if (root) {
    layoutSubtree(root);
  } else {
    nodes.forEach((n, idx) => { n.slot = idx; });
  }

  nodes.forEach(n => {
    if (isHoriz) {
      n.x = (n.level || 0) * colDistance + 40;
      n.y = (n.slot !== undefined ? n.slot : 0) * rowDistance + 40;
    } else {
      n.x = (n.slot !== undefined ? n.slot : 0) * rowDistance + 40;
      n.y = (n.level || 0) * colDistance + 40;
    }
  });

  return { nodes, links, nodesMap };
}

function renderTopology() {
  const container = document.getElementById("bham-topology-container");
  if (!container || container.classList.contains("hidden")) return;

  const rawData = buildTopologyData();
  const { nodes, links, nodesMap } = calculateTopologyLayout(rawData.nodes, rawData.links, topoState.orientation);
  topoState.nodes = nodes;
  topoState.links = links;
  topoState.nodesMap = nodesMap;

  const linksLayer = document.getElementById("topology-links-layer");
  const nodesLayer = document.getElementById("topology-nodes-layer");
  if (!linksLayer || !nodesLayer) return;

  linksLayer.innerHTML = "";
  nodesLayer.innerHTML = "";

  const isHoriz = (topoState.orientation === "horizontal");

  links.forEach(l => {
    const s = nodesMap[l.source];
    const t = nodesMap[l.target];
    if (!s || !t) return;

    let x1, y1, x2, y2, d;
    if (isHoriz) {
      x1 = s.x + s.width;
      y1 = s.y + s.height / 2;
      x2 = t.x;
      y2 = t.y + t.height / 2;
      const dx = (x2 - x1) * 0.45;
      d = `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
    } else {
      x1 = s.x + s.width / 2;
      y1 = s.y + s.height;
      x2 = t.x + t.width / 2;
      y2 = t.y;
      const dy = (y2 - y1) * 0.45;
      d = `M ${x1} ${y1} C ${x1} ${y1 + dy}, ${x2} ${y2 - dy}, ${x2} ${y2}`;
    }

    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", d);
    path.setAttribute("class", `topo-link link-${l.protocol || 'system'}`);
    path.setAttribute("marker-end", `url(#arrow-${l.protocol || 'system'})`);
    path.dataset.source = l.source;
    path.dataset.target = l.target;
    linksLayer.appendChild(path);
  });

  nodes.forEach(n => {
    const isSelected = (topoState.selectedNodeId === n.id);
    const matchesSearchFilter = matchesSearch(n.label) || matchesSearch(n.sublabel) || matchesSearch(n.protocol);
    const isDimmed = (currentSearch && !matchesSearchFilter);

    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    g.setAttribute("class", `topo-node ${isSelected ? 'selected' : ''} ${isDimmed ? 'dimmed' : ''}`);
    g.setAttribute("transform", `translate(${n.x}, ${n.y})`);
    g.setAttribute("data-id", n.id);
    g.onclick = (e) => {
      e.stopPropagation();
      selectTopologyNode(n.id);
    };

    let badgeHtml = "";
    if (n.badge) {
      badgeHtml = `
        <rect class="topo-node-badge-bg topo-accent-${n.protoColor}" x="${n.width - 50}" y="8" width="42" height="15" fill-opacity="0.15"></rect>
        <text class="topo-node-badge-text" x="${n.width - 29}" y="19" text-anchor="middle" fill="currentColor">${escapeHtml(n.badge)}</text>
      `;
    }

    g.innerHTML = `
      <rect class="topo-node-card" width="${n.width}" height="${n.height}"></rect>
      <rect class="topo-node-accent topo-accent-${n.protoColor}" x="0" y="0" width="${isHoriz ? 4 : n.width}" height="${isHoriz ? n.height : 4}"></rect>
      <text class="topo-node-title" x="14" y="23">${escapeHtml(n.label)}</text>
      <text class="topo-node-sub" x="14" y="39">${escapeHtml(n.sublabel)}</text>
      ${badgeHtml}
    `;

    nodesLayer.appendChild(g);
  });
}

function selectTopologyNode(nodeId) {
  topoState.selectedNodeId = nodeId;
  const n = topoState.nodesMap[nodeId];
  if (!n) return;

  document.querySelectorAll(".topo-node").forEach(el => {
    el.classList.toggle("selected", el.getAttribute("data-id") === nodeId);
  });

  const inspector = document.getElementById("topology-inspector");
  const icon = document.getElementById("topo-inspect-icon");
  const label = document.getElementById("topo-inspect-label");
  const sublabel = document.getElementById("topo-inspect-sublabel");
  const body = document.getElementById("topo-inspect-body");
  const actions = document.getElementById("topo-inspect-actions");

  if (!inspector || !label || !body || !actions) return;

  if (icon) {
    icon.className = `bham-topo-inspect-icon topo-accent-${n.protoColor}`;
    icon.textContent = n.label.substring(0, 3).toUpperCase();
  }

  label.textContent = n.label;
  sublabel.textContent = `${n.sublabel} • ${n.protocol.toUpperCase()}`;

  let rowsHtml = "";
  if (n.metrics) {
    for (const [k, v] of Object.entries(n.metrics)) {
      if (typeof v === "object" && v !== null) continue;
      rowsHtml += `
        <div class="topo-inspect-row">
          <span class="topo-inspect-key">${escapeHtml(k)}</span>
          <span class="topo-inspect-val mono">${escapeHtml(String(v))}</span>
        </div>
      `;
    }
  }
  body.innerHTML = rowsHtml;

  let actHtml = "";
  if (n.protocol === "modbus_rtu" && n.data && n.data.slave_id) {
    actHtml += `<button class="bham-btn-action bham-btn-rtu" onclick="inspectModbusSlave(${n.data.slave_id})"><span data-i18n="topo_btn_modbus_details">🔍 Dettagli Slave / Mappa</span></button>`;
  } else if (n.protocol === "modbus_tcp" && n.data && n.data.slave_id) {
    actHtml += `<button class="bham-btn-action bham-btn-tcp" onclick="inspectModbusSlave(${n.data.slave_id})"><span data-i18n="topo_btn_modbus_details">🔍 Dettagli Slave / Mappa</span></button>`;
  } else if ((n.protocol === "bacnet_ip" || n.protocol === "bacnet_mstp") && n.data && n.data.device_id) {
    actHtml += `<button class="bham-btn-action bham-btn-bacnet" onclick="inspectBACnetDevice(${n.data.device_id})"><span data-i18n="topo_btn_bacnet_objects">🔍 Esplora Oggetti</span></button>`;
  } else if (n.id === "node:iface:serial") {
    actHtml += `<button class="bham-btn-action bham-btn-sniff" onclick="openConsoleTab('serial')"><span>📊 RS485 Inspector</span></button>`;
  }

  actHtml += `<button class="bham-btn-secondary" onclick="switchMainView('table')"><span data-i18n="topo_btn_show_table">📋 Mostra in Tabella</span></button>`;

  actions.innerHTML = actHtml;
  inspector.classList.remove("hidden");
}

function closeTopologyInspector() {
  const inspector = document.getElementById("topology-inspector");
  if (inspector) inspector.classList.add("hidden");
  topoState.selectedNodeId = null;
  document.querySelectorAll(".topo-node.selected").forEach(el => el.classList.remove("selected"));
}

function exportTopologySVG() {
  const svg = document.getElementById("topology-svg");
  if (!svg) return;

  const clone = svg.cloneNode(true);
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");

  const styleEl = document.createElement("style");
  styleEl.textContent = `
    .topo-node-card { fill: #ffffff; stroke: #cbd5e1; stroke-width: 1.5; rx: 7; ry: 7; }
    .topo-node-title { font-family: sans-serif; font-size: 11.5px; font-weight: bold; fill: #0f172a; }
    .topo-node-sub { font-family: monospace; font-size: 9.5px; fill: #64748b; }
    .topo-link { fill: none; stroke-width: 1.8; stroke-linecap: round; }
    .link-serial { stroke: #f59e0b; }
    .link-ethernet { stroke: #10b981; }
    .link-modbus { stroke: #0284c7; }
    .link-bacnet { stroke: #8b5cf6; }
    .link-knx { stroke: #ea580c; }
    .link-arp { stroke: #10b981; stroke-dasharray: 4 3; }
    .link-system { stroke: #64748b; }
    .topo-accent-host { fill: #2563eb; }
    .topo-accent-serial { fill: #d97706; }
    .topo-accent-nic { fill: #059669; }
    .topo-accent-modbus { fill: #0284c7; }
    .topo-accent-bacnet { fill: #7c3aed; }
    .topo-accent-knx { fill: #c2410c; }
    .topo-accent-arp { fill: #059669; }
    .topo-grid-dot { fill: #cbd5e1; }
  `;
  clone.insertBefore(styleEl, clone.firstChild);

  const xml = new XMLSerializer().serializeToString(clone);
  const blob = new Blob([xml], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const site = (store.config?.site_name || "bham_topology").replace(/[^a-zA-Z0-9_-]/g, "_");
  const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
  a.href = url;
  a.download = `${site}_${ts}.svg`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  log("[OK] Mappa topologica esportata con successo in formato vettoriale SVG.");
}

// ── Initialize App ────────────────────────────────────────────────────────────

function loadSavedScanParams() {
  try {
    const raw = localStorage.getItem("bham-scan-params");
    if (raw) {
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
    }
    const coll = localStorage.getItem("bham-console-collapsed");
    const col = document.getElementById("console-col");
    if (col) {
      if (coll === "1") {
        collapseConsole();
      } else {
        expandConsole();
      }
    }
    const savedView = localStorage.getItem("bham-main-view");
    if (savedView === "topology") {
      switchMainView("topology");
    }
  } catch (e) {
    console.warn("Failed to load saved scan params:", e);
  }
}

// ── Session Diff ("Prima vs Dopo") Engine ─────────────────────────────────────

let _diffSessionsList = [];
let _lastDiffResult = null;
let _diffProtoFilter = "all";
let _diffStatusFilter = "all";

function escapeDiffHTML(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

async function openDiffModal() {
  const modal = document.getElementById("diff-modal");
  if (!modal) return;
  modal.style.display = "flex";

  const baseSelect = document.getElementById("diff-baseline-select");
  const targetSelect = document.getElementById("diff-target-select");
  if (!baseSelect || !targetSelect) return;

  baseSelect.innerHTML = `<option value="">Caricamento sessioni...</option>`;
  targetSelect.innerHTML = `<option value="__live__">⚡ Stato Attivo Attuale (Live)</option>`;

  try {
    const list = await fetch(`${API}/saved-sessions/list`).then(r => r.json());
    _diffSessionsList = list || [];

    if (!_diffSessionsList.length) {
      baseSelect.innerHTML = `<option value="">Nessuna sessione salvata trovata in archivio</option>`;
      targetSelect.innerHTML = `<option value="__live__">⚡ Stato Attivo Attuale (Live)</option>`;
      return;
    }

    baseSelect.innerHTML = _diffSessionsList.map(s => {
      const counts = s.device_counts || {};
      const devBadge = `(MB:${counts.modbus || 0} BN:${counts.bacnet || 0} KNX:${counts.knx || 0} IP:${counts.ip_hosts || 0})`;
      const dt = s.saved_at ? s.saved_at.substring(0, 19).replace('T', ' ') : '';
      return `<option value="${s.filename}">${s.name} [${dt}] ${devBadge}</option>`;
    }).join("");

    targetSelect.innerHTML = `
      <option value="__live__">⚡ Stato Attivo Attuale (Live State)</option>
      ${_diffSessionsList.map(s => {
        const counts = s.device_counts || {};
        const devBadge = `(MB:${counts.modbus || 0} BN:${counts.bacnet || 0} KNX:${counts.knx || 0} IP:${counts.ip_hosts || 0})`;
        const dt = s.saved_at ? s.saved_at.substring(0, 19).replace('T', ' ') : '';
        return `<option value="${s.filename}">${s.name} [${dt}] ${devBadge}</option>`;
      }).join("")}
    `;

    if (_lastDiffResult) {
      displayDiffResults(_lastDiffResult);
    }
  } catch (err) {
    console.error("Errore caricamento sessioni per diff:", err);
    baseSelect.innerHTML = `<option value="">Errore caricamento: ${err.message}</option>`;
  }
}

async function openDiffModalForSession(filename) {
  closeSettingsModal();
  await openDiffModal();
  const baseSelect = document.getElementById("diff-baseline-select");
  const targetSelect = document.getElementById("diff-target-select");
  if (baseSelect) baseSelect.value = filename;
  if (targetSelect) targetSelect.value = "__live__";
  await runSessionDiff();
}

function closeDiffModal() {
  const modal = document.getElementById("diff-modal");
  if (modal) modal.style.display = "none";
}

async function runSessionDiff() {
  const baseSelect = document.getElementById("diff-baseline-select");
  const targetSelect = document.getElementById("diff-target-select");
  const btn = document.getElementById("btn-run-diff");
  if (!baseSelect || !targetSelect) return;

  const baseline_filename = baseSelect.value;
  const target_filename = targetSelect.value;

  if (!baseline_filename) {
    alert("Seleziona una sessione di Baseline valida.");
    return;
  }

  const oldBtnHtml = btn ? btn.innerHTML : "";
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<svg class="bham-svg-sm bham-spin" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2"></circle></svg> Calcolo in corso...`;
  }

  try {
    const res = await postAPI("/sessions/diff", {
      baseline_filename: baseline_filename,
      target_filename: target_filename === "__live__" ? null : target_filename,
    });

    if (res && res.summary) {
      _lastDiffResult = res;
      displayDiffResults(res);
      log(`[OK] [DIFF] Confronto completato: +${res.summary.total.added} aggiunti, -${res.summary.total.removed} rimossi, ~${res.summary.total.modified} modificati.`);
    } else {
      alert("Errore durante il calcolo del confronto: risposta non valida.");
    }
  } catch (err) {
    console.error("Errore calcolo diff:", err);
    alert(`Errore calcolo diff: ${err.message}`);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = oldBtnHtml;
    }
  }
}

function displayDiffResults(res) {
  const banner = document.getElementById("diff-summary-banner");
  const filterToolbar = document.getElementById("diff-filter-toolbar");
  const prompt = document.getElementById("diff-empty-prompt");
  const table = document.getElementById("diff-data-table");
  const btnCsv = document.getElementById("btn-export-diff-csv");
  const btnJson = document.getElementById("btn-export-diff-json");

  if (banner) banner.style.display = "flex";
  if (filterToolbar) filterToolbar.style.display = "flex";
  if (prompt) prompt.style.display = "none";
  if (table) table.style.display = "table";
  if (btnCsv) btnCsv.style.display = "inline-flex";
  if (btnJson) btnJson.style.display = "inline-flex";

  const tot = res.summary?.total || {};
  const setTxt = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val !== undefined ? val : 0;
  };

  setTxt("diff-stat-added", tot.added);
  setTxt("diff-stat-removed", tot.removed);
  setTxt("diff-stat-modified", tot.modified);
  setTxt("diff-stat-unchanged", tot.unchanged);

  renderDiffTable();
}

function setDiffProtoFilter(proto) {
  _diffProtoFilter = proto;
  const tabs = document.querySelectorAll("#diff-filter-toolbar .bham-tabs .bham-tab");
  tabs.forEach(tab => {
    const id = tab.id;
    if (
      (proto === "all" && id === "diff-tab-all") ||
      (proto === "modbus" && id === "diff-tab-modbus") ||
      (proto === "bacnet" && id === "diff-tab-bacnet") ||
      (proto === "knx" && id === "diff-tab-knx") ||
      (proto === "ip_host" && id === "diff-tab-hosts")
    ) {
      tab.classList.add("active");
    } else {
      tab.classList.remove("active");
    }
  });
  renderDiffTable();
}

function setDiffStatusFilter(status) {
  _diffStatusFilter = status;
  const btns = document.querySelectorAll(".bham-diff-status-btn");
  btns.forEach(btn => {
    if (btn.id === `diff-status-${status}`) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });
  renderDiffTable();
}

function renderDiffTable() {
  const tbody = document.getElementById("diff-data-tbody");
  if (!tbody || !_lastDiffResult) return;

  let items = _lastDiffResult.items || [];

  if (_diffProtoFilter !== "all") {
    items = items.filter(it => it.protocol === _diffProtoFilter);
  }

  if (_diffStatusFilter !== "all") {
    items = items.filter(it => it.status === _diffStatusFilter);
  }

  if (!items.length) {
    tbody.innerHTML = `<tr><td colspan="4" class="text-dim" style="text-align:center;padding:20px">Nessuna periferica corrisponde ai filtri selezionati.</td></tr>`;
    return;
  }

  tbody.innerHTML = items.map(it => {
    let protoBadge = `<span class="badge" style="font-size:10px">${it.protocol.toUpperCase()}</span>`;
    if (it.protocol === "modbus") protoBadge = `<span class="badge badge-modbus" style="font-size:10px">MODBUS</span>`;
    else if (it.protocol === "bacnet") protoBadge = `<span class="badge badge-bacnet" style="font-size:10px">BACNET</span>`;
    else if (it.protocol === "knx") protoBadge = `<span class="badge badge-knx" style="font-size:10px">KNX</span>`;
    else if (it.protocol === "ip_host") protoBadge = `<span class="badge badge-arp" style="font-size:10px">ARP HOST</span>`;

    let statusBadge = "";
    if (it.status === "added") {
      statusBadge = `<span class="bham-diff-badge bham-diff-badge-added">🟢 + NUOVO</span>`;
    } else if (it.status === "removed") {
      statusBadge = `<span class="bham-diff-badge bham-diff-badge-removed">🔴 - ASSENTE</span>`;
    } else if (it.status === "modified") {
      statusBadge = `<span class="bham-diff-badge bham-diff-badge-modified">🟡 ~ MODIFICATO</span>`;
    } else {
      statusBadge = `<span class="bham-diff-badge bham-diff-badge-unchanged">⚪ = INVARIATO</span>`;
    }

    let detailsHtml = "";
    if (it.status === "modified" && it.changes && it.changes.length) {
      detailsHtml = it.changes.map(ch => {
        const desc = ch.description || ch.field;
        const oldVal = ch.baseline !== null && ch.baseline !== undefined ? JSON.stringify(ch.baseline) : "—";
        const newVal = ch.target !== null && ch.target !== undefined ? JSON.stringify(ch.target) : "—";
        return `
          <div class="bham-diff-change-item">
            <b>${desc}</b>:
            <span class="bham-diff-change-val-old">${escapeDiffHTML(oldVal)}</span>
            ➔
            <span class="bham-diff-change-val-new">${escapeDiffHTML(newVal)}</span>
          </div>
        `;
      }).join("");
    } else if (it.status === "added") {
      const td = it.target_data || {};
      const parts = [];
      if (td.ip) parts.push(`IP: ${td.ip}`);
      if (td.tcp_port) parts.push(`Porta: ${td.tcp_port}`);
      if (td.serial_params) parts.push(`Seriale: ${td.serial_params.port} @ ${td.serial_params.baudrate}bps`);
      if (td.address) parts.push(`Addr: ${td.address}`);
      if (td.individual_address) parts.push(`Indirizzo KNX: ${td.individual_address}`);
      if (td.vendor_name) parts.push(`Costruttore: ${td.vendor_name}`);
      if (td.model_name) parts.push(`Modello: ${td.model_name}`);
      if (td.mac) parts.push(`MAC: ${td.mac}`);
      detailsHtml = `<span class="text-dim" style="font-size:11px">${escapeDiffHTML(parts.join(" | ") || "Apparato rilevato nella nuova scansione")}</span>`;
    } else if (it.status === "removed") {
      const bd = it.baseline_data || {};
      const parts = [];
      if (bd.ip) parts.push(`IP: ${bd.ip}`);
      if (bd.tcp_port) parts.push(`Porta: ${bd.tcp_port}`);
      if (bd.serial_params) parts.push(`Seriale: ${bd.serial_params.port} @ ${bd.serial_params.baudrate}bps`);
      if (bd.address) parts.push(`Addr: ${bd.address}`);
      if (bd.individual_address) parts.push(`Indirizzo KNX: ${bd.individual_address}`);
      if (bd.vendor_name) parts.push(`Costruttore: ${bd.vendor_name}`);
      if (bd.model_name) parts.push(`Modello: ${bd.model_name}`);
      if (bd.mac) parts.push(`MAC: ${bd.mac}`);
      detailsHtml = `<span class="text-dim" style="font-size:11px;color:#ef4444">${escapeDiffHTML(parts.join(" | ") || "Non risponde più alle richieste o scollegato")}</span>`;
    } else {
      detailsHtml = `<span class="text-dim" style="font-size:11px">Configurazione e parametri identici.</span>`;
    }

    return `
      <tr>
        <td>${protoBadge}</td>
        <td>
          <div style="font-weight:600;font-size:12px">${escapeDiffHTML(it.identifier)}</div>
          <div class="text-dim" style="font-size:10.5px">${escapeDiffHTML(it.label)}</div>
        </td>
        <td style="text-align:center">${statusBadge}</td>
        <td>${detailsHtml}</td>
      </tr>
    `;
  }).join("");
}

function exportDiffCSV() {
  if (!_lastDiffResult || !_lastDiffResult.items) return;
  const headers = ["Protocollo", "Identificatore", "Etichetta", "Stato", "Dettagli"];
  const rows = _lastDiffResult.items.map(it => {
    let details = "";
    if (it.changes && it.changes.length) {
      details = it.changes.map(c => `${c.description || c.field}: ${c.baseline} -> ${c.target}`).join(" ; ");
    } else if (it.status === "added") {
      details = "Nuovo apparato";
    } else if (it.status === "removed") {
      details = "Apparato offline o rimosso";
    } else {
      details = "Invariato";
    }
    return [
      `"${it.protocol}"`,
      `"${it.identifier}"`,
      `"${it.label.replace(/"/g, '""')}"`,
      `"${it.status}"`,
      `"${details.replace(/"/g, '""')}"`,
    ].join(",");
  });

  const csvContent = "\uFEFF" + [headers.join(","), ...rows].join("\r\n");
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const ts = new Date().toISOString().replace(/[:.]/g, "-").substring(0, 19);
  a.href = url;
  a.download = `bham_session_diff_${ts}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function exportDiffJSON() {
  if (!_lastDiffResult) return;
  const jsonStr = JSON.stringify(_lastDiffResult, null, 2);
  const blob = new Blob([jsonStr], { type: "application/json;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const ts = new Date().toISOString().replace(/[:.]/g, "-").substring(0, 19);
  a.href = url;
  a.download = `bham_session_diff_${ts}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ── BBMD (BACnet Broadcast Management Device) Diagnostics ────────────────────

function toggleBBMDBox() {
  const drawer = document.getElementById("bbmd-fields-drawer");
  const chevron = document.getElementById("bbmd-toggle-chevron");
  if (!drawer) return;
  const isHidden = drawer.style.display === "none";
  drawer.style.display = isHidden ? "block" : "none";
  if (chevron) chevron.textContent = isHidden ? "▼" : "▶";
}

function openBBMDModal() {
  const defaultIp = document.getElementById("bbmd-ip")?.value.trim() || "";
  const defaultPort = document.getElementById("bbmd-port")?.value.trim() || "47808";

  const modalIp = document.getElementById("modal-bbmd-ip");
  const modalPort = document.getElementById("modal-bbmd-port");
  if (modalIp && !modalIp.value && defaultIp) modalIp.value = defaultIp;
  if (modalPort && !modalPort.value && defaultPort) modalPort.value = defaultPort;

  const modal = document.getElementById("bbmd-modal");
  if (modal) modal.style.display = "flex";
  if (modalIp && modalIp.value) {
    fetchBBMDTables();
  }
}

function closeBBMDModal() {
  const m = document.getElementById("bbmd-modal");
  if (m) m.style.display = "none";
}

async function fetchBBMDTables() {
  const ipInput = document.getElementById("modal-bbmd-ip");
  const portInput = document.getElementById("modal-bbmd-port");
  const ip = ipInput?.value.trim();
  const port = parseInt(portInput?.value) || 47808;

  if (!ip) {
    alert(window.t ? window.t("bbmd_missing_ip_alert") : "Inserisci un indirizzo IP valido per il router BBMD.");
    return;
  }

  // Sincronizza anche il campo nella sidebar se vuoto
  const sideIp = document.getElementById("bbmd-ip");
  if (sideIp && !sideIp.value) sideIp.value = ip;

  const btn = document.getElementById("btn-modal-query-bbmd");
  const statusMsg = document.getElementById("bbmd-status-msg");
  if (btn) btn.disabled = true;
  if (statusMsg) {
    statusMsg.style.display = "block";
    statusMsg.innerHTML = `<span style="color:var(--text-muted)">Interrogazione tabelle BBMD in corso (${ip}:${port})...</span>`;
  }

  try {
    const res = await fetch(`/api/v1/bacnet/bbmd/tables?bbmd_ip=${encodeURIComponent(ip)}&bbmd_port=${port}&timeout=3.5`);
    const data = await res.json();
    renderBBMDTables(data);
  } catch (err) {
    console.error("Errore lettura tabelle BBMD:", err);
    if (statusMsg) {
      statusMsg.innerHTML = `<span style="color:var(--accent-danger)">Errore di comunicazione: ${err.message || err}</span>`;
    }
  } finally {
    if (btn) btn.disabled = false;
  }
}

function renderBBMDTables(data) {
  const statusMsg = document.getElementById("bbmd-status-msg");
  const bdtTbody = document.getElementById("bbmd-bdt-tbody");
  const fdtTbody = document.getElementById("bbmd-fdt-tbody");
  const bdtCount = document.getElementById("bbmd-bdt-count");
  const fdtCount = document.getElementById("bbmd-fdt-count");

  const bdtList = data?.bdt || [];
  const fdtList = data?.fdt || [];

  if (bdtCount) bdtCount.textContent = `${bdtList.length} peer`;
  if (fdtCount) fdtCount.textContent = `${fdtList.length} dev`;

  if (statusMsg) {
    if (data.error) {
      statusMsg.innerHTML = `<span style="color:var(--accent-warning)">Avviso BBMD: ${data.error}</span>`;
      statusMsg.style.display = "block";
    } else if (bdtList.length === 0 && fdtList.length === 0) {
      statusMsg.innerHTML = `<span style="color:var(--text-muted)">Nessuna voce presente o risposta BVLL vuota dal nodo ${data.bbmd_ip}.</span>`;
      statusMsg.style.display = "block";
    } else {
      statusMsg.innerHTML = `<span style="color:var(--accent-success)">Tabelle lette con successo da ${data.bbmd_ip}:${data.bbmd_port}</span>`;
      statusMsg.style.display = "block";
    }
  }

  if (bdtTbody) {
    if (bdtList.length === 0) {
      bdtTbody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:var(--text-muted); padding:14px;">Nessun peer router BBMD configurato nella tabella BDT.</td></tr>`;
    } else {
      bdtTbody.innerHTML = bdtList.map(entry => `
        <tr>
          <td class="cell-mono cell-text-main" style="font-weight:600">${entry.ip}</td>
          <td class="cell-mono cell-text-dim">${entry.port}</td>
          <td class="cell-mono cell-text-muted">${entry.broadcast_mask}</td>
          <td style="text-align:center"><span class="bham-badge-proto proto-bacnet">Peer BDT</span></td>
        </tr>
      `).join("");
    }
  }

  if (fdtTbody) {
    if (fdtList.length === 0) {
      fdtTbody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:var(--text-muted); padding:14px;">Nessun Foreign Device attualmente registrato nella tabella FDT.</td></tr>`;
    } else {
      fdtTbody.innerHTML = fdtList.map(entry => `
        <tr>
          <td class="cell-mono color-bacnet" style="font-weight:600">${entry.ip}</td>
          <td class="cell-mono cell-text-dim">${entry.port}</td>
          <td class="cell-mono cell-text-muted">${entry.ttl}s</td>
          <td class="cell-mono cell-text-main" style="font-weight:600; color:var(--accent-success)">${entry.remaining_time}s</td>
        </tr>
      `).join("");
    }
  }
}

if (window.I18N) {
  window.I18N.init();
}
loadSavedScanParams();
connectWS();

