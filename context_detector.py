"""SurpriseSage — macOS context detection (active app, window title, fullscreen).

Uses native PyObjC (AppKit + Quartz) to detect what the user is doing.
Requires one-time macOS Accessibility permission for window titles.
"""

import logging
from typing import Dict

logger = logging.getLogger("surprisesage.context")

# Friendly human-readable labels for common apps
_APP_LABELS: Dict[str, str] = {
    # Browsers
    "Safari": "browsing the web",
    "Google Chrome": "browsing the web",
    "Firefox": "browsing the web",
    "Arc": "browsing the web",
    "Microsoft Edge": "browsing the web",

    # Code editors / IDEs
    "Code": "coding",
    "Visual Studio Code": "coding",
    "IntelliJ IDEA": "coding",
    "PyCharm": "coding",
    "Xcode": "coding",
    "Sublime Text": "coding",

    # Terminals
    "Terminal": "in the terminal",
    "iTerm2": "in the terminal",
    "Warp": "in the terminal",
    "Alacritty": "in the terminal",

    # Communication
    "Slack": "chatting on Slack",
    "Discord": "chatting on Discord",
    "Microsoft Teams": "in a Teams call or chat",
    "Zoom": "in a Zoom meeting",
    "FaceTime": "on a FaceTime call",

    # Media
    "Spotify": "listening to music",
    "Apple Music": "listening to music",
    "Music": "listening to music",
    "TV": "watching something",
    "VLC": "watching something",
    "IINA": "watching something",

    # Productivity
    "Notion": "working in Notion",
    "Obsidian": "writing notes",
    "Notes": "writing notes",
    "Figma": "designing",
    "Preview": "reading a document",

    # AI tools
    "Claude": "chatting with AI",
    "ChatGPT": "chatting with AI",
}


def get_friendly_label(app_name: str) -> str:
    """Return a short human-readable label for the current app."""
    if not app_name:
        return "hanging out on the Mac"
    return _APP_LABELS.get(app_name, f"using {app_name}")


_IDE_APPS = {
    "Code", "Visual Studio Code", "IntelliJ IDEA", "PyCharm",
    "WebStorm", "GoLand", "CLion", "Rider", "RubyMine",
    "PhpStorm", "DataGrip", "Android Studio", "Xcode",
    "Sublime Text", "Atom", "Cursor",
}


def get_active_context() -> Dict[str, str | bool]:
    """
    Return current context as a dict:
        {
            "app_name": str,
            "window_title": str,
            "is_fullscreen": bool,
            "is_ide": bool,
            "friendly_label": str
        }
    """
    result = {
        "app_name": "",
        "window_title": "",
        "is_fullscreen": False,
        "is_ide": False,
        "friendly_label": "hanging out on the Mac",
    }

    try:
        from AppKit import NSWorkspace, NSScreen
        from Quartz import (
            CGWindowListCopyWindowInfo,
            kCGWindowListOptionOnScreenOnly,
            kCGWindowListExcludeDesktopElements,
            kCGNullWindowID,
        )

        # 1. Active app
        active_app = NSWorkspace.sharedWorkspace().frontmostApplication()
        if active_app:
            app_name = active_app.localizedName() or ""
            result["app_name"] = app_name
            result["friendly_label"] = get_friendly_label(app_name)
            result["is_ide"] = app_name in _IDE_APPS

        # 2. Window title + fullscreen detection
        if active_app:
            pid = active_app.processIdentifier()
            screen = NSScreen.mainScreen()
            screen_w = screen.frame().size.width
            screen_h = screen.frame().size.height

            window_list = CGWindowListCopyWindowInfo(
                kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements,
                kCGNullWindowID,
            )

            for win in window_list or []:
                if win.get("kCGWindowOwnerPID") != pid:
                    continue

                # Window title (may be empty without Accessibility permission)
                title = win.get("kCGWindowName", "") or ""
                if title:
                    result["window_title"] = title[:80]   # truncate for privacy

                # Fullscreen check
                bounds = win.get("kCGWindowBounds", {})
                if bounds:
                    w = bounds.get("Width", 0)
                    h = bounds.get("Height", 0)
                    if abs(w - screen_w) < 5 and abs(h - screen_h) < 5:
                        result["is_fullscreen"] = True

                break  # only need the topmost window of the active app

    except Exception as e:
        logger.warning("Could not detect context (PyObjC issue): %s", e)

    return result