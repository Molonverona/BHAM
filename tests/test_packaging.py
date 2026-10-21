"""
BHAM – Test di packaging, preflight e sincronizzazione versioni.

Copre le regressioni che i test funzionali non intercettano perché riguardano il
modo in cui BHAM viene impacchettato e distribuito:

- scelta del target ASGI nel binario congelato PyInstaller (guasto v1.1.0:
  l'eseguibile installato su Windows terminava subito con
  "Error loading ASGI app. Could not import module \\"main\\"");
- verifiche di preflight e fallback automatico di porta;
- allineamento della versione su tutti i file di packaging;
- correttezza dei manifest winget e del launcher Windows.
"""

from __future__ import annotations

import re
import socket
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import main as main_module
from core import preflight
from core.config import settings


def _read(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def _pyproject_version() -> str:
    match = re.search(r'^version\s*=\s*"([^"]+)"', _read("pyproject.toml"), re.MULTILINE)
    assert match, "versione non trovata in pyproject.toml"
    return match.group(1)


class TestFrozenServerTarget(unittest.TestCase):
    """
    Regressione v1.1.0: in modalità congelata lo script di ingresso gira come
    ``__main__`` e il modulo ``main`` non è importabile. Passare la stringa
    "main:app" a uvicorn faceva terminare immediatamente bham.exe.
    """

    def test_source_mode_uses_import_string(self):
        target = main_module.server_target()
        self.assertEqual(target, "main:app")
        self.assertIsInstance(target, str)

    def test_frozen_mode_returns_app_object(self):
        with mock.patch.object(sys, "frozen", True, create=True), \
             mock.patch.object(sys, "_MEIPASS", str(REPO_ROOT), create=True):
            target = main_module.server_target()
        self.assertIs(target, main_module.app)
        self.assertNotIsInstance(
            target, str,
            "in modalità congelata uvicorn deve ricevere l'oggetto app, non una stringa di import",
        )

    def test_reload_is_never_requested_for_an_object_target(self):
        # L'auto-reload di uvicorn richiede una stringa di import: con l'oggetto
        # applicazione va sempre disattivato, altrimenti uvicorn solleva errore.
        with mock.patch.object(sys, "frozen", True, create=True), \
             mock.patch.object(sys, "_MEIPASS", str(REPO_ROOT), create=True):
            frozen_target = main_module.server_target()

        # Replica della decisione presa in run_cli() con debug attivo.
        reload_for_frozen = True and isinstance(frozen_target, str)
        self.assertFalse(reload_for_frozen)

        reload_for_source = True and isinstance(main_module.server_target(), str)
        self.assertTrue(reload_for_source)


class TestCliArguments(unittest.TestCase):
    """Il binario congelato deve esporre flag reali, non ignorare argv."""

    def test_defaults_match_settings(self):
        args = main_module.build_arg_parser().parse_args([])
        self.assertEqual(args.port, settings.port)
        self.assertEqual(args.host, settings.host)
        self.assertFalse(args.demo)
        self.assertFalse(args.check)
        self.assertFalse(args.no_browser)

    def test_explicit_flags_are_parsed(self):
        args = main_module.build_arg_parser().parse_args(
            ["--host", "127.0.0.1", "--port", "9000", "--demo", "--no-browser",
             "--no-port-fallback", "--check"]
        )
        self.assertEqual(args.host, "127.0.0.1")
        self.assertEqual(args.port, 9000)
        self.assertTrue(args.demo)
        self.assertTrue(args.no_browser)
        self.assertTrue(args.no_port_fallback)
        self.assertTrue(args.check)

    def test_version_flag_exits_zero(self):
        with self.assertRaises(SystemExit) as ctx:
            main_module.build_arg_parser().parse_args(["--version"])
        self.assertEqual(ctx.exception.code, 0)


class TestPreflight(unittest.TestCase):
    """Verifiche di avvio: porta, directory dati e asset del frontend."""

    def test_free_port_is_available(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            free_port = probe.getsockname()[1]
        self.assertTrue(preflight.is_port_available(free_port, "127.0.0.1"))

    def test_bound_port_is_detected_as_busy(self):
        with socket.socket() as busy:
            busy.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            busy.bind(("127.0.0.1", 0))
            busy.listen(1)
            port = busy.getsockname()[1]
            self.assertFalse(preflight.is_port_available(port, "127.0.0.1"))
            self.assertEqual(
                preflight.find_free_port(port, "127.0.0.1", attempts=3), port + 1
            )

    def test_run_preflight_falls_back_to_next_free_port(self):
        with socket.socket() as busy:
            busy.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            busy.bind(("127.0.0.1", 0))
            busy.listen(1)
            port = busy.getsockname()[1]
            report = preflight.run_preflight(port=port, host="127.0.0.1")
        self.assertTrue(report.is_healthy)
        self.assertTrue(report.port_changed)
        self.assertEqual(report.resolved_port, port + 1)
        self.assertTrue(any("già in uso" in w for w in report.warnings))

    def test_run_preflight_reports_error_when_fallback_disabled(self):
        with socket.socket() as busy:
            busy.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            busy.bind(("127.0.0.1", 0))
            busy.listen(1)
            port = busy.getsockname()[1]
            report = preflight.run_preflight(
                port=port, host="127.0.0.1", allow_port_fallback=False
            )
        self.assertFalse(report.is_healthy)
        self.assertFalse(report.port_changed)
        self.assertTrue(any("occupata" in e for e in report.errors))

    def test_frontend_assets_present_in_checkout(self):
        frontend_dir, error = preflight.check_frontend_assets()
        self.assertIsNone(error)
        self.assertIsNotNone(frontend_dir)
        self.assertTrue((frontend_dir / "index.html").is_file())

    def test_data_dir_is_writable(self):
        data_dir, error = preflight.check_data_dir()
        self.assertIsNone(error)
        self.assertIsNotNone(data_dir)

    def test_report_serialises_to_json_friendly_dict(self):
        payload = preflight.run_preflight(port=0, host="127.0.0.1").as_dict()
        for key in ("requested_port", "resolved_port", "port_changed", "errors",
                    "warnings", "is_healthy", "data_dir", "frontend_dir"):
            self.assertIn(key, payload)


class TestWindowsFirewallDetection(unittest.TestCase):
    """Rilevamento della regola firewall che abilita il pairing LAN via QR code."""

    def test_returns_none_on_non_windows(self):
        from core import system_requirements as sr
        with mock.patch.object(sr, "is_windows", return_value=False):
            self.assertIsNone(sr.check_windows_firewall_rule())

    def test_detects_existing_rule(self):
        from core import system_requirements as sr
        completed = mock.Mock(returncode=0, stdout="Rule Name: BHAM - BACS Help Auto Mapper\n")
        with mock.patch.object(sr, "is_windows", return_value=True), \
             mock.patch.object(sr.subprocess, "run", return_value=completed):
            self.assertIs(sr.check_windows_firewall_rule(), True)

    def test_detects_missing_rule(self):
        from core import system_requirements as sr
        completed = mock.Mock(returncode=0, stdout="No rules match the specified criteria.\n")
        with mock.patch.object(sr, "is_windows", return_value=True), \
             mock.patch.object(sr.subprocess, "run", return_value=completed):
            self.assertIs(sr.check_windows_firewall_rule(), False)

    def test_returns_none_when_netsh_unavailable(self):
        from core import system_requirements as sr
        with mock.patch.object(sr, "is_windows", return_value=True), \
             mock.patch.object(sr.subprocess, "run", side_effect=OSError("netsh assente")):
            self.assertIsNone(sr.check_windows_firewall_rule())

    def test_firewall_rule_name_matches_installer_script(self):
        from core.system_requirements import WINDOWS_FIREWALL_RULE_NAME
        iss = _read("installer/bham.iss")
        self.assertIn(f'#define MyFirewallRule "{WINDOWS_FIREWALL_RULE_NAME}"', iss)


class TestDiagnosticsPackagingFields(unittest.TestCase):
    """La diagnostica deve dichiarare come BHAM è stato installato."""

    def test_diagnostics_exposes_packaging_metadata(self):
        from core.system_requirements import get_system_diagnostics
        diag = get_system_diagnostics()
        for key in ("app_version", "is_frozen", "is_portable", "listen_port",
                    "windows_firewall_rule"):
            self.assertIn(key, diag)
        self.assertEqual(diag["app_version"], settings.app_version)
        self.assertIsInstance(diag["is_frozen"], bool)

    def test_frozen_runtime_does_not_flag_interpreter_version(self):
        # Nel binario congelato il runtime è incorporato: la versione
        # dell'interprete di sistema non deve generare falsi allarmi.
        from core import system_requirements as sr
        with mock.patch("core.paths.is_frozen", return_value=True), \
             mock.patch.object(sr, "get_python_info", return_value={
                 "version": "3.9.1", "major": 3, "minor": 9,
                 "executable": "bham.exe", "is_venv": False,
                 "is_supported": False, "architecture": "AMD64",
             }):
            diag = sr.get_system_diagnostics()
        self.assertFalse(
            any("non ufficialmente supportato" in m for m in diag["missing_requirements"]),
            "il binario congelato non deve lamentare la versione dell'interprete di sistema",
        )


class TestEnvironmentAliases(unittest.TestCase):
    """Le variabili documentate con prefisso BHAM_ devono essere realmente lette."""

    def _reloaded_settings(self, env: dict[str, str]):
        import importlib
        import core.config
        with mock.patch.dict("os.environ", env, clear=False):
            module = importlib.reload(core.config)
            return module.settings

    def tearDown(self):
        import importlib
        import core.config
        importlib.reload(core.config)

    def test_prefixed_port_and_token_are_honoured(self):
        cfg = self._reloaded_settings({"BHAM_PORT": "9123", "BHAM_API_TOKEN": "tok-prefix"})
        self.assertEqual(cfg.port, 9123)
        self.assertEqual(cfg.api_token, "tok-prefix")

    def test_bare_names_still_supported(self):
        cfg = self._reloaded_settings({"PORT": "9456", "API_TOKEN": "tok-bare"})
        self.assertEqual(cfg.port, 9456)
        self.assertEqual(cfg.api_token, "tok-bare")


class TestVersionSynchronisation(unittest.TestCase):
    """
    La versione di pyproject.toml è l'unica fonte di verità: ogni file di
    packaging deve riportarla. Impedisce il drift che aveva lasciato bham.bat,
    bootstrap_windows.ps1 e system_requirements.py fermi a una versione vecchia.
    """

    def setUp(self):
        self.version = _pyproject_version()

    def test_runtime_settings_match_pyproject(self):
        self.assertEqual(settings.app_version, self.version)

    def test_all_packaging_files_declare_the_version(self):
        expectations = [
            ("core/config.py", f'app_version: str = "{self.version}"'),
            ("installer/bham.iss", f'#define MyAppVersion "{self.version}"'),
            ("bham.bat", f'set "BHAM_VERSION={self.version}"'),
            ("scripts/bootstrap_windows.ps1", f"BHAM-Bootstrap/{self.version}"),
            ("core/system_requirements.py", f"BHAM-FieldStation/{self.version}"),
            ("scripts/package_deb.sh", f'VERSION="${{1:-{self.version}}}"'),
            ("scripts/install.sh", f'TAG_NAME="v{self.version}"'),
            (".env.example", f"APP_VERSION={self.version}"),
            ("winget/BacsHelp.BHAM.yaml", f"PackageVersion: {self.version}"),
            ("winget/BacsHelp.BHAM.installer.yaml", f"PackageVersion: {self.version}"),
            ("winget/BacsHelp.BHAM.locale.en-US.yaml", f"PackageVersion: {self.version}"),
            ("frontend/index.html", f"BACS Help Auto Mapper v{self.version}"),
            ("frontend/index.html", f"?v={self.version}"),
            ("MANUALE_UTENTE.md", f"Guida Operativa di Campo (v{self.version})"),
            ("frontend/MANUALE_UTENTE.md", f"Guida Operativa di Campo (v{self.version})"),
        ]
        for relative, needle in expectations:
            with self.subTest(file=relative, needle=needle):
                self.assertIn(needle, _read(relative))

    def test_i18n_declares_version_for_all_three_languages(self):
        occurrences = _read("frontend/js/i18n.js").count(
            f"BACS Help Auto Mapper v{self.version}"
        )
        self.assertEqual(occurrences, 3, "attese 3 occorrenze (IT, EN, ES)")

    def test_changelog_has_an_entry_for_the_current_version(self):
        self.assertIn(f"## [{self.version}]", _read("CHANGELOG.md"))

    def test_bump_script_covers_every_windows_target(self):
        bump = _read("scripts/bump_version.py")
        for target in ("bham.bat", "bootstrap_windows.ps1", "system_requirements.py",
                       "installer", "bham.iss"):
            with self.subTest(target=target):
                self.assertIn(target, bump)


class TestWingetManifest(unittest.TestCase):
    """I manifest winget devono puntare ad asset di release realmente esistenti."""

    def setUp(self):
        self.version = _pyproject_version()
        self.installer = _read("winget/BacsHelp.BHAM.installer.yaml")

    def test_points_at_the_published_portable_asset(self):
        expected = (
            f"https://github.com/Molonverona/BHAM/releases/download/"
            f"v{self.version}/bham-windows-x64-portable.zip"
        )
        self.assertIn(expected, self.installer)

    def test_does_not_reference_a_nonexistent_asset_name(self):
        self.assertNotIn("download/v%s/bham-windows-x64.zip" % self.version, self.installer)

    def test_release_asset_name_matches_the_release_workflow(self):
        workflow = _read(".github/workflows/release.yml")
        self.assertIn("bham-windows-x64-portable.zip", workflow)

    def test_no_stale_publisher_repository(self):
        for relative in (
            "winget/BacsHelp.BHAM.installer.yaml",
            "winget/BacsHelp.BHAM.locale.en-US.yaml",
        ):
            with self.subTest(file=relative):
                self.assertNotIn("github.com/BacsHelp/BHAM", _read(relative))


class TestWindowsLauncher(unittest.TestCase):
    """Il launcher a doppio clic deve restare leggibile su console Windows."""

    def test_bat_file_is_pure_ascii(self):
        raw = (REPO_ROOT / "bham.bat").read_bytes()
        offenders = [b for b in raw if b > 0x7E or (b < 0x20 and b not in (0x09, 0x0A, 0x0D))]
        self.assertEqual(
            offenders, [],
            "bham.bat deve restare ASCII: la console Windows usa code page legacy",
        )

    def test_detects_both_supported_python_versions(self):
        content = _read("bham.bat")
        self.assertIn("Python312", content)
        self.assertIn("Python313", content)
        self.assertIn("3.12 3.13", content)

    def test_sets_utf8_code_page(self):
        self.assertIn("chcp 65001", _read("bham.bat"))


class TestPyInstallerSpec(unittest.TestCase):
    """Lo spec deve produrre un eseguibile Windows installabile e riconoscibile."""

    def setUp(self):
        self.spec = _read("bham.spec")

    def test_upx_is_disabled(self):
        # UPX corrompe le DLL del runtime Python e innesca falsi positivi AV.
        self.assertIn("upx=False", self.spec)
        self.assertNotIn("upx=True", self.spec)

    def test_applies_manifest_and_version_resource(self):
        self.assertIn("manifest=WIN_MANIFEST_FILE", self.spec)
        self.assertIn("version=WIN_VERSION_FILE", self.spec)
        self.assertIn("bham.exe.manifest", self.spec)

    def test_bundles_new_core_modules(self):
        for module in ("core.preflight", "core.browser"):
            with self.subTest(module=module):
                self.assertIn(f"'{module}'", self.spec)

    def test_reads_version_from_pyproject(self):
        self.assertIn("pyproject.toml", self.spec)


if __name__ == "__main__":
    unittest.main()
