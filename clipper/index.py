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
