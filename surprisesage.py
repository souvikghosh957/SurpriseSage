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

            if context.get("is_fullscreen"):
                logger.info("Skipping surprise (user in fullscreen)")
                return

            memories = memory.get_relevant_memories(
                context.get("friendly_label", "general wisdom")
            )

            prompt, vibe, fmt = build_surprise_prompt(p, context, memories, theme=theme)
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

            # Show popup
            show_popup(text, surprise_id, on_feedback)

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
