import os
import sys
import json
import re
import time
from pathlib import Path
from typing import Optional, Tuple
from pydantic import BaseModel, Field

# Add scripts directory to sys.path
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from config import VAULT_DIR, load_known_courses

def get_known_courses(vault_dir: Path = VAULT_DIR) -> list[str]:
    courses = set(load_known_courses())
    if vault_dir.is_dir():
        for p in vault_dir.iterdir():
            if p.is_dir() and not p.name.startswith(".") and p.name.lower() != "templates":
                courses.add(p.name)
    return sorted(list(courses))

class LectureIdentity(BaseModel):
    course: str = Field(description="Dokładna nazwa przedmiotu ściśle wybrana z podanej listy dozwolonych przedmiotów")
    topic: str = Field(description="Krótki, precyzyjny temat wykładu (2-6 słów, bez znaków zakazanych w nazwach plików jak / : * ? \" < > |)")
    explicit_lecture_number: Optional[int] = Field(None, description="Numer wykładu w semestrze (np. 1, 2, 3), TYLKO jeśli wykładowca wprost i bez wątpliwości wypowiedział go w nagraniu. W przeciwnym razie null.")

def clean_topic_name(topic: str) -> str:
    """Sanitizes topic string for filesystem and Obsidian note titles."""
    if not topic:
        return "Temat ogólny"
    cleaned = re.sub(r'[\\/*?:"<>|]', '', topic).strip()
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned if cleaned else "Temat ogólny"

def get_next_lecture_index(course_name: str, vault_dir: Path = VAULT_DIR) -> int:
    """Calculates next lecture index based on existing notes in Obsidian Vault for that course."""
    course_path = vault_dir / course_name
    if not course_path.is_dir():
        return 1
    max_idx = 0
    for note in course_path.glob("Wykład *.md"):
        m = re.match(r"^Wykład\s+(\d+)", note.name, re.IGNORECASE)
        if m:
            max_idx = max(max_idx, int(m.group(1)))
    return max_idx + 1 if max_idx > 0 else 1

def resolve_lecture_identity(
    transcript_text: str = "",
    file_hint: str = "",
    vault_dir: Path = VAULT_DIR
) -> Tuple[str, str, int]:
    """
    Identifies course, topic, and lecture index using Gemini API with strict course constraint,
    hybrid lecture numbering (spoken number or N = existing_notes + 1).
    """
    known_courses = get_known_courses(vault_dir)
    api_key = os.environ.get("GEMINI_API_KEY")
    
    if api_key and (transcript_text or file_hint):
        from google import genai
        client = genai.Client(api_key=api_key)
        
        courses_str = "\n".join(f"- {c}" for c in known_courses)
        sample = transcript_text[:25000] if transcript_text else ""
        
        prompt = f"""Jesteś inteligentnym modułem identyfikacji wykładów akademickich dla studenta.
Twoim zadaniem jest przypisanie nagrania do DOKŁADNIE JEDNEGO ze znanych przedmiotów oraz sformułowanie zwięzłego tematu wykładu.

DOZWOLONE PRZEDMIOTY (musisz wybrać ściśle jedną z poniższych nazw):
{courses_str}

Wskazówka z nazwy pliku / ścieżki: {file_hint}

Fragment transkrypcji wykładu:
{sample}

Wymagania:
1. `course`: Wybierz dokładnie jeden przedmiot z powyższej listy dozwolonych przedmiotów, który odpowiada dziedzinie wykładu.
2. `topic`: Stwórz zwięzły, konkretny temat wykładu w języku polskim (2-6 słów, np. "Wprowadzenie i podstawowe pojęcia", "Nakłady, aktywa i pojęcie zysku", "Audyt norm ISO i ryzyko"). Nie używaj znaków zakazanych w nazwach plików (/ \\ : * ? " < > |).
3. `explicit_lecture_number`: Jeśli wykładowca wprost i bez wątpliwości powiedział na początku lub w toku wykładu, który to jest numer wykładu (np. "witam na pierwszym wykładzie", "dzisiaj nasz trzeci wykład"), podaj liczbę całkowitą. Jeśli numer nie padł lub nie masz pewności, podaj null.
"""
        models_to_try = ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.1-flash-lite"]
        for model in models_to_try:
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": LectureIdentity,
                    }
                )
                if resp.text:
                    data = json.loads(resp.text)
                    raw_course = data.get("course", "").strip()
                    raw_topic = clean_topic_name(data.get("topic", ""))
                    explicit_idx = data.get("explicit_lecture_number")
                    
                    # Strict validation of course against known courses
                    matched_course = None
                    for c in known_courses:
                        if c.lower() == raw_course.lower():
                            matched_course = c
                            break
                    if not matched_course:
                        for c in known_courses:
                            if c.lower() in raw_course.lower() or raw_course.lower() in c.lower():
                                matched_course = c
                                break
                    if not matched_course:
                        matched_course = known_courses[0] if known_courses else raw_course
                        
                    if explicit_idx and isinstance(explicit_idx, int) and explicit_idx > 0:
                        lecture_idx = explicit_idx
                    else:
                        lecture_idx = get_next_lecture_index(matched_course, vault_dir)
                        
                    return matched_course, raw_topic, lecture_idx
            except Exception:
                time.sleep(1)

    # Local fallback
    matched_course = known_courses[0] if known_courses else "Wykłady"
    for c in known_courses:
        if c.lower() in file_hint.lower():
            matched_course = c
            break
            
    topic = "Temat ogólny"
    lecture_idx = get_next_lecture_index(matched_course, vault_dir)
    return matched_course, topic, lecture_idx

def detect_course_and_index(file_path: Path, transcript_text: str = "") -> Tuple[str, int]:
    """Backward compatibility wrapper."""
    course, _, idx = resolve_lecture_identity(transcript_text, file_hint=str(file_path))
    return course, idx
