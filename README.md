# clipper

A small, extensible video toolkit. Today it clips videos to a length, from a
local file or a URL. Built to grow — transcription and analysis are planned as
additional subcommands.

## Requirements

- Python 3.10+
- `ffmpeg` + `ffprobe` — `brew install ffmpeg`
- `yt-dlp` (only for URLs) — `brew install yt-dlp`

## Usage

```sh
./clip clip <input> --duration <length> [--start <time>] [--output <file>]
```

`<input>` is either a local path or an `http(s)` URL — it's auto-detected.

Times accept seconds (`90`), `M:SS` (`1:30`), or `H:MM:SS` (`00:01:30`).

### Examples

```sh
# First 30 seconds of a local file
./clip clip talk.mp4 -d 30

# 15-second clip starting at 1:30
./clip clip talk.mp4 -s 1:30 -d 15 -o highlight.mp4

# From YouTube
./clip clip "https://www.youtube.com/watch?v=..." -s 0:10 -d 20

# From X / Twitter
./clip clip "https://x.com/user/status/123..." -d 10
```

Anything yt-dlp supports as a source works here (YouTube, X/Twitter, Vimeo, and
~1000 other sites).

### Options

| Flag | Meaning |
|------|---------|
| `-s, --start` | Start time (default `0`) |
| `-d, --duration` | Clip length (required) |
| `-o, --output` | Output path (default `<name>_clip.mp4` in cwd) |
| `--copy` | Stream-copy instead of re-encoding: instant, but the start snaps to the nearest keyframe |
| `--overwrite` | Replace an existing output file |
| `-q, --quiet` | Less output |

By default clips are **re-encoded** (libx264/aac) so the cut is frame-accurate.
Use `--copy` when you want an instant cut and don't mind the start landing on a
keyframe.

## Project layout

```
clip                 # executable wrapper
clipper/
  cli.py             # argparse + subcommand dispatch
  video.py           # ffmpeg/ffprobe: probe + clip
  download.py        # yt-dlp URL handling
  timeparse.py       # time parsing/formatting
```

To add a feature later (e.g. `transcribe`), add a module plus an
`_add_<name>_parser` registration in `cli.py`.
