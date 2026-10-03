#!/usr/bin/env python3
"""
BHAM – Automated Version Bump Utility
Updates version across pyproject.toml, core/config.py, winget manifests,
frontend (title, badge, cache-busters, i18n), user manuals and Debian packaging.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PYPROJECT_FILE = ROOT / "pyproject.toml"
CONFIG_FILE = ROOT / "core" / "config.py"
WINGET_DIR = ROOT / "winget"


def get_current_version() -> str:
    content = PYPROJECT_FILE.read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if not m:
        raise ValueError("Impossibile trovare la versione in pyproject.toml")
    return m.group(1)


def bump(current: str, mode: str) -> str:
    parts = current.split(".")
    if len(parts) != 3:
        raise ValueError(f"Versione attuale '{current}' non conforme a SemVer (X.Y.Z)")
    major, minor, patch = map(int, parts)

    if mode == "patch":
        patch += 1
    elif mode == "minor":
        minor += 1
        patch = 0
    elif mode == "major":
        major += 1
        minor = 0
        patch = 0
    else:
        # custom version string passed directly
        if not re.match(r"^\d+\.\d+\.\d+$", mode):
            raise ValueError(f"Versione personalizzata '{mode}' non valida (richiesto formato X.Y.Z)")
        return mode

    return f"{major}.{minor}.{patch}"


def update_pyproject(new_ver: str):
    content = PYPROJECT_FILE.read_text(encoding="utf-8")
    content = re.sub(
        r'^(version\s*=\s*)"[^"]+"',
        rf'\g<1>"{new_ver}"',
        content,
        flags=re.MULTILINE,
    )
    PYPROJECT_FILE.write_text(content, encoding="utf-8")


def update_config(new_ver: str):
    content = CONFIG_FILE.read_text(encoding="utf-8")
    content = re.sub(
        r'(app_version:\s*str\s*=\s*)"[^"]+"',
        rf'\g<1>"{new_ver}"',
        content,
    )
    CONFIG_FILE.write_text(content, encoding="utf-8")


def update_winget(new_ver: str):
    if not WINGET_DIR.exists():
        return
    for yml in WINGET_DIR.glob("*.yaml"):
        txt = yml.read_text(encoding="utf-8")
        txt = re.sub(r'^(PackageVersion:\s*).+$', rf'\g<1>{new_ver}', txt, flags=re.MULTILINE)
        txt = re.sub(r'/releases/download/v[^/]+/', f'/releases/download/v{new_ver}/', txt)
        txt = re.sub(r'/releases/tag/v[^/\s]+', f'/releases/tag/v{new_ver}', txt)
        yml.write_text(txt, encoding="utf-8")


# File con stringhe di versione "vX.Y.Z" / "?v=X.Y.Z" da sincronizzare.
# Ogni voce: (file, lista di (regex, sostituzione con {v}))
EXTRA_TARGETS = [
    (ROOT / "frontend" / "index.html", [
        (r"(BACS Help Auto Mapper v)\d+\.\d+\.\d+", r"\g<1>{v}"),
        (r"(\?v=)\d+\.\d+\.\d+", r"\g<1>{v}"),
    ]),
    (ROOT / "frontend" / "js" / "i18n.js", [
        (r"(BACS Help Auto Mapper v)\d+\.\d+\.\d+", r"\g<1>{v}"),
    ]),
    (ROOT / "MANUALE_UTENTE.md", [
        (r"(Guida Operativa di Campo \(v)\d+\.\d+\.\d+", r"\g<1>{v}"),
    ]),
    (ROOT / "frontend" / "MANUALE_UTENTE.md", [
        (r"(Guida Operativa di Campo \(v)\d+\.\d+\.\d+", r"\g<1>{v}"),
    ]),
    (ROOT / "scripts" / "package_deb.sh", [
        (r'(VERSION="\$\{1:-)\d+\.\d+\.\d+', r"\g<1>{v}"),
    ]),
    (ROOT / "scripts" / "install.sh", [
        (r'(TAG_NAME="v)\d+\.\d+\.\d+', r"\g<1>{v}"),
    ]),
    (ROOT / ".env.example", [
        (r'(APP_VERSION=)\d+\.\d+\.\d+', r"\g<1>{v}"),
    ]),
    (ROOT / "installer" / "bham.iss", [
        (r'(#define MyAppVersion\s*")[^"]+', r'\g<1>{v}'),
    ]),
]

# Elenco file da includere nel commit di release (usato da release.sh / CI).
RELEASE_FILES = [
    "pyproject.toml", "core/config.py", "winget/",
    "frontend/index.html", "frontend/js/i18n.js",
    "MANUALE_UTENTE.md", "frontend/MANUALE_UTENTE.md",
    "scripts/package_deb.sh", "scripts/install.sh", ".env.example", "installer/bham.iss",
    "CHANGELOG.md",
]


def update_extra(new_ver: str):
    for path, rules in EXTRA_TARGETS:
        if not path.exists():
            continue
        txt = path.read_text(encoding="utf-8")
        for pattern, repl in rules:
            txt = re.sub(pattern, repl.replace("{v}", new_ver), txt)
        path.write_text(txt, encoding="utf-8")


def main():
    if len(sys.argv) < 2:
        print("Uso: python3 scripts/bump_version.py <patch|minor|major|X.Y.Z> [--get]")
        sys.exit(1)

    arg = sys.argv[1]
    curr = get_current_version()

    if arg == "--get":
        print(curr)
        return
    if arg == "--files":
        print(" ".join(RELEASE_FILES))
        return

    new_ver = bump(curr, arg)
    update_pyproject(new_ver)
    update_config(new_ver)
    update_winget(new_ver)
    update_extra(new_ver)

    # Stampa la nuova versione per catturarla negli script / GitHub Actions
    print(new_ver)


if __name__ == "__main__":
    main()
