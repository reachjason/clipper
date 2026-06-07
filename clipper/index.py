"""Append-only CSV index of everything clipper produces.

Lives at outputs/index.csv (git-ignored) so you can trace any clip back to its
source link and the raw footage it came from.
"""

from __future__ import annotations

import csv
from pathlib import Path

FIELDS = ["timestamp", "link", "input_path", "output_path"]


def append_row(
    index_path: Path,
    *,
    timestamp: str,
    link: str,
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
