"""Command-line entry point.

Subcommand-based so new capabilities (transcribe, analyze) slot in cleanly:
each subcommand registers itself with its own args and a handler.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from . import __version__
from .download import download, is_url
from .timeparse import parse_time
from .video import FFmpegError, ToolNotFound, clip, probe_duration


def _add_clip_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "clip",
        help="cut a clip from a local file or URL",
        description="Cut a clip of a given start + duration from a video.",
    )
    p.add_argument("input", help="local video path or a URL (http/https)")
    p.add_argument(
        "-s", "--start", default="0",
        help="start time: seconds, M:SS, or H:MM:SS (default: 0)",
    )
    p.add_argument(
        "-d", "--duration", required=True,
        help="clip length: seconds, M:SS, or H:MM:SS",
    )
    p.add_argument(
        "-o", "--output", default=None,
        help="output file (default: <name>_clip.mp4 in the cwd)",
    )
    p.add_argument(
        "--copy", action="store_true",
        help="stream-copy instead of re-encoding (instant, but start snaps to "
             "nearest keyframe)",
    )
    p.add_argument(
        "--overwrite", action="store_true",
        help="overwrite the output file if it exists",
    )
    p.add_argument("-q", "--quiet", action="store_true", help="less output")
    p.set_defaults(func=_cmd_clip)


def _default_output(source_name: str) -> Path:
    stem = Path(source_name).stem or "video"
    return Path.cwd() / f"{stem}_clip.mp4"


def _cmd_clip(args: argparse.Namespace) -> int:
    try:
        start = parse_time(args.start)
        duration = parse_time(args.duration)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if duration <= 0:
        print("error: --duration must be greater than 0", file=sys.stderr)
        return 2

    tmpdir: tempfile.TemporaryDirectory | None = None
    try:
        # Resolve the source: download if it's a URL.
        if is_url(args.input):
            tmpdir = tempfile.TemporaryDirectory(prefix="clipper-")
            if not args.quiet:
                print(f"Downloading {args.input} ...", file=sys.stderr)
            source = download(args.input, Path(tmpdir.name), quiet=args.quiet)
            output_basis = args.input.rstrip("/").split("/")[-1] or source.name
        else:
            source = Path(args.input).expanduser()
            if not source.exists():
                print(f"error: input not found: {source}", file=sys.stderr)
                return 1
            output_basis = source.name

        output = Path(args.output).expanduser() if args.output else _default_output(output_basis)

        # Validate against the source duration when we can read it.
        total = probe_duration(source)
        if total is not None:
            if start >= total:
                print(
                    f"error: start ({start:g}s) is at or past the video length "
                    f"({total:g}s)",
                    file=sys.stderr,
                )
                return 1
            if start + duration > total + 0.5:
                avail = total - start
                print(
                    f"warning: requested {duration:g}s but only {avail:g}s remain "
                    f"after the start; clip will be truncated.",
                    file=sys.stderr,
                )

        if not args.quiet:
            print(
                f"Clipping {duration:g}s from {start:g}s -> {output}",
                file=sys.stderr,
            )
        clip(
            source, output, start, duration,
            copy=args.copy, overwrite=args.overwrite, quiet=args.quiet,
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
    finally:
        if tmpdir is not None:
            tmpdir.cleanup()


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
    # Future: _add_transcribe_parser(subparsers), _add_analyze_parser(subparsers)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
