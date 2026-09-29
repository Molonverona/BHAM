# Permessi Hardware – BHAM

BHAM accede a **porte seriali** (RS485/USB) e **schede di rete** (ARP sniffer). Questi richiedono autorizzazioni a livello OS.

---

## 🐧 Linux (Debian, Ubuntu, Fedora, Arch)

### Requisiti
- **Porte seriali RS485** (via `/dev/ttyUSB*`, `/dev/ttyACM*`): gruppo `dialout`
- **ARP Sniffer** (raw socket): `CAP_NET_RAW` capability

### Opzione 1: Setup Automatico (CONSIGLIATO)

```bash
sudo ./scripts/setup_permissions.sh
```

Questo:
1. Aggiunge il tuo utente al gruppo `dialout` (porte seriali)
2. Imposta `CAP_NET_RAW` su Python (ARP sniffer)
3. Richiede **logout/login** se modificati i gruppi

Dopo il setup, avvia:
```bash
./start.sh
```

### Opzione 2: Manuale (senza Logout)

**Per porte seriali:**
```bash
sudo usermod -aG dialout $USER
# Richiede logout/login per avere effetto
```

**Per ARP Sniffer (immediato):**
```bash
sudo setcap cap_net_raw+eip .venv/bin/python3
# NON richiede logout/login – ha effetto subito
```

Dopo questa riga, avvia normalmente:
```bash
./start.sh
```

### Opzione 3: Esecuzione con Sudo (Temporaneo)

Se non vuoi configurare i permessi:
```bash
sudo ./start.sh
```

**Non consigliato** per uso prolungato (il server gira come root, rischio di sicurezza).

---

## 🪟 Windows 10/11

### Requisiti
- **Porte seriali (COM)**: Funzionano automaticamente
- **ARP Sniffer**: Richiede **Administrator**

### Esecuzione come Amministratore

1. Tasto **destro** su `start.cmd` → **"Esegui come amministratore"**
   
   Oppure:

2. Da PowerShell/CMD come admin:
   ```cmd
   python3 -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   python3 main.py
   ```

3. Oppure eseguibile compilato (PyInstaller):
   - Tasto destro su `bham.exe` → **"Esegui come amministratore"**

### Note
- Le porte **COM seriali** funzionano senza elevazione
- L'**ARP sniffer** (Scapy) richiede Administrator per sniffing raw
- Se non sei admin: eseguibile ARP sniffer disabilitato, serial/Modbus normali

---

## 🍎 macOS

**Porte seriali**: Funzionano su `/dev/tty.*` / `/dev/cu.*` senza permessi speciali.

**ARP Sniffer**: Richiede `sudo` (Scapy su macOS ha limitazioni).

```bash
sudo python3 main.py
```

---

## 📋 Verifica Permessi

Avvia `./start.sh`. Il controllo al boot mostrerà:

```
✅  Permessi OK (dialout + cap_net_raw)
```

Se manca qualcosa:
```
⚠️  Porte seriali RS485: utente non in gruppo 'dialout'
⚠️  ARP Sniffer: CAP_NET_RAW non configurata

Opzioni per avviare BHAM:
  1. Avvia con sudo (accesso completo subito):
     sudo ./start.sh
  2. Esegui setup e poi avvia normalmente:
     sudo ./scripts/setup_permissions.sh
```

---

## ⚡ Riassunto Veloce

| OS | Comando | Note |
|----|---------|------|
| **Linux** | `sudo ./scripts/setup_permissions.sh` then `./start.sh` | Setup una volta, poi no sudo |
| **Linux** (temp) | `sudo ./start.sh` | Veloce, ma rischioso (root) |
| **Windows** | Esegui come Amministratore | Tasto destro → "Esegui come admin" |
| **macOS** | `sudo python3 main.py` | ARP richiede sudo |

---

## 🔧 Troubleshooting

### "Permesso negato" su porta seriale
```bash
# Check se sei in dialout:
groups $USER

# Se no, aggiungi:
sudo usermod -aG dialout $USER
# Poi logout/login
```

### "Operazione non consentita" (raw socket / ARP)
```bash
# Check CAP_NET_RAW:
getcap .venv/bin/python3

# Se no, imposta:
sudo setcap cap_net_raw+eip .venv/bin/python3

# Verifica:
getcap .venv/bin/python3
# Deve mostrare: .venv/bin/python3 = cap_net_raw+eip
```

### "Device /dev/ttyUSB0 non trovato"
- USB-RS485 non rilevato: controlla connessione, driver FTDI/CP210x
- `dmesg | tail` per vedere se riconosciuto
- `ls -la /dev/tty*` per elencare porte disponibili

---

## 🔐 Note di Sicurezza

- **`setcap`** è preferibile a **`sudo`** (capability è granulare, root permette tutto)
- **Gruppo `dialout`**: accesso a tutte le porte seriali (qualsiasi USB) – rischio se utenti non fidati
- **BHAM su `0.0.0.0`**: accessibile da qualsiasi IP sulla rete (no auth) – bind su `127.0.0.1` se sensibile
