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
    on_deep_dive: Callable[[str], None] | None = None,
) -> None:
    """
    Launch the CustomTkinter popup as a separate process.
    This avoids Tkinter conflicts with rumps (menu bar).
    Feedback is returned via stdout as JSON (may be multiple lines).
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
                stdout, stderr = proc.communicate(timeout=config.POPUP_DURATION_SEC + 30)

                if stdout:
                    for line in stdout.strip().splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        # Handle deep dive request
                        if data.get("action") == "deep_dive" and on_deep_dive:
                            original = data.get("original_text", message)
                            on_deep_dive(original)
                            logger.info("Deep dive requested for surprise %s", surprise_id[:8])
                            continue

                        # Handle feedback
                        sid = data.get("surprise_id")
                        score = data.get("score")
                        reason = data.get("reason", "")
                        if sid and score is not None:
                            on_feedback(sid, score)
                            reason_log = f" (reason: {reason})" if reason else ""
                            logger.info(
                                "Feedback received: %+d for surprise %s%s",
                                score, sid[:8], reason_log,
                            )
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