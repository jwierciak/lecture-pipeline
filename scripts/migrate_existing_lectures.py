#!/usr/bin/env python3
"""
Migration script: Flat Disk Storage Layout for Lecture Pipeline.
Moves existing nested lecture folders:
  Wykłady/[Course]/Wykład [N]/
to the standardized flat layout:
  Wykłady/[Course]/Wykład [N] - [Topic].mp4
  Wykłady/[Course]/Wykład [N] - Transkrypcja.md
  Wykłady/[Course]/slajdy_W[N]/
  Wykłady/[Course]/Wykład [N] - [Topic].md
"""

import sys
import shutil
from pathlib import Path

# Add scripts directory to sys.path
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from config import WATCH_DIR

MIGRATIONS = [
    {
        "course": "Doradztwo podatkowe",
        "nested_folder": "Wykład 1",
        "lecture_idx": 1,
        "topic": "Wprowadzenie i podstawowe pojęcia",
        "video_src_name": "Doradztwo podatkowe 1.mp4",
        "note_src_name": "Wykład 1 - Wprowadzenie i podstawowe pojęcia.md"
    },
    {
        "course": "Rachunkowość Zarządcza",
        "nested_folder": "Wykład 1",
        "lecture_idx": 1,
        "topic": "Nakłady, aktywa i pojęcie zysku",
        "video_src_name": "Screen Recording 2026-10-07 at 15.01.55.mp4",
        "note_src_name": "Wykład 1 - Nakłady, aktywa i pojęcie zysku.md"
    }
]

def migrate_all():
    print("=== Rozpoczynanie migracji do płaskiej struktury ===")
    
    for item in MIGRATIONS:
        course_name = item["course"]
        course_dir = WATCH_DIR / course_name
        src_dir = course_dir / item["nested_folder"]
        idx = item["lecture_idx"]
        topic = item["topic"]
        
        if not src_dir.exists():
            print(f"[{course_name}] Folder {src_dir} nie istnieje lub został już zmigrowany.")
            continue
            
        print(f"\nMigracja: {course_name} / {item['nested_folder']} -> Wykład {idx} - {topic}")
        
        # 1. Wideo
        src_video = src_dir / item["video_src_name"]
        dest_video = course_dir / f"Wykład {idx} - {topic}.mp4"
        if src_video.exists():
            print(f"  -> Przenoszenie wideo: {src_video.name} -> {dest_video.name}")
            shutil.move(str(src_video), str(dest_video))
        elif not dest_video.exists():
            # Sprawdź czy jest jakikolwiek inny plik wideo
            videos = [f for f in src_dir.iterdir() if f.suffix.lower() in [".mp4", ".mov", ".m4v"]]
            if videos:
                print(f"  -> Przenoszenie wideo (znaleziony): {videos[0].name} -> {dest_video.name}")
                shutil.move(str(videos[0]), str(dest_video))
                
        # 2. Transkrypcja
        src_trans = src_dir / "transcript.md"
        dest_trans = course_dir / f"Wykład {idx} - Transkrypcja.md"
        if src_trans.exists():
            print(f"  -> Przenoszenie transkrypcji -> {dest_trans.name}")
            shutil.move(str(src_trans), str(dest_trans))
            
        # 3. Slajdy
        src_slides = src_dir / "slides"
        dest_slides = course_dir / f"slajdy_W{idx}"
        if src_slides.exists():
            print(f"  -> Przenoszenie slajdów: slides -> {dest_slides.name}")
            if dest_slides.exists():
                shutil.rmtree(str(dest_slides))
            shutil.move(str(src_slides), str(dest_slides))
            
        # 4. Notatka lokalna
        dest_note = course_dir / f"Wykład {idx} - {topic}.md"
        src_notes = list(src_dir.glob("Wykład *.md"))
        if src_notes:
            print(f"  -> Kopia notatki lokalnej -> {dest_note.name}")
            shutil.copy2(str(src_notes[0]), str(dest_note))
            
        # 5. Usunięcie plików tymczasowych i pustego katalogu
        for temp_name in ["audio.m4a", "transcript_raw.txt", ".DS_Store"]:
            p = src_dir / temp_name
            if p.exists():
                p.unlink()
                
        remaining = list(src_dir.iterdir())
        if not remaining or all(f.name == ".DS_Store" for f in remaining):
            shutil.rmtree(str(src_dir), ignore_errors=True)
            print(f"  -> Usunięto pusty folder źródłowy: {src_dir.name}")
        else:
            print(f"  [Uwaga] W folderze {src_dir.name} pozostały pliki: {[f.name for f in remaining]}")

    print("\n=== Migracja zakończona sukcesem! ===")

if __name__ == "__main__":
    migrate_all()
