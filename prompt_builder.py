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
        "Dostoevsky, Nietzsche, Camus, Kafka, Simone de Beauvoir, or Gandhi. "
        "Use a real quote or a striking philosophical idea."
    ),
    "indian_mythology": (
        "Draw from the Mahabharata, Ramayana, Bhagavad Gita, Upanishads, or stories of "
        "Shiva, Krishna, Arjuna, Karna, Draupadi, Hanuman, Chanakya, Eklavya, Bhishma, "
        "or Vivekananda. Use a real story or teaching."
    ),
    "tech_innovation": (
        "Draw from the real stories of Steve Jobs, Elon Musk, Ada Lovelace, Alan Turing, "
        "Nikola Tesla, the Wright Brothers, Grace Hopper, Linus Torvalds, Dennis Ritchie, "
        "Hedy Lamarr, or Sam Altman. Use a real anecdote or lesser-known fact."
    ),
    "stoic_wisdom": (
        "Draw from Marcus Aurelius (Meditations), Epictetus (Discourses), Seneca (Letters), "
        "Zeno of Citium, or Cato the Younger. Use a real Stoic quote or principle."
    ),
    "science_breakthroughs": (
        "Draw from real breakthroughs — Feynman, Marie Curie, Darwin, Hawking, "
        "Srinivasa Ramanujan, Einstein, Rosalind Franklin, Nikola Tesla, CV Raman, "
        "or APJ Abdul Kalam. Use a real fact or discovery story."
    ),
    "entrepreneurship": (
        "Draw from founders like Dhirubhai Ambani, Narayana Murthy, Sara Blakely, "
        "Jeff Bezos (garage days), Jack Ma (rejected 30 times), Phil Knight (Nike), "
        "or Ratan Tata. Use a real founder story."
    ),
    "sports_grit": (
        "Draw from athletes like Sourav Ganguly (the Dada of Indian cricket), "
        "Kobe Bryant (Mamba Mentality), Sachin Tendulkar, Michael Jordan, "
        "MS Dhoni (ticket collector to World Cup captain), Usain Bolt, or Neeraj Chopra. "
        "Use a real sports moment or lesser-known story."
    ),
}

# ── Time-of-day awareness ─────────────────────────────────────────────────
def _get_time_context() -> tuple[str, str]:
    """Return (time description for user prompt, personality vibe for system prompt)."""
    hour = datetime.now().hour
    weekday = datetime.now().strftime("%A")  # "Monday", "Friday", etc.

    if hour < 6:
        desc = "It's late night / very early morning — the user is up late."
        vibe = "Be gentle, understanding, and impressed they're still going. Short and warm."
    elif hour < 10:
        desc = f"It's {weekday} morning — a fresh start to the day."
        vibe = "Be energetic and motivational. Fire them up for the day ahead."
    elif hour < 13:
        desc = f"It's {weekday} late morning — the user is likely deep in work."
        vibe = "Be focused and sharp. Respect their flow — deliver something punchy."
    elif hour < 15:
        desc = f"It's {weekday} early afternoon — post-lunch energy dip."
        vibe = "Be light and playful. Give them a quick spark to fight the slump."
    elif hour < 18:
        desc = f"It's {weekday} afternoon — the productive stretch."
        vibe = "Be encouraging and forward-looking. They're in the zone."
    elif hour < 21:
        desc = f"It's {weekday} evening — winding down or doing personal work."
        vibe = "Be reflective and warm. Help them appreciate what they've done today."
    else:
        desc = f"It's {weekday} night — the user might be reflecting or working late."
        vibe = "Be calm, philosophical, and introspective. Night-mode wisdom."

    # Special day-of-week flavor
    if weekday == "Monday" and hour < 12:
        vibe += " It's Monday — give them a strong 'let's conquer the week' energy."
    elif weekday == "Friday" and hour >= 17:
        vibe += " It's Friday evening — celebrate the week. Be warm and congratulatory."
    elif weekday in ("Saturday", "Sunday"):
        vibe += " It's the weekend — be relaxed, fun, and personal. No work pressure."

    return desc, vibe


def _build_system_prompt(profile: dict, personality_vibe: str = "") -> str:
    """Build the system prompt dynamically using profile data. No hardcoding."""
    display_name = profile.get("display_name", profile.get("name", "Friend"))
    tone = profile.get("tone", "warm, slightly cheeky wise companion who feels like a fun older brother")

    vibe_line = f"\nCurrent vibe: {personality_vibe}" if personality_vibe else ""

    return f"""You are SurpriseSage — a {tone}.

You are talking to {display_name}. You know them well and care about their journey.
{vibe_line}

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


def _pick_context_aware_theme(context: dict, favorites: list[str]) -> str:
    """Pick a theme that fits what the user is doing right now."""
    label = context.get("friendly_label", "")

    # Context-to-theme affinity — nudge toward relevant themes when possible
    affinities: dict[str, list[str]] = {
        "coding": ["tech_innovation", "entrepreneurship", "stoic_wisdom"],
        "in the terminal": ["tech_innovation", "science_breakthroughs"],
        "browsing the web": ["philosophy", "science_breakthroughs"],
        "listening to music": ["philosophy", "indian_mythology"],
        "watching something": ["sports_grit", "philosophy"],
        "chatting": ["stoic_wisdom", "philosophy"],
        "designing": ["tech_innovation", "entrepreneurship"],
        "writing notes": ["philosophy", "stoic_wisdom"],
    }

    preferred = affinities.get(label, [])
    # 40% chance to use context-aware theme, 60% pure random (keeps variety)
    if preferred and random.random() < 0.4:
        candidates = [t for t in preferred if t in favorites]
        if candidates:
            return random.choice(candidates)

    return random.choice(favorites)


def build_surprise_prompt(
    profile: dict,
    context: dict,
    memories: list[dict],
    theme: str | None = None,
) -> tuple[str, str]:
    """Build the full user prompt. Returns (prompt_text, personality_vibe)."""
    favorites = profile.get("preferences", {}).get("favorite_themes", config.THEMES)
    chosen_theme = theme or _pick_context_aware_theme(context, favorites)

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
    time_desc, personality_vibe = _get_time_context()

    parts.append("")
    parts.append(f"Right now: {context.get('friendly_label', 'on the Mac')}")
    if context.get("window_title"):
        parts.append(f"Window: {context['window_title']}")
    parts.append(time_desc)

    # ── Recent memories (for variety / continuity) ────────────────────
    if memories:
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

    return "\n".join(parts), personality_vibe


def generate_surprise(
    prompt: str,
    profile: dict | None = None,
    personality_vibe: str = "",
) -> tuple[str, str]:
    """Generate surprise using the custom model. Profile needed for dynamic system prompt."""
    surprise_id = uuid.uuid4().hex

    if profile is None:
        profile = config.load_profile()

    display_name = profile.get("display_name", profile.get("name", "Friend"))
    system_prompt = _build_system_prompt(profile, personality_vibe)

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
