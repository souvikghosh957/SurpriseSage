# SurpriseSage

**Your Mac's gentle tap on the shoulder — with wisdom, warmth, and a wink.**

SurpriseSage is a local-first, personal AI companion that lives in your Mac's menu bar. It delivers context-aware micro-surprises throughout your day — philosophy, Indian mythology, tech history, Stoic wisdom, sports grit, and more — tailored to your goals, your mood, and what you're doing right now.

It feels like a wise, slightly cheeky older brother who knows you deeply and gently nudges you with exactly what you need.

## What It Does

- Pops up short, personalized surprises tied to **your real goals and context**
- Detects what app you're using and adapts (coding? browsing? relaxing?)
- Shifts personality by time of day (energetic mornings, calm late nights, reflective evenings)
- Remembers past surprises and never repeats itself (ChromaDB RAG)
- Learns from your feedback (thumbs up/down)
- Runs **100% locally** — your data never leaves your machine

## Screenshots

> *Coming soon — the popup is a dark-themed card with gold accents, fade-in animation, progress bar, and click-to-hold.*

## Features

| Feature | Status |
|---|---|
| Local LLM via Ollama (qwen3.5:27b) | Done |
| ChromaDB memory with RAG | Done |
| macOS context detection (active app, window title, fullscreen) | Done |
| Dynamic prompt builder (time-aware, context-smart themes) | Done |
| CustomTkinter popup with fade-in/out, progress bar, click-to-hold | Done |
| System tray with theme picker, pause-with-timer, stats | Done |
| Feedback loop (thumbs up/down saves to memory) | Done |
| Scheduled surprises (fixed + Poisson random) | Done |
| DND hours, fullscreen skip | Done |
| Cloud fallback via LiteLLM | Ready (toggle in profile) |
| Knowledge fetcher (stocks, sports, news) | Planned |
| Chat mode | Planned |
| Cross-platform (Windows/Linux) | Future |

## Quick Start

### Prerequisites

- **macOS** (Apple Silicon recommended)
- **Python 3.11+**
- **Ollama** installed ([ollama.com](https://ollama.com))
- **16+ GB RAM** (the 27b model uses ~22 GB; swap to a smaller model if needed)

### Setup

```bash
# 1. Clone
git clone https://github.com/souvikghosh957/SurpriseSage.git
cd SurpriseSage

# 2. Pull models
ollama pull nomic-embed-text
ollama create surprisesage -f Modelfile

# 3. Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4. Create your profile
python onboarding.py

# 5. Run
python surprisesage.py
```

The owl icon appears in your menu bar. Click it and hit **"Next Surprise Now"** to try it out.

### Accessibility Permission

On first run, macOS will ask for Accessibility permission (needed to read window titles). Grant it in **System Settings > Privacy & Security > Accessibility**.

## How It Works

```
Scheduler (fixed + random triggers)
    |
    v
Context Detector --> what app are you using?
    |
    v
Memory (ChromaDB) --> what did we talk about before?
    |
    v
Prompt Builder --> assembles: goals + context + memories + theme + time-of-day vibe
    |
    v
AI Brain (Ollama qwen3.5:27b, think=False) --> generates surprise
    |
    v
Popup (CustomTkinter, separate process) --> shows it, collects feedback
    |
    v
Memory --> saves surprise + feedback for next time
```

## Customization

Edit `user_profile.json` (created by onboarding) to change:

- **Goals** — what you're working toward
- **Personal details** — job, hobbies, family (used to make surprises personal)
- **Favorite themes** — philosophy, indian_mythology, tech_innovation, stoic_wisdom, science_breakthroughs, entrepreneurship, sports_grit
- **Tone** — how the companion talks to you
- **Schedule** — DND hours, fixed surprise times, frequency
- **Memory settings** — retention days, cleanup rules

Changes take effect immediately via **Reload Profile** in the menu bar.

A sample is provided in `sample_user_profile.json`.

## Menu Bar Options

| Menu Item | What It Does |
|---|---|
| Next Surprise Now | Trigger a surprise immediately |
| Surprise Me About... | Pick a specific theme (philosophy, sports, etc.) |
| Recent Surprises | View and re-show past surprises |
| Pause Surprises | Toggle pause, or pause for 30m / 1hr / 3hr with auto-resume |
| Stats | See surprise count, feedback breakdown, memory stats |
| Reload Profile | Hot-reload user_profile.json without restarting |
| Quit | Stop the app |

## Project Structure

```
surprisesage/
├── surprisesage.py          # main entry point
├── tray.py                  # macOS system tray (rumps)
├── scheduler.py             # APScheduler triggers
├── prompt_builder.py        # dynamic prompt assembly + AI generation
├── memory.py                # ChromaDB RAG layer
├── context_detector.py      # active app/window detection
├── ui_popup.py              # popup launcher (subprocess bridge)
├── _popup_window.py         # CustomTkinter popup window
├── config.py                # constants, paths, defaults
├── onboarding.py            # first-run CLI wizard
├── Modelfile                # Ollama custom model definition
├── sample_user_profile.json # template for your profile
├── requirements.txt
└── SURPRISESAGE_DESIGN_SPEC.md
```

## Privacy

- **100% local by default** — no data leaves your machine
- Memory stored in `~/.surprisesage/` with `chmod 700` permissions
- No telemetry, no analytics, no cloud calls unless you opt in
- `user_profile.json` is gitignored — your personal data stays local

## Using a Smaller Model

If you have less than 24 GB RAM, edit the `Modelfile`:

```
FROM qwen3:8b
```

Then rebuild: `ollama create surprisesage -f Modelfile`

## License

MIT
