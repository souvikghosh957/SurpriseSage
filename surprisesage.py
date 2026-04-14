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


def _check_ollama() -> bool:
    """Quick health check for Ollama."""
    try:
        import ollama
        ollama.list()
        return True
    except Exception:
        return False


def main() -> None:
    setup_logging()
    logger.info("🚀 SurpriseSage starting up...")

    # ── Profile validation ───────────────────────────────────────────────
    if not profile_exists():
        print("❌ No user profile found.")
        print("   Run:  python onboarding.py")
        sys.exit(1)

    profile = load_profile()
    user_name = profile.get("display_name", profile.get("name", "Friend"))
    logger.info("✅ Profile loaded for '%s' (id=%s)", user_name, profile["user_id"])

    # ── Ollama check ─────────────────────────────────────────────────────
    if not _check_ollama():
        logger.warning(
            "⚠️  Ollama is not reachable. Surprises will use fallback messages. "
            "Start Ollama with: ollama serve"
        )

    # ── Core components ──────────────────────────────────────────────────
    memory = MemoryStore(profile["user_id"])

    # Create scheduler first
    def trigger_surprise() -> None:
        try:
            context = get_active_context()

            if context.get("is_fullscreen"):
                logger.info("Skipping surprise (user in fullscreen)")
                return

            memories = memory.get_relevant_memories(
                context.get("friendly_label", "general wisdom")
            )

            prompt = build_surprise_prompt(profile, context, memories)
            text, surprise_id = generate_surprise(prompt, profile)

            # Save to memory
            memory.save_memory(
                text=text,
                category="surprise",
                metadata={"surprise_id": surprise_id},
            )

            def on_feedback(sid: str, score: int) -> None:
                memory.save_feedback(sid, score, text)

            # Show popup
            show_popup(text, surprise_id, on_feedback)

            # Add to tray recent list
            tray.add_surprise(text)

            logger.info("✅ Surprise delivered: %s...", text[:70])

        except Exception:
            logger.exception("❌ Surprise pipeline failed")

    # Scheduler
    scheduler = SurpriseScheduler(
        trigger_callback=trigger_surprise,
        profile=profile,
    )

    # Tray (created after scheduler so we can pass it)
    tray = SurpriseSageTray(
        scheduler=scheduler,
        on_reload=lambda: _reload_profile(profile, scheduler, memory),
        on_reshow=lambda text: show_popup(text, "reshow", lambda _s, _sc: None),
    )

    # Wire cleanup
    scheduler._cleanup_stub = memory.run_cleanup

    # Start everything
    scheduler.start()

    logger.info("✅ SurpriseSage is now running! Look for the 🦉 in your menu bar.")
    tray.run()   # This blocks forever


def _reload_profile(current_profile: dict, scheduler: SurpriseScheduler, memory: MemoryStore) -> None:
    """Hot-reload the user profile."""
    try:
        new_profile = load_profile()
        scheduler.reload_profile(new_profile)
        logger.info("✅ Profile hot-reloaded successfully")
    except Exception:
        logger.exception("Failed to reload profile")


if __name__ == "__main__":
    main()