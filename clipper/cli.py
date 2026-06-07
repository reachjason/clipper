"""Command-line entry point.

Subcommand-based so new capabilities (transcribe, analyze) slot in cleanly:
each subcommand registers itself with its own args and a handler.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__, index
from .download import download, is_url
from .timeparse import parse_time
from .video import FFmpegError, ToolNotFound, clip, probe_duration

# Generated files land here by default; this folder is git-ignored.
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "outputs"
RAW_DIR = OUTPUT_DIR / "raw"          # downloaded source footage, kept
INDEX_PATH = OUTPUT_DIR / "index.csv"  # link -> input -> output log


def _log_index(link: str, input_path: Path, output_path: Path) -> None:
    index.append_row(
        INDEX_PATH,
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        link=link,
        input_path=str(input_path),
        output_path=str(output_path),
    )


def _add_clip_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "clip",
        help="clip or download a video from a local file or URL",
        description=(
            "Cut a clip from a video. With no --start/--duration, a URL is "
            "simply downloaded in full."
        ),
    )
    p.add_argument("input", help="local video path or a URL (http/https)")
    p.add_argument(
        "-s", "--start", default=None,
        help="start time: seconds, M:SS, or H:MM:SS (default: 0)",
    )
    p.add_argument(
        "-d", "--duration", default=None,
        help="clip length: seconds, M:SS, or H:MM:SS. Omit with --start to clip "
             "to the end; omit both to just download a URL.",
    )
    p.add_argument(
        "-o", "--output", default=None,
        help="output file (default: a name in the outputs/ folder)",
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
    p.add_argument(
        "--force-download", action="store_true",
        help="re-download from a URL even if the footage is already cached",
    )
    p.add_argument("-q", "--quiet", action="store_true", help="less output")
    p.set_defaults(func=_cmd_clip)


def _clip_output(source_name: str) -> Path:
    stem = Path(source_name).stem or "video"
    return OUTPUT_DIR / f"{stem}_clip.mp4"


def _get_footage(link: str, *, force: bool, quiet: bool) -> Path:
    """Return raw footage for a URL, reusing the cached copy unless `force`."""
    if not force:
        cached = index.find_raw_for_link(INDEX_PATH, link)
        if cached is not None:
            if not quiet:
                print(f"Reusing cached footage: {cached}", file=sys.stderr)
            return cached
    if not quiet:
        print(f"Downloading {link} ...", file=sys.stderr)
    return download(link, RAW_DIR, quiet=quiet)


def _cmd_clip(args: argparse.Namespace) -> int:
    try:
        start = parse_time(args.start) if args.start is not None else 0.0
        duration = parse_time(args.duration) if args.duration is not None else None
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if duration is not None and duration <= 0:
        print("error: --duration must be greater than 0", file=sys.stderr)
        return 2

    # No start and no duration => download-only mode (URLs only).
    download_only = args.start is None and args.duration is None
    is_url_input = is_url(args.input)
    link = args.input if is_url_input else ""
    output = Path(args.output).expanduser() if args.output else None

    try:
        # Download-only: the raw footage IS the deliverable; keep it in raw/.
        if download_only:
            if not is_url_input:
                print(
                    "error: nothing to do — the input is already a local file. "
                    "Add --duration (and optionally --start) to make a clip.",
                    file=sys.stderr,
                )
                return 1
            source = _get_footage(link, force=args.force_download, quiet=args.quiet)
            if output is not None and output != source:
                output.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(output))
                source = output
            _log_index(link, source, source)
            print(source)
            return 0

        # Clip mode. Resolve the source: download (and keep) if it's a URL.
        if is_url_input:
            source = _get_footage(link, force=args.force_download, quiet=args.quiet)
            output_basis = source.name
        else:
            source = Path(args.input).expanduser()
            if not source.exists():
                print(f"error: input not found: {source}", file=sys.stderr)
                return 1
            output_basis = source.name

        if output is None:
            output = _clip_output(output_basis)

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
            if duration is not None and start + duration > total + 0.5:
                avail = total - start
                print(
                    f"warning: requested {duration:g}s but only {avail:g}s remain "
                    f"after the start; clip will be truncated.",
                    file=sys.stderr,
                )

        if not args.quiet:
            span = f"{duration:g}s" if duration is not None else "to end"
            print(f"Clipping {span} from {start:g}s -> {output}", file=sys.stderr)
        clip(
            source, output, start, duration,
            copy=args.copy, overwrite=args.overwrite, quiet=args.quiet,
        )
        _log_index(link, source, output)
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
