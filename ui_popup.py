"""SurpriseSage — Popup launcher (separate process to avoid rumps/Tkinter conflicts)."""

import json
import logging
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable

import config

logger = logging.getLogger("surprisesage.popup")

# Path to the actual popup window script
_POPUP_SCRIPT = Path(__file__).parent / "_popup_window.py"


def show_popup(
    message: str,
    surprise_id: str,
    on_feedback: Callable[[str, int], None],
) -> None:
    """
    Launch the CustomTkinter popup as a separate process.
    This avoids Tkinter conflicts with rumps (menu bar).
    Feedback is returned via stdout as JSON.
    """
    try:
        proc = subprocess.Popen(
            [
                sys.executable,
                str(_POPUP_SCRIPT),
                message,
                surprise_id,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        logger.debug("Popup process launched for surprise %s", surprise_id[:8])

        # Listen for feedback in background thread
        def _listen_for_feedback() -> None:
            try:
                stdout, stderr = proc.communicate(timeout=config.POPUP_DURATION_SEC + 15)

                if stdout:
                    try:
                        data = json.loads(stdout.strip())
                        sid = data.get("surprise_id")
                        score = data.get("score")
                        if sid and score is not None:
                            on_feedback(sid, score)
                            logger.info("Feedback received: %+d for surprise %s", score, sid[:8])
                    except json.JSONDecodeError:
                        logger.debug("Popup closed without button feedback (dismissed)")
                else:
                    logger.debug("Popup timed out or was dismissed")

            except subprocess.TimeoutExpired:
                proc.kill()
                logger.debug("Popup process killed after timeout")
            except Exception:
                logger.exception("Error while waiting for popup feedback")

        threading.Thread(target=_listen_for_feedback, daemon=True).start()

    except Exception:
        logger.exception("Failed to launch popup")
        # Fallback to native notification
        show_notification(message, surprise_id, on_feedback)


def show_notification(
    message: str,
    surprise_id: str,
    on_feedback: Callable[[str, int], None],
) -> None:
    """Fallback: Show native macOS notification."""
    try:
        import rumps
        rumps.notification(
            title="SurpriseSage",
            subtitle="",
            message=message[:120],
        )
        logger.info("Native notification shown as popup fallback")
    except Exception:
        logger.exception("Failed to show native notification")