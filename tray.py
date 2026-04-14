"""SurpriseSage — macOS menu bar (system tray) application."""

import logging
from collections import deque
from datetime import datetime
from typing import Callable, Optional

import rumps

from scheduler import SurpriseScheduler

logger = logging.getLogger("surprisesage.tray")


class SurpriseSageTray(rumps.App):
    """Menu bar controller for SurpriseSage."""

    def __init__(
        self,
        scheduler: SurpriseScheduler,
        on_reload: Optional[Callable] = None,
        on_reshow: Optional[Callable[[str], None]] = None,
    ) -> None:
        super().__init__(
            name="SurpriseSage",
            title="🦉",
            quit_button=None,
        )

        self.scheduler = scheduler
        self.on_reload = on_reload
        self.on_reshow = on_reshow
        self._paused = False

        self._recent: deque[tuple[str, str]] = deque(maxlen=10)
        self._recent_menu = rumps.MenuItem("Recent Surprises")

        self.menu = [
            rumps.MenuItem("Next Surprise Now", callback=self._next_surprise),
            self._recent_menu,
            None,
            rumps.MenuItem("Pause Surprises", callback=self._toggle_pause),
            None,
            rumps.MenuItem("Reload Profile", callback=self._reload_profile),
            None,
            rumps.MenuItem("Quit SurpriseSage", callback=self._quit),
        ]

        # Safe initial build
        self._rebuild_recent_menu()

    def add_surprise(self, text: str) -> None:
        """Add a new surprise to the recent list and refresh the menu."""
        timestamp = datetime.now().strftime("%H:%M")
        self._recent.appendleft((timestamp, text))
        self._rebuild_recent_menu()

    def _rebuild_recent_menu(self) -> None:
        """Safely rebuild the Recent Surprises submenu."""
        # Safe way to clear rumps submenu
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

    # ── Menu Actions ─────────────────────────────────────────────────────

    def _next_surprise(self, _sender) -> None:
        logger.info("Menu: Manual 'Next Surprise' triggered")
        self.scheduler.trigger_now()

    def _toggle_pause(self, sender: rumps.MenuItem) -> None:
        if self._paused:
            self.scheduler.resume()
            sender.title = "Pause Surprises"
            self._paused = False
            logger.info("Menu: Scheduler resumed")
        else:
            self.scheduler.pause()
            sender.title = "Resume Surprises"
            self._paused = True
            logger.info("Menu: Scheduler paused")

    def _reload_profile(self, _sender) -> None:
        if self.on_reload:
            self.on_reload()
            rumps.notification(
                title="SurpriseSage",
                subtitle="",
                message="✅ Profile reloaded successfully",
            )
            logger.info("Menu: Profile reloaded")

    def _quit(self, _sender) -> None:
        logger.info("Menu: Quit requested")
        self.scheduler.stop()
        rumps.quit_application()