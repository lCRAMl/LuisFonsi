"""PDF aus dem HTML-Report erzeugen – über Microsoft Edge oder Google Chrome im Hintergrund.

Es wird kein zusätzliches Python-Paket benötigt. Der Browser läuft mit einem eigenen,
temporären Profil, damit ein bereits geöffnetes Browserfenster nicht stört.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

BROWSER_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]
BROWSER_NAMES = ["msedge", "chrome", "google-chrome", "chromium", "chromium-browser"]


class PdfError(Exception):
    """PDF konnte nicht erzeugt werden."""


def find_browser() -> Path | None:
    for candidate in BROWSER_CANDIDATES:
        path = Path(candidate)
        if path.is_file():
            return path
    for name in BROWSER_NAMES:
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def html_to_pdf(html_path: Path, pdf_path: Path, browser: Path | None = None,
                timeout: float = 120) -> Path:
    """Druckt `html_path` als PDF nach `pdf_path`."""
    browser = browser or find_browser()
    if browser is None:
        raise PdfError("Kein Microsoft Edge oder Google Chrome gefunden")
    html_path = Path(html_path).resolve()
    pdf_path = Path(pdf_path).resolve()
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    if pdf_path.exists():
        pdf_path.unlink()

    with tempfile.TemporaryDirectory(prefix="palletizer-browser-") as profile:
        command = [
            str(browser),
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--disable-extensions",
            f"--user-data-dir={profile}",
            "--no-pdf-header-footer",
            "--print-to-pdf-no-header",
            f"--print-to-pdf={pdf_path}",
            html_path.as_uri(),
        ]
        try:
            subprocess.run(command, check=False, timeout=timeout,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.TimeoutExpired as exc:
            raise PdfError(f"Browser hat nach {timeout:g} s nicht geantwortet") from exc

    if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
        raise PdfError(f"PDF wurde nicht erzeugt: {pdf_path}")
    return pdf_path
