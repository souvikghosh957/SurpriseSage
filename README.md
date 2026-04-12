# SurpriseSage

**Your Mac's gentle tap on the shoulder — with wisdom, warmth, and a wink.**

SurpriseSage is a non-intrusive, personal AI life companion that lives quietly in your Mac's menu bar. It delivers delightful, context-aware micro-surprises — goal nudges, philosophical wisdom, Indian mythology parallels, tech history, and Stoic insights — exactly when you need them.

## Highlights

- 100% local-first (runs on Ollama + qwen3.5, zero servers by default)
- Personal memory that grows with you (ChromaDB RAG)
- Context-aware (knows what app you're using)
- Non-intrusive popups with auto-dismiss
- Hybrid-ready (optional cloud fallback via LiteLLM)

## Status

Early development — see [SURPRISESAGE_DESIGN_SPEC.md](SURPRISESAGE_DESIGN_SPEC.md) for full architecture and roadmap.

## Quick Start

```bash
# Prerequisites: Ollama installed, Python 3.11+
ollama pull nomic-embed-text
ollama create surprisesage -f Modelfile

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python onboarding.py   # first-run setup
python surprisesage.py # start the app
```

## License

TBD