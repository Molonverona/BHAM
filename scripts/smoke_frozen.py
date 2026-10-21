#!/usr/bin/env python3
"""
BHAM – Smoke test del binario congelato (PyInstaller).

Verifica che l'eseguibile prodotto da `pyinstaller bham.spec` sia realmente
avviabile e in grado di servire la console web. È il controllo che intercetta le
regressioni di packaging invisibili ai test unitari: per esempio il passaggio a
uvicorn della stringa di import "main:app", che in un bundle PyInstaller fa
terminare subito il processo con
``Error loading ASGI app. Could not import module "main"``.

Uso:
    python scripts/smoke_frozen.py [--port 8899] [--timeout 90]
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def binary_path() -> Path:
    name = "bham.exe" if platform.system() == "Windows" else "bham"
    return ROOT / "dist" / name


def expected_version() -> str:
    import re
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return match.group(1) if match else ""


def fail(msg: str) -> "None":
    print(f"[FAIL] {msg}")
    sys.exit(1)


def run_capture(cmd: list[str], timeout: float = 120.0) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def http_get(url: str, timeout: float = 3.0) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "BHAM-Smoke/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def wait_for_health(port: int, proc: subprocess.Popen, timeout: float) -> dict:
    url = f"http://127.0.0.1:{port}/api/v1/health"
    deadline = time.time() + timeout
    last_error = "nessun tentativo effettuato"
    while time.time() < deadline:
        if proc.poll() is not None:
            out = (proc.stdout.read() if proc.stdout else "") or ""
            fail(
                f"il binario è terminato prematuramente con codice {proc.returncode}.\n"
                f"--- output ---\n{out}"
            )
        try:
            status, body = http_get(url)
            if status == 200:
                return json.loads(body)
            last_error = f"HTTP {status}"
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            last_error = str(exc)
        time.sleep(1.0)
    fail(f"timeout: /api/v1/health non ha risposto entro {timeout:.0f}s (ultimo errore: {last_error})")
    raise AssertionError  # pragma: no cover – fail() esce sempre


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test del binario congelato BHAM")
    parser.add_argument("--port", type=int, default=8899)
    parser.add_argument("--timeout", type=float, default=90.0)
    args = parser.parse_args()

    exe = binary_path()
    if not exe.is_file():
        fail(f"binario non trovato in {exe}: eseguire prima 'pyinstaller bham.spec'")
    print(f"[i] Binario sotto test: {exe}")

    version = expected_version()

    # 1. --version non deve avviare il server.
    res = run_capture([str(exe), "--version"])
    if res.returncode != 0 or version not in res.stdout:
        fail(f"'--version' inatteso (rc={res.returncode}): {res.stdout.strip()} {res.stderr.strip()}")
    print(f"[OK] --version riporta {version}")

    # 2. --check esegue il preflight ed esce.
    res = run_capture([str(exe), "--check"])
    if res.returncode != 0:
        fail(f"'--check' ha restituito {res.returncode}:\n{res.stdout}\n{res.stderr}")
    print("[OK] --check completato senza errori di preflight")

    # 3. Avvio reale del server e verifica delle risposte HTTP.
    env = dict(os.environ)
    env["BHAM_NO_BROWSER"] = "1"
    proc = subprocess.Popen(
        [str(exe), "--no-browser", "--no-port-fallback", "--port", str(args.port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    try:
        health = wait_for_health(args.port, proc, args.timeout)
        if health.get("status") != "ok":
            fail(f"/api/v1/health ha risposto {health}")
        if version and health.get("version") != version:
            fail(f"versione riportata {health.get('version')!r}, attesa {version!r}")
        print(f"[OK] /api/v1/health -> {health}")

        status, body = http_get(f"http://127.0.0.1:{args.port}/", timeout=10.0)
        if status != 200 or "BHAM" not in body:
            fail(f"la console web non è stata servita correttamente (HTTP {status})")
        print("[OK] console web servita dagli asset del bundle")

        status, _ = http_get(f"http://127.0.0.1:{args.port}/api/v1/system/diagnostics", timeout=15.0)
        if status != 200:
            fail(f"/api/v1/system/diagnostics ha risposto HTTP {status}")
        print("[OK] endpoint di diagnostica raggiungibile")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()

    print("\n[SUCCESS] Smoke test del binario congelato superato.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
