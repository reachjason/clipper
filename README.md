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
./clip clip <input> [--duration <length>] [--start <time>] [--output <file>]
```

`<input>` is either a local path or an `http(s)` URL — it's auto-detected.

Times accept seconds (`90`), `M:SS` (`1:30`), or `H:MM:SS` (`00:01:30`).

By default, results are saved into the **`outputs/`** folder (created
automatically, and git-ignored). Pass `--output` to choose your own path.

Downloaded source footage is kept under **`outputs/raw/`**, and every run is
logged to **`outputs/index.csv`** (columns: `timestamp`, `link`, `input_path`,
`output_path`) so any clip can be traced back to its source. See
[`outputs/README.md`](outputs/README.md) for details.

### What gets produced

| You provide | Result |
|-------------|--------|
| `--duration` (and optionally `--start`) | A clip of that length |
| `--start` only | A clip from that point **to the end** |
| **Neither** (URL input) | The **full video, downloaded** (no re-encode) |
| Neither (local file) | Nothing to do — friendly error |

### Examples

```sh
# Just download a full video (no clipping)
./clip clip "https://x.com/user/status/123..."

# First 30 seconds of a local file
./clip clip talk.mp4 -d 30

# 15-second clip starting at 1:30, to a chosen path
./clip clip talk.mp4 -s 1:30 -d 15 -o ~/Desktop/highlight.mp4

# From 0:10 to the end
./clip clip talk.mp4 -s 0:10

# From YouTube
./clip clip "https://www.youtube.com/watch?v=..." -s 0:10 -d 20
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
  index.py           # outputs/index.csv logging
outputs/             # generated media + index.csv (git-ignored)
```

To add a feature later (e.g. `transcribe`), add a module plus an
`_add_<name>_parser` registration in `cli.py`.
