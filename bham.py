#!/usr/bin/env python3
"""
BHAM Launcher – auto-setup cross-platform (Windows / Linux / macOS).

Uso:
    python bham.py              # verifica dipendenze, installa e apre il browser
    python bham.py --yes        # installa senza chiedere conferma
    python bham.py --check      # verifica solo le dipendenze (exit 0 = OK, 1 = mancanti)
    python bham.py --no-browser # non aprire automaticamente il browser
    python bham.py --no-reload  # avvia senza auto-reload (uso in campo)
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.resolve()
VENV_DIR = ROOT_DIR / ".venv"
REQ_FILE = ROOT_DIR / "requirements.txt"
IS_WINDOWS = platform.system() == "Windows"
# Versioni per cui le dipendenze pinnate hanno wheel binari (niente compilazione).
# 3.12 è quella testata in CI; aggiornare insieme a requirements.txt.
SUPPORTED_PY = [(3, 12), (3, 13)]

# Console di Windows / pipe non-UTF8: evita UnicodeEncodeError sui simboli.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

# Script eseguito DENTRO il venv: confronta requirements.txt con i pacchetti installati.
_CHECK_SCRIPT = r"""
import re, sys
from importlib import metadata
missing = []
for raw in open(sys.argv[1], encoding="utf-8"):
    line = raw.split("#", 1)[0].strip()
    if not line:
        continue
    m = re.match(r"^([A-Za-z0-9_.\-]+)(\[[^\]]*\])?\s*(==|>=)?\s*([^\s;]*)", line)
    if not m:
        continue
    name, op, want = m.group(1), m.group(3), m.group(4)
    try:
        have = metadata.version(name)
    except metadata.PackageNotFoundError:
        missing.append(f"{line}  (non installato)")
        continue
    if op == "==" and have != want:
        missing.append(f"{line}  (installato {have})")
print("\n".join(missing))
sys.exit(1 if missing else 0)
"""


def venv_python() -> Path:
    return VENV_DIR / ("Scripts/python.exe" if IS_WINDOWS else "bin/python3")


def _py_version(exe: str | Path, prefix: list[str] | None = None) -> tuple[int, int] | None:
    try:
        out = subprocess.check_output(
            (prefix or [str(exe)]) + ["-c", "import sys;print(sys.version_info[0],sys.version_info[1])"],
            text=True, stderr=subprocess.DEVNULL, timeout=15,
        )
        a, b = out.split()
        return int(a), int(b)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def find_compatible_python() -> str | None:
    """Interprete compatibile: quello corrente se supportato, altrimenti cerca nel sistema."""
    if sys.version_info[:2] in SUPPORTED_PY:
        return sys.executable
    for major, minor in SUPPORTED_PY:
        if IS_WINDOWS and shutil.which("py"):
            # Python Launcher per Windows: "py -3.12"
            try:
                exe = subprocess.check_output(
                    ["py", f"-{major}.{minor}", "-c", "import sys;print(sys.executable)"],
                    text=True, stderr=subprocess.DEVNULL, timeout=15,
                ).strip()
                if exe:
                    return exe
            except (OSError, subprocess.SubprocessError):
                pass
        exe = shutil.which(f"python{major}.{minor}")
        if exe and _py_version(exe) == (major, minor):
            return exe
    return None


def supported_list() -> str:
    return ", ".join(f"{a}.{b}" for a, b in SUPPORTED_PY)


def read_requirements() -> list[str]:
    if not REQ_FILE.exists():
        return []
    deps = []
    for raw in REQ_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            deps.append(line)
    return deps


def missing_dependencies() -> list[str] | None:
    """None = venv assente; [] = tutto OK; lista = pacchetti mancanti/disallineati."""
    py = venv_python()
    if not py.exists():
        return None
    res = subprocess.run(
        [str(py), "-c", _CHECK_SCRIPT, str(REQ_FILE)],
        capture_output=True, text=True,
    )
    if res.returncode == 0:
        return []
    out = [l for l in res.stdout.splitlines() if l.strip()]
    return out or ["(verifica fallita) " + res.stderr.strip()[:200]]


def ask(prompt: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    if not sys.stdin or not sys.stdin.isatty():
        print("Terminale non interattivo: usa --yes per installare automaticamente.")
        return False
    try:
        return input(prompt).strip().lower() not in ("n", "no")
    except EOFError:
        return False


def setup(missing: list[str] | None, assume_yes: bool) -> bool:
    print("=" * 60)
    if missing is None:
        print(" BHAM – ambiente virtuale non trovato (.venv).")
        todo = read_requirements()
    else:
        print(" BHAM – dipendenze mancanti o con versione diversa.")
        todo = missing
    print("=" * 60)
    if not REQ_FILE.exists():
        print("ERRORE: requirements.txt non trovato in", ROOT_DIR)
        return False

    print("Pacchetti da scaricare/installare:")
    for d in todo:
        print(f"  - {d}")
    print(f"\nDestinazione: {VENV_DIR}  (isolato, non tocca il Python di sistema)")

    if not ask("\nProcedere con download e installazione? [S/n]: ", assume_yes):
        print("Operazione annullata. BHAM non può avviarsi senza dipendenze.")
        return False

    try:
        if missing is None:
            base = find_compatible_python()
            if not base:
                print_python_help()
                return False
            print(f"\n[1/3] Creazione ambiente virtuale con {base} ...")
            try:
                subprocess.check_call([base, "-m", "venv", str(VENV_DIR)], stderr=subprocess.PIPE)
            except subprocess.CalledProcessError:
                # Caso frequente su Debian/Ubuntu: ensurepip assente (pacchetto python3-venv non installato)
                print("[i] ensurepip non presente nel sistema, creazione venv con bootstrap automatico di pip...")
                subprocess.check_call([base, "-m", "venv", "--without-pip", str(VENV_DIR)])
                py_tmp = str(venv_python())
                import urllib.request
                get_pip_path = VENV_DIR / "get-pip.py"
                urllib.request.urlretrieve("https://bootstrap.pypa.io/get-pip.py", str(get_pip_path))
                subprocess.check_call([py_tmp, str(get_pip_path), "-q"])
                if get_pip_path.exists():
                    get_pip_path.unlink()
        else:
            print("\n[1/3] Ambiente virtuale esistente, riutilizzo.")
        py = str(venv_python())
        print("[2/3] Aggiornamento pip...")
        subprocess.check_call([py, "-m", "pip", "install", "--upgrade", "pip", "-q"])
        print("[3/3] Installazione dipendenze (può richiedere qualche minuto)...")
        subprocess.check_call([py, "-m", "pip", "install", "-r", str(REQ_FILE)])
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"\nERRORE durante l'installazione: {exc}")
        print("Cause più comuni (leggi i messaggi di pip qui sopra):")
        print("  - connessione Internet assente o proxy aziendale")
        print(f"  - versione di Python non supportata (supportate: {supported_list()})")
        if platform.system() == "Linux":
            print("  - modulo venv mancante:  sudo apt install python3-venv")
        return False

    print("\n[OK] Installazione completata.")
    return True


def print_python_help() -> None:
    cur = platform.python_version()
    print(f"\nERRORE: Python {cur} non è supportato dalle dipendenze di BHAM.")
    print(f"Versioni supportate: {supported_list()} – nessuna trovata sul sistema.")
    if IS_WINDOWS:
        print("Installa Python 3.12 da https://www.python.org/downloads/ (oppure: winget install Python.Python.3.12)")
        print("poi rilancia:  py -3.12 bham.py")
    else:
        print("Installa Python 3.12 (es. Debian/Ubuntu: sudo apt install python3.12 python3.12-venv)")
        print("poi rilancia:  python3.12 bham.py")


def stale_venv() -> tuple[int, int] | None:
    """Restituisce la versione del .venv se è stato creato con un Python non supportato."""
    py = venv_python()
    if not py.exists():
        return None
    ver = _py_version(py)
    if ver is None or ver not in SUPPORTED_PY:
        return ver or (0, 0)
    return None


def linux_permission_hints() -> None:
    if platform.system() != "Linux":
        return
    try:
        if "dialout" not in subprocess.check_output(["id", "-Gn"], text=True).split():
            print("[!] Utente non nel gruppo 'dialout': l'accesso RS485 potrebbe fallire.")
            print("    Soluzione: sudo ./scripts/setup_permissions.sh")
    except (OSError, subprocess.CalledProcessError):
        pass


def get_local_lan_ips() -> list[str]:
    """Rileva gli indirizzi IPv4 locali non-loopback per mostrare gli URL di accesso LAN."""
    ips: set[str] = set()
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            if ip and not ip.startswith("127.") and not ip.startswith("169.254."):
                ips.add(ip)
        except Exception:
            pass
        finally:
            s.close()

        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127.") and not ip.startswith("169.254."):
                ips.add(ip)
    except Exception:
        pass
    return sorted(ips)


def find_installed_browser() -> str | None:
    """Restituisce il percorso dell'eseguibile del browser installato su Linux."""
    candidates = [
        "firefox",
        "google-chrome-stable",
        "google-chrome",
        "chromium-browser",
        "chromium",
        "brave-browser",
        "microsoft-edge",
        "epiphany",
        "x-www-browser",
    ]
    for c in candidates:
        path = shutil.which(c)
        if path:
            return path
    return None


def open_browser_when_ready(url: str, port: int = 8765, timeout: float = 12.0) -> None:
    """
    Attende che il server HTTP sia in ascolto su localhost:port,
    quindi apre automaticamente il browser sul client locale.
    Non blocca l'esecuzione e gestisce ambienti headless (es. SSH / Raspberry headless).
    """
    import threading
    import time
    import socket
    import webbrowser

    def _worker():
        # Su Linux, evita l'apertura se non è presente un display grafico (es. SSH / Raspberry headless)
        if platform.system() == "Linux" and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            return

        start_time = time.time()
        ready = False
        while time.time() - start_time < timeout:
            time.sleep(0.3)
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                    ready = True
                    break
            except (OSError, ConnectionRefusedError):
                continue

        if not ready:
            return

        # Tentativo 1: su Linux, esecuzione diretta del binario browser rilevato
        # per aggirare associazioni MIME corrotte o browser predefiniti mancanti (es. xdg-open che punta a Chrome disinstallato)
        opened = False
        if platform.system() == "Linux":
            browser_bin = find_installed_browser()
            if browser_bin:
                try:
                    subprocess.Popen(
                        [browser_bin, url],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                    opened = True
                except Exception:
                    pass

        # Tentativo 2: modulo webbrowser standard Python
        if not opened:
            try:
                webbrowser.open(url)
            except Exception:
                pass

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def start(reload: bool, auto_open: bool = True) -> int:
    port = 8765
    lan_ips = get_local_lan_ips()

    print("=" * 64)
    print("  ⚡ BHAM – BACS Help Auto Mapper")
    print("=" * 64)
    print(f"  🌐 Accesso locale:        http://localhost:{port}")
    if lan_ips:
        for ip in lan_ips:
            print(f"  🌐 Accesso da rete LAN:   http://{ip}:{port}")
    else:
        print(f"  🌐 Accesso da rete LAN:   http://<IP-DEL-DISPOSITIVO>:{port}")
    print(f"  📖 Documentazione API:    http://localhost:{port}/docs")
    print("-" * 64)
    print("  💡 Accesso remoto: per usare BHAM da un altro PC, tablet")
    print("     o smartphone nella stessa rete, apri l'URL LAN sopra.")
    if platform.system() == "Linux":
        print("  💡 Se la pagina non risponde da altri dispositivi, sblocca:")
        print(f"     sudo ufw allow {port}/tcp")
    print("  Premi CTRL+C per arrestare il server.")
    print("=" * 64)
    linux_permission_hints()

    if auto_open:
        open_browser_when_ready(f"http://localhost:{port}", port=port)

    cmd = [str(venv_python()), "-m", "uvicorn", "main:app",
           "--host", "0.0.0.0", "--port", str(port)]
    if reload:
        cmd.append("--reload")
    try:
        return subprocess.call(cmd, cwd=str(ROOT_DIR))
    except KeyboardInterrupt:
        print("\nArresto di BHAM.")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="BHAM launcher")
    parser.add_argument("--yes", "-y", action="store_true", help="installa senza chiedere")
    parser.add_argument("--check", action="store_true", help="verifica solo le dipendenze")
    parser.add_argument("--no-browser", action="store_true", help="disabilita l'apertura automatica del browser")
    parser.add_argument("--no-reload", action="store_true", help="disabilita auto-reload")
    parser.add_argument("--demo", action="store_true", help="avvia in modalità simulazione impianto virtuale (Demo Mode)")
    args = parser.parse_args()

    if args.demo:
        os.environ["BHAM_DEMO"] = "1"

    if sys.version_info[:2] not in SUPPORTED_PY:
        print(f"[i] Python {platform.python_version()} non supportato: cerco {supported_list()} sul sistema...")

    bad = stale_venv()
    if bad is not None:
        label = f"{bad[0]}.{bad[1]}" if bad != (0, 0) else "sconosciuta/corrotta"
        print(f"[!] Il .venv esistente usa Python {label}, non supportato (supportate: {supported_list()}).")
        if args.check:
            return 1
        if not ask("Ricreare il .venv con una versione compatibile? [S/n]: ", args.yes):
            return 1
        shutil.rmtree(VENV_DIR)

    missing = missing_dependencies()

    if args.check:
        if missing == []:
            print("[OK] Tutte le dipendenze sono installate.")
            return 0
        print("Dipendenze mancanti:" if missing else "Ambiente virtuale assente.")
        for d in missing or []:
            print(f"  - {d}")
        return 1

    if missing != []:
        if not setup(missing, args.yes):
            return 1

    return start(reload=not args.no_reload, auto_open=not args.no_browser)


if __name__ == "__main__":
    os.chdir(ROOT_DIR)
    sys.exit(main())
