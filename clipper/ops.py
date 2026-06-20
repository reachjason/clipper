"""Shared orchestration for clipper's operations.

The CLI handlers and the TUI both call into here, so download/clip/transcribe
behave identically no matter how they're invoked. Each function returns the
output Path and logs a row to outputs/index.csv.
"""

from __future__ import annotations

import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import index
from .download import download
from .transcribe import DEFAULT_MODEL, transcribe
from .video import clip, probe_duration

# Generated files land here by default; this folder is git-ignored.
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "outputs"
RAW_DIR = OUTPUT_DIR / "raw"           # downloaded source footage, kept
INDEX_PATH = OUTPUT_DIR / "index.csv"  # link -> input -> output log

# A status sink: callers pass something to receive human-readable progress
# lines. The CLI prints to stderr; the TUI appends to its log pane.
Logger = Callable[[str], None]


def _stderr(msg: str) -> None:
    print(msg, file=sys.stderr)


def log_index(link: str, input_path: Path, output_path: Path) -> None:
    index.append_row(
        INDEX_PATH,
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        link=link,
        video_id=index.id_from_name(input_path.name),
        input_path=str(input_path),
        output_path=str(output_path),
    )


def clip_output_path(source_name: str) -> Path:
    stem = Path(source_name).stem or "video"
    return OUTPUT_DIR / f"{stem}_clip.mp4"


def transcript_output_path(source_name: str) -> Path:
    stem = Path(source_name).stem or "video"
    return OUTPUT_DIR / f"{stem}.txt"


def get_footage(link: str, *, force: bool, quiet: bool, log: Logger = _stderr) -> Path:
    """Return raw footage for a URL, reusing a cached copy unless `force`.

    Dedup is by video ID: an exact-URL hit is the fast path (no network); a
    different URL for the same video is caught via a metadata-only id probe.
    """
    from .download import probe_filename

    if not force:
        cached = index.find_raw_for_link(INDEX_PATH, link)
        if cached is None:
            predicted = probe_filename(link, RAW_DIR, quiet=quiet)
            video_id = index.id_from_name(predicted)
            cached = index.find_raw_by_id(INDEX_PATH, RAW_DIR, video_id)
        if cached is not None:
            log(f"Reusing cached footage: {cached}")
            return cached
    log(f"Downloading {link} ...")
    return download(link, RAW_DIR, quiet=quiet)


def clip_video(
    source: Path,
    output: Path,
    start: float,
    duration: float | None,
    *,
    link: str = "",
    copy: bool = False,
    overwrite: bool = False,
    quiet: bool = False,
    log: Logger = _stderr,
) -> Path:
    """Cut a clip and log it. `source` must already be a local file."""
    total = probe_duration(source)
    if total is not None:
        if start >= total:
            raise ValueError(
                f"start ({start:g}s) is at or past the video length ({total:g}s)"
            )
        if duration is not None and start + duration > total + 0.5:
            avail = total - start
            log(
                f"warning: requested {duration:g}s but only {avail:g}s remain "
                f"after the start; clip will be truncated."
            )
    span = f"{duration:g}s" if duration is not None else "to end"
    log(f"Clipping {span} from {start:g}s -> {output}")
    clip(source, output, start, duration, copy=copy, overwrite=overwrite, quiet=quiet)
    log_index(link, source, output)
    return output


def transcribe_source(
    source: Path,
    output: Path,
    *,
    start: float = 0.0,
    duration: float | None = None,
    link: str = "",
    model: str = DEFAULT_MODEL,
    srt: bool = False,
    quiet: bool = False,
    log: Logger = _stderr,
) -> Path:
    """Transcribe a span of `source` to a .txt and log it."""
    span = f"{duration:g}s" if duration is not None else "to end"
    log(f"Transcribing {span} from {start:g}s with {model} -> {output}")
    result = transcribe(
        source, output, start=start, duration=duration,
        model=model, srt=srt, quiet=quiet,
    )
    log_index(link, source, result)
    return result


def download_only(
    link: str,
    *,
    output: Path | None = None,
    force: bool = False,
    quiet: bool = False,
    log: Logger = _stderr,
) -> Path:
    """Download a URL in full (no clipping) and log it."""
    source = get_footage(link, force=force, quiet=quiet, log=log)
    if output is not None and output != source:
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(output))
        source = output
    log_index(link, source, source)
    return source
