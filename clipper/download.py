"""URL handling via yt-dlp."""

from __future__ import annotations

import subprocess
from pathlib import Path
from urllib.parse import urlparse

from .video import ToolNotFound, require


def is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def download(url: str, dest_dir: Path, *, quiet: bool = False) -> Path:
    """Download `url` into `dest_dir`, returning the saved file path."""
    yt_dlp = require("yt-dlp")  # raises ToolNotFound with a helpful message

    out_template = str(dest_dir / "%(id)s.%(ext)s")
    cmd = [
        yt_dlp,
        "-f", "bv*+ba/b",          # best video+audio, fall back to best single
        "--merge-output-format", "mp4",
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
