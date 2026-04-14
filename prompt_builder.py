"""SurpriseSage — dynamic prompt assembly and AI surprise generation."""

import logging
import random
import re
import uuid
from datetime import datetime

import ollama

import config

logger = logging.getLogger("surprisesage.prompt")

# ── Theme-specific flavor text for richer prompts ─────────────────────────
_THEME_HINTS: dict[str, str] = {
    "philosophy": (
        "Draw from thinkers like Seneca, Epicurus, Lao Tzu, Rumi, Confucius, "
        "Nietzsche, Camus, or Simone de Beauvoir. Use a real quote or a striking philosophical idea."
    ),
    "indian_mythology": (
        "Draw from the Mahabharata, Ramayana, Bhagavad Gita, Upanishads, or stories of "
        "Shiva, Krishna, Arjuna, Karna, Draupadi, Hanuman, or Chanakya. Use a real story or teaching."
    ),
    "tech_innovation": (
        "Draw from the real stories of Steve Jobs, Elon Musk, Ada Lovelace, Alan Turing, "
        "Nikola Tesla, the Wright Brothers, Grace Hopper, Linus Torvalds, or other tech pioneers. "
        "Use a real anecdote or lesser-known fact."
    ),
    "stoic_wisdom": (
        "Draw from Marcus Aurelius (Meditations), Epictetus (Discourses), Seneca (Letters), "
        "or Zeno of Citium. Use a real Stoic quote or principle."
    ),
    "science_breakthroughs": (
        "Draw from real breakthroughs — Feynman, Curie, Darwin, Hawking, Ramanujan, "
        "Einstein, Rosalind Franklin, or Srinivasa Ramanujan. Use a real fact or discovery story."
    ),
    "entrepreneurship": (
        "Draw from founders like Dhirubhai Ambani, Narayana Murthy, Sara Blakely, "
        "Jeff Bezos (garage days), or Jack Ma (rejected 30 times). Use a real founder story."
    ),
}

# ── Time-of-day awareness ─────────────────────────────────────────────────
def _get_time_context() -> str:
    """Return a time-of-day hint for the prompt."""
    hour = datetime.now().hour
    if hour < 6:
        return "It's late night / very early morning — the user is up late."
    elif hour < 10:
        return "It's morning — a fresh start to the day."
    elif hour < 13:
        return "It's late morning — the user is likely deep in work."
    elif hour < 15:
        return "It's early afternoon — post-lunch energy dip."
    elif hour < 18:
        return "It's afternoon — the productive stretch of the day."
    elif hour < 21:
        return "It's evening — winding down or doing personal work."
    else:
        return "It's night — the user might be reflecting or working late."


def _build_system_prompt(profile: dict) -> str:
    """Build the system prompt dynamically using profile data. No hardcoding."""
    display_name = profile.get("display_name", profile.get("name", "Friend"))
    tone = profile.get("tone", "warm, slightly cheeky wise companion who feels like a fun older brother")

    return f"""You are SurpriseSage — a {tone}.

You are talking to {display_name}. You know them well and care about their journey.

Rules you MUST follow:
- Start your response with: "Hey {display_name},"
- Structure: ONE powerful quote/anecdote/fact + ONE warm sentence connecting it to the user's life
- Total response: under 60 words
- Tone: warm, playful, slightly cheeky — like a wise older brother giving a gentle nudge
- Use ONLY the context and details provided in the user message
- NEVER fabricate details about the user that aren't in the prompt
- NEVER output thinking, reasoning, tags, or internal monologue
- Output ONLY the final surprise — nothing else
- Do NOT repeat quotes or stories from the "Recent surprises" section
- Each surprise must feel fresh and different from the last"""


def build_surprise_prompt(
    profile: dict,
    context: dict,
    memories: list[dict],
    theme: str | None = None,
) -> str:
    """Build the full user prompt injected at runtime."""
    chosen_theme = theme or random.choice(
        profile.get("preferences", {}).get("favorite_themes", config.THEMES)
    )

    display_name = profile.get("display_name", profile.get("name", "Friend"))
    goals = profile.get("goals", [])
    details = profile.get("personal_details", {})

    parts: list[str] = []

    # ── User context ──────────────────────────────────────────────────
    parts.append(f"User: {display_name}")

    if goals:
        # Pick 1-2 random goals to keep it focused and varied
        selected_goals = random.sample(goals, min(2, len(goals)))
        parts.append("Current goals:")
        for g in selected_goals:
            parts.append(f"  - {g}")

    if details.get("job"):
        parts.append(f"Job: {details['job']}")
    if details.get("hobbies"):
        parts.append(f"Hobbies: {details['hobbies']}")
    if details.get("family"):
        parts.append(f"Personal: {details['family']}")

    # ── What the user is doing right now ──────────────────────────────
    parts.append("")
    parts.append(f"Right now: {context.get('friendly_label', 'on the Mac')}")
    if context.get("window_title"):
        parts.append(f"Window: {context['window_title']}")
    parts.append(_get_time_context())

    # ── Recent memories (for variety / continuity) ────────────────────
    if memories:
        # Filter to only surprise-category memories for de-duplication
        surprise_memories = [
            m for m in memories
            if m.get("metadata", {}).get("category") == "surprise"
        ]
        if surprise_memories:
            parts.append("")
            parts.append("Recent surprises (DO NOT repeat these — be fresh and different):")
            for mem in surprise_memories[:3]:
                parts.append(f"  - {mem['text'][:100]}")

    # ── Theme + flavor ────────────────────────────────────────────────
    theme_label = chosen_theme.replace("_", " ").title()
    theme_hint = _THEME_HINTS.get(chosen_theme, f"Draw from {theme_label} wisdom and real stories.")

    parts.append("")
    parts.append(f"Theme for this surprise: {theme_label}")
    parts.append(theme_hint)

    parts.append("")
    parts.append(f"Generate one surprise for {display_name} now.")

    return "\n".join(parts)


def generate_surprise(prompt: str, profile: dict | None = None) -> tuple[str, str]:
    """Generate surprise using the custom model. Profile needed for dynamic system prompt."""
    surprise_id = uuid.uuid4().hex

    if profile is None:
        profile = config.load_profile()

    display_name = profile.get("display_name", profile.get("name", "Friend"))
    system_prompt = _build_system_prompt(profile)

    try:
        response = ollama.chat(
            model=config.MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            options={"num_predict": 300, "temperature": 0.82},
            think=False,
        )
        text = response.message.content.strip()

        # Clean up model artifacts — thinking tags, draft labels, etc.
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

        # Remove lines that look like internal reasoning
        lines = text.split("\n")
        cleaned = []
        for line in lines:
            lower = line.strip().lower()
            if any(lower.startswith(prefix) for prefix in [
                "thinking", "draft", "let me", "i'll", "here's", "okay",
                "sure", "note:", "---", "***",
            ]):
                continue
            cleaned.append(line)
        text = "\n".join(cleaned).strip()

        # If the model didn't start with the greeting, prepend it
        if text and not text.startswith(f"Hey {display_name}"):
            # Check if it starts with some other greeting pattern and fix it
            if text.startswith("Hey "):
                # Model used a different name — replace just the first line's name
                pass  # keep as is, the model knows best
            else:
                text = f"Hey {display_name},\n{text}"

        if not text or len(text) < 20:
            logger.warning("Model returned empty or very short response, using fallback")
            fallback = random.choice(config.FALLBACK_MESSAGES)
            text = f"Hey {display_name}, {fallback}"

        logger.info("Surprise generated (%d chars)", len(text))
        return text, surprise_id

    except Exception:
        logger.exception("Surprise generation failed — using fallback")
        fallback = random.choice(config.FALLBACK_MESSAGES)
        return f"Hey {display_name}, {fallback}", surprise_id
