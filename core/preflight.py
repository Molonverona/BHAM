"""
BHAM – Preflight Bootstrap Checks
Verifiche eseguite immediatamente prima dell'avvio del server per diagnosticare
i guasti tipici di una installazione appena effettuata (installer Windows,
pacchetto portable, binario congelato PyInstaller):

- directory dati effettivamente scrivibile (installazione in Program Files);
- asset del frontend realmente presenti nel bundle;
- porta TCP di ascolto libera, con fallback automatico sulla successiva.

Le funzioni non sollevano eccezioni e non scrivono su console: restituiscono un
rapporto strutturato che il chiamante (`main.py` o l'endpoint di diagnostica)
può stampare o serializzare in JSON.
"""

from __future__ import annotations

import socket
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Numero massimo di porte consecutive provate prima di arrendersi.
PORT_FALLBACK_ATTEMPTS = 20


@dataclass
class PreflightReport:
    """Esito delle verifiche di preflight."""

    requested_port: int
    resolved_port: int
    host: str = "0.0.0.0"
    data_dir: str = ""
    frontend_dir: str = ""
    # Problemi bloccanti: il server non può funzionare correttamente.
    errors: list[str] = field(default_factory=list)
    # Problemi non bloccanti: il server parte ma con funzionalità ridotte.
    warnings: list[str] = field(default_factory=list)

    @property
    def is_healthy(self) -> bool:
        return not self.errors

    @property
    def port_changed(self) -> bool:
        return self.resolved_port != self.requested_port

    def as_dict(self) -> dict:
        return {
            "requested_port": self.requested_port,
            "resolved_port": self.resolved_port,
            "port_changed": self.port_changed,
            "host": self.host,
            "data_dir": self.data_dir,
            "frontend_dir": self.frontend_dir,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "is_healthy": self.is_healthy,
        }


def is_port_available(port: int, host: str = "0.0.0.0") -> bool:
    """
    True se la porta TCP è libera e associabile sull'host indicato.

    Replica le opzioni socket usate da uvicorn: su POSIX viene impostato
    SO_REUSEADDR (così una socket in TIME_WAIT non viene segnalata come
    occupata), mentre su Windows l'opzione è deliberatamente omessa perché
    permetterebbe a due processi di legarsi alla stessa porta mascherando
    un conflitto reale.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sys.platform != "win32":
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
        return True
    except OSError:
        return False


def find_free_port(
    preferred: int,
    host: str = "0.0.0.0",
    attempts: int = PORT_FALLBACK_ATTEMPTS,
) -> int | None:
    """
    Restituisce la prima porta libera partendo da `preferred`, oppure None se
    nessuna delle `attempts` porte consecutive è disponibile.
    """
    for offset in range(max(1, attempts)):
        candidate = preferred + offset
        if candidate > 65535:
            break
        if is_port_available(candidate, host):
            return candidate
    return None


def check_data_dir() -> tuple[Path | None, str | None]:
    """
    Verifica che la directory dati utente sia creabile e scrivibile.
    Ritorna (path, None) se tutto è a posto, oppure (path_o_None, messaggio).
    """
    try:
        from core.paths import get_data_dir
        data_dir = get_data_dir()
    except Exception as exc:
        return None, f"Impossibile determinare la directory dati utente: {exc}"

    probe = data_dir / ".bham-write-test"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return data_dir, (
            f"Directory dati non scrivibile ({data_dir}): {exc}. "
            "Su Windows avvia BHAM dal collegamento creato dall'installer, "
            "oppure usa l'edizione portable in una cartella con permessi di scrittura."
        )
    return data_dir, None


def check_frontend_assets() -> tuple[Path | None, str | None]:
    """
    Verifica che gli asset della console web siano presenti nel bundle.
    Un bundle PyInstaller incompleto è la causa tipica di una pagina bianca.
    """
    try:
        from core.paths import get_frontend_dir
        frontend_dir = get_frontend_dir()
    except Exception as exc:
        return None, f"Impossibile determinare la directory del frontend: {exc}"

    if not frontend_dir.is_dir():
        return frontend_dir, (
            f"Asset del frontend non trovati ({frontend_dir}). "
            "Il pacchetto è incompleto: reinstalla BHAM o riscarica l'archivio portable."
        )
    if not (frontend_dir / "index.html").is_file():
        return frontend_dir, (
            f"File index.html mancante in {frontend_dir}. "
            "Il pacchetto è incompleto: reinstalla BHAM."
        )
    return frontend_dir, None


def run_preflight(port: int, host: str = "0.0.0.0", allow_port_fallback: bool = True) -> PreflightReport:
    """
    Esegue tutte le verifiche di preflight e restituisce il rapporto completo,
    con la porta di ascolto effettivamente utilizzabile.
    """
    report = PreflightReport(requested_port=port, resolved_port=port, host=host)

    data_dir, data_err = check_data_dir()
    if data_dir is not None:
        report.data_dir = str(data_dir)
    if data_err:
        report.errors.append(data_err)

    frontend_dir, fe_err = check_frontend_assets()
    if frontend_dir is not None:
        report.frontend_dir = str(frontend_dir)
    if fe_err:
        report.errors.append(fe_err)

    if not is_port_available(port, host):
        if not allow_port_fallback:
            report.errors.append(
                f"La porta {port} è già occupata da un altro processo su {host}."
            )
        else:
            alternative = find_free_port(port + 1, host)
            if alternative is None:
                report.errors.append(
                    f"La porta {port} è occupata e non è stata trovata alcuna porta "
                    f"libera nelle {PORT_FALLBACK_ATTEMPTS} successive."
                )
            else:
                report.resolved_port = alternative
                report.warnings.append(
                    f"La porta {port} è già in uso (probabile istanza di BHAM già avviata): "
                    f"passo automaticamente alla porta {alternative}."
                )

    return report
