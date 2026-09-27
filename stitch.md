# BHAM — Design System & Style Tokens Spec (per Antigravity / Frontend)
**Versione:** 2.0 Industrial Telemetry  
**Target:** Applicazione desktop/mobile per collaudi BACS (Modbus RTU/TCP, BACnet/IP, ARP sniffer, FC43 diagnostics)

---

## 1. Principi di Design Ergonomico Industriale
1. **Zero Distrazioni & No-Frills**: Contrasti netti, bordi sottili e precisi (1px solid), niente sfocature eccessive.
2. **Dual Mode (Dark Lab / Light Field)**:
   - **Dark Mode (Default)**: Ideale per sale quadri, locali tecnici con scarsa illuminazione e lunghe sessioni di collaudo.
   - **Light Mode (Field High-Contrast)**: Calibrato stile *Siemens TIA Portal / Fluke Telemetry* per visibilità sotto luce solare o neon intensi in cantiere.
3. **Color-Coded Protocol Identity**:
   - 🔵 **Modbus (RTU / TCP)**: Ciano `#00d2ff` (Dark) / `#0077b6` (Light)
   - 🟣 **BACnet/IP**: Viola `#b57edc` / `#a855f7` (Dark) / `#7c3aed` (Light)
   - 🟢 **ARP / Network Host**: Smeraldo `#10b981` (Dark) / `#059669` (Light)
   - 🟠 **FC43 / Diagnostics**: Ambra `#f59e0b` (Dark) / `#d97706` (Light)
   - 🔴 **Emergency / Abort Scan**: Rosso segnale `#ef4444` (Dark) / `#dc2626` (Light)
4. **Tipografia Monospace Tattica**:
   - `JetBrains Mono`, `Fira Code`, o `ui-monospace` per tutti i valori hardware: indirizzi IP, CIDR, registri Modbus, Slave ID, porte `/dev/tty*`, MAC address e timestamp dei log.
   - `Inter`, `system-ui` per label di controllo e navigazione.

---

## 2. Token CSS (Tailwind & CSS Custom Properties)

```css
:root {
  /* ========================================================
     THEME: LIGHT MODE (Field High-Contrast)
     ======================================================== */
  --bham-bg-canvas: #f1f4f9;
  --bham-bg-surface: #ffffff;
  --bham-bg-surface-elevated: #e6ebf2;
  --bham-bg-input: #f8fafc;
  --bham-border: #cbd5e1;
  --bham-border-focus: #0077b6;

  /* Typography */
  --bham-text-main: #0f172a;
  --bham-text-muted: #475569;
  --bham-text-dim: #64748b;

  /* Status & Protocol Accents */
  --bham-modbus: #0284c7;
  --bham-modbus-bg: rgba(2, 132, 199, 0.10);
  --bham-bacnet: #7c3aed;
  --bham-bacnet-bg: rgba(124, 58, 237, 0.10);
  --bham-network: #059669;
  --bham-network-bg: rgba(5, 150, 105, 0.10);
  --bham-diag: #d97706;
  --bham-diag-bg: rgba(217, 119, 6, 0.10);
  --bham-danger: #dc2626;
  --bham-danger-bg: rgba(220, 38, 38, 0.12);
  --bham-success: #16a34a;

  /* Console Log Specifics */
  --bham-console-bg: #0f172a;
  --bham-console-text: #94a3b8;
  --bham-console-highlight: #38bdf8;

  --bham-radius: 4px;
}

[data-theme="dark"] {
  /* ========================================================
     THEME: DARK MODE (Obsidian Telemetry)
     ======================================================== */
  --bham-bg-canvas: #090e17;
  --bham-bg-surface: #101726;
  --bham-bg-surface-elevated: #162035;
  --bham-bg-input: #0b111c;
  --bham-border: #1e293b;
  --bham-border-focus: #00f2fe;

  /* Typography */
  --bham-text-main: #f1f5f9;
  --bham-text-muted: #94a3b8;
  --bham-text-dim: #64748b;

  /* Status & Protocol Accents */
  --bham-modbus: #00f2fe;
  --bham-modbus-bg: rgba(0, 242, 254, 0.12);
  --bham-bacnet: #c084fc;
  --bham-bacnet-bg: rgba(192, 132, 252, 0.12);
  --bham-network: #10b981;
  --bham-network-bg: rgba(16, 185, 129, 0.12);
  --bham-diag: #f59e0b;
  --bham-diag-bg: rgba(245, 158, 11, 0.12);
  --bham-danger: #ef4444;
  --bham-danger-bg: rgba(239, 68, 68, 0.18);
  --bham-success: #22c55e;

  /* Console Log Specifics */
  --bham-console-bg: #070b12;
  --bham-console-text: #86efac;
  --bham-console-highlight: #38bdf8;
}
```

---

## 3. Tailwind Configuration Snippet (`tailwind.config.js`)

```javascript
module.exports = {
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        bham: {
          canvas: 'var(--bham-bg-canvas)',
          surface: 'var(--bham-bg-surface)',
          elevated: 'var(--bham-bg-surface-elevated)',
          input: 'var(--bham-bg-input)',
          border: 'var(--bham-border)',
          main: 'var(--bham-text-main)',
          muted: 'var(--bham-text-muted)',
          modbus: 'var(--bham-modbus)',
          bacnet: 'var(--bham-bacnet)',
          network: 'var(--bham-network)',
          diag: 'var(--bham-diag)',
          danger: 'var(--bham-danger)',
        }
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      }
    }
  }
}
```

---

## 4. Linee Guida per Antigravity
1. **Pulsanti d'Emergenza / Abort**: Devono rimanere *sticky* in header per prevenire freeze della porta seriale o flood di rete in caso di broadcast non controllato.
2. **Scrolling indipendente delle 3 colonne**: I form a sinistra e la console a destra non devono scrollare insieme alla tabella dei dispositivi trovati.
3. **Toggle Scuro/Chiaro**: Aggiungere un data attribute `data-theme="dark"` / `data-theme="light"` sul tag root `<html>` o sul container principale.
