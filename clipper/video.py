"""ffmpeg/ffprobe wrappers: probing and clipping."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from .timeparse import format_time


class ToolNotFound(RuntimeError):
    """A required external binary is missing."""


class FFmpegError(RuntimeError):
    """ffmpeg/ffprobe exited non-zero."""


def require(binary: str) -> str:
    path = shutil.which(binary)
    if not path:
        raise ToolNotFound(
            f"`{binary}` not found on PATH. Install it with: brew install ffmpeg"
        )
    return path


def probe_duration(path: Path) -> float | None:
    """Return the media duration in seconds, or None if unknown."""
    ffprobe = require("ffprobe")
    proc = subprocess.run(
        [
            ffprobe,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise FFmpegError(proc.stderr.strip() or "ffprobe failed")
    try:
        data = json.loads(proc.stdout)
        dur = data.get("format", {}).get("duration")
        return float(dur) if dur is not None else None
    except (json.JSONDecodeError, ValueError):
        return None


def clip(
    source: Path,
    output: Path,
    start: float,
    duration: float | None = None,
    *,
    copy: bool = False,
    overwrite: bool = False,
    quiet: bool = False,
) -> Path:
    """Cut from `start` into `output`.

    If `duration` is given, cut that many seconds; if `None`, cut to the end of
    the source. By default re-encodes for frame-accurate cuts. `copy=True` uses
    stream-copy (instant, but snaps the start to the nearest keyframe).
    """
    ffmpeg = require("ffmpeg")

    if duration is not None and duration <= 0:
        raise ValueError("duration must be positive")

    if output.exists() and not overwrite:
        raise FileExistsError(
            f"{output} already exists (use --overwrite to replace it)"
        )

    output.parent.mkdir(parents=True, exist_ok=True)

    cmd = [ffmpeg, "-hide_banner", "-y"]
    # -ss before -i is fast and, combined with re-encoding, still frame-accurate.
    cmd += ["-ss", format_time(start), "-i", str(source)]
    if duration is not None:
        cmd += ["-t", format_time(duration)]

    if copy:
        cmd += ["-c", "copy"]
    else:
        cmd += [
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
        ]
    cmd += [str(output)]

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise FFmpegError(proc.stderr.strip() or "ffmpeg failed")
    if not quiet:
        # ffmpeg writes progress to stderr; surface its tail on success too.
        pass
    return output
