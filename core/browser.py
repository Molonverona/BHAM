"""
BHAM – Browser Auto-Open Helper
Apertura automatica della console web di collaudo sul client locale.

Il modulo usa esclusivamente la libreria standard: può quindi essere importato
sia dal launcher `bham.py` (eseguito con il Python di sistema, prima che il
virtualenv esista) sia dall'applicazione congelata PyInstaller, senza trascinare
dipendenze di terze parti.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import threading

# Candidati browser su Linux, in ordine di preferenza. Serve ad aggirare
# associazioni MIME corrotte o browser predefiniti disinstallati (es. xdg-open
# che punta a un Chrome rimosso).
LINUX_BROWSERS = [
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


def find_installed_browser() -> str | None:
    """Restituisce il percorso dell'eseguibile del browser installato su Linux."""
    for candidate in LINUX_BROWSERS:
        path = shutil.which(candidate)
        if path:
            return path
    return None


def has_graphical_session() -> bool:
    """
    True se è plausibile che esista un ambiente grafico in cui aprire il browser.
    Su Linux headless (SSH, Raspberry senza X/Wayland) ritorna False.
    """
    if platform.system() != "Linux":
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def open_browser_when_ready(url: str, port: int = 8765, timeout: float = 12.0) -> None:
    """
    Attende che il server HTTP sia in ascolto su localhost:port,
    quindi apre automaticamente il browser sul client locale.
    Non blocca l'esecuzione e gestisce ambienti headless (es. SSH / Raspberry headless).
    """
    import socket
    import time
    import webbrowser

    def _worker():
        if not has_graphical_session():
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
