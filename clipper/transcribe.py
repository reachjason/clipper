"""Local transcription via whisper.cpp.

Extracts audio with ffmpeg (optionally just a clip span) and runs the
`whisper-cli` binary against a local GGML model. Fully offline and free.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from .timeparse import format_time
from .video import FFmpegError, ToolNotFound, require

# Where downloaded GGML models live (under the git-ignored outputs/ folder).
MODELS_DIR = Path(__file__).resolve().parents[1] / "outputs" / "models"
DEFAULT_MODEL = "base.en"


def model_path(name: str) -> Path:
    """Resolve a model name (e.g. 'base.en') to its ggml .bin path."""
    return MODELS_DIR / f"ggml-{name}.bin"


def require_model(name: str) -> Path:
    path = model_path(name)
    if not path.exists():
        raise ToolNotFound(
            f"model not found: {path}\n"
            f"Download it, e.g.:\n  curl -L -o {path} "
            f"https://huggingface.co/ggerganov/whisper.cpp/resolve/main/"
            f"ggml-{name}.bin"
        )
    return path


def extract_audio(
    source: Path,
    dest: Path,
    *,
    start: float = 0.0,
    duration: float | None = None,
    quiet: bool = False,
) -> Path:
    """Pull a 16kHz mono WAV out of `source` (the format whisper.cpp wants).

    When `start`/`duration` are given, only that span is extracted, so we
    transcribe just the clip rather than the whole source.
    """
    ffmpeg = require("ffmpeg")
    cmd = [ffmpeg, "-y", "-ss", format_time(start), "-i", str(source)]
    if duration is not None:
        cmd += ["-t", format_time(duration)]
    cmd += ["-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(dest)]
    if quiet:
        cmd += ["-loglevel", "error"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise FFmpegError(proc.stderr.strip() or "ffmpeg audio extraction failed")
    return dest


def transcribe(
    source: Path,
    output: Path,
    *,
    start: float = 0.0,
    duration: float | None = None,
    model: str = DEFAULT_MODEL,
    srt: bool = False,
    quiet: bool = False,
) -> Path:
    """Transcribe `source` (a span of it) to a readable .txt at `output`.

    Returns the path to the written .txt. When `srt` is set, a timestamped
    .srt is written alongside it.
    """
    whisper = require("whisper-cli")
    model_bin = require_model(model)

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        wav = extract_audio(
            source,
            Path(tmp) / "audio.wav",
            start=start,
            duration=duration,
            quiet=quiet,
        )
        # whisper-cli appends the format extension to the -of prefix itself.
        prefix = output.with_suffix("")
        cmd = [
            whisper,
            "-m", str(model_bin),
            "-f", str(wav),
            "-otxt",
            "-of", str(prefix),
        ]
        if srt:
            cmd.append("-osrt")
        if quiet:
            cmd.append("--no-prints")
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "whisper-cli failed")

    if not output.exists():
        raise RuntimeError(f"expected transcript at {output}, not found")
    return output


__all__ = ["transcribe", "extract_audio", "model_path", "DEFAULT_MODEL"]
