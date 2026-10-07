#!/usr/bin/env python3
"""
HUD Tracker Manager for Lecture Pipeline.
Safely spawns and streams JSON updates to scripts/progress_window.py.
Handles Rich console mirroring and gracefully degrades if GUI is unavailable.
"""

import sys
import json
import subprocess
from pathlib import Path
from typing import Optional
from rich.console import Console

class LectureProgressTracker:
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.gui_process: Optional[subprocess.Popen] = None
        self.hud_script = Path(__file__).parent / "progress_window.py"
        self._spawn_gui()

    def _spawn_gui(self):
        try:
            self.gui_process = subprocess.Popen(
                [sys.executable, str(self.hud_script)],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1  # Line buffered
            )
        except Exception as e:
            if self.console:
                self.console.print(f"[dim yellow]Nie udało się uruchomić okienka HUD: {e}. Kontynuuję w trybie konsoli.[/dim yellow]")
            self.gui_process = None

    def _send_event(self, data: dict):
        if not self.gui_process or not self.gui_process.stdin:
            return
        try:
            line = json.dumps(data) + "\n"
            self.gui_process.stdin.write(line)
            self.gui_process.stdin.flush()
        except (BrokenPipeError, OSError):
            # Window was closed by user or terminated
            self.gui_process = None

    def start_lecture(self, filename: str):
        self._send_event({
            "event": "start",
            "filename": filename
        })

    def start_step(self, step_idx: int, name: str, detail: str = ""):
        self._send_event({
            "event": "step",
            "step": step_idx,
            "name": name,
            "detail": detail
        })

    def update_progress(self, step_idx: int, pct: float, detail: str = ""):
        self._send_event({
            "event": "progress",
            "step": step_idx,
            "pct": pct,
            "detail": detail
        })

    def finish_step(self, step_idx: int, name: str = ""):
        self._send_event({
            "event": "step_done",
            "step": step_idx,
            "name": name
        })

    def complete_lecture(self, course: str, lecture: int, topic: str, note_path: str = "", course_dir: str = ""):
        self._send_event({
            "event": "complete",
            "course": course,
            "lecture": lecture,
            "topic": topic,
            "note_path": str(note_path),
            "course_dir": str(course_dir)
        })

    def report_error(self, message: str):
        self._send_event({
            "event": "error",
            "message": message
        })

    def close(self):
        # Close stdin stream to notify child of end of events without killing the GUI
        if self.gui_process and self.gui_process.stdin:
            try:
                self.gui_process.stdin.close()
            except Exception:
                pass

    def wait_until_closed(self, timeout: Optional[float] = None):
        """
        Keeps parent process alive so launchd / OS does not tear down
        the GUI HUD process until the user explicitly closes it.
        """
        if self.gui_process:
            try:
                self.gui_process.wait(timeout=timeout)
            except (subprocess.TimeoutExpired, Exception):
                pass

