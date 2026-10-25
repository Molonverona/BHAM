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

import importlib
import socket
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Numero massimo di porte consecutive provate prima di arrendersi.
PORT_FALLBACK_ATTEMPTS = 20

# Motori di protocollo e di reporting caricati su richiesta (import tardivo).
# In un bundle PyInstaller un hiddenimport dimenticato non si manifesta
# all'avvio: l'eseguibile parte regolarmente e fallisce settimane dopo, in
# cantiere, quando il tecnico apre la funzione corrispondente. La verifica è
# particolarmente importante su Windows, dove scapy carica moduli di
# piattaforma diversi da quelli raccolti nella build Linux.
ENGINE_IMPORTS: list[tuple[str, str]] = [
    ("Modbus RTU/TCP", "pymodbus.client"),
    ("BACnet/IP", "bacpypes3.apdu"),
    ("Sniffer L2 / ARP", "scapy.all"),
    ("Seriale RS485", "serial.tools.list_ports"),
    ("Report Excel", "openpyxl"),
    ("Report PDF", "reportlab.pdfgen.canvas"),
    ("Telemetria di sistema", "psutil"),
]


@dataclass
class EngineStatus:
    """Esito del caricamento di un motore opzionale."""

    label: str
    module: str
    available: bool
    error: str = ""
    # True solo quando il modulo (o una sua dipendenza) non esiste nel pacchetto:
    # è l'unico caso che indica davvero un bundle incompleto. Un import fallito
    # per altre ragioni — tipicamente scapy che non riesce a leggere la tabella
    # di routing, o l'assenza del driver Npcap su Windows — significa che il
    # pacchetto è integro ma la funzione non è utilizzabile su questa macchina.
    missing: bool = False

    @property
    def degraded(self) -> bool:
        """Modulo presente nel pacchetto ma non inizializzabile qui."""
        return not self.available and not self.missing


def check_engines(engines: list[tuple[str, str]] | None = None) -> list[EngineStatus]:
    """
    Tenta l'import di ogni motore di protocollo/reporting e ne riporta l'esito.

    Non solleva eccezioni: un motore difettoso viene segnalato, non propagato.
    Da non invocare all'avvio normale del demone (l'import di scapy è costoso):
    è una verifica on-demand per `--check` e per la diagnostica di campo.
    """
    import contextlib
    import io

    results: list[EngineStatus] = []
    for label, module in engines if engines is not None else ENGINE_IMPORTS:
        try:
            # Alcuni motori (scapy in particolare) scrivono avvisi e traceback
            # su stderr durante l'import: vanno trattenuti, altrimenti sommergono
            # l'esito della verifica. L'eventuale eccezione viene comunque
            # riportata nel campo `error`.
            with contextlib.redirect_stderr(io.StringIO()):
                importlib.import_module(module)
        except ModuleNotFoundError as exc:
            results.append(
                EngineStatus(label, module, False, f"{type(exc).__name__}: {exc}", missing=True)
            )
        except BaseException as exc:  # noqa: BLE001 - un motore rotto non deve propagare
            results.append(
                EngineStatus(label, module, False, f"{type(exc).__name__}: {exc}", missing=False)
            )
        else:
            results.append(EngineStatus(label, module, True))
    return results


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
