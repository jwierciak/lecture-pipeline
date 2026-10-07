# Contributing to Lecture Pipeline

Thank you for your interest in contributing to **Lecture Pipeline**! This project aims to provide the fastest, cleanest, and most reliable local lecture ingestion pipeline for macOS on Apple Silicon.

---

## 🛠️ Development Setup

1. **Fork and clone** the repository:
   ```bash
   git clone https://github.com/<your-username>/lecture-pipeline.git
   cd lecture-pipeline
   ```

2. **Create a virtual environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Setup environment**:
   ```bash
   cp .env.example .env
   # Add your GEMINI_API_KEY for end-to-end testing
   ```

---

## 🧪 Testing

Before submitting a Pull Request, verify that all unit and integration tests pass:

```bash
pytest -v
```

To test the GUI HUD interaction and layout:
```bash
python scripts/progress_window.py --test
```

---

## 📐 Guidelines & Coding Standards

1. **Zero Hardcoded Paths**:
   - Never hardcode user home directories (`/Users/...`) in Python code or configs.
   - Always resolve paths via `scripts/config.py` using `Path.home()` or environment variables.

2. **Hardware Constraints**:
   - Audio transcription relies on `mlx` and `parakeet-mlx` optimized for Apple Silicon (macOS Darwin with unified memory).
   - Video encoding relies on macOS `avconvert` / Apple VideoToolbox. Keep OS-specific features guarded or modularized.

3. **No Secret Leaks**:
   - Ensure `.env`, local `.plist` files, temporary `.staging/` files, and `.wav` audio buffers are excluded via `.gitignore`.

4. **Code Quality**:
   - Follow PEP 8 style guidelines.
   - Include type annotations where appropriate (`pathlib.Path`, `typing.Optional`, etc.).
   - Add unit tests under `tests/` for any new functionality.

---

## 📬 Pull Request Process

1. Create a feature branch (`git checkout -b feature/amazing-feature`).
2. Commit your changes (`git commit -m "feat: Add amazing feature"`).
3. Push to the branch (`git push origin feature/amazing-feature`).
4. Open a Pull Request on GitHub describing your changes and testing performed.

