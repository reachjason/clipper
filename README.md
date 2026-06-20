# clipper

A small, extensible video toolkit. It **clips** videos to a length,
**downloads** them from a URL, and **transcribes** them to text — from the
command line or an interactive **TUI**. Source can be a local file or a URL.

## Requirements

- Python 3.10+
- `ffmpeg` + `ffprobe` — `brew install ffmpeg`
- `yt-dlp` (only for URLs) — `brew install yt-dlp`
- `whisper-cpp` (only for `transcribe`) — `brew install whisper-cpp`
- `textual` (only for the TUI) — installed into a project venv (see Setup)

### Setup (for the TUI)

The TUI needs Textual, which installs into a project virtualenv so it never
touches your system Python:

```sh
python3 -m venv .venv
./.venv/bin/python -m pip install textual
```

The `./clip` wrapper auto-detects `.venv` and uses it. The `clip`, `download`,
and `transcribe` commands work without it.

## Usage

```sh
./clip clip <input> [--start <time>] [--duration <length> | --end <time>] [--output <file>]
```

`<input>` is either a local path or an `http(s)` URL — it's auto-detected.

Times accept seconds (`90`), `M:SS` (`1:30`), or `H:MM:SS` (`00:01:30`).

By default, results are saved into the **`outputs/`** folder (created
automatically, and git-ignored). Pass `--output` to choose your own path.

Downloaded source footage is kept under **`outputs/raw/`**, and every run is
logged to **`outputs/index.csv`** (columns: `timestamp`, `link`, `video_id`,
`input_path`, `output_path`) so any clip can be traced back to its source. See
[`outputs/README.md`](outputs/README.md) for details.

If you've already downloaded a video before, clipper **reuses the cached
footage** instead of re-downloading it. Dedup is **by video ID**, so a different
URL for the same video (e.g. `youtu.be/abc` vs `youtube.com/watch?v=abc`) still
reuses the existing copy. Pass `--force-download` to fetch a fresh copy.

### What gets produced

| You provide | Result |
|-------------|--------|
| `--duration` (and optionally `--start`) | A clip of that length |
| `--end` (and optionally `--start`) | A clip from `--start` **to that point** |
| `--start` only | A clip from that point **to the end** |
| **Nothing** (URL input) | The **full video, downloaded** (no re-encode) |
| Nothing (local file) | Nothing to do — friendly error |

`--duration` and `--end` are two ways to say the same thing — use whichever is
handier. They can't be combined.

### Examples

```sh
# Just download a full video (no clipping)
./clip clip "https://x.com/user/status/123..."

# First 30 seconds of a local file
./clip clip talk.mp4 -d 30

# 15-second clip starting at 1:30, to a chosen path
./clip clip talk.mp4 -s 1:30 -d 15 -o ~/Desktop/highlight.mp4

# From 1:30 to 1:45 (by end time, no duration math)
./clip clip talk.mp4 -s 1:30 -e 1:45

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
| `-d, --duration` | Clip length (mutually exclusive with `--end`) |
| `-e, --end` | End time — clip runs from `--start` to here (mutually exclusive with `--duration`) |
| `-o, --output` | Output path (default `<name>_clip.mp4` in cwd) |
| `--copy` | Stream-copy instead of re-encoding: instant, but the start snaps to the nearest keyframe |
| `--overwrite` | Replace an existing output file |
| `--force-download` | Re-download a URL even if its footage is already cached |
| `-q, --quiet` | Less output |

By default clips are **re-encoded** (libx264/aac) so the cut is frame-accurate.
Use `--copy` when you want an instant cut and don't mind the start landing on a
keyframe.

## Transcribe

Turn a video (or just a span of it) into readable text, fully **locally** via
whisper.cpp — no network, no API keys.

```sh
./clip transcribe <input> [--start <time>] [--duration <length> | --end <time>] [--srt]
```

The same `-s/-d/-e` time flags as `clip` apply, so you can transcribe **only a
clip's span** without cutting it first. Output is a readable `.txt` in
`outputs/`; add `--srt` for a timestamped subtitle file alongside it.

```sh
# Whole file
./clip transcribe talk.mp4

# Just 1:30–1:45, with subtitles
./clip transcribe talk.mp4 -s 1:30 -e 1:45 --srt

# Straight from a URL (footage is cached/deduped like clip)
./clip transcribe "https://www.youtube.com/watch?v=..."
```

| Flag | Meaning |
|------|---------|
| `-s/-d/-e` | Same time selection as `clip` (transcribe only that span) |
| `--model` | whisper model name (default `base.en`) |
| `--srt` | Also write a timestamped `.srt` |
| `-o, --output` | Output `.txt` path |

Models live in `outputs/models/` as `ggml-<name>.bin`. `base.en` (~140MB) is
downloaded during setup; grab others from
[Hugging Face](https://huggingface.co/ggerganov/whisper.cpp/tree/main).

## Interactive TUI

```sh
./clip tui
```

A terminal front-end over everything above: enter a source, set start/end or
duration, and hit **Download**, **Clip**, or **Transcribe**. Progress streams
into a log pane, and a library table shows past outputs from `index.csv` —
select a row to reload its source. Runs the exact same code as the CLI.

## Project layout

```
clip                 # executable wrapper (re-execs into .venv if present)
clipper/
  cli.py             # argparse + subcommand dispatch
  ops.py             # shared orchestration (CLI + TUI call into here)
  tui.py             # Textual interactive UI
  video.py           # ffmpeg/ffprobe: probe + clip
  download.py        # yt-dlp URL handling
  transcribe.py      # whisper.cpp transcription
  timeparse.py       # time parsing/formatting
  index.py           # outputs/index.csv logging
outputs/             # generated media, models, index.csv (git-ignored)
```

To add a subcommand, put its orchestration in `ops.py` and register an
`_add_<name>_parser` in `cli.py` so the CLI and TUI share one code path.
