"""URL handling via yt-dlp."""

from __future__ import annotations

import subprocess
from pathlib import Path
from urllib.parse import urlparse

from .video import ToolNotFound, require

# Raw download naming. The literal " [", "]" survive --restrict-filenames (only
# the substituted field values are sanitized), so the id stays bracketed.
RAW_TEMPLATE = "%(title).100s [%(id)s].%(ext)s"


def is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def probe_filename(url: str, dest_dir: Path, *, quiet: bool = True) -> str | None:
    """Predict the basename yt-dlp would save for `url`, without downloading.

    Does a metadata-only extraction (cheap, no media). Returns the basename, or
    None if it can't be determined (caller should then just try downloading).
    """
    try:
        yt_dlp = require("yt-dlp")
    except ToolNotFound:
        return None
    cmd = [
        yt_dlp,
        "--skip-download",
        "--no-playlist",
        "--restrict-filenames",
        "--print", "filename",
        "-o", str(dest_dir / RAW_TEMPLATE),
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    return Path(lines[-1]).name if lines else None


def download(url: str, dest_dir: Path, *, quiet: bool = False) -> Path:
    """Download `url` into `dest_dir`, returning the saved file path."""
    yt_dlp = require("yt-dlp")  # raises ToolNotFound with a helpful message

    out_template = str(dest_dir / RAW_TEMPLATE)
    cmd = [
        yt_dlp,
        "-f", "bv*+ba/b",          # best video+audio, fall back to best single
        "--merge-output-format", "mp4",
        "--restrict-filenames",    # safe, shell-friendly filenames
        "-o", out_template,
        "--print", "after_move:filepath",
        "--no-simulate",
        url,
    ]
    if quiet:
        cmd.insert(1, "--quiet")

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "yt-dlp failed")

    # The last non-empty stdout line is the final filepath.
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    if not lines:
        raise RuntimeError("yt-dlp did not report an output file")
    path = Path(lines[-1])
    if not path.exists():
        raise RuntimeError(f"expected downloaded file at {path}, not found")
    return path


__all__ = ["is_url", "download", "ToolNotFound"]
