"""SurpriseSage — APScheduler-based trigger engine."""

import logging
import random
from datetime import datetime, timedelta
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

import config

logger = logging.getLogger("surprisesage.scheduler")


def _parse_time(t: str) -> tuple[int, int]:
    """Parse 'HH:MM' into (hour, minute)."""
    h, m = t.strip().split(":")
    return int(h), int(m)


def _is_dnd_now(profile: dict) -> bool:
    """Check if current time falls within the DND window."""
    dnd = profile.get("schedule", {}).get("dnd", config.DND_DEFAULT)
    start_h, start_m = _parse_time(dnd["start"])
    end_h, end_m = _parse_time(dnd["end"])

    now = datetime.now()
    start = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    end = now.replace(hour=end_h, minute=end_m, second=0, microsecond=0)

    # Handle overnight DND (e.g., 23:00 → 07:00)
    if start > end:
        return now >= start or now <= end
    return start <= now <= end


class SurpriseScheduler:
    """Manages fixed-time and random Poisson surprise triggers."""

    def __init__(
        self,
        trigger_callback: Callable[[], None],
        profile: dict,
    ) -> None:
        self.trigger_callback = trigger_callback
        self.profile = profile
        self.paused = False
        self._scheduler = BackgroundScheduler()

    def _guarded_trigger(self) -> None:
        """Run the trigger callback only if not paused or in DND."""
        if self.paused:
            logger.debug("Trigger skipped: paused")
            return
        if _is_dnd_now(self.profile):
            logger.info("Trigger skipped: DND active")
            return
        self.trigger_callback()

    def _next_random_time(self) -> datetime:
        """Compute next random trigger time using Poisson (exponential)."""
        gap_hours = random.expovariate(1 / config.POISSON_MEAN_HOURS)
        gap_hours = max(gap_hours, config.MIN_RANDOM_GAP_MINUTES / 60)
        return datetime.now() + timedelta(hours=gap_hours)

    def _fire_random(self) -> None:
        """Fire a random surprise, then schedule the next one."""
        self._guarded_trigger()
        self._schedule_next_random()

    def _schedule_next_random(self) -> None:
        """Add a one-shot date trigger for the next random surprise."""
        next_time = self._next_random_time()
        self._scheduler.add_job(
            self._fire_random,
            trigger=DateTrigger(run_date=next_time),
            id="random_next",
            replace_existing=True,
        )
        logger.info("Next random surprise at %s", next_time.strftime("%H:%M"))

    def start(self) -> None:
        """Start the scheduler with fixed-time and random triggers."""
        # Fixed-time triggers from profile
        fixed_times = (
            self.profile.get("schedule", {}).get(
                "fixed_times", config.DEFAULT_FIXED_TIMES
            )
        )
        for t in fixed_times:
            h, m = _parse_time(t)
            self._scheduler.add_job(
                self._guarded_trigger,
                trigger=CronTrigger(hour=h, minute=m),
                id=f"fixed_{h:02d}{m:02d}",
                replace_existing=True,
            )
            logger.info("Fixed trigger at %02d:%02d", h, m)

        # First random trigger
        self._schedule_next_random()

        # Daily memory cleanup at 03:00
        self._scheduler.add_job(
            self._cleanup_stub,
            trigger=CronTrigger(hour=3, minute=0),
            id="daily_cleanup",
            replace_existing=True,
        )

        self._scheduler.start()
        logger.info("Scheduler started")

    def _cleanup_stub(self) -> None:
        """Placeholder — wired to MemoryStore.run_cleanup() from main."""
        pass  # overridden in surprisesage.py

    def trigger_now(self) -> None:
        """Immediately fire a surprise (for 'Next Surprise' menu item)."""
        logger.info("Manual trigger requested")
        self.trigger_callback()

    def pause(self) -> None:
        self.paused = True
        logger.info("Scheduler paused")

    def resume(self) -> None:
        self.paused = False
        logger.info("Scheduler resumed")

    def stop(self) -> None:
        self._scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")

    def reload_profile(self, profile: dict) -> None:
        """Hot-reload profile (e.g., after user edits JSON)."""
        self.profile = profile
        logger.info("Profile reloaded in scheduler")
