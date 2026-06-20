"""Command-line entry point.

Subcommand-based so new capabilities slot in cleanly: each subcommand registers
itself with its own args and a handler. Orchestration lives in ops.py, shared
with the TUI.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, ops
from .download import is_url
from .timeparse import parse_time
from .transcribe import DEFAULT_MODEL
from .video import FFmpegError, ToolNotFound


def _add_time_args(p: argparse.ArgumentParser, *, with_duration: bool = True) -> None:
    """Add the shared -s/-d/-e time selection arguments."""
    p.add_argument(
        "-s", "--start", default=None,
        help="start time: seconds, M:SS, or H:MM:SS (default: 0)",
    )
    span = p.add_mutually_exclusive_group()
    span.add_argument(
        "-d", "--duration", default=None,
        help="clip length: seconds, M:SS, or H:MM:SS.",
    )
    span.add_argument(
        "-e", "--end", default=None,
        help="end time: seconds, M:SS, or H:MM:SS (mutually exclusive with "
             "--duration).",
    )


def _resolve_span(args: argparse.Namespace) -> tuple[float, float | None]:
    """Turn parsed -s/-d/-e into (start, duration). Raises ValueError."""
    start = parse_time(args.start) if args.start is not None else 0.0
    duration = parse_time(args.duration) if args.duration is not None else None
    end = parse_time(args.end) if args.end is not None else None
    if duration is not None and duration <= 0:
        raise ValueError("--duration must be greater than 0")
    if end is not None:
        if end <= start:
            raise ValueError(f"--end ({end:g}s) must be after --start ({start:g}s)")
        duration = end - start
    return start, duration


# --- clip ------------------------------------------------------------------

def _add_clip_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "clip",
        help="clip or download a video from a local file or URL",
        description=(
            "Cut a clip from a video. With no --start/--duration/--end, a URL "
            "is simply downloaded in full."
        ),
    )
    p.add_argument("input", help="local video path or a URL (http/https)")
    _add_time_args(p)
    p.add_argument(
        "-o", "--output", default=None,
        help="output file (default: a name in the outputs/ folder)",
    )
    p.add_argument(
        "--copy", action="store_true",
        help="stream-copy instead of re-encoding (instant, but start snaps to "
             "nearest keyframe)",
    )
    p.add_argument("--overwrite", action="store_true",
                   help="overwrite the output file if it exists")
    p.add_argument("--force-download", action="store_true",
                   help="re-download from a URL even if the footage is cached")
    p.add_argument("-q", "--quiet", action="store_true", help="less output")
    p.set_defaults(func=_cmd_clip)


def _cmd_clip(args: argparse.Namespace) -> int:
    try:
        start, duration = _resolve_span(args)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    download_mode = args.start is None and args.duration is None and args.end is None
    is_url_input = is_url(args.input)
    link = args.input if is_url_input else ""
    output = Path(args.output).expanduser() if args.output else None
    quiet = args.quiet

    try:
        if download_mode:
            if not is_url_input:
                print(
                    "error: nothing to do — the input is already a local file. "
                    "Add --duration/--end (and optionally --start) to make a clip.",
                    file=sys.stderr,
                )
                return 1
            result = ops.download_only(
                link, output=output, force=args.force_download, quiet=quiet,
            )
            print(result)
            return 0

        source = _resolve_source(args.input, is_url_input, args.force_download, quiet)
        if source is None:
            return 1
        if output is None:
            output = ops.clip_output_path(source.name)
        ops.clip_video(
            source, output, start, duration,
            link=link, copy=args.copy, overwrite=args.overwrite, quiet=quiet,
        )
        print(output)
        return 0
    except ToolNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 127
    except FileExistsError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except (FFmpegError, RuntimeError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


# --- transcribe ------------------------------------------------------------

def _add_transcribe_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "transcribe",
        help="transcribe a video/clip to text (local, via whisper.cpp)",
        description=(
            "Transcribe a local file or URL to a readable .txt. With "
            "--start/--duration/--end, only that span is transcribed."
        ),
    )
    p.add_argument("input", help="local video path or a URL (http/https)")
    _add_time_args(p)
    p.add_argument(
        "-o", "--output", default=None,
        help="output .txt (default: a name in the outputs/ folder)",
    )
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help=f"whisper model name (default: {DEFAULT_MODEL})")
    p.add_argument("--srt", action="store_true",
                   help="also write a timestamped .srt alongside the .txt")
    p.add_argument("--force-download", action="store_true",
                   help="re-download from a URL even if the footage is cached")
    p.add_argument("-q", "--quiet", action="store_true", help="less output")
    p.set_defaults(func=_cmd_transcribe)


def _cmd_transcribe(args: argparse.Namespace) -> int:
    try:
        start, duration = _resolve_span(args)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    is_url_input = is_url(args.input)
    link = args.input if is_url_input else ""
    quiet = args.quiet

    try:
        source = _resolve_source(args.input, is_url_input, args.force_download, quiet)
        if source is None:
            return 1
        output = (
            Path(args.output).expanduser() if args.output
            else ops.transcript_output_path(source.name)
        )
        result = ops.transcribe_source(
            source, output, start=start, duration=duration, link=link,
            model=args.model, srt=args.srt, quiet=quiet,
        )
        print(result)
        return 0
    except ToolNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 127
    except (FFmpegError, RuntimeError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


# --- tui -------------------------------------------------------------------

def _add_tui_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "tui",
        help="launch the interactive terminal UI",
        description="An interactive front-end over download/clip/transcribe.",
    )
    p.set_defaults(func=_cmd_tui)


def _cmd_tui(args: argparse.Namespace) -> int:
    try:
        from .tui import run as run_tui
    except ModuleNotFoundError as e:
        print(
            f"error: the TUI needs Textual ({e.name}). Install it with:\n"
            f"  ./.venv/bin/python -m pip install textual",
            file=sys.stderr,
        )
        return 127
    run_tui()
    return 0


# --- shared ----------------------------------------------------------------

def _resolve_source(
    raw_input: str, is_url_input: bool, force_download: bool, quiet: bool,
) -> Path | None:
    """Resolve the input to a local file, downloading a URL if needed.

    Returns None (after printing an error) if a local path doesn't exist.
    """
    if is_url_input:
        return ops.get_footage(raw_input, force=force_download, quiet=quiet)
    source = Path(raw_input).expanduser()
    if not source.exists():
        print(f"error: input not found: {source}", file=sys.stderr)
        return None
    return source


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clipper",
        description="A small, extensible video toolkit.",
    )
    parser.add_argument(
        "-V", "--version", action="version", version=f"clipper {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_clip_parser(subparsers)
    _add_transcribe_parser(subparsers)
    _add_tui_parser(subparsers)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
