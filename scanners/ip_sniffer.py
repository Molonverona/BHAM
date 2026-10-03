"""
BHAM – IP Sniffer (ARP passive discovery)
Captures ARP packets on the local network without sending any probes.
Completely non-intrusive – only listens.
"""

from __future__ import annotations

import asyncio
import platform
from typing import TYPE_CHECKING

from core.logger import logger
from core.priv_check import has_cap_net_raw
from data.models import IPHost, ScanStatus
from data.state import state
from scanners.base import BaseScanner

if TYPE_CHECKING:
    from api.routes import ARPSniffRequest

_SYSTEM = platform.system()


def npcap_installed() -> bool:
    """True se il driver Npcap (o WinPcap legacy) è presente. Solo Windows."""
    import os
    sysroot = os.environ.get("SystemRoot", r"C:\Windows")
    candidates = [
        os.path.join(sysroot, "System32", "Npcap", "wpcap.dll"),
        os.path.join(sysroot, "System32", "wpcap.dll"),
    ]
    return any(os.path.isfile(c) for c in candidates)


class IPSniffer(BaseScanner):

    async def scan(self, *args, **kwargs) -> None:
        pass

    async def sniff(self, req: "ARPSniffRequest") -> None:
        """
        Passive ARP listener.
        Runs Scapy's sniff() in a thread pool so the event-loop stays free.

        Privilege check runs first: if CAP_NET_RAW (Linux) or Administrator
        (Windows) is missing the session is closed immediately with a clear
        error_message that the frontend can display.
        """
        log = logger.getChild("arp_sniffer")
        state.update_session(self.session_id, status=ScanStatus.RUNNING, progress_pct=0.0)

        # ── Pre-flight privilege check ────────────────────────────────────────
        if not has_cap_net_raw():
            if _SYSTEM == "Windows":
                advice = (
                    "L'ARP Sniffer richiede i privilegi di Amministratore su Windows. "
                    "Riesegui BHAM con 'Esegui come amministratore'."
                )
            else:
                import sys
                advice = (
                    "L'ARP Sniffer richiede CAP_NET_RAW (raw socket). "
                    "Abilita con (una-tantum):  "
                    f"sudo setcap cap_net_raw+eip {sys.executable}  "
                    "oppure esegui BHAM con sudo."
                )
            log.error("ARP sniffer: permessi insufficienti. %s", advice)
            state.update_session(self.session_id, error_message=advice)
            state.finish_session(self.session_id, ScanStatus.ERROR)
            return

        # ── Pre-flight Npcap (Windows) ────────────────────────────────────────
        # Senza driver di cattura Scapy non riceve pacchetti: meglio un errore
        # esplicito che una scansione "completata" con 0 host.
        if _SYSTEM == "Windows" and not npcap_installed():
            advice = (
                "L'ARP Sniffer su Windows richiede il driver Npcap. "
                "Installalo da https://npcap.com (opzione 'WinPcap API-compatible mode') "
                "e riavvia BHAM."
            )
            log.error("ARP sniffer: %s", advice)
            state.update_session(self.session_id, error_message=advice)
            state.finish_session(self.session_id, ScanStatus.ERROR)
            return

        log.info(
            "ARP sniffer started – iface=%r, duration=%.0fs",
            req.iface or "auto",
            req.duration,
        )

        seen: dict[str, IPHost] = {}

        def _packet_callback(pkt) -> None:
            try:
                from scapy.layers.l2 import ARP
                if pkt.haslayer(ARP):
                    arp = pkt[ARP]
                    ip = arp.psrc
                    mac = arp.hwsrc
                    if ip and ip != "0.0.0.0" and ip not in seen:
                        host = IPHost(ip=ip, mac=mac)
                        seen[ip] = host
                        state.upsert_ip_host(host)
                        log.info("  ✓ ARP host: %s  MAC: %s", ip, mac)
            except Exception as exc:
                log.debug("ARP callback error: %s", exc)

        def _run_sniff() -> str | None:
            """Returns an error string on permission failure, None on success."""
            try:
                from scapy.all import sniff
                kw: dict = {
                    "filter": "arp",
                    "prn": _packet_callback,
                    "timeout": req.duration,
                    "store": False,
                }
                if req.iface:
                    kw["iface"] = req.iface
                sniff(**kw)
                return None
            except PermissionError as exc:
                msg = f"Raw socket negato dal kernel: {exc}"
                log.error("ARP sniffer PermissionError: %s", exc)
                return msg
            except ImportError:
                msg = "Scapy non installato – ARP sniffer non disponibile."
                log.error(msg)
                return msg
            except Exception as exc:
                # Qualsiasi errore di cattura invalida il risultato: va segnalato,
                # altrimenti l'utente vedrebbe "0 host" e penserebbe a una rete vuota.
                msg = f"Errore di cattura ARP: {exc}"
                log.error("Sniffer error: %s", exc)
                return msg

        loop = asyncio.get_event_loop()
        err = await loop.run_in_executor(None, _run_sniff)

        if err:
            state.update_session(self.session_id, error_message=err)
            state.finish_session(self.session_id, ScanStatus.ERROR)
            return

        state.update_session(
            self.session_id,
            found_devices=len(seen),
            progress_pct=100.0,
        )
        log.info("ARP sniff finished – %d host(s) discovered.", len(seen))
        state.finish_session(self.session_id, ScanStatus.COMPLETED)
