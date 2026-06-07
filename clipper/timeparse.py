"""Flexible time parsing/formatting shared across subcommands."""

from __future__ import annotations


def parse_time(value: str) -> float:
    """Parse a timecode into seconds.

    Accepts:
      - plain seconds:        "90", "12.5"
      - minutes:seconds:      "1:30", "1:30.5"
      - hours:minutes:seconds:"01:02:03"
    """
    if value is None:
        raise ValueError("missing time value")

    text = str(value).strip()
    if not text:
        raise ValueError("empty time value")

    parts = text.split(":")
    if len(parts) > 3:
        raise ValueError(f"invalid time {value!r}: too many ':' segments")

    try:
        nums = [float(p) for p in parts]
    except ValueError:
        raise ValueError(f"invalid time {value!r}: non-numeric segment") from None

    if any(n < 0 for n in nums):
        raise ValueError(f"invalid time {value!r}: negative value")

    # For M:SS and H:MM:SS, the trailing fields are 0-59.
    if len(nums) >= 2 and nums[-1] >= 60:
        raise ValueError(f"invalid time {value!r}: seconds must be < 60")
    if len(nums) == 3 and nums[1] >= 60:
        raise ValueError(f"invalid time {value!r}: minutes must be < 60")

    seconds = 0.0
    for n in nums:
        seconds = seconds * 60 + n
    return seconds


def format_time(seconds: float) -> str:
    """Format seconds as H:MM:SS.mmm for ffmpeg."""
    if seconds < 0:
        raise ValueError("negative duration")
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{int(hours):02d}:{int(minutes):02d}:{secs:06.3f}"
