# Contributing to SurpriseSage

Thanks for wanting to make SurpriseSage better! Here's how to get started.

## Setup

1. Clone the repo and create a virtual environment:
   ```bash
   git clone https://github.com/your-username/SurpriseSage.git
   cd SurpriseSage
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Copy the environment file and add your keys:
   ```bash
   cp .env.example .env
   ```

3. Run onboarding:
   ```bash
   python3 onboarding.py
   ```

4. Start the app:
   ```bash
   python3 surprisesage.py
   ```

## How to Contribute

### Reporting Bugs
- Open an issue with a clear title
- Include your macOS version, Python version, and LLM provider
- Paste any relevant log output from `~/.surprisesage/surprisesage.log`

### Suggesting Features
- Open an issue tagged `enhancement`
- Describe the feature and why it matters

### Submitting Code
1. Fork the repo
2. Create a feature branch: `git checkout -b my-feature`
3. Make your changes
4. Test locally by running `python3 surprisesage.py`
5. Commit with a clear message
6. Open a pull request

## Code Style

- Keep it simple. Short functions, clear names.
- No over-engineering. If three lines work, don't write a class.
- Follow existing patterns in the codebase.
- Add docstrings to new functions.

## Project Structure

| File | Purpose |
|------|---------|
| `surprisesage.py` | Main entry point |
| `config.py` | Constants and settings |
| `prompt_builder.py` | Prompt assembly and LLM generation |
| `llm_provider.py` | Multi-provider LLM abstraction |
| `memory.py` | ChromaDB vector memory |
| `scheduler.py` | Timing and triggers |
| `context_detector.py` | macOS active app detection |
| `tray.py` | Menu bar UI |
| `_popup_window.py` | Popup window (CustomTkinter) |
| `ui_popup.py` | Popup subprocess launcher |
| `onboarding.py` | First-run setup wizard |

## Good First Issues

Look for issues tagged `good first issue` — these are great starting points.

## Questions?

Open an issue or start a discussion. We're friendly.
