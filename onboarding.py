"""SurpriseSage — First-run onboarding wizard (CLI)."""

import json
import re
import uuid
from pathlib import Path

import config


def _slugify(text: str) -> str:
    """Turn a name into a safe user_id slug."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _ask(prompt: str, default: str = "") -> str:
    """Simple input with optional default."""
    suffix = f" [{default}]" if default else ""
    answer = input(f" {prompt}{suffix}: ").strip()
    return answer or default


def run_onboarding() -> None:
    """Interactive CLI wizard that creates a clean user_profile.json."""
    print()
    print("=" * 60)
    print(" 🎉 Welcome to SurpriseSage!")
    print("   Let's create your personal AI companion.")
    print("=" * 60)
    print()

    # Check if profile already exists
    if config.PROFILE_PATH.exists():
        overwrite = _ask("A profile already exists. Overwrite it? (y/n)", "n")
        if overwrite.lower() != "y":
            print("Keeping existing profile. You can run this again anytime.")
            return

    # ── Basic Info ───────────────────────────────────────────────────────
    name = _ask("What's your name?")
    while not name:
        name = _ask("I really need at least a name to get started!")

    display_name = _ask("What should I call you in surprises?", name)

    # ── Goals ────────────────────────────────────────────────────────────
    print("\n🎯 Let's talk about your goals.")
    print('Type one goal per line. Type "done" or leave empty when finished.\n')

    goals: list[str] = []
    while True:
        goal = input(f" Goal {len(goals) + 1}: ").strip()
        if goal.lower() in {"done", ""} and goals:
            break
        if goal:
            goals.append(goal)

    if not goals:
        goals = ["Become the best version of myself"]

    # ── Personal Details ─────────────────────────────────────────────────
    print("\n📍 A bit more about you...")
    job = _ask("What do you do for work?", "Software Engineer")
    location = _ask("Where are you based?")
    family = _ask("Family / important people?")
    hobbies = _ask("Hobbies (comma-separated)?", "building software, reading, walking")

    # ── Favorite Themes ──────────────────────────────────────────────────
    print("\n❤️ Which themes would you like surprises about?")
    themes = config.THEMES
    for i, theme in enumerate(themes, 1):
        print(f" {i}. {theme.replace('_', ' ').title()}")

    print(f" {len(themes) + 1}. All of the above")
    choices = _ask("Enter numbers separated by commas", str(len(themes) + 1))

    try:
        nums = [int(x.strip()) for x in choices.split(",")]
        if len(themes) + 1 in nums:
            favorite_themes = themes[:]
        else:
            favorite_themes = [themes[n - 1] for n in nums if 1 <= n <= len(themes)]
    except Exception:
        favorite_themes = themes[:]

    # ── LLM Provider ──────────────────────────────────────────────────────
    print("\n🤖 Which AI model should power your surprises?")
    providers = [
        ("ollama", "Ollama (local, free — requires Ollama installed)"),
        ("grok", "Grok (x.ai — needs API key)"),
        ("claude", "Claude (Anthropic — needs API key)"),
        ("chatgpt", "ChatGPT (OpenAI — needs API key)"),
        ("gemini", "Gemini (Google — needs API key)"),
    ]
    for i, (_, desc) in enumerate(providers, 1):
        print(f" {i}. {desc}")

    llm_choice = _ask("Enter number", "1")
    try:
        llm_idx = int(llm_choice.strip()) - 1
        llm_provider_name = providers[llm_idx][0]
    except (ValueError, IndexError):
        llm_provider_name = "ollama"

    llm_config = {"provider": llm_provider_name}

    if llm_provider_name != "ollama":
        from llm_provider import _DEFAULT_MODELS, _PROVIDER_ENV_KEY
        default_model = _DEFAULT_MODELS.get(llm_provider_name, "")
        model = _ask(f"Model name?", default_model)
        llm_config["model"] = model

        env_var = _PROVIDER_ENV_KEY.get(llm_provider_name, "")
        print(f"\n   You'll need to set your API key.")
        print(f"   Option A: Add to .env file →  {env_var}=your-key-here")
        print(f"   Option B: Add to user_profile.json →  \"llm\": {{\"api_key\": \"...\"}}")
        api_key = _ask("Paste API key now (or press Enter to set later)", "")
        if api_key:
            llm_config["api_key"] = api_key

    # ── Schedule ─────────────────────────────────────────────────────────
    print("\n⏰ Schedule settings")
    dnd_start = _ask("Do-Not-Disturb start time (HH:MM)?", "00:00")
    dnd_end = _ask("Do-Not-Disturb end time (HH:MM)?", "07:00")

    fixed_raw = _ask(
        "Fixed surprise times (comma-separated HH:MM)?",
        ", ".join(config.DEFAULT_FIXED_TIMES),
    )
    fixed_times = [t.strip() for t in fixed_raw.split(",") if t.strip()]

    # ── Build final profile ──────────────────────────────────────────────
    user_id = f"{_slugify(name)}-{uuid.uuid4().hex[:6]}"

    profile = {
        "user_id": user_id,
        "name": name,
        "display_name": display_name,

        "goals": goals,

        "personal_details": {
            "job": job,
            "location": location,
            "family": family,
            "hobbies": hobbies,
        },

        "preferences": {
            "favorite_themes": favorite_themes,
            "sports_teams": [],
            "stocks": [],
            "news_topics": [],
        },

        "tone": "warm, slightly cheeky wise companion who feels like a fun older brother",

        "schedule": {
            "dnd": {"start": dnd_start, "end": dnd_end},
            "frequency": "medium",
            "fixed_times": fixed_times,
        },

        "memory_settings": {
            "max_memories_per_query": 5,
            "default_retention_days": 90,
            "auto_cleanup_enabled": True,
            "run_every_days": 30,
        },

        "llm": llm_config,
    }

    # ── Save ─────────────────────────────────────────────────────────────
    with open(config.PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)

    print()
    print("✅ Profile created successfully!")
    print(f"   Saved to: {config.PROFILE_PATH}")
    print(f"   Your user ID: {user_id}")
    print()
    print("You can now edit user_profile.json anytime to update goals, hobbies, etc.")
    print("Next step:")
    print("   python surprisesage.py")
    print()


if __name__ == "__main__":
    run_onboarding()