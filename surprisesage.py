"""SurpriseSage — Main Application Entry Point."""

import logging
import sys

import config
from config import setup_logging, load_profile, profile_exists

from context_detector import get_active_context
from memory import MemoryStore
from prompt_builder import build_surprise_prompt, generate_surprise
from scheduler import SurpriseScheduler
from tray import SurpriseSageTray
from ui_popup import show_popup

logger = logging.getLogger("surprisesage.main")


def _check_llm_provider(profile: dict) -> bool:
    """Quick health check for the configured LLM provider."""
    import llm_provider
    return llm_provider.check_provider_health(profile)


def main() -> None:
    setup_logging()
    logger.info("SurpriseSage starting up...")

    # ── Profile validation ───────────────────────────────────────────────
    if not profile_exists():
        print("No user profile found.")
        print("   Run:  python onboarding.py")
        sys.exit(1)

    # Wrap profile in a mutable container so hot-reload propagates to all closures
    state = {"profile": load_profile()}
    profile = state["profile"]
    user_name = profile.get("display_name", profile.get("name", "Friend"))
    logger.info("Profile loaded for '%s' (id=%s)", user_name, profile["user_id"])

    # ── LLM provider check ────────────────────────────────────────────────
    import llm_provider
    llm_cfg = llm_provider.get_llm_config(profile)
    if not _check_llm_provider(profile):
        if llm_cfg["provider"] == "ollama":
            logger.warning(
                "Ollama is not reachable. Surprises will use fallback messages. "
                "Start Ollama with: ollama serve"
            )
        else:
            logger.warning(
                "No API key found for provider '%s'. "
                "Set it in user_profile.json (llm.api_key) or as env var %s",
                llm_cfg["provider"],
                llm_provider._PROVIDER_ENV_KEY.get(llm_cfg["provider"], ""),
            )
    else:
        logger.info("LLM provider '%s' (model: %s) is ready",
                     llm_cfg["provider"], llm_cfg["model"])

    # ── Core components ──────────────────────────────────────────────────
    memory = MemoryStore(profile["user_id"])

    # ── Surprise pipeline ─────────────────────────────────────────────
    def trigger_surprise(theme: str | None = None) -> None:
        try:
            p = state["profile"]  # always use the latest reloaded profile
            context = get_active_context()

            if context.get("is_fullscreen") and not context.get("is_ide"):
                logger.info("Skipping surprise (user in fullscreen, non-IDE app)")
                return

            # Fetch context-based + theme-based memories and merge (dedup by text)
            context_memories = memory.get_relevant_memories(
                context.get("friendly_label", "general wisdom"),
                category_filter="surprise",
            )
            theme_query = (theme or "").replace("_", " ") or "general wisdom"
            theme_memories = memory.get_relevant_memories(
                theme_query, category_filter="surprise"
            )
            seen_texts = set()
            memories = []
            for m in context_memories + theme_memories:
                key = m["text"][:80]
                if key not in seen_texts:
                    seen_texts.add(key)
                    memories.append(m)

            feedback_scores = memory.get_feedback_summary()
            prompt, vibe, fmt = build_surprise_prompt(
                p, context, memories, theme=theme, feedback_scores=feedback_scores,
            )
            text, surprise_id = generate_surprise(prompt, p, vibe, fmt)

            # Save to memory
            memory.save_memory(
                text=text,
                category="surprise",
                metadata={"surprise_id": surprise_id},
            )

            def on_feedback(sid: str, score: int) -> None:
                memory.save_feedback(sid, score, text)
                tray.record_feedback(score)

            def on_deep_dive(original_text: str) -> None:
                """Generate a longer, deeper follow-up surprise."""
                try:
                    import llm_provider as llm
                    display_name = p.get("display_name", p.get("name", "Friend"))
                    deep_system = (
                        f"You are SurpriseSage. The user loved a surprise and wants the full story.\n\n"
                        f"Write 70-100 words. Tell the story behind the story — the human details, "
                        f"the struggles, the moments that gave people chills.\n\n"
                        f"LANGUAGE:\n"
                        f"- Short sentences. Simple words. Like telling a friend over chai.\n"
                        f"- 'use' not 'utilize'. 'old' not 'ancient'. 'trick' not 'mechanism'. "
                        f"'brain' not 'subconscious'.\n"
                        f"- BANNED: paradigm, catalyst, transcend, illuminate, resonate, endeavor, "
                        f"forge, testament, pivotal, embark, framework, fragment, circuit, "
                        f"harness, leverage, navigate, landscape, ecosystem, holistic.\n"
                        f"- Proper sentence case. No random caps.\n"
                        f"- End with a line that stays with {display_name}. Something inspiring "
                        f"and deeply personal — the kind of thought that lingers.\n\n"
                        f"Start with 'Hey {display_name},' — warm and personal."
                    )
                    deep_prompt = (
                        f"The user loved this and wants the full story:\n\n"
                        f'"{original_text}"\n\n'
                        f"Tell the real story behind this. The people, the moments, "
                        f"the details most people don't know. Simple words. "
                        f"End by connecting it to their life."
                    )
                    deep_text = llm.generate(deep_system, deep_prompt, p)
                    deep_text = deep_text.strip()
                    if deep_text and len(deep_text) > 20:
                        show_popup(deep_text, f"deep_{surprise_id}", lambda _s, _sc: None)
                        tray.add_surprise(deep_text)
                        memory.save_memory(text=deep_text, category="surprise",
                                           metadata={"surprise_id": f"deep_{surprise_id}", "type": "deep_dive"})
                except Exception:
                    logger.exception("Deep dive generation failed")

            # Show popup
            show_popup(text, surprise_id, on_feedback, on_deep_dive)

            # Add to tray recent list
            tray.add_surprise(text)

            logger.info("Surprise delivered: %s...", text[:70])

        except Exception:
            logger.exception("Surprise pipeline failed")

    # Scheduler (uses the no-theme version)
    scheduler = SurpriseScheduler(
        trigger_callback=lambda: trigger_surprise(),
        profile=profile,
    )

    # Tray
    tray = SurpriseSageTray(
        scheduler=scheduler,
        on_reload=lambda: _reload_profile(state, scheduler, memory),
        on_reshow=lambda text: show_popup(text, "reshow", lambda _s, _sc: None),
        on_themed_surprise=lambda theme: trigger_surprise(theme=theme),
        memory_stats=memory.get_stats,
        llm_info=llm_cfg,
    )

    # Wire cleanup
    scheduler._cleanup_stub = memory.run_cleanup

    # Start everything
    scheduler.start()

    logger.info("SurpriseSage is now running! Look for the owl in your menu bar.")
    tray.run()   # This blocks forever


def _reload_profile(state: dict, scheduler: SurpriseScheduler, memory: MemoryStore) -> None:
    """Hot-reload the user profile into the shared state container."""
    try:
        new_profile = load_profile()
        state["profile"] = new_profile  # updates for all closures
        scheduler.reload_profile(new_profile)
        logger.info("Profile hot-reloaded successfully")
    except Exception:
        logger.exception("Failed to reload profile")


if __name__ == "__main__":
    main()
