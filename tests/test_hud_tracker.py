import sys
import json
import time
from pathlib import Path
import pytest

# Ensure scripts/ is on sys.path
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from gui_tracker import LectureProgressTracker

def test_tracker_lifecycle():
    tracker = LectureProgressTracker()
    try:
        tracker.start_lecture("Test_Recording.mov")
        tracker.start_step(1, "Buforowanie", "Przygotowanie...")
        tracker.update_progress(1, 100.0, "Gotowe")
        tracker.finish_step(1, "Krok 1 gotowy")
        tracker.start_step(2, "Transkrypcja", "Model Parakeet...")
        tracker.finish_step(2, "Krok 2 gotowy")
        tracker.complete_lecture("Przedmiot Testowy", 1, "Temat Wykładu")
    finally:
        if tracker.gui_process:
            tracker.gui_process.terminate()

def test_tracker_handles_closed_pipe():
    tracker = LectureProgressTracker()
    if tracker.gui_process:
        tracker.gui_process.terminate()
        tracker.gui_process.wait()
    # Sending events after process terminated should not raise exceptions
    tracker.start_step(3, "Test", "Detail")
    tracker.update_progress(3, 50.0, "Detail")
    tracker.finish_step(3)
    tracker.complete_lecture("Course", 1, "Topic")
    tracker.report_error("Some error")
    tracker.close()

