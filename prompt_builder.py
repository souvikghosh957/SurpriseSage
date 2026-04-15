"""SurpriseSage — dynamic prompt assembly and AI surprise generation.

Builds premium, varied micro-surprises by combining:
  - User profile (goals, details, tone)
  - Real-time macOS context (active app, time of day)
  - RAG memory (recent surprises, feedback)
  - Randomized surprise "formats" for variety
  - Rich theme-specific hints grounded in real people and stories
"""

import logging
import random
import re
import uuid
from datetime import datetime

import config
import llm_provider

logger = logging.getLogger("surprisesage.prompt")

# ── Surprise formats — varied angles so every surprise feels fresh ────────────
_SURPRISE_FORMATS: list[str] = [
    "Tell a real story most people have never heard about someone from this theme. The kind of thing that makes you say 'no way, that actually happened?'",
    "Share a fact that flips a common assumption on its head. Something counter-intuitive and real. Make the user rethink something they took for granted.",
    "Ask the user a thought-provoking question inspired by this theme. Not a quiz — a question that sticks in your head for the next hour.",
    "Connect what the user is doing RIGHT NOW to something unexpected from this theme. Draw a fun, surprising parallel they'd never see coming.",
    "Share how something legendary actually started — small, messy, or by accident. The bigger the contrast between the beginning and the outcome, the better.",
    "Share someone's real last words, farewell letter, or final act from this theme. The kind of moment that gives you chills. Then connect it forward.",
    "Drop one jaw-dropping number or statistic from this theme. Let the number do the heavy lifting, then tie it to the user's world.",
    "Share a beautiful, simple idea from this theme that changes how you see everyday life. Not a lecture — just a perspective shift in two sentences.",
]

# ── Theme-specific flavor text for richer prompts ────────────────────────────
_THEME_HINTS: dict[str, str] = {
    "philosophy": (
        "Draw from thinkers like Seneca, Epicurus, Lao Tzu, Rumi, Confucius, "
        "Dostoevsky, Nietzsche, Camus, Kafka, Simone de Beauvoir, Kierkegaard, "
        "Wittgenstein, Hannah Arendt, or Gandhi. Use a real quote, a paradox, "
        "or a striking thought experiment. Go deep, not obvious."
    ),
    "indian_mythology": (
        "Draw from the Mahabharata, Ramayana, Bhagavad Gita, Upanishads, Puranas, "
        "or stories of Shiva, Krishna, Arjuna, Karna, Draupadi, Hanuman, Chanakya, "
        "Eklavya, Bhishma, Savitri, Nachiketa, Garuda, or Vivekananda. "
        "Use lesser-known episodes — not the obvious ones everyone knows. "
        "The Mahabharata alone has 100,000 verses; find the hidden gems."
    ),
    "tech_innovation": (
        "Draw from real stories of Steve Jobs, Ada Lovelace, Alan Turing, Nikola Tesla, "
        "Grace Hopper, Linus Torvalds, Dennis Ritchie, Margaret Hamilton, Hedy Lamarr, "
        "Ken Thompson, Tim Berners-Lee, Vint Cerf, or Claude Shannon. Include the "
        "messy, human side — the failures, the late nights, the accidents that became inventions."
    ),
    "stoic_wisdom": (
        "Draw from Marcus Aurelius (Meditations), Epictetus (Discourses), Seneca (Letters "
        "to Lucilius), Zeno of Citium, Cato the Younger, Musonius Rufus, or Cleanthes. "
        "Use a real Stoic quote or principle, but apply it to modern life in a way that "
        "feels fresh — not the same 'memento mori' everyone posts on Instagram."
    ),
    "science_breakthroughs": (
        "Draw from real breakthroughs — Feynman, Marie Curie, Darwin, Hawking, "
        "Srinivasa Ramanujan, Einstein, Rosalind Franklin, CV Raman, Chandrasekhar, "
        "Barbara McClintock, Vera Rubin, APJ Abdul Kalam, Emmy Noether, or Satyendra "
        "Nath Bose. Focus on the human story behind the discovery — the doubt, "
        "the accident, the moment of 'eureka'."
    ),
    "entrepreneurship": (
        "Draw from founders like Dhirubhai Ambani, Narayana Murthy, Sara Blakely, "
        "Jeff Bezos (garage days), Jack Ma (rejected 30 times), Phil Knight (selling "
        "shoes from his car), Ratan Tata, Kiran Mazumdar-Shaw, Elon Musk (sleeping in "
        "the factory), or James Dyson (5,126 failed prototypes). Use the raw, gritty "
        "early days — not the polished success story."
    ),
    "sports_grit": (
        "Draw from Sourav Ganguly (the Lord's balcony moment), Kobe Bryant (4 AM workouts), "
        "Sachin Tendulkar (desert storm innings), Michael Jordan (cut from high school team), "
        "MS Dhoni (ticket collector to World Cup helicopter shot), Usain Bolt, Neeraj Chopra, "
        "Simone Biles (the Twisties), Muhammad Ali (the Rumble in the Jungle), "
        "PV Sindhu, or Milkha Singh. Use a specific, vivid moment — not generic motivation."
    ),
    "psychology_and_mind": (
        "Draw from real cognitive science — the Dunning-Kruger effect, flow states "
        "(Csikszentmihalyi), the Zeigarnik effect (unfinished tasks haunt you), Kahneman's "
        "System 1/2 thinking, the mere exposure effect, sunk cost fallacy, the Baader-Meinhof "
        "phenomenon, or neuroplasticity research. Share something that makes the user see "
        "their own mind differently."
    ),
    "art_and_creativity": (
        "Draw from Michelangelo (4 years on his back painting the Sistine Chapel), "
        "Frida Kahlo, Van Gogh (sold one painting in his lifetime), Hokusai (said he "
        "understood nothing at 73), Picasso, Rabindranath Tagore, M.F. Husain, "
        "Da Vinci's notebooks, Basquiat, or Yayoi Kusama. Focus on the creative "
        "struggle, the obsession, the moment art broke through."
    ),
    "history_turning_points": (
        "Draw from moments that changed everything — the fall of Constantinople, "
        "the printing press, India's 1947 midnight hour, the moon landing, "
        "the invention of zero (India), the Library of Alexandria's destruction, "
        "Gutenberg, the French Revolution, the fall of the Berlin Wall, "
        "or the day the internet went live. Focus on the human story inside the big event."
    ),
    "space_and_cosmos": (
        "Draw from Voyager's Golden Record, the Pale Blue Dot (Sagan), Apollo 13, "
        "ISRO's Mangalyaan (Mars mission cheaper than a Hollywood movie), Hubble Deep "
        "Field, black hole photography (Katie Bouman), Kalpana Chawla, Valentina "
        "Tereshkova, the Fermi Paradox, neutron stars, or the overview effect. "
        "Make the user feel the scale — then bring it back to something personal."
    ),
    "music_and_soul": (
        "Draw from Beethoven composing while deaf, AR Rahman's journey from Chennai "
        "to Oscars, Bob Dylan going electric (and getting booed), Nina Simone, "
        "Nusrat Fateh Ali Khan, Ravi Shankar teaching George Harrison, Mozart's "
        "final Requiem, Freddie Mercury's last recordings, Kishore Kumar, "
        "or the neuroscience of why music gives us chills. Connect sound to soul."
    ),
    "leadership_lessons": (
        "Draw from Chanakya's Arthashastra, Lincoln (Team of Rivals), Shackleton "
        "(Endurance expedition — lost the ship, saved every life), Subhas Chandra "
        "Bose, Mandela (27 years then forgiveness), Indira Gandhi, Genghis Khan's "
        "meritocracy, or Satya Nadella's transformation of Microsoft. "
        "Focus on one specific decision or moment that defined the leader."
    ),
    "rebel_thinkers": (
        "Draw from people who said 'no' when the world said 'yes' — Galileo, "
        "Socrates (drank the hemlock), Bhagat Singh, Rosa Parks, Aaron Swartz, "
        "Hypatia of Alexandria, Alan Turing (persecuted then pardoned), Savitribai "
        "Phule (India's first female teacher, had stones thrown at her), Giordano Bruno, "
        "or Edward Snowden. Celebrate the cost of thinking differently."
    ),
    "nature_and_evolution": (
        "Draw from the real wonders of biology — octopuses editing their own RNA, "
        "tardigrades surviving in space, mycelium networks ('the wood wide web'), "
        "the axolotl regrowing its brain, whales singing across ocean basins, "
        "crows using tools, the 4-billion-year story of DNA, or the biomimicry "
        "behind Velcro, bullet trains (kingfisher beak), and self-healing concrete. "
        "Nature has already solved most of our problems."
    ),
}

# ── Time-of-day awareness ────────────────────────────────────────────────────
def _get_time_context() -> tuple[str, str]:
    """Return (time description for user prompt, personality vibe for system prompt)."""
    hour = datetime.now().hour
    weekday = datetime.now().strftime("%A")

    # ── Fine-grained time slots ──────────────────────────────────────
    if hour < 5:
        # Late night / very early morning (midnight–5 AM)
        desc = "It's the dead of night — the user is up while the world sleeps."
        vibe = (
            "Whisper-mode. Be gentle, a little awed they're still going. "
            "This is the hour for deep thoughts, not hustle talk. "
            "Share something quiet and profound — the kind of thing "
            "that only lands at 3 AM."
        )
    elif hour < 7:
        # Early morning (5–7 AM)
        desc = f"It's early {weekday} morning — the user is up before most people."
        vibe = (
            "They're an early riser today. Be calm and grounding — "
            "not loud, not hyper. A gentle spark to start the day. "
            "Think sunrise energy, not alarm-clock energy."
        )
    elif hour < 9:
        # Morning (7–9 AM)
        desc = f"It's {weekday} morning — the day is just getting started."
        vibe = (
            "Morning fuel. Be warm and energizing — one insight they "
            "can carry into the day like a good cup of coffee. "
            "Set the tone, don't overwhelm."
        )
    elif hour < 11:
        # Late morning (9–11 AM)
        desc = f"It's {weekday} late morning — the user is likely in work mode."
        vibe = (
            "They're in the zone. Be sharp and punchy — respect their focus. "
            "A quick hit of brilliance, then get out of the way. "
            "Think espresso shot, not full lecture."
        )
    elif hour < 13:
        # Noon (11 AM–1 PM)
        desc = f"It's around noon on {weekday} — midday energy."
        vibe = (
            "Midday check-in. Be bright and interesting — "
            "they might be taking a break or about to eat. "
            "Something fun and easy to digest. Light but smart."
        )
    elif hour < 15:
        # Early afternoon (1–3 PM)
        desc = f"It's {weekday} early afternoon — the post-lunch dip."
        vibe = (
            "The afternoon slump is real. Be playful and surprising — "
            "wake them up with something they didn't expect. "
            "This is the time for 'wait, really?' facts."
        )
    elif hour < 17:
        # Afternoon (3–5 PM)
        desc = f"It's {weekday} afternoon — the productive stretch."
        vibe = (
            "They're pushing through the day. Be encouraging and forward-looking. "
            "Give them fuel for the final stretch. Something that makes the grind "
            "feel worth it."
        )
    elif hour < 19:
        # Early evening (5–7 PM)
        desc = f"It's {weekday} early evening — wrapping up the day."
        vibe = (
            "The workday is winding down. Be warm and reflective — "
            "help them transition from work-mode to life-mode. "
            "Something personal, not professional."
        )
    elif hour < 21:
        # Evening (7–9 PM)
        desc = f"It's {weekday} evening — personal time."
        vibe = (
            "Evening mode. Be relaxed, warm, maybe a little philosophical. "
            "This is their time — with family, with themselves. "
            "Share something that makes the evening feel richer."
        )
    elif hour < 23:
        # Night (9–11 PM)
        desc = f"It's {weekday} night — the day is almost done."
        vibe = (
            "Night-mode. Be calm and introspective. The kind of thought "
            "you'd share sitting on a balcony at night. "
            "Philosophical, personal, maybe a little poetic."
        )
    else:
        # Late night (11 PM–midnight)
        desc = f"It's late {weekday} night — the world is getting quiet."
        vibe = (
            "Late night energy. Be intimate and thoughtful. "
            "They're still up — maybe working, maybe thinking. "
            "Share something that feels like a conversation between friends "
            "at midnight."
        )

    # ── Day-of-week flavor ───────────────────────────────────────────
    if weekday == "Monday" and hour < 12:
        vibe += " It's Monday morning — set the tone for the whole week. Strong but not preachy."
    elif weekday == "Monday" and hour >= 17:
        vibe += " Monday evening — they made it through day one. Acknowledge that."
    elif weekday == "Wednesday":
        vibe += " It's midweek — they're in the thick of it. Be their second wind."
    elif weekday == "Friday" and hour < 12:
        vibe += " Friday morning — the finish line is in sight. Keep the energy up."
    elif weekday == "Friday" and hour >= 17:
        vibe += " Friday evening — the week is done. Celebrate. Be warm and congratulatory."
    elif weekday == "Saturday":
        vibe += " It's Saturday — no hustle talk. Be fun, be human, be personal. Weekend vibes."
    elif weekday == "Sunday" and hour < 17:
        vibe += " Sunday — recharge day. Be gentle and restorative. No pressure."
    elif weekday == "Sunday" and hour >= 17:
        vibe += " Sunday evening — the week is about to start. Be grounding, not anxiety-inducing."

    return desc, vibe


def _build_system_prompt(profile: dict, personality_vibe: str = "", surprise_format: str = "") -> str:
    """Build a system prompt that produces friendly, readable, insightful surprises."""
    display_name = profile.get("display_name", profile.get("name", "Friend"))
    tone = profile.get("tone", "warm, slightly cheeky wise companion who feels like a fun older brother")

    vibe_line = f"\nMood right now: {personality_vibe}" if personality_vibe else ""
    format_line = f"\nStyle to use: {surprise_format}" if surprise_format else ""

    return f"""You are SurpriseSage — a {tone}.

You're talking to {display_name}, someone you genuinely care about. Write like a smart friend sharing something cool over chai — simple words, big ideas, warm delivery.
{vibe_line}
{format_line}

How to write the surprise:
1. Start with "Hey {display_name},"
2. Share ONE real story, fact, quote, or insight — something specific and true
3. Connect it to their life with a warm, personal line
4. Done. That's the whole response.

The golden rules:
- Write 50 to 80 WORDS. Not characters — words. Count them. This is important.
- Use simple, everyday language. If a 15-year-old can't understand it, rewrite it.
- Take complex, beautiful ideas from any field and explain them simply.
- Be specific. "Ramanujan mailed 120 theorems to Hardy on 11 pages" beats "Ramanujan was a genius."
- Make them go "wait, really?" — surprise them, don't just motivate them.
- No jargon, no fancy vocabulary, no academic tone. Just clear and warm.
- Use ONLY facts about the user given in the prompt — never make things up.
- Do NOT repeat anything from the "Recent surprises" list.
- Output ONLY the surprise text. No thinking, no preamble, no labels, no tags."""


def _pick_context_aware_theme(context: dict, favorites: list[str]) -> str:
    """Pick a theme that fits what the user is doing right now."""
    label = context.get("friendly_label", "")

    affinities: dict[str, list[str]] = {
        "coding": ["tech_innovation", "science_breakthroughs", "rebel_thinkers", "psychology_and_mind"],
        "in the terminal": ["tech_innovation", "science_breakthroughs", "nature_and_evolution"],
        "browsing the web": ["philosophy", "history_turning_points", "psychology_and_mind", "space_and_cosmos"],
        "listening to music": ["music_and_soul", "art_and_creativity", "philosophy"],
        "watching something": ["sports_grit", "art_and_creativity", "history_turning_points"],
        "chatting": ["stoic_wisdom", "philosophy", "psychology_and_mind", "leadership_lessons"],
        "designing": ["art_and_creativity", "tech_innovation", "nature_and_evolution"],
        "writing notes": ["philosophy", "stoic_wisdom", "psychology_and_mind", "rebel_thinkers"],
        "chatting with AI": ["tech_innovation", "science_breakthroughs", "philosophy", "rebel_thinkers"],
        "reading a document": ["philosophy", "history_turning_points", "science_breakthroughs"],
    }

    preferred = affinities.get(label, [])
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
) -> tuple[str, str, str]:
    """Build the full user prompt.

    Returns (prompt_text, personality_vibe, surprise_format).
    """
    favorites = profile.get("preferences", {}).get("favorite_themes", config.THEMES)
    chosen_theme = theme or _pick_context_aware_theme(context, favorites)

    display_name = profile.get("display_name", profile.get("name", "Friend"))
    goals = profile.get("goals", [])
    details = profile.get("personal_details", {})

    # Pick a random surprise format for variety
    surprise_format = random.choice(_SURPRISE_FORMATS)

    parts: list[str] = []

    # ── User context ──────────────────────────────────────────────────
    parts.append(f"User: {display_name}")

    if goals:
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
            parts.append("Recent surprises (DO NOT repeat these — be completely fresh):")
            for mem in surprise_memories[:5]:
                parts.append(f"  - {mem['text'][:120]}")

    # ── Theme + flavor + format ───────────────────────────────────────
    theme_label = chosen_theme.replace("_", " ").title()
    theme_hint = _THEME_HINTS.get(chosen_theme, f"Draw from {theme_label} wisdom and real stories.")

    parts.append("")
    parts.append(f"Theme: {theme_label}")
    parts.append(theme_hint)

    parts.append("")
    parts.append(f"Generate one surprise for {display_name} now.")

    return "\n".join(parts), personality_vibe, surprise_format


def generate_surprise(
    prompt: str,
    profile: dict | None = None,
    personality_vibe: str = "",
    surprise_format: str = "",
) -> tuple[str, str]:
    """Generate surprise via the configured LLM. Returns (text, surprise_id)."""
    surprise_id = uuid.uuid4().hex

    if profile is None:
        profile = config.load_profile()

    display_name = profile.get("display_name", profile.get("name", "Friend"))
    system_prompt = _build_system_prompt(profile, personality_vibe, surprise_format)

    try:
        text = llm_provider.generate(system_prompt, prompt, profile)

        # Clean up model artifacts — thinking tags, draft labels, etc.
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

        # Remove lines that look like internal reasoning
        lines = text.split("\n")
        cleaned = []
        for line in lines:
            lower = line.strip().lower()
            if any(lower.startswith(prefix) for prefix in [
                "thinking", "draft", "let me", "i'll", "here's", "okay",
                "sure", "note:", "---", "***", "format:", "approach:",
            ]):
                continue
            cleaned.append(line)
        text = "\n".join(cleaned).strip()

        # Ensure the greeting is present
        if text and not text.startswith(f"Hey {display_name}"):
            if text.startswith("Hey "):
                pass  # model used a variant — keep it
            else:
                text = f"Hey {display_name}, {text}"

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
