"""Append-only CSV index of everything clipper produces.

Lives at outputs/index.csv (git-ignored) so you can trace any clip back to its
source link and the raw footage it came from.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

FIELDS = ["timestamp", "link", "video_id", "input_path", "output_path"]

# Raw files are named "<title> [<id>].<ext>"; pull the bracketed id back out.
_ID_RE = re.compile(r"\[([^\[\]]+)\]\.[^.]+$")


def id_from_name(name: str | None) -> str:
    """Extract the `[id]` token from a raw filename, or '' if absent."""
    if not name:
        return ""
    m = _ID_RE.search(Path(name).name)
    return m.group(1) if m else ""


def append_row(
    index_path: Path,
    *,
    timestamp: str,
    link: str,
    video_id: str,
    input_path: str,
    output_path: str,
) -> None:
    """Append one row, writing the header first if the file is new."""
    index_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not index_path.exists()
    with index_path.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow(
            {
                "timestamp": timestamp,
                "link": link,
                "video_id": video_id,
                "input_path": input_path,
                "output_path": output_path,
            }
        )


def find_raw_for_link(index_path: Path, link: str) -> Path | None:
    """Return the most recent raw file we downloaded for `link`, if it still
    exists on disk. Used to avoid re-downloading footage we already have."""
    if not link or not index_path.exists():
        return None
    match: Path | None = None
    with index_path.open(newline="") as f:
        for row in csv.DictReader(f):
            if row.get("link") == link:
                candidate = Path(row.get("input_path", ""))
                if candidate.exists():
                    match = candidate  # keep scanning; last match wins
    return match


def find_raw_by_id(index_path: Path, raw_dir: Path, video_id: str) -> Path | None:
    """Return cached footage for `video_id` regardless of which URL fetched it.

    Checks the index's video_id column first, then falls back to scanning
    raw_dir for a file whose name carries the same `[id]` token.
    """
    if not video_id:
        return None
    match: Path | None = None
    if index_path.exists():
        with index_path.open(newline="") as f:
            for row in csv.DictReader(f):
                vid = row.get("video_id") or id_from_name(row.get("input_path"))
                if vid == video_id:
                    candidate = Path(row.get("input_path", ""))
                    if candidate.exists():
                        match = candidate
    if match is not None:
        return match
    token = f"[{video_id}]"
    if raw_dir.exists():
        for p in sorted(raw_dir.iterdir()):
            if p.is_file() and token in p.name:
                match = p
    return match
