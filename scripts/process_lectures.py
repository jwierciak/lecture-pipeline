#!/usr/bin/env python3
"""
Automated Multimodal Lecture Processing Pipeline (Audio + Video Slides)
Watches configured lecture folder for new recordings,
buffers in .staging/, transcribes using NVIDIA Parakeet TDT V3 via MLX on Apple Silicon,
semantically identifies course and topic via Gemini API,
extracts visual presentation slides and board diagrams with OpenCV sequential grab,
synthesizes concise academic notes embedding structured JSON,
organizes flat media under Wykłady/[Course]/, syncs note directly to Obsidian Vault,
compresses video using VideoToolbox HEVC, and sends desktop notifications.
"""

import os
import sys
import time
import re
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeElapsedColumn
)

console = Console()

# Add scripts folder to sys.path so modules resolve cleanly
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from config import WATCH_DIR, STAGING_DIR, VAULT_DIR, SUPPORTED_EXTS, LOCK_FILE

from course_matcher import resolve_lecture_identity
from note_synthesizer import generate_academic_note
from extract_slides import extract_slides
from gui_tracker import LectureProgressTracker

def send_notification(title: str, message: str):
    clean_title = title.replace('"', '\\"')
    clean_msg = message.replace('"', '\\"')
    script = f'display notification "{clean_msg}" with title "{clean_title}" sound name "Glass"'
    subprocess.run(["/usr/bin/osascript", "-e", script], check=False)

def wait_for_file_settled(file_path: Path, wait_secs: int = 2) -> bool:
    """Ensure file copy/write operation is finished before processing."""
    last_size = -1
    for _ in range(15):
        if not file_path.exists():
            return False
        current_size = file_path.stat().st_size
        if current_size > 0 and current_size == last_size:
            return True
        last_size = current_size
        time.sleep(wait_secs)
    return True

def transcribe_audio(wav_path: Path, output_md: Path, raw_txt: Path, progress_callback=None):
    import soundfile as sf
    import mlx.core as mx
    import numpy as np
    import parakeet_mlx.parakeet as p_module
    import parakeet_mlx.audio as a_module
    from parakeet_mlx import from_pretrained

    def custom_load_audio(filename, sampling_rate: int, dtype=mx.bfloat16):
        data, sr = sf.read(str(filename), dtype="float32")
        if data.ndim > 1:
            data = np.mean(data, axis=1)
        if sr != sampling_rate:
            import librosa
            data = librosa.resample(data, orig_sr=sr, target_sr=sampling_rate)
        return mx.array(data, dtype=mx.float32)

    p_module.load_audio = custom_load_audio
    a_module.load_audio = custom_load_audio

    # Retrieve audio file details for exact duration tracking
    wav_info = sf.info(str(wav_path))
    sr = wav_info.samplerate
    total_samples = wav_info.frames

    def on_chunk(current_samples, tot_samples):
        if progress_callback and tot_samples > 0:
            pct = (current_samples / tot_samples) * 100.0
            done_m = (current_samples / sr) / 60.0
            tot_m = (tot_samples / sr) / 60.0
            progress_callback(pct, done_m, tot_m)

    model = from_pretrained("mlx-community/parakeet-tdt-0.6b-v3")
    result = model.transcribe(
        str(wav_path),
        chunk_duration=120.0,
        overlap_duration=15.0,
        chunk_callback=on_chunk
    )

    if progress_callback and total_samples > 0:
        tot_m = (total_samples / sr) / 60.0
        progress_callback(100.0, tot_m, tot_m)

    with open(raw_txt, "w", encoding="utf-8") as f:
        f.write(result.text if hasattr(result, "text") else str(result))

    with open(output_md, "w", encoding="utf-8") as f:
        f.write("# Transkrypcja (Parakeet V3)\n\n")
        if hasattr(result, "sentences") and result.sentences:
            for sent in result.sentences:
                s_start = int(sent.start)
                s_end = int(sent.end)
                f.write(f"[{s_start//60:02d}:{s_start%60:02d} - {s_end//60:02d}:{s_end%60:02d}] {sent.text.strip()}\n")
        elif hasattr(result, "text"):
            f.write(result.text.strip() + "\n")

def process_file(source_file: Path):
    if source_file.name.startswith(".") or "_compressed" in source_file.stem:
        return

    console.rule(f"[bold blue]Rozpoczęto przetwarzanie: {source_file.name}[/bold blue]")
    tracker = LectureProgressTracker(console=console)
    tracker.start_lecture(source_file.name)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=35),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=False
        ) as progress:
            
            overall_task = progress.add_task("[bold cyan]Całkowity postęp potoku", total=5)
            
            # Krok 1: Weryfikacja i buforowanie w .staging
            step1 = progress.add_task("[cyan]Krok 1/5: Przygotowanie sesji & buforowanie w .staging/", total=1)
            tracker.start_step(1, "Przygotowanie sesji & buforowanie w .staging/", f"Oczekiwanie na zapis {source_file.name}...")
            
            if not wait_for_file_settled(source_file):
                console.print(f"[bold red]Plik {source_file.name} nie ustabilizował się na dysku. Pomijam.[/bold red]")
                tracker.report_error(f"Plik {source_file.name} nie ustabilizował się na dysku.")
                tracker.close()
                return

            STAGING_DIR.mkdir(parents=True, exist_ok=True)
            staged_media = STAGING_DIR / source_file.name
            if source_file.resolve() != staged_media.resolve():
                shutil.move(str(source_file), str(staged_media))
            else:
                staged_media = source_file

            send_notification("Przetwarzanie wykładu", f"Rozpoczęto buforowanie: {source_file.name}")
            progress.update(step1, completed=1, description=f"[cyan]Krok 1/5: Zbuforowano w .staging/ ({source_file.name}) [bold green]✓[/bold green]")
            tracker.finish_step(1, f"Zbuforowano w .staging/ ({source_file.name}) ✓")
            progress.update(overall_task, advance=1)

            # Krok 2: Ekstrakcja Audio & Transkrypcja Parakeet V3
            step2 = progress.add_task("[magenta]Krok 2/5: Transkrypcja mowy (NVIDIA Parakeet V3 MLX)...", total=100)
            tracker.start_step(2, "Transkrypcja mowy (NVIDIA Parakeet V3 MLX)", "Ekstrakcja ścieżki audio 16kHz mono (afconvert)...")
            mono_wav = STAGING_DIR / f"{staged_media.stem}_16k_mono.wav"
            transcript_md = STAGING_DIR / f"{staged_media.stem}_transcript.md"
            transcript_txt = STAGING_DIR / f"{staged_media.stem}_transcript_raw.txt"

            if not transcript_txt.exists():
                subprocess.run([
                    "/usr/bin/afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1",
                    str(staged_media), str(mono_wav)
                ], check=True)

                tracker.update_progress(2, 5.0, "Ładowanie modelu Parakeet V3 MLX na Apple Silicon...")
                progress.update(step2, completed=5, description="[magenta]Krok 2/5: Ładowanie modelu Parakeet V3 MLX...")

                def on_transcription_update(pct, done_m, tot_m):
                    desc = f"[magenta]Krok 2/5: Transkrypcja mowy ({done_m:.1f}/{tot_m:.1f} min, {int(pct)}%)"
                    progress.update(step2, completed=pct, description=desc)
                    tracker.update_progress(2, pct, f"Transkrypcja audio: {done_m:.1f}/{tot_m:.1f} min ({int(pct)}%) • Parakeet MLX")

                transcribe_audio(mono_wav, transcript_md, transcript_txt, progress_callback=on_transcription_update)
                if mono_wav.exists():
                    mono_wav.unlink()

            transcript_text = transcript_txt.read_text(encoding="utf-8") if transcript_txt.exists() else ""
            progress.update(step2, completed=100, description="[magenta]Krok 2/5: Transkrypcja audio ukończona [bold green]✓[/bold green]")
            tracker.finish_step(2, "Transkrypcja audio ukończona ✓")
            progress.update(overall_task, advance=1)

            # Krok 3: Semantyczna identyfikacja Gemini & Ekstrakcja slajdów WebP
            step3 = progress.add_task("[yellow]Krok 3/5: Identyfikacja Gemini & ekstrakcja slajdów...", total=100)
            tracker.start_step(3, "Identyfikacja Gemini & ekstrakcja slajdów", "Analiza semantyczna przedmiotu i tematu...")
            
            # 3a. Identyfikacja przedmiotu, tematu i numeru
            course_name, topic, lecture_idx = resolve_lecture_identity(
                transcript_text=transcript_text,
                file_hint=source_file.name,
                vault_dir=VAULT_DIR
            )

            tracker.update_progress(3, 15.0, f"Zidentyfikowano: {course_name} (W{lecture_idx}: {topic})")

            # 3b. Ekstrakcja slajdów
            staged_slides_dir = STAGING_DIR / f"{staged_media.stem}_slides"
            slides = []
            if staged_media.suffix.lower() in [".mov", ".mp4", ".m4v"]:
                def on_slides_update(pct, done_m, tot_m, count):
                    progress.update(step3, completed=pct, description=f"[yellow]Krok 3/5: Slajdy WebP ({count} wykrytych, {done_m:.1f}/{tot_m:.1f} min)")
                    tracker.update_progress(3, pct, f"Slajdy WebP: {count} wykrytych • {done_m:.1f}/{tot_m:.1f} min ({int(pct)}%)")
                
                slides = extract_slides(staged_media, staged_slides_dir, progress_callback=on_slides_update)
                progress.update(step3, completed=100, description=f"[yellow]Krok 3/5: Zidentyfikowano '{course_name}' (W{lecture_idx}: {topic}) [bold green]✓[/bold green]")
            else:
                progress.update(step3, completed=100, description=f"[yellow]Krok 3/5: Zidentyfikowano '{course_name}' (W{lecture_idx}: {topic}, audio) [bold green]✓[/bold green]")
            tracker.finish_step(3, f"Zidentyfikowano '{course_name}' (W{lecture_idx}: {topic}, slajdy: {len(slides)}) ✓")
            progress.update(overall_task, advance=1)

            # Krok 4: Synteza notatki Obsidian & Relokacja do płaskiej struktury
            step4 = progress.add_task("[blue]Krok 4/5: Synteza notatki Obsidian & organizacja plików...", total=None)
            tracker.start_step(4, "Synteza notatki Obsidian & organizacja plików", f"Generowanie notatki dla '{course_name}'...")
            
            course_dir = WATCH_DIR / course_name
            course_dir.mkdir(parents=True, exist_ok=True)
            vault_course_dir = VAULT_DIR / course_name
            vault_course_dir.mkdir(parents=True, exist_ok=True)

            # Synteza notatki
            note_content = generate_academic_note(course_name, lecture_idx, transcript_text, slides, topic_hint=topic)
            vault_note_path = vault_course_dir / f"Wykład {lecture_idx} - {topic}.md"
            vault_note_path.write_text(note_content, encoding="utf-8")
            
            # Kopia lokalna notatki w folderze przedmiotu
            local_note_path = course_dir / f"Wykład {lecture_idx} - {topic}.md"
            local_note_path.write_text(note_content, encoding="utf-8")

            # Przeniesienie transkrypcji
            final_transcript = course_dir / f"Wykład {lecture_idx} - Transkrypcja.md"
            if transcript_md.exists():
                shutil.move(str(transcript_md), str(final_transcript))
            if transcript_txt.exists():
                transcript_txt.unlink()

            # Przeniesienie slajdów do slajdy_W[N]
            if staged_slides_dir.exists():
                final_slides_dir = course_dir / f"slajdy_W{lecture_idx}"
                if final_slides_dir.exists():
                    shutil.rmtree(str(final_slides_dir))
                shutil.move(str(staged_slides_dir), str(final_slides_dir))

            # Przeniesienie pliku wideo/audio do płaskiego folderu przedmiotu
            final_media = course_dir / f"Wykład {lecture_idx} - {topic}{staged_media.suffix}"
            if staged_media.resolve() != final_media.resolve():
                shutil.move(str(staged_media), str(final_media))

            progress.update(step4, total=1, completed=1, description=f"[blue]Krok 4/5: Zapisano do Obsidiana i uporządkowano pliki [bold green]✓[/bold green]")
            tracker.finish_step(4, "Zapisano notatkę w Obsidianie i zorganizowano pliki ✓")
            progress.update(overall_task, advance=1)

            # Krok 5: Sprzętowa kompresja HEVC VideoToolbox
            step5 = progress.add_task("[green]Krok 5/5: Sprzętowa kompresja wideo HEVC VideoToolbox...", total=None)
            tracker.start_step(5, "Sprzętowa kompresja HEVC VideoToolbox", "Ocena rozmiaru wideo...")
            if final_media.suffix.lower() in [".mov", ".mp4", ".m4v"] and final_media.stat().st_size > 100 * 1024 * 1024:
                tracker.update_progress(5, 10.0, "Uruchamiam sprzętowy koder Apple VideoToolbox HEVC 1080p...")
                compressed_mp4 = course_dir / f"{final_media.stem}_compressed.mp4"
                target_mp4 = course_dir / f"Wykład {lecture_idx} - {topic}.mp4"
                
                res = subprocess.run([
                    "/usr/bin/avconvert", "-s", str(final_media), "-o", str(compressed_mp4),
                    "-p", "PresetHEVC1920x1080", "--replace"
                ], capture_output=True)

                if res.returncode == 0 and compressed_mp4.exists() and compressed_mp4.stat().st_size > 1000:
                    import cv2
                    cap = cv2.VideoCapture(str(compressed_mp4))
                    is_valid = cap.isOpened()
                    if is_valid:
                        ret, _ = cap.read()
                        is_valid = ret
                    cap.release()

                    if is_valid:
                        if final_media.suffix.lower() == ".mov":
                            final_media.unlink()
                        compressed_mp4.replace(target_mp4)
                        progress.update(step5, total=1, completed=1, description="[green]Krok 5/5: Kompresja HEVC ukończona (oryginał zwolniony) [bold green]✓[/bold green]")
                        tracker.finish_step(5, "Kompresja HEVC ukończona (oryginał zwolniony) ✓")
                    else:
                        compressed_mp4.unlink()
                        progress.update(step5, total=1, completed=1, description="[yellow]Krok 5/5: Kompresja niepoprawna, zachowano oryginał [dim]![/dim]")
                        tracker.finish_step(5, "Kompresja niepoprawna, zachowano oryginał")
                else:
                    progress.update(step5, total=1, completed=1, description="[yellow]Krok 5/5: Kompresja pominięta [dim]![/dim]")
                    tracker.finish_step(5, "Kompresja pominięta")
            else:
                progress.update(step5, total=1, completed=1, description="[green]Krok 5/5: Kompresja zbędna / plik audio [dim]✓[/dim]")
                tracker.finish_step(5, "Kompresja zbędna")
            progress.update(overall_task, advance=1)

        send_notification("Wykład gotowy!", f"{course_name}: Wykład {lecture_idx} - {topic} dodany do Obsidiana.")
        console.print(f"[bold green]✔ Zakończono sukcesem:[/bold green] [bold cyan]{course_name}[/bold cyan] Wykład {lecture_idx} ({topic}) -> [underline]{vault_note_path}[/underline]\n")
        
        tracker.complete_lecture(
            course=course_name,
            lecture=lecture_idx,
            topic=topic,
            note_path=str(vault_note_path),
            course_dir=str(course_dir)
        )
        tracker.close()
        return tracker

    except Exception as e:
        tracker.report_error(str(e))
        tracker.close()
        console.print(f"[bold red]Błąd podczas przetwarzania: {e}[/bold red]")
        return tracker

def scan_and_process():
    import fcntl
    lock_file_path = str(LOCK_FILE)
    try:
        lock_fd = os.open(lock_file_path, os.O_CREAT | os.O_RDWR)
    except OSError as e:
        console.print(f"[bold red]Błąd otwarcia pliku blokady: {e}[/bold red]")
        return
        
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, OSError):
        console.print("[dim yellow]Potok już działa w innej instancji (blokada flock aktywna). Kończenie.[/dim yellow]")
        os.close(lock_fd)
        return

    try:
        # Check if specific file path passed as argument
        if len(sys.argv) > 1:
            target_arg = Path(sys.argv[1])
            if target_arg.is_file() and target_arg.suffix.lower() in SUPPORTED_EXTS:
                tracker = process_file(target_arg)
                # Release flock lock before waiting so subsequent runs are never blocked
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)
                lock_fd = None
                if tracker:
                    tracker.wait_until_closed()
                return

        pending_files = [
            item for item in WATCH_DIR.iterdir()
            if item.is_file() and item.suffix.lower() in SUPPORTED_EXTS
            and not item.name.startswith(".") and "_compressed" not in item.stem
        ]
        
        if not pending_files:
            if sys.stdout.isatty():
                console.print(Panel.fit(
                    "[bold cyan]Lecture Pipeline[/bold cyan] [green]● Aktywny[/green]\n"
                    f"[dim]Katalog: {WATCH_DIR}\nBrak nowych nagrań do przetworzenia.[/dim]",
                    border_style="cyan"
                ))
            return

        console.print(Panel.fit(
            f"[bold cyan]Lecture Pipeline[/bold cyan] — Wykryto nowych nagrań: [bold green]{len(pending_files)}[/bold green]\n"
            "[dim]Silnik: Parakeet V3 MLX • Gemini Semantic ID & JSON • Apple VideoToolbox HEVC[/dim]",
            border_style="cyan"
        ))

        last_tracker = None
        for file in pending_files:
            last_tracker = process_file(file)

        # Release flock lock before waiting so future runs are not blocked
        if lock_fd is not None:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
            lock_fd = None

        # Keep process alive until user explicitly closes the HUD window
        if last_tracker:
            last_tracker.wait_until_closed()
            
    finally:
        if lock_fd is not None:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)

if __name__ == "__main__":
    scan_and_process()
