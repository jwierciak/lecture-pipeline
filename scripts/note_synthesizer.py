import os
import json
import re
from pathlib import Path
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional

# Load key from .env if present
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
if ENV_FILE.exists():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip().strip('"').strip("'")

import time

# Candidate models in order of capability and stability
MODELS_TO_TRY = ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.1-flash-lite"]


# Pydantic schema for Structured Outputs
class Frontmatter(BaseModel):
    topic: str = Field(description="Precyzyjny temat wykładu")
    date: str = Field(description="Data wykładu w formacie YYYY-MM-DD")
    course: str = Field(description="Dokładna nazwa przedmiotu")
    tags: List[str] = Field(default_factory=lambda: ["#studia"], description="Tagi w formacie Obsidian")

class ConceptItem(BaseModel):
    concept: str = Field(description="Nazwa pojęcia (z wikilinkiem [[...]])")
    definition: str = Field(description="Zwięzła, ścisła definicja")

class ExampleItem(BaseModel):
    case_title: str = Field(description="Nazwa lub tytuł przykładu/studium przypadku")
    description: str = Field(description="Opis wyliczenia lub sytuacji omówionej przez wykładowcę")

class LectureNoteSchema(BaseModel):
    frontmatter: Frontmatter
    title: str = Field(description="Tytuł H1 notatki")
    key_concepts: List[ConceptItem] = Field(description="Lista kluczowych pojęć")
    important_details: List[str] = Field(description="Szczegóły prawne, bilansowe, wzory i wyjątki")
    examples: List[ExampleItem] = Field(description="Przykłady i studia przypadków")
    summary: str = Field(description="Zwięzłe podsumowanie wykładu")
    related_topics: List[str] = Field(description="Powiązane zagadnienia wikilinkami [[...]]")

def json_to_markdown(data: dict) -> str:
    """Converts the structured JSON output into clean, Obsidian-ready Markdown."""
    fm = data.get("frontmatter", {})
    raw_tags = fm.get("tags", ["#studia"])
    
    clean_tags = []
    if isinstance(raw_tags, list):
        for t in raw_tags:
            if isinstance(t, str):
                t_clean = re.sub(r"['\"\[\]\{\}]", "", t).strip()
                for sub in t_clean.split(","):
                    sub = sub.strip()
                    if sub:
                        clean_tags.append(sub if sub.startswith("#") else f"#{sub}")
    elif isinstance(raw_tags, str):
        for sub in re.sub(r"['\"\[\]\{\}]", "", raw_tags).split():
            if sub:
                clean_tags.append(sub if sub.startswith("#") else f"#{sub}")
    if not clean_tags:
        clean_tags = ["#studia"]

    tags_str = " ".join(dict.fromkeys(clean_tags))
    
    topic = str(fm.get('topic', '')).replace('"', '\\"')
    course = str(fm.get('course', '')).replace('"', '\\"')
    
    md_lines = [
        "---",
        f"topic: \"{topic}\"",
        f"date: \"{fm.get('date', '')}\"",
        f"course: \"{course}\"",
        f"tags: {tags_str}",
        "---",
        "",
        f"# {data.get('title', 'Notatka z wykładu')}",
        "",
        "## Key Concepts"
    ]
    
    for c in data.get("key_concepts", []):
        if isinstance(c, dict):
            c_name = str(c.get("concept", "")).strip()
            c_def = str(c.get("definition", "")).strip()
            # Ensure wikilink format
            if c_name and not c_name.startswith("[["):
                c_name = f"[[{c_name.strip('[]')}]]"
            md_lines.append(f"- **{c_name}**: {c_def}")
    
    md_lines.extend(["", "## Important Details"])
    for d in data.get("important_details", []):
        md_lines.append(f"- {str(d).strip()}")
        
    md_lines.extend(["", "## Examples"])
    for ex in data.get("examples", []):
        if isinstance(ex, dict):
            md_lines.append(f"- **{ex.get('case_title', '')}**: {ex.get('description', '')}")
        
    md_lines.extend([
        "",
        "## Summary",
        str(data.get("summary", "")).strip(),
        "",
        "## Related Topics"
    ])
    for rt in data.get("related_topics", []):
        if isinstance(rt, str):
            clean_rt = rt.strip().strip("[]'\"")
            if clean_rt:
                md_lines.append(f"- [[{clean_rt}]]")
        
    return "\n".join(md_lines) + "\n"

def generate_academic_note(course_name: str, lecture_idx: int, transcript_text: str, slides: list = None, topic_hint: str = "") -> str:
    """
    Synthesize a concise, high-yield academic note using Structured JSON Output (via Gemini API)
    and formats it into clean Obsidian Markdown.
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    api_key = os.environ.get("GEMINI_API_KEY")

    if api_key:
        from google import genai
        client = genai.Client(api_key=api_key)
        
        topic_line = f"Temat wykładu: {topic_hint}\n" if topic_hint else ""
        prompt = f"""Jesteś wyspecjalizowanym asystentem akademickim tworzącym zwięzłe notatki ze studiów.
Przeanalizuj transkrypcję wykładu i zwróć ustrukturyzowany obiekt JSON zgodnie ze schematem.

Dane wejściowe:
Przedmiot: {course_name}
Numer wykładu: {lecture_idx}
{topic_line}Data: {today_str}

Transkrypcja wykładu:
{transcript_text[:45000]}

Zasady:
- Kluczowe pojęcia i powiązane zagadnienia formatuj jako wikilinki Obsidiana, np. [[Aktywa]], [[Zysk]].
- Nie dodawaj grafik ani slajdów.
- Skup się na ścisłych definicjach, wzorach, artykułach prawnych i konkretnych liczbach z przykładów.
"""
        schema_file = Path(__file__).resolve().parent.parent / "schemas" / "note_schema.json"
        if schema_file.exists():
            try:
                raw_schema = json.loads(schema_file.read_text(encoding="utf-8"))
                schema_config = {k: v for k, v in raw_schema.items() if k not in ["$schema"]}
            except Exception as e:
                print(f"Warning: Failed to load schema from {schema_file}: {e}, falling back to Pydantic", flush=True)
                schema_config = LectureNoteSchema
        else:
            schema_config = LectureNoteSchema

        for model_name in MODELS_TO_TRY:
            try:
                print(f"Calling Gemini ({model_name}) with Structured JSON output (schema: schemas/note_schema.json)...", flush=True)
                resp = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": LectureNoteSchema,
                    }
                )
                if resp.text:
                    parsed_json = json.loads(resp.text)
                    print(f"Structured JSON output successfully generated by {model_name}!", flush=True)
                    return json_to_markdown(parsed_json)
            except Exception as e:
                print(f"Model {model_name} failed: {e}. Trying next...", flush=True)
                time.sleep(1.5)

    # Fallback to local deterministic structure
    print("Using local fallback...", flush=True)
    fallback_topic = topic_hint if topic_hint else f"{course_name} – Wykład {lecture_idx}"
    fallback_title = f"Wykład {lecture_idx}: {topic_hint}" if topic_hint else f"Wykład {lecture_idx}: {course_name}"
    fallback_data = {
        "frontmatter": {
            "topic": fallback_topic,
            "date": today_str,
            "course": course_name,
            "tags": ["#studia"]
        },
        "title": fallback_title,
        "key_concepts": [
            {"concept": f"[[{course_name}]]", "definition": "Wykład zarejestrowany i przetworzony automatycznie."}
        ],
        "important_details": ["Pełny zapis rozmowy i wypowiedzi znajduje się w załączonym pliku transcript.md."],
        "examples": [],
        "summary": "Notatka wygenerowana z transkrypcji ASR Parakeet V3.",
        "related_topics": [f"[[{course_name}]]"]
    }
    return json_to_markdown(fallback_data)
