"""SurpriseSage — macOS menu bar (system tray) application."""

import logging
import threading
from collections import deque
from datetime import datetime
from typing import Callable, Optional

import rumps

import config
from scheduler import SurpriseScheduler

logger = logging.getLogger("surprisesage.tray")


class SurpriseSageTray(rumps.App):
    """Menu bar controller for SurpriseSage."""

    def __init__(
        self,
        scheduler: SurpriseScheduler,
        on_reload: Optional[Callable] = None,
        on_reshow: Optional[Callable[[str], None]] = None,
        on_themed_surprise: Optional[Callable[[str], None]] = None,
        memory_stats: Optional[Callable[[], dict]] = None,
    ) -> None:
        super().__init__(
            name="SurpriseSage",
            title="\U0001f989",
            quit_button=None,
        )

        self.scheduler = scheduler
        self.on_reload = on_reload
        self.on_reshow = on_reshow
        self.on_themed_surprise = on_themed_surprise
        self.memory_stats = memory_stats
        self._paused = False
        self._pause_timer: Optional[threading.Timer] = None

        self._recent: deque[tuple[str, str]] = deque(maxlen=10)
        self._surprise_count = 0
        self._feedback_pos = 0
        self._feedback_neg = 0

        # ── Submenus ──────────────────────────────────────────────────
        self._recent_menu = rumps.MenuItem("Recent Surprises")
        self._theme_menu = rumps.MenuItem("Surprise Me About...")
        self._pause_menu = rumps.MenuItem("Pause Surprises")

        # Build theme picker submenu
        for theme in config.THEMES:
            label = theme.replace("_", " ").title()

            def make_theme_cb(t: str):
                def cb(_sender):
                    if self.on_themed_surprise:
                        self.on_themed_surprise(t)
                    logger.info("Menu: Themed surprise requested — %s", t)
                return cb

            self._theme_menu.add(rumps.MenuItem(label, callback=make_theme_cb(theme)))

        # Build pause submenu
        self._pause_menu.add(rumps.MenuItem("Toggle Pause", callback=self._toggle_pause))
        self._pause_menu.add(None)
        self._pause_menu.add(rumps.MenuItem("Pause for 30 min", callback=lambda _: self._pause_for(30)))
        self._pause_menu.add(rumps.MenuItem("Pause for 1 hour", callback=lambda _: self._pause_for(60)))
        self._pause_menu.add(rumps.MenuItem("Pause for 3 hours", callback=lambda _: self._pause_for(180)))

        # ── Main menu ─────────────────────────────────────────────────
        self.menu = [
            rumps.MenuItem("Next Surprise Now", callback=self._next_surprise),
            self._theme_menu,
            self._recent_menu,
            None,
            self._pause_menu,
            None,
            rumps.MenuItem("Stats", callback=self._show_stats),
            rumps.MenuItem("Reload Profile", callback=self._reload_profile),
            None,
            rumps.MenuItem("Quit SurpriseSage", callback=self._quit),
        ]

        self._rebuild_recent_menu()

    # ── Surprise tracking ─────────────────────────────────────────────

    def add_surprise(self, text: str) -> None:
        """Add a new surprise to the recent list and refresh the menu."""
        timestamp = datetime.now().strftime("%H:%M")
        self._recent.appendleft((timestamp, text))
        self._surprise_count += 1
        self._rebuild_recent_menu()

    def record_feedback(self, score: int) -> None:
        """Track feedback counts for stats."""
        if score > 0:
            self._feedback_pos += 1
        elif score < 0:
            self._feedback_neg += 1

    def _rebuild_recent_menu(self) -> None:
        """Safely rebuild the Recent Surprises submenu."""
        for key in list(self._recent_menu.keys()):
            del self._recent_menu[key]

        if not self._recent:
            self._recent_menu.add(rumps.MenuItem("No surprises yet"))
            return

        for ts, text in self._recent:
            label = f"[{ts}] {text[:55]}..." if len(text) > 55 else f"[{ts}] {text}"

            def make_callback(full_text: str):
                def callback(_sender):
                    if self.on_reshow:
                        self.on_reshow(full_text)
                    else:
                        rumps.alert(title="SurpriseSage", message=full_text)
                return callback

            self._recent_menu.add(rumps.MenuItem(label, callback=make_callback(text)))

    # ── Menu Actions ──────────────────────────────────────────────────

    def _next_surprise(self, _sender) -> None:
        logger.info("Menu: Manual 'Next Surprise' triggered")
        self.scheduler.trigger_now()

    def _toggle_pause(self, _sender) -> None:
        if self._paused:
            self._cancel_pause_timer()
            self.scheduler.resume()
            self.title = "\U0001f989"
            self._paused = False
            logger.info("Menu: Scheduler resumed")
        else:
            self.scheduler.pause()
            self.title = "\U0001f989\u23f8"
            self._paused = True
            logger.info("Menu: Scheduler paused")

    def _pause_for(self, minutes: int) -> None:
        """Pause for a fixed duration, then auto-resume."""
        if not self._paused:
            self.scheduler.pause()
            self._paused = True

        self._cancel_pause_timer()
        self.title = f"\U0001f989 {minutes}m"

        def auto_resume():
            self.scheduler.resume()
            self._paused = False
            self.title = "\U0001f989"
            self._pause_timer = None
            logger.info("Menu: Auto-resumed after %d min pause", minutes)
            rumps.notification(
                title="SurpriseSage",
                subtitle="",
                message="Surprises resumed! Back in action.",
            )

        self._pause_timer = threading.Timer(minutes * 60, auto_resume)
        self._pause_timer.daemon = True
        self._pause_timer.start()
        logger.info("Menu: Paused for %d minutes", minutes)

    def _cancel_pause_timer(self) -> None:
        if self._pause_timer and self._pause_timer.is_alive():
            self._pause_timer.cancel()
            self._pause_timer = None

    def _show_stats(self, _sender) -> None:
        """Show quick stats in a native alert."""
        total = self._surprise_count
        loved = self._feedback_pos
        nah = self._feedback_neg
        dismissed = total - loved - nah

        mem_info = ""
        if self.memory_stats:
            try:
                stats = self.memory_stats()
                mem_info = f"\nMemories stored: {stats.get('total_memories', '?')}"
            except Exception:
                pass

        msg = (
            f"Surprises delivered: {total}\n"
            f"Loved: {loved}  |  Nah: {nah}  |  Dismissed: {dismissed}"
            f"{mem_info}\n\n"
            f"Session started: {datetime.now().strftime('%H:%M')}"
        )
        rumps.alert(title="SurpriseSage Stats", message=msg)

    def _reload_profile(self, _sender) -> None:
        if self.on_reload:
            self.on_reload()
            rumps.notification(
                title="SurpriseSage",
                subtitle="",
                message="Profile reloaded successfully",
            )
            logger.info("Menu: Profile reloaded")

    def _quit(self, _sender) -> None:
        logger.info("Menu: Quit requested")
        self._cancel_pause_timer()
        self.scheduler.stop()
        rumps.quit_application()
