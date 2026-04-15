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

# ── Known figures per theme (used for dedup extraction) ────────────────────────
_KNOWN_FIGURES: list[str] = [
    # entrepreneurship
    "Dyson", "James Dyson", "Dhirubhai Ambani", "Narayana Murthy", "Sara Blakely",
    "Jeff Bezos", "Jack Ma", "Phil Knight", "Ratan Tata", "Kiran Mazumdar-Shaw",
    "Elon Musk", "Steve Jobs", "Sam Walton", "Oprah Winfrey", "Howard Schultz",
    "Estée Lauder", "Madam C.J. Walker", "Ritesh Agarwal", "Jan Koum",
    # tech
    "Ada Lovelace", "Alan Turing", "Nikola Tesla", "Grace Hopper", "Linus Torvalds",
    "Dennis Ritchie", "Margaret Hamilton", "Hedy Lamarr", "Tim Berners-Lee",
    "Claude Shannon", "Ken Thompson", "Vint Cerf",
    # philosophy & stoic
    "Seneca", "Epicurus", "Lao Tzu", "Rumi", "Confucius", "Nietzsche", "Camus",
    "Kafka", "Kierkegaard", "Marcus Aurelius", "Epictetus", "Zeno",
    # science
    "Feynman", "Marie Curie", "Darwin", "Hawking", "Ramanujan", "Einstein",
    "Rosalind Franklin", "CV Raman", "Chandrasekhar", "APJ Abdul Kalam",
    "Emmy Noether", "Satyendra Nath Bose",
    # sports
    "Sourav Ganguly", "Kobe Bryant", "Sachin Tendulkar", "Michael Jordan",
    "MS Dhoni", "Usain Bolt", "Muhammad Ali", "Milkha Singh", "Neeraj Chopra",
    # mythology
    "Krishna", "Arjuna", "Karna", "Draupadi", "Hanuman", "Chanakya", "Bhishma",
    # arts/music
    "Michelangelo", "Frida Kahlo", "Van Gogh", "Picasso", "Da Vinci",
    "Beethoven", "AR Rahman", "Bob Dylan", "Freddie Mercury", "Mozart",
    # leaders
    "Lincoln", "Shackleton", "Mandela", "Genghis Khan", "Satya Nadella",
    # rebels
    "Galileo", "Socrates", "Rosa Parks", "Aaron Swartz", "Bhagat Singh",
    # space
    "Carl Sagan", "Kalpana Chawla", "Katie Bouman",
]


def _extract_figures(memories: list[dict]) -> list[str]:
    """Extract names of known figures mentioned in recent surprise texts."""
    combined = " ".join(m.get("text", "") for m in memories)
    found = []
    seen_lower = set()
    for name in _KNOWN_FIGURES:
        if name in combined and name.lower() not in seen_lower:
            found.append(name)
            seen_lower.add(name.lower())
    return found


# ── Surprise formats — varied angles so every surprise feels fresh ────────────
_SURPRISE_FORMATS: list[str] = [
    "Tell a real story most people have never heard. The kind that makes you say 'no way, that actually happened?' Use simple words — make the story feel alive, not like a Wikipedia entry. End by connecting it to the user's life.",
    "Share a fact that flips something obvious on its head. Something that makes the user rethink what they took for granted. Say it plainly — the surprise does the work, not fancy words. Then tie it to their world.",
    "Ask the user one question that stays in their head. Not a quiz — something personal, inspired by this theme. The kind of question you'd ask a friend while walking. Simple, deep, no right answer.",
    "Connect what the user is doing RIGHT NOW to something unexpected from this theme. Draw a fun, surprising parallel they'd never see coming. Make it feel like a personal discovery, not a lecture.",
    "Share how something legendary actually started — small, messy, or by accident. The bigger the contrast between the beginning and the outcome, the better. Tell it like a story, not a history lesson. Connect it to the user's own journey.",
    "Share someone's real last words, farewell letter, or final moment from this theme. The kind of moment that gives you chills. Tell it simply — let the moment speak. Then connect it to something the user cares about.",
    "Drop one jaw-dropping number or statistic. Let the number do the heavy lifting — say it simply, then tie it to the user's everyday life. Make the number feel personal, not abstract.",
    "Share one beautiful, simple idea from this theme that changes how you see everyday life. Not a lecture — just a quiet perspective shift in plain words. The kind of thing you'd think about on a walk.",
    "Find a surprising hidden connection between TWO different fields — link this theme to something totally unrelated (music to math, mythology to physics, sports to philosophy). The weirder the real connection, the better. Explain it simply.",
]

# Track recently used format indices to avoid staleness
_recent_format_indices: list[int] = []


def _pick_fresh_format() -> str:
    """Pick a surprise format, avoiding the last 4 used formats."""
    available = [
        i for i in range(len(_SURPRISE_FORMATS))
        if i not in _recent_format_indices
    ]
    if not available:
        available = list(range(len(_SURPRISE_FORMATS)))
        _recent_format_indices.clear()

    idx = random.choice(available)
    _recent_format_indices.append(idx)
    if len(_recent_format_indices) > 4:
        _recent_format_indices.pop(0)

    return _SURPRISE_FORMATS[idx]

# ── Theme-specific flavor text for richer prompts ────────────────────────────
_THEME_HINTS: dict[str, str] = {
    "philosophy": (
        "Draw from a WIDE variety of thinkers — Seneca, Epicurus, Lao Tzu, Rumi, Confucius, "
        "Dostoevsky, Nietzsche, Camus, Kafka, Simone de Beauvoir, Kierkegaard, "
        "Wittgenstein, Hannah Arendt, Gandhi, Ibn Arabi, Zhuangzi, Thich Nhat Hanh, "
        "Iris Murdoch, Judith Butler, Frantz Fanon, or Rabindranath Tagore. "
        "Use a real quote, a paradox, or a striking thought experiment. Go deep, not obvious. "
        "Pick someone DIFFERENT each time."
    ),
    "indian_mythology": (
        "Draw from the Mahabharata, Ramayana, Bhagavad Gita, Upanishads, Puranas, "
        "or stories of Shiva, Krishna, Arjuna, Karna, Draupadi, Hanuman, Chanakya, "
        "Eklavya, Bhishma, Savitri, Nachiketa, Garuda, Vivekananda, Adi Shankaracharya, "
        "Meerabai, Aryabhata, Charaka, Gargi Vachaknavi, Maitreyi, or Matsyendranath. "
        "Use lesser-known episodes — not the obvious ones everyone knows. "
        "The Mahabharata alone has 100,000 verses; find the hidden gems. "
        "Pick someone DIFFERENT each time."
    ),
    "tech_innovation": (
        "Draw from a WIDE variety — Steve Jobs, Ada Lovelace, Alan Turing, Nikola Tesla, "
        "Grace Hopper, Linus Torvalds, Dennis Ritchie, Margaret Hamilton, Hedy Lamarr, "
        "Ken Thompson, Tim Berners-Lee, Vint Cerf, Claude Shannon, Doug Engelbart, "
        "Fei-Fei Li, John Carmack, Sophie Wilson (ARM chip), Brendan Eich, or "
        "Demis Hassabis. Include the messy, human side — the failures, the late nights, "
        "the accidents that became inventions. Pick someone DIFFERENT each time."
    ),
    "stoic_wisdom": (
        "Draw from Marcus Aurelius (Meditations), Epictetus (Discourses), Seneca (Letters "
        "to Lucilius), Zeno of Citium, Cato the Younger, Musonius Rufus, Cleanthes, "
        "Chrysippus, Posidonius, or Hierocles. Also consider modern Stoics like "
        "James Stockdale (POW who survived through Epictetus) or Viktor Frankl. "
        "Use a real Stoic quote or principle, but apply it to modern life in a way that "
        "feels fresh — not the same 'memento mori' everyone posts on Instagram. "
        "Pick someone DIFFERENT each time."
    ),
    "science_breakthroughs": (
        "Draw from a WIDE variety — Feynman, Marie Curie, Darwin, Hawking, "
        "Srinivasa Ramanujan, Einstein, Rosalind Franklin, CV Raman, Chandrasekhar, "
        "Barbara McClintock, Vera Rubin, APJ Abdul Kalam, Emmy Noether, Satyendra "
        "Nath Bose, Lise Meitner (nuclear fission, Nobel stolen), Homi Bhabha, "
        "Tu Youyou (malaria cure from ancient texts), Katalin Karikó (mRNA pioneer), "
        "or Santiago Ramón y Cajal. Focus on the human story behind the discovery — "
        "the doubt, the accident, the moment of 'eureka'. Pick someone DIFFERENT each time."
    ),
    "entrepreneurship": (
        "Draw from a WIDE variety of founders — Dhirubhai Ambani (textile trader to empire), "
        "Narayana Murthy (started Infosys with $250), Sara Blakely (sold fax machines door-to-door), "
        "Jeff Bezos (garage days), Jack Ma (rejected 30 times), Phil Knight (selling shoes from his car), "
        "Ratan Tata, Kiran Mazumdar-Shaw, Sam Walton (borrowed $20K for first store), "
        "Madam C.J. Walker (first female self-made millionaire), Oprah Winfrey (fired from first TV job), "
        "Howard Schultz (grew up in housing projects), Jan Koum (WhatsApp founder — on food stamps as a kid), "
        "Ritesh Agarwal (OYO at 19), Estée Lauder (started in her kitchen), James Dyson, "
        "Elon Musk (sleeping in the factory), or Colonel Sanders (rejected 1,009 times before KFC). "
        "Pick someone DIFFERENT each time. Use the raw, gritty early days — not the polished success story."
    ),
    "sports_grit": (
        "Draw from a WIDE variety — Sourav Ganguly (Lord's balcony moment), Kobe Bryant (4 AM workouts), "
        "Sachin Tendulkar (desert storm innings), Michael Jordan (cut from high school team), "
        "MS Dhoni (ticket collector to World Cup helicopter shot), Usain Bolt, Neeraj Chopra, "
        "Simone Biles (the Twisties), Muhammad Ali (Rumble in the Jungle), "
        "PV Sindhu, Milkha Singh, Serena Williams, Jimmy Connors (comeback at 39), "
        "Dick Fosbury (invented the Fosbury Flop, everyone laughed), Eliud Kipchoge "
        "(sub-2-hour marathon), or Dhyan Chand (Hitler offered him German citizenship). "
        "Use a specific, vivid moment — not generic motivation. Pick someone DIFFERENT each time."
    ),
    "psychology_and_mind": (
        "Draw from real cognitive science — the Dunning-Kruger effect, flow states "
        "(Csikszentmihalyi), the Zeigarnik effect (unfinished tasks haunt you), Kahneman's "
        "System 1/2 thinking, the mere exposure effect, sunk cost fallacy, the Baader-Meinhof "
        "phenomenon, neuroplasticity research, the doorway effect, spotlight effect, "
        "the IKEA effect, hedonic adaptation, Asch conformity experiment, Stanford prison "
        "experiment, or the paradox of choice (Barry Schwartz). Share something that makes "
        "the user see their own mind differently. Pick a DIFFERENT concept each time."
    ),
    "art_and_creativity": (
        "Draw from a WIDE variety — Michelangelo (4 years painting the Sistine Chapel), "
        "Frida Kahlo, Van Gogh (sold one painting in his lifetime), Hokusai (said he "
        "understood nothing at 73), Picasso, Rabindranath Tagore, M.F. Husain, "
        "Da Vinci's notebooks, Basquiat, Yayoi Kusama, Amrita Sher-Gil, "
        "Ai Weiwei, Marina Abramović, Banksy, Satyajit Ray (Pather Panchali on zero budget), "
        "or Hayao Miyazaki (retired and un-retired 7 times). Focus on the creative "
        "struggle, the obsession, the moment art broke through. Pick someone DIFFERENT each time."
    ),
    "history_turning_points": (
        "Draw from moments that changed everything — the fall of Constantinople, "
        "the printing press, India's 1947 midnight hour, the moon landing, "
        "the invention of zero (India), the Library of Alexandria's destruction, "
        "Gutenberg, the French Revolution, the fall of the Berlin Wall, "
        "the day the internet went live, the Silk Road's cultural exchange, "
        "the Haitian Revolution (only successful slave revolt), the Treaty of Tordesillas "
        "(two countries splitting the world), or Vasili Arkhipov (the man who saved the "
        "world from nuclear war). Focus on the human story inside the big event. "
        "Pick a DIFFERENT event each time."
    ),
    "space_and_cosmos": (
        "Draw from Voyager's Golden Record, the Pale Blue Dot (Sagan), Apollo 13, "
        "ISRO's Mangalyaan (Mars mission cheaper than a Hollywood movie), Hubble Deep "
        "Field, black hole photography (Katie Bouman), Kalpana Chawla, Valentina "
        "Tereshkova, the Fermi Paradox, neutron stars, the overview effect, "
        "Chandrayaan-3's south pole landing, JWST's first deep field image, "
        "the Wow! signal, Oumuamua (interstellar visitor), or the fact that there are "
        "more stars than grains of sand on Earth. "
        "Make the user feel the scale — then bring it back to something personal. "
        "Pick something DIFFERENT each time."
    ),
    "music_and_soul": (
        "Draw from a WIDE variety — Beethoven composing while deaf, AR Rahman's journey from "
        "Chennai to Oscars, Bob Dylan going electric (and getting booed), Nina Simone, "
        "Nusrat Fateh Ali Khan, Ravi Shankar teaching George Harrison, Mozart's "
        "final Requiem, Freddie Mercury's last recordings, Kishore Kumar, "
        "the neuroscience of why music gives us chills, Billie Holiday's 'Strange Fruit', "
        "Ustad Bismillah Khan (played shehnai at India's first Independence Day), "
        "Robert Johnson's crossroads legend, or Björk. Connect sound to soul. "
        "Pick someone DIFFERENT each time."
    ),
    "leadership_lessons": (
        "Draw from a WIDE variety — Chanakya's Arthashastra, Lincoln (Team of Rivals), "
        "Shackleton (Endurance expedition — lost the ship, saved every life), Subhas Chandra "
        "Bose, Mandela (27 years then forgiveness), Indira Gandhi, Genghis Khan's "
        "meritocracy, Satya Nadella's transformation of Microsoft, Jacinda Ardern "
        "(empathy as leadership), Verghese Kurien (Operation Flood — made India the "
        "world's largest milk producer), or Akio Morita (Sony — 'Made in Japan' "
        "from insult to badge of honor). "
        "Focus on one specific decision or moment that defined the leader. "
        "Pick someone DIFFERENT each time."
    ),
    "rebel_thinkers": (
        "Draw from people who said 'no' when the world said 'yes' — Galileo, "
        "Socrates (drank the hemlock), Bhagat Singh, Rosa Parks, Aaron Swartz, "
        "Hypatia of Alexandria, Alan Turing (persecuted then pardoned), Savitribai "
        "Phule (India's first female teacher, had stones thrown at her), Giordano Bruno, "
        "Edward Snowden, Malala Yousafzai, Wangari Maathai (planted 30 million trees, "
        "beaten by police), Ignaz Semmelweis (told doctors to wash hands, was mocked), "
        "or Rachel Carson (Silent Spring, attacked by chemical industry). "
        "Celebrate the cost of thinking differently. Pick someone DIFFERENT each time."
    ),
    "nature_and_evolution": (
        "Draw from the real wonders of biology — octopuses editing their own RNA, "
        "tardigrades surviving in space, mycelium networks ('the wood wide web'), "
        "the axolotl regrowing its brain, whales singing across ocean basins, "
        "crows using tools, the 4-billion-year story of DNA, biomimicry "
        "behind Velcro, bullet trains (kingfisher beak), self-healing concrete, "
        "the immortal jellyfish (Turritopsis dohrnii), ant supercolonies spanning continents, "
        "the pistol shrimp (creates plasma with its claw), or slime mold solving mazes "
        "faster than engineers. Nature has already solved most of our problems. "
        "Pick something DIFFERENT each time."
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


# ── Special days awareness ────────────────────────────────────────────────────
_SPECIAL_DAYS: dict[tuple[int, int], str] = {
    (1, 1): "It's New Year's Day! A fresh start, infinite possibilities. Make this surprise feel like the first page of a new chapter.",
    (1, 26): "It's Republic Day! India's constitution came alive today. Weave in something about courage, rights, or nation-building.",
    (2, 14): "It's Valentine's Day! Love is in the air. Share something about the science, history, or poetry of love.",
    (3, 8): "It's International Women's Day! Celebrate a remarkable woman's story from this theme.",
    (4, 22): "It's Earth Day! Connect this theme to our planet, nature, or sustainability.",
    (5, 1): "It's May Day / Labour Day! Honor the dignity of work and the people who build things.",
    (6, 21): "It's the longest day of the year (Summer Solstice)! Share something about light, endurance, or seasons.",
    (8, 15): "It's Indian Independence Day! Bring in the spirit of freedom, sacrifice, or self-determination.",
    (10, 2): "It's Gandhi Jayanti! Non-violence, truth, and the power of one person to change the world.",
    (10, 31): "It's Halloween! Share something eerie, mysterious, or delightfully dark from this theme.",
    (11, 1): "It's Diwali season! Light over darkness, knowledge over ignorance. Make this surprise sparkle.",
    (12, 25): "It's Christmas! Generosity, wonder, and stories that warm the heart.",
    (12, 31): "It's New Year's Eve! Reflection, gratitude, and looking ahead. End the year with something beautiful.",
}


def _get_special_day_vibe(profile: dict) -> str:
    """Check if today is a special day or the user's birthday."""
    today = datetime.now()
    month_day = (today.month, today.day)
    parts = []

    # Check special days
    if month_day in _SPECIAL_DAYS:
        parts.append(_SPECIAL_DAYS[month_day])

    # Check birthday
    birthday = profile.get("personal_details", {}).get("birthday", "")
    if birthday:
        try:
            bday = datetime.strptime(birthday, "%m-%d")
            if (bday.month, bday.day) == month_day:
                name = profile.get("display_name", "Friend")
                parts.append(
                    f"It's {name}'s BIRTHDAY today! Make this surprise extra special — "
                    f"warm, celebratory, and personal. Wish them happy birthday naturally "
                    f"as part of the surprise."
                )
        except ValueError:
            pass

    return " ".join(parts)


def _build_system_prompt(profile: dict, personality_vibe: str = "", surprise_format: str = "") -> str:
    """Build a system prompt that produces friendly, readable, insightful surprises."""
    display_name = profile.get("display_name", profile.get("name", "Friend"))
    tone = profile.get("tone", "warm, slightly cheeky wise companion who feels like a fun older brother")

    vibe_line = f"\nMood right now: {personality_vibe}" if personality_vibe else ""
    format_line = f"\nStyle to use: {surprise_format}" if surprise_format else ""
    special_day = _get_special_day_vibe(profile)
    special_line = f"\nSpecial occasion: {special_day}" if special_day else ""

    return f"""You are SurpriseSage — a {tone}.

You're talking to {display_name}. Write like a wise friend sharing one beautiful idea over chai.
{vibe_line}
{format_line}
{special_line}

Structure:
1. "Hey {display_name}," (greeting)
2. One real story, fact, or idea — specific, true, surprising
3. One warm line connecting it to their life right now
4. That's it. Nothing else.

LANGUAGE (follow exactly):
- Short sentences. Simple words. Like texting a friend.
- Take the deepest, most complex idea and say it so a 12-year-old loves it.
- "use" not "utilize". "show" not "demonstrate". "start" not "commence". "old" not "ancient". "brain" not "subconscious". "trick" not "mechanism".
- BANNED: paradigm, synergy, catalyst, pivotal, testament, embark, endeavor, forge, illuminate, resonate, transcend, framework, fragment, circuit, harness, leverage, navigate, landscape, ecosystem, holistic, cusp.
- BAD: "His paradigm-shifting innovation catalyzed a transformative era."
- GOOD: "He failed 5,126 times. Then vacuum cleaners changed forever."

TONE:
- Inspiring and positive. Leave them feeling better.
- Specific beats generic. Numbers, names, real details.
- Make them think "wait, really?"
- Connect to what they're doing right now.

CONSTRAINTS:
- Write 35 to 55 WORDS only. Short and punchy. Like a quote card.
- Proper sentence case. No random caps. No ALL CAPS words.
- Use ONLY facts about the user from the prompt.
- Do NOT repeat anything from "Recent surprises".
- Do NOT reuse anyone from "People/figures already used".
- Output ONLY the surprise text. No labels, no tags, no preamble."""


def _pick_context_aware_theme(
    context: dict, favorites: list[str], feedback_scores: dict[str, int] | None = None,
) -> str:
    """Pick a theme that fits what the user is doing right now.

    Uses feedback_scores (from memory) to boost loved themes and reduce disliked ones.
    """
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
            return _weighted_theme_pick(candidates, feedback_scores)

    return _weighted_theme_pick(favorites, feedback_scores)


def _weighted_theme_pick(
    themes: list[str], feedback_scores: dict[str, int] | None = None,
) -> str:
    """Pick a theme with weights boosted/reduced by user feedback history."""
    if not feedback_scores or not themes:
        return random.choice(themes)

    # Base weight 10 for each, then add/subtract feedback (clamped to 1 minimum)
    weights = []
    for t in themes:
        w = 10 + feedback_scores.get(t, 0) * 2
        weights.append(max(w, 1))

    return random.choices(themes, weights=weights, k=1)[0]


def build_surprise_prompt(
    profile: dict,
    context: dict,
    memories: list[dict],
    theme: str | None = None,
    feedback_scores: dict[str, int] | None = None,
) -> tuple[str, str, str]:
    """Build the full user prompt.

    Returns (prompt_text, personality_vibe, surprise_format).
    """
    favorites = profile.get("preferences", {}).get("favorite_themes", config.THEMES)
    chosen_theme = theme or _pick_context_aware_theme(context, favorites, feedback_scores)

    display_name = profile.get("display_name", profile.get("name", "Friend"))
    goals = profile.get("goals", [])
    details = profile.get("personal_details", {})

    # Pick a surprise format, avoiding recently used ones
    surprise_format = _pick_fresh_format()

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
            for mem in surprise_memories[:8]:
                parts.append(f"  - {mem['text'][:200]}")

            # Extract mentioned figures so the LLM avoids them explicitly
            _used_figures = _extract_figures(surprise_memories[:8])
            if _used_figures:
                parts.append("")
                parts.append(
                    f"People/figures already used (DO NOT use any of these again): "
                    f"{', '.join(_used_figures)}"
                )

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
