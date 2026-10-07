#!/usr/bin/env python3
"""
Floating HUD Progress Window for Lecture Pipeline (macOS)
Modern, Apple Human Interface Guidelines-inspired dark HUD.
Features artifact-free pure polygon rounded corners, canvas vector icons,
high-contrast accessible buttons, and compact layout.
"""

import os
import sys
import json
import time
import math
import queue
import threading
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import font as tkfont

# Apple Dark Mode Palette
BG_COLOR = "#161618"
CARD_BG = "#1f1f23"
CARD_BORDER = "#2e2e35"
TEXT_PRIMARY = "#ffffff"
TEXT_SECONDARY = "#a1a1aa"
TEXT_MUTED = "#585862"
ACCENT_BLUE = "#0a84ff"
ACCENT_BLUE_HOVER = "#0071e3"
ACCENT_GREEN = "#30d158"
ACCENT_AMBER = "#f59e0b"
ACCENT_RED = "#ef4444"
PROGRESS_TRACK = "#2a2a32"

STEPS = [
    (1, "Buforowanie w bezpiecznym katalogu .staging"),
    (2, "Transkrypcja mowy (NVIDIA Parakeet V3 MLX)"),
    (3, "Identyfikacja Gemini & ekstrakcja slajdów WebP"),
    (4, "Synteza notatki Obsidian & struktura folderów"),
    (5, "Sprzętowa kompresja wideo HEVC VideoToolbox")
]

def draw_rounded_rect(canvas: tk.Canvas, x1: float, y1: float, x2: float, y2: float, r: float = 8, fill: str = "", outline: str = "", width: int = 1):
    """
    Renders an exact, artifact-free rounded rectangle as a single smooth polygon.
    Eliminates pie-slice seams, corner ticks, and radial lines.
    """
    points = []
    r = max(1.0, min(float(r), (x2 - x1) / 2.0, (y2 - y1) / 2.0))
    corners = [
        (x2 - r, y1 + r, -math.pi / 2, 0),
        (x2 - r, y2 - r, 0, math.pi / 2),
        (x1 + r, y2 - r, math.pi / 2, math.pi),
        (x1 + r, y1 + r, math.pi, 3 * math.pi / 2)
    ]
    steps = 8
    for cx, cy, start_angle, end_angle in corners:
        for i in range(steps + 1):
            theta = start_angle + (end_angle - start_angle) * (i / steps)
            px = cx + r * math.cos(theta)
            py = cy + r * math.sin(theta)
            points.extend([px, py])

    kwargs = {}
    if fill:
        kwargs["fill"] = fill
    if outline:
        kwargs["outline"] = outline
        kwargs["width"] = width
    else:
        kwargs["outline"] = ""
        kwargs["width"] = 0
    return canvas.create_polygon(points, **kwargs)

class ModernCanvasButton(tk.Canvas):
    """High-contrast, artifact-free button with centered vector icons and smooth hover state."""
    def __init__(self, parent, text: str, icon_type: str, command, variant: str = "primary", width: int = 130, height: int = 34):
        super().__init__(parent, width=width, height=height, bg=BG_COLOR, highlightthickness=0, cursor="pointinghand")
        self.text = text
        self.icon_type = icon_type
        self.command = command
        self.variant = variant
        self.w = width
        self.h = height

        if variant == "primary":
            self.bg_normal = ACCENT_BLUE
            self.bg_hover = ACCENT_BLUE_HOVER
            self.border_normal = ""
            self.border_hover = ""
            self.fg_color = "#ffffff"
        elif variant == "secondary":
            self.bg_normal = "#2c2c30"
            self.bg_hover = "#3a3a42"
            self.border_normal = "#3a3a44"
            self.border_hover = "#4a4a56"
            self.fg_color = "#f4f4f6"
        else:  # ghost / close
            self.bg_normal = "#222226"
            self.bg_hover = "#2e2e34"
            self.border_normal = "#32323a"
            self.border_hover = "#42424c"
            self.fg_color = "#a1a1aa"

        self.current_bg = self.bg_normal
        self.current_border = self.border_normal
        self._render()

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _render(self):
        self.delete("all")
        draw_rounded_rect(
            self, 1, 1, self.w - 1, self.h - 1,
            r=7, fill=self.current_bg, outline=self.current_border,
            width=1 if self.current_border else 0
        )

        cy = self.h // 2
        is_bold = (self.variant == "primary")
        fnt = tkfont.Font(family="Helvetica Neue", size=10, weight="bold" if is_bold else "normal")
        text_w = fnt.measure(self.text)

        if self.icon_type == "obsidian":
            icon_w = 12
            gap = 7
            total_w = icon_w + gap + text_w
            start_x = (self.w - total_w) // 2
            ix = start_x
            # Crisp vector document outline
            self.create_polygon(ix, cy - 6, ix + 8, cy - 6, ix + 12, cy - 2, ix + 12, cy + 7, ix, cy + 7, fill="", outline=self.fg_color, width=1.5)
            self.create_line(ix + 8, cy - 6, ix + 8, cy - 2, ix + 12, cy - 2, fill=self.fg_color, width=1.5)
            self.create_text(ix + icon_w + gap, cy, text=self.text, fill=self.fg_color, font=fnt, anchor="w")

        elif self.icon_type == "finder":
            icon_w = 13
            gap = 7
            total_w = icon_w + gap + text_w
            start_x = (self.w - total_w) // 2
            ix = start_x
            # Crisp vector folder outline
            self.create_polygon(ix, cy - 5, ix + 5, cy - 5, ix + 7, cy - 3, ix + 13, cy - 3, ix + 13, cy + 6, ix, cy + 6, fill="", outline=self.fg_color, width=1.5)
            self.create_text(ix + icon_w + gap, cy, text=self.text, fill=self.fg_color, font=fnt, anchor="w")

        elif self.icon_type == "close":
            icon_w = 8
            gap = 6
            total_w = icon_w + gap + text_w
            start_x = (self.w - total_w) // 2
            ix = start_x
            # Crisp vector X cross
            self.create_line(ix, cy - 4, ix + 8, cy + 4, fill=self.fg_color, width=1.5, capstyle="round")
            self.create_line(ix + 8, cy - 4, ix, cy + 4, fill=self.fg_color, width=1.5, capstyle="round")
            self.create_text(ix + icon_w + gap, cy, text=self.text, fill=self.fg_color, font=fnt, anchor="w")

        else:
            self.create_text(self.w // 2, cy, text=self.text, fill=self.fg_color, font=fnt, anchor="center")

    def _on_enter(self, _):
        self.current_bg = self.bg_hover
        self.current_border = self.border_hover
        self._render()

    def _on_leave(self, _):
        self.current_bg = self.bg_normal
        self.current_border = self.border_normal
        self._render()

    def _on_click(self, _):
        if self.command:
            self.command()

class StepIndicator(tk.Canvas):
    """Vector status indicator for individual pipeline steps."""
    def __init__(self, parent):
        super().__init__(parent, width=16, height=16, bg=CARD_BG, highlightthickness=0)
        self.state = "pending"
        self._render()

    def set_state(self, state: str):
        self.state = state
        self._render()

    def _render(self):
        self.delete("all")
        if self.state == "done":
            self.create_oval(1, 1, 15, 15, fill=ACCENT_GREEN, outline="")
            self.create_line(4, 8, 7, 11, 12, 5, fill="#ffffff", width=1.6, capstyle="round", joinstyle="round")
        elif self.state == "active":
            self.create_oval(1, 1, 15, 15, fill="", outline=ACCENT_AMBER, width=1.8)
            self.create_oval(5, 5, 11, 11, fill=ACCENT_AMBER, outline="")
        else:
            self.create_oval(2, 2, 14, 14, fill="", outline="#3e3e48", width=1.4)

class LectureHUDApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Lecture Pipeline")
        self.root.configure(bg=BG_COLOR)

        self.win_width = 440
        self.win_height = 380

        sw = self.root.winfo_screenwidth()
        x_pos = max(20, sw - self.win_width - 32)
        y_pos = 48
        self.root.geometry(f"{self.win_width}x{self.win_height}+{x_pos}+{y_pos}")
        self.root.resizable(False, False)

        # Floating HUD (Always on top)
        self.root.attributes("-topmost", True)

        try:
            import AppKit
            AppKit.NSApplication.sharedApplication().activateIgnoringOtherApps_(False)
        except Exception:
            pass

        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)

        self.start_time = time.time()
        self.event_queue = queue.Queue()
        self.is_completed = False
        self.note_path = None
        self.course_dir = None
        self.progress_pct = 0.0

        self._build_ui()
        self._start_timer()
        self._start_ipc_listener()
        self.root.after(40, self._process_events)

    def _build_ui(self):
        # 1. Top Header Bar
        header = tk.Frame(self.root, bg=BG_COLOR)
        header.pack(fill="x", padx=16, pady=(14, 8))

        # Status badge pill
        self.status_pill = tk.Canvas(header, width=130, height=22, bg=BG_COLOR, highlightthickness=0)
        self.status_pill.pack(side="left")
        self._render_status_pill("active", "LECTURE PIPELINE")

        # Timer badge pill
        self.timer_pill = tk.Canvas(header, width=72, height=22, bg=BG_COLOR, highlightthickness=0)
        self.timer_pill.pack(side="right")
        self._render_timer("00:00")

        # 2. Main Lecture Status Card (Rounded 9px, pure polygon)
        self.card_canvas = tk.Canvas(self.root, width=408, height=62, bg=BG_COLOR, highlightthickness=0)
        self.card_canvas.pack(fill="x", padx=16, pady=(0, 10))
        draw_rounded_rect(self.card_canvas, 1, 1, 407, 61, r=9, fill=CARD_BG, outline=CARD_BORDER, width=1)

        self.card_icon_items = []
        self._render_card_icon("active")

        self.title_text_id = self.card_canvas.create_text(
            38, 20, text="Oczekiwanie na nagranie...",
            fill=TEXT_PRIMARY, font=("Helvetica Neue", 11, "bold"), anchor="w"
        )
        self.detail_text_id = self.card_canvas.create_text(
            38, 41, text="Inicjalizacja środowiska i modeli...",
            fill=TEXT_SECONDARY, font=("Helvetica Neue", 10), anchor="w"
        )

        # 3. Overall Progress Section
        prog_header = tk.Frame(self.root, bg=BG_COLOR)
        prog_header.pack(fill="x", padx=16, pady=(0, 4))

        self.overall_label = tk.Label(
            prog_header, text="Postęp potoku: 0%",
            font=("Helvetica Neue", 10, "bold"), fg=TEXT_PRIMARY, bg=BG_COLOR
        )
        self.overall_label.pack(side="left")

        self.step_counter_lbl = tk.Label(
            prog_header, text="Krok 0 z 5",
            font=("Helvetica Neue", 10), fg=TEXT_SECONDARY, bg=BG_COLOR
        )
        self.step_counter_lbl.pack(side="right")

        # Custom rounded progress track (Overall Pipeline: 8px)
        self.bar_canvas = tk.Canvas(self.root, width=408, height=8, bg=BG_COLOR, highlightthickness=0)
        self.bar_canvas.pack(fill="x", padx=16, pady=(0, 4))
        draw_rounded_rect(self.bar_canvas, 0, 0, 408, 8, r=4, fill=PROGRESS_TRACK, outline="")

        # Detailed Step Progress Track (Sub-step Micro-progress: 4px)
        self.sub_bar_canvas = tk.Canvas(self.root, width=408, height=4, bg=BG_COLOR, highlightthickness=0)
        self.sub_bar_canvas.pack(fill="x", padx=16, pady=(0, 10))
        draw_rounded_rect(self.sub_bar_canvas, 0, 0, 408, 4, r=2, fill=PROGRESS_TRACK, outline="")

        # 4. Steps Checklist Card (Rounded 9px to match top card)
        self.steps_container = tk.Canvas(self.root, width=408, height=138, bg=BG_COLOR, highlightthickness=0)
        self.steps_container.pack(fill="x", padx=16, pady=(0, 12))
        draw_rounded_rect(self.steps_container, 1, 1, 407, 137, r=9, fill=CARD_BG, outline=CARD_BORDER, width=1)

        inner_steps = tk.Frame(self.steps_container, bg=CARD_BG)
        self.step_widgets = {}
        for idx, desc in STEPS:
            row = tk.Frame(inner_steps, bg=CARD_BG)
            row.pack(fill="x", pady=2)

            indicator = StepIndicator(row)
            indicator.pack(side="left", padx=(0, 8))

            desc_lbl = tk.Label(
                row, text=f"{idx}. {desc}",
                font=("Helvetica Neue", 9), fg=TEXT_MUTED, bg=CARD_BG, anchor="w"
            )
            desc_lbl.pack(side="left", fill="x", expand=True)

            self.step_widgets[idx] = {"indicator": indicator, "desc": desc_lbl}

        self.steps_container.create_window(12, 9, window=inner_steps, anchor="nw")

        # 5. Bottom Action Container
        self.action_frame = tk.Frame(self.root, bg=BG_COLOR)
        self.action_frame.pack(fill="x", padx=16, pady=(0, 12))

        self.running_hint = tk.Label(
            self.action_frame, text="Trwa autonomiczne przetwarzanie w tle...",
            font=("Helvetica Neue", 9), fg=TEXT_MUTED, bg=BG_COLOR
        )
        self.running_hint.pack(pady=4)

    def _render_card_icon(self, state: str):
        for it in self.card_icon_items:
            self.card_canvas.delete(it)
        self.card_icon_items.clear()

        cx = 22
        cy = 31
        if state == "done":
            # Circular green badge with white checkmark
            bg_id = self.card_canvas.create_oval(cx - 8, cy - 8, cx + 8, cy + 8, fill=ACCENT_GREEN, outline="")
            chk_id = self.card_canvas.create_line(cx - 4, cy, cx - 1, cy + 3, cx + 5, cy - 3, fill="#ffffff", width=1.6, capstyle="round", joinstyle="round")
            self.card_icon_items.extend([bg_id, chk_id])
        elif state == "error":
            bg_id = self.card_canvas.create_oval(cx - 8, cy - 8, cx + 8, cy + 8, fill=ACCENT_RED, outline="")
            ex_id = self.card_canvas.create_line(cx, cy - 4, cx, cy + 2, fill="#ffffff", width=1.6, capstyle="round")
            pt_id = self.card_canvas.create_oval(cx - 1, cy + 4, cx + 1, cy + 6, fill="#ffffff", outline="")
            self.card_icon_items.extend([bg_id, ex_id, pt_id])
        else:
            # Active pulsing ring
            ring_id = self.card_canvas.create_oval(cx - 8, cy - 8, cx + 8, cy + 8, fill="", outline=ACCENT_BLUE, width=1.8)
            dot_id = self.card_canvas.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill=ACCENT_BLUE, outline="")
            self.card_icon_items.extend([ring_id, dot_id])

    def _render_status_pill(self, state: str, label: str):
        self.status_pill.delete("all")
        bg = "#1b2a38" if state == "active" else ("#1b2e22" if state == "done" else "#331c1c")
        dot_color = ACCENT_BLUE if state == "active" else (ACCENT_GREEN if state == "done" else ACCENT_RED)
        text_color = "#93c5fd" if state == "active" else ("#86efac" if state == "done" else "#fca5a5")

        draw_rounded_rect(self.status_pill, 1, 1, 128, 21, r=10, fill=bg, outline="")
        self.status_pill.create_oval(8, 7, 14, 13, fill=dot_color, outline="")
        self.status_pill.create_text(20, 11, text=label, fill=text_color, font=("Helvetica Neue", 9, "bold"), anchor="w")

    def _render_timer(self, time_str: str):
        self.timer_pill.delete("all")
        draw_rounded_rect(self.timer_pill, 1, 1, 70, 21, r=10, fill="#222226", outline="#2e2e34", width=1)
        self.timer_pill.create_text(35, 11, text=time_str, fill=TEXT_SECONDARY, font=("Menlo", 10), anchor="center")

    def _start_timer(self):
        def update_clock():
            if not self.is_completed:
                elapsed = int(time.time() - self.start_time)
                mins = elapsed // 60
                secs = elapsed % 60
                self._render_timer(f"{mins:02d}:{secs:02d}")
            self.root.after(1000, update_clock)
        update_clock()

    def _set_progress(self, percent: float):
        self.progress_pct = max(0.0, min(100.0, percent))
        self.bar_canvas.delete("all")
        draw_rounded_rect(self.bar_canvas, 0, 0, 408, 8, r=4, fill=PROGRESS_TRACK, outline="")

        w = int(408 * (self.progress_pct / 100.0))
        if w >= 8:
            fill_color = ACCENT_GREEN if self.progress_pct >= 100.0 else ACCENT_BLUE
            draw_rounded_rect(self.bar_canvas, 0, 0, w, 8, r=4, fill=fill_color, outline="")

        self.overall_label.config(text=f"Postęp potoku: {int(self.progress_pct)}%")

    def _set_sub_progress(self, percent: float):
        pct = max(0.0, min(100.0, percent))
        self.sub_bar_canvas.delete("all")
        draw_rounded_rect(self.sub_bar_canvas, 0, 0, 408, 4, r=2, fill=PROGRESS_TRACK, outline="")

        w = int(408 * (pct / 100.0))
        if w >= 4:
            fill_color = ACCENT_GREEN if pct >= 100.0 else "#38bdf8"
            draw_rounded_rect(self.sub_bar_canvas, 0, 0, w, 4, r=2, fill=fill_color, outline="")

    def _start_ipc_listener(self):
        def reader():
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    self.event_queue.put(data)
                except Exception:
                    pass
        t = threading.Thread(target=reader, daemon=True)
        t.start()

    def _process_events(self):
        while not self.event_queue.empty():
            data = self.event_queue.get()
            event = data.get("event")

            if event == "start":
                filename = data.get("filename", "")
                self.start_time = time.time()
                self._render_status_pill("active", "PRZETWARZANIE")
                self._render_card_icon("active")
                self.card_canvas.itemconfig(self.title_text_id, text=filename)
                self.card_canvas.itemconfig(self.detail_text_id, text="Przygotowanie sesji w bezpiecznym buforze...", fill=TEXT_SECONDARY)
                self._set_progress(4.0)
                self._set_sub_progress(0.0)

            elif event == "step":
                step_idx = data.get("step", 1)
                name = data.get("name", "")
                detail = data.get("detail", "")

                self.step_counter_lbl.config(text=f"Krok {step_idx} z 5", fg=ACCENT_BLUE)
                self.card_canvas.itemconfig(self.detail_text_id, text=detail or name, fill=TEXT_SECONDARY)
                self._set_sub_progress(0.0)

                # Previous steps done
                for s in range(1, step_idx):
                    if s in self.step_widgets:
                        self.step_widgets[s]["indicator"].set_state("done")
                        base_desc = STEPS[s - 1][1]
                        self.step_widgets[s]["desc"].config(text=f"{s}. {base_desc}", fg=TEXT_SECONDARY, font=("Helvetica Neue", 9))

                # Current step active
                if step_idx in self.step_widgets:
                    self.step_widgets[step_idx]["indicator"].set_state("active")
                    base_desc = STEPS[step_idx - 1][1]
                    self.step_widgets[step_idx]["desc"].config(text=f"{step_idx}. {base_desc}", fg=TEXT_PRIMARY, font=("Helvetica Neue", 9, "bold"))

                base_pct = (step_idx - 1) * 20.0
                self._set_progress(base_pct)

            elif event == "progress":
                step_idx = data.get("step", 3)
                pct = data.get("pct", 0.0)
                detail = data.get("detail", "")
                if detail:
                    self.card_canvas.itemconfig(self.detail_text_id, text=detail, fill="#93c5fd")

                # Update micro-progress bar
                self._set_sub_progress(pct)

                # Update live step progress label
                step_labels = {1: "Buforowanie", 2: "Transkrypcja", 3: "Slajdy WebP", 4: "Notatka", 5: "Kompresja"}
                st_name = step_labels.get(step_idx, f"Krok {step_idx}")
                self.step_counter_lbl.config(text=f"{st_name}: {int(pct)}%", fg="#38bdf8")

                # Update checklist step line in real time
                if step_idx in self.step_widgets:
                    base_desc = STEPS[step_idx - 1][1]
                    self.step_widgets[step_idx]["desc"].config(
                        text=f"{step_idx}. {base_desc} — {int(pct)}%",
                        fg=TEXT_PRIMARY, font=("Helvetica Neue", 9, "bold")
                    )

                base = (step_idx - 1) * 20.0
                total_pct = base + (pct * 0.2)
                self._set_progress(total_pct)

            elif event == "step_done":
                step_idx = data.get("step", 1)
                if step_idx in self.step_widgets:
                    self.step_widgets[step_idx]["indicator"].set_state("done")
                    base_desc = STEPS[step_idx - 1][1]
                    self.step_widgets[step_idx]["desc"].config(text=f"{step_idx}. {base_desc}", fg=TEXT_SECONDARY, font=("Helvetica Neue", 9))
                self._set_sub_progress(100.0)
                self._set_progress(step_idx * 20.0)

            elif event == "complete":
                self.is_completed = True
                self._set_sub_progress(100.0)
                self._set_progress(100.0)
                self._render_status_pill("done", "UKOŃCZONO")
                self._render_card_icon("done")

                # Mark all steps done
                for s in self.step_widgets:
                    self.step_widgets[s]["indicator"].set_state("done")
                    self.step_widgets[s]["desc"].config(fg=TEXT_SECONDARY, font=("Helvetica Neue", 9))

                course = data.get("course", "Nieznany kurs")
                lecture_idx = data.get("lecture", 1)
                topic = data.get("topic", "")
                self.note_path = data.get("note_path")
                self.course_dir = data.get("course_dir")

                # Card updates
                self.card_canvas.itemconfig(self.title_text_id, text=f"{course} (Wykład {lecture_idx})")
                self.card_canvas.itemconfig(self.detail_text_id, text=f"Temat: {topic}", fill="#86efac")
                self.step_counter_lbl.config(text="Gotowe!", fg=ACCENT_GREEN)

                # Replace footer with high-contrast, artifact-free action buttons
                for child in self.action_frame.winfo_children():
                    child.destroy()

                btn_row = tk.Frame(self.action_frame, bg=BG_COLOR)
                btn_row.pack(fill="x")

                # Obsidian button (Primary)
                btn_obsidian = ModernCanvasButton(
                    btn_row, text="Otwórz w Obsidianie", icon_type="obsidian",
                    command=self._open_obsidian, variant="primary", width=175, height=34
                )
                btn_obsidian.pack(side="left", padx=(0, 6))

                # Finder button (Secondary)
                btn_finder = ModernCanvasButton(
                    btn_row, text="Pokaż w Finderze", icon_type="finder",
                    command=self._open_finder, variant="secondary", width=145, height=34
                )
                btn_finder.pack(side="left", padx=(0, 6))

                # Close button (Ghost)
                btn_close = ModernCanvasButton(
                    btn_row, text="Zamknij", icon_type="close",
                    command=self.root.destroy, variant="ghost", width=76, height=34
                )
                btn_close.pack(side="left")

            elif event == "error":
                self.is_completed = True
                self._render_status_pill("error", "BŁĄD POTOKU")
                self._render_card_icon("error")
                err_msg = data.get("message", "Wystąpił nieznany błąd.")
                self.card_canvas.itemconfig(self.detail_text_id, text=f"Błąd: {err_msg}", fill=ACCENT_RED)
                self.step_counter_lbl.config(text="Błąd!", fg=ACCENT_RED)

        self.root.after(40, self._process_events)

    def _open_obsidian(self):
        if self.note_path and os.path.exists(self.note_path):
            subprocess.run(["open", str(self.note_path)])

    def _open_finder(self):
        target = self.note_path or self.course_dir
        if target and os.path.exists(target):
            subprocess.run(["open", "-R", str(target)])

def run_test_simulation():
    """Simulates a full pipeline run for visual testing."""
    root = tk.Tk()
    app = LectureHUDApp(root)

    def simulate():
        app.event_queue.put({"event": "start", "filename": "Screen Recording 2026-10-07 at 16.45.25.mov"})
        time.sleep(0.8)
        app.event_queue.put({"event": "step", "step": 1, "name": "Buforowanie w .staging/", "detail": "Przygotowanie sesji..."})
        time.sleep(0.8)
        app.event_queue.put({"event": "step_done", "step": 1})

        app.event_queue.put({"event": "step", "step": 2, "name": "Transkrypcja audio", "detail": "Ekstrakcja ścieżki audio 16kHz mono..."})
        time.sleep(0.5)
        for p in range(0, 101, 20):
            time.sleep(0.35)
            done_m = (p / 100.0) * 88.0
            app.event_queue.put({
                "event": "progress",
                "step": 2,
                "pct": float(p),
                "detail": f"Transkrypcja audio: {done_m:.1f}/88.0 min ({p}%) • Parakeet MLX"
            })
        app.event_queue.put({"event": "step_done", "step": 2})

        app.event_queue.put({"event": "step", "step": 3, "name": "Identyfikacja i slajdy", "detail": "Skanowanie klatek wideo..."})
        for p in range(0, 101, 25):
            time.sleep(0.3)
            app.event_queue.put({"event": "progress", "step": 3, "pct": float(p), "detail": f"Slajdy WebP: {p//4} wykrytych ({p*0.9:.1f}/90.0 min)"})
        app.event_queue.put({"event": "step_done", "step": 3})

        app.event_queue.put({"event": "step", "step": 4, "name": "Synteza notatki Obsidian", "detail": "Generowanie akademickiej notatki..."})
        time.sleep(0.8)
        app.event_queue.put({"event": "step_done", "step": 4})

        app.event_queue.put({"event": "step", "step": 5, "name": "Kompresja wideo", "detail": "VideoToolbox HEVC 1080p..."})
        time.sleep(0.8)
        app.event_queue.put({"event": "step_done", "step": 5})

        app.event_queue.put({
            "event": "complete",
            "course": "Audyt systemów zarządzania",
            "lecture": 1,
            "topic": "Organizacja i metodyka audytu",
            "note_path": str(Path(__file__).resolve().parent.parent / "README.md"),
            "course_dir": str(Path.home() / "Documents" / "Wykłady")
        })

    threading.Thread(target=simulate, daemon=True).start()
    root.mainloop()

if __name__ == "__main__":
    if "--test" in sys.argv:
        run_test_simulation()
    else:
        root = tk.Tk()
        app = LectureHUDApp(root)
        root.mainloop()
