"""Interactive terminal UI (Textual) over download / clip / transcribe.

A thin front-end: every action calls the same ops.py functions the CLI uses.
Long-running work runs in a worker thread so the UI stays responsive.
"""

from __future__ import annotations

import csv
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    RichLog,
)

from . import ops
from .download import is_url
from .timeparse import parse_time
from .transcribe import DEFAULT_MODEL


def _parse_form_span(start_s: str, dur_s: str, end_s: str) -> tuple[float, float | None]:
    """Turn the three time fields into (start, duration). Raises ValueError."""
    start = parse_time(start_s) if start_s.strip() else 0.0
    duration = parse_time(dur_s) if dur_s.strip() else None
    end = parse_time(end_s) if end_s.strip() else None
    if duration is not None and duration <= 0:
        raise ValueError("duration must be greater than 0")
    if end is not None:
        if end <= start:
            raise ValueError(f"end ({end:g}s) must be after start ({start:g}s)")
        duration = end - start
    return start, duration


class ClipperApp(App):
    TITLE = "clipper"
    SUB_TITLE = "download · clip · transcribe"

    CSS = """
    #form { height: auto; padding: 1 1 0 1; }
    #form Input { width: 1fr; }
    .row { height: auto; }
    .field { height: auto; width: 1fr; padding: 0 1; }
    .field Label { color: $text-muted; }
    #actions { height: auto; padding: 1; }
    #actions Button { margin: 0 1 0 0; }
    #log { height: 1fr; border: round $primary; margin: 0 1; }
    #library { height: 14; border: round $secondary; margin: 1; }
    """

    BINDINGS = [
        ("r", "refresh", "Refresh library"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="form"):
            yield Input(placeholder="URL or local file path…", id="source")
            with Horizontal(classes="row"):
                with Vertical(classes="field"):
                    yield Label("Start (e.g. 1:30)")
                    yield Input(id="start")
                with Vertical(classes="field"):
                    yield Label("Duration (e.g. 15)")
                    yield Input(id="duration")
                with Vertical(classes="field"):
                    yield Label("End (e.g. 1:45)")
                    yield Input(id="end")
                with Vertical(classes="field"):
                    yield Label("Model (transcribe)")
                    yield Input(value=DEFAULT_MODEL, id="model")
        with Horizontal(id="actions"):
            yield Button("Download", id="download", variant="primary")
            yield Button("Clip", id="clip", variant="success")
            yield Button("Transcribe", id="transcribe", variant="warning")
        yield RichLog(id="log", highlight=True, markup=True, wrap=True)
        yield DataTable(id="library")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#library", DataTable)
        table.cursor_type = "row"
        table.add_columns("when", "source", "output")
        self._row_sources: dict = {}
        self.action_refresh()
        self.query_one("#source", Input).focus()
        self._write_log("[dim]Ready. Enter a source, then pick an action.[/dim]")

    # --- logging / table helpers (called via call_from_thread from workers) --

    def _write_log(self, msg: str) -> None:
        self.query_one("#log", RichLog).write(msg)

    def action_refresh(self) -> None:
        table = self.query_one("#library", DataTable)
        table.clear()
        self._row_sources = {}
        if not ops.INDEX_PATH.exists():
            return
        rows = []
        with ops.INDEX_PATH.open(newline="") as f:
            rows = list(csv.DictReader(f))
        for r in rows[-200:]:
            source = r.get("link") or r.get("input_path", "")
            when = (r.get("timestamp", "") or "").replace("T", " ").replace("+00:00", "")
            out = Path(r.get("output_path", "")).name
            key = table.add_row(when, _ellipsize(source, 48), out)
            self._row_sources[key] = source

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        source = self._row_sources.get(event.row_key)
        if source:
            self.query_one("#source", Input).value = source

    # --- actions ------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        source = self.query_one("#source", Input).value.strip()
        if not source:
            self._write_log("[red]Enter a source first.[/red]")
            return
        try:
            start, duration = _parse_form_span(
                self.query_one("#start", Input).value,
                self.query_one("#duration", Input).value,
                self.query_one("#end", Input).value,
            )
        except ValueError as e:
            self._write_log(f"[red]error: {e}[/red]")
            return
        model = self.query_one("#model", Input).value.strip() or DEFAULT_MODEL
        self._set_busy(True)
        self._run_op(event.button.id, source, start, duration, model)

    def _set_busy(self, busy: bool) -> None:
        for bid in ("download", "clip", "transcribe"):
            self.query_one(f"#{bid}", Button).disabled = busy

    @work(thread=True, exclusive=True)
    def _run_op(
        self, kind: str, source: str, start: float, duration: float | None, model: str,
    ) -> None:
        def log(msg: str) -> None:
            self.call_from_thread(self._write_log, msg)

        try:
            is_url_input = is_url(source)
            link = source if is_url_input else ""

            if kind == "download":
                if not is_url_input:
                    log("[red]error: download needs a URL.[/red]")
                    return
                result = ops.download_only(link, quiet=True, log=log)

            elif kind == "clip":
                local = self._resolve_local(source, is_url_input, log)
                if local is None:
                    return
                output = ops.clip_output_path(local.name)
                result = ops.clip_video(
                    local, output, start, duration,
                    link=link, overwrite=True, quiet=True, log=log,
                )

            elif kind == "transcribe":
                local = self._resolve_local(source, is_url_input, log)
                if local is None:
                    return
                output = ops.transcript_output_path(local.name)
                result = ops.transcribe_source(
                    local, output, start=start, duration=duration,
                    link=link, model=model, quiet=True, log=log,
                )
            else:
                return

            log(f"[green]✓ done:[/green] {result}")
            self.call_from_thread(self.action_refresh)
        except Exception as e:  # surface any failure in the log, never crash
            log(f"[red]error: {e}[/red]")
        finally:
            self.call_from_thread(self._set_busy, False)

    def _resolve_local(self, source: str, is_url_input: bool, log) -> Path | None:
        if is_url_input:
            return ops.get_footage(source, force=False, quiet=True, log=log)
        path = Path(source).expanduser()
        if not path.exists():
            log(f"[red]error: input not found: {path}[/red]")
            return None
        return path


def _ellipsize(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def run() -> None:
    ClipperApp().run()


__all__ = ["run", "ClipperApp"]
