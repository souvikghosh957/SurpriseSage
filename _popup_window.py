"""SurpriseSage — Standalone popup window (launched as subprocess).

Premium-feel popup with:
- Smooth fade-in/out + progress bar countdown
- Click anywhere to pause/hold, click again to resume
- Clean typography with generous spacing
- Feedback buttons with modern pill design
"""

import json
import platform
import sys
from pathlib import Path

import customtkinter as ctk

# Import config for shared constants (popup runs as subprocess, so we import directly)
sys.path.insert(0, str(Path(__file__).parent))
import config

# ── Configuration (derived from config.py) ────────────────────────────────
POPUP_DURATION_MS = config.POPUP_DURATION_SEC * 1000
POPUP_WIDTH = config.POPUP_WIDTH
POPUP_ALPHA = config.POPUP_ALPHA
POPUP_MIN_HEIGHT = 240
POPUP_MAX_HEIGHT = 480
PROGRESS_TICK_MS = 40

# ── Colors — refined dark palette ─────────────────────────────────────────
BG_DARK = "#0c0c10"
BG_CARD = "#16161e"
BG_CARD_INNER = "#1c1c28"        # subtle inner surface for message area
ACCENT_GOLD = "#e8b84b"          # brighter, warmer gold
ACCENT_GOLD_DIM = "#c49a3a"      # muted gold for secondary text
TEXT_PRIMARY = "#f0ece4"          # warm off-white — easy on the eyes
TEXT_SECONDARY = "#a8a8b0"
TEXT_MUTED = "#5e5e6e"
BTN_POSITIVE = "#1a7a52"
BTN_POSITIVE_HOVER = "#22a06b"
BTN_NEGATIVE = "#32323e"
BTN_NEGATIVE_HOVER = "#48485a"
BORDER_SUBTLE = "#2a2a3a"
BORDER_GLOW = "#3a3550"          # faint purple-ish glow border
PROGRESS_BG = "#1e1e2a"
PROGRESS_FG = ACCENT_GOLD
PAUSED_COLOR = "#e07850"

# ── Font helpers ──────────────────────────────────────────────────────────
_IS_MAC = platform.system() == "Darwin"
# Use the best available sans-serif for each platform
FONT_FAMILY = "SF Pro Display" if _IS_MAC else "Segoe UI"
FONT_BODY = "SF Pro Text" if _IS_MAC else "Segoe UI"
FONT_MONO = "SF Mono" if _IS_MAC else "Cascadia Code"


def _font(size: int, weight: str = "normal", family: str | None = None) -> ctk.CTkFont:
    return ctk.CTkFont(family=family or FONT_FAMILY, size=size, weight=weight)


def main() -> None:
    if len(sys.argv) < 3:
        print("Error: Missing arguments", file=sys.stderr)
        sys.exit(1)

    message = sys.argv[1]
    surprise_id = sys.argv[2]

    # ── State ─────────────────────────────────────────────────────────
    state = {
        "elapsed_ms": 0,
        "paused": False,
        "feedback_sent": False,
    }

    # ── Window setup ──────────────────────────────────────────────────
    ctk.set_appearance_mode("dark")

    root = ctk.CTk()
    root.title("")
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.0)
    root.configure(fg_color=BG_DARK)

    # ── Position: top-LEFT ────────────────────────────────────────────
    x_pos = 24
    y_pos = 48
    root.geometry(f"{POPUP_WIDTH}x{POPUP_MIN_HEIGHT}+{x_pos}+{y_pos}")
    root.update_idletasks()

    # ── Main card ─────────────────────────────────────────────────────
    card = ctk.CTkFrame(
        root,
        corner_radius=18,
        fg_color=BG_CARD,
        border_width=1,
        border_color=BORDER_GLOW,
    )
    card.pack(fill="both", expand=True, padx=6, pady=6)

    # ── Header: owl + name + status ───────────────────────────────────
    header = ctk.CTkFrame(card, fg_color="transparent")
    header.pack(fill="x", padx=24, pady=(18, 0))

    ctk.CTkLabel(
        header,
        text="\U0001f989",
        font=_font(24),
    ).pack(side="left")

    # App name — use letter-spacing feel via slightly larger font
    ctk.CTkLabel(
        header,
        text="Surprise Sage",
        font=_font(14, "bold"),
        text_color=ACCENT_GOLD,
    ).pack(side="left", padx=(10, 0))

    status_label = ctk.CTkLabel(
        header,
        text="just now",
        font=_font(11, family=FONT_MONO),
        text_color=TEXT_MUTED,
    )
    status_label.pack(side="right")

    # ── Thin accent line ──────────────────────────────────────────────
    accent_bar = ctk.CTkFrame(card, fg_color=ACCENT_GOLD, height=1)
    accent_bar.pack(fill="x", padx=24, pady=(14, 0))

    # ── Message area with inner surface ───────────────────────────────
    msg_frame = ctk.CTkFrame(
        card,
        fg_color=BG_CARD_INNER,
        corner_radius=12,
    )
    msg_frame.pack(fill="both", expand=True, padx=16, pady=(12, 0))

    # ── Message: split greeting from body ─────────────────────────────
    greeting = ""
    body = message
    if message.startswith("Hey "):
        lines = message.split("\n", 1)
        if len(lines) == 2:
            greeting = lines[0]
            body = lines[1].strip()
        elif "," in lines[0]:
            comma_idx = lines[0].index(",")
            greeting = lines[0][: comma_idx + 1]
            body = lines[0][comma_idx + 1 :].strip()

    if greeting:
        ctk.CTkLabel(
            msg_frame,
            text=greeting,
            font=_font(16, "bold"),
            text_color=ACCENT_GOLD,
            anchor="w",
        ).pack(padx=16, pady=(14, 0), anchor="w")

    body_label = ctk.CTkLabel(
        msg_frame,
        text=body,
        font=_font(15, family=FONT_BODY),
        wraplength=POPUP_WIDTH - 90,
        justify="left",
        text_color=TEXT_PRIMARY,
        anchor="nw",
    )
    body_label.pack(
        padx=16, pady=(8 if greeting else 14, 14), anchor="w", fill="both", expand=True
    )

    # ── Pause hint (shown when held) ──────────────────────────────────
    hint_label = ctk.CTkLabel(
        card,
        text="",
        font=_font(10, family=FONT_MONO),
        text_color=TEXT_MUTED,
        anchor="w",
    )
    hint_label.pack(padx=24, pady=(6, 0), anchor="w")

    # ── Buttons — modern pill style ───────────────────────────────────
    btn_frame = ctk.CTkFrame(card, fg_color="transparent")
    btn_frame.pack(fill="x", padx=20, pady=(10, 0))

    def fade_out(step: int = 0) -> None:
        steps = 10
        if step >= steps:
            try:
                root.destroy()
            except Exception:
                pass
            return
        alpha = POPUP_ALPHA * (1 - step / steps)
        try:
            root.attributes("-alpha", max(alpha, 0))
            root.after(25, lambda: fade_out(step + 1))
        except Exception:
            try:
                root.destroy()
            except Exception:
                pass

    def send_feedback(score: int) -> None:
        if state["feedback_sent"]:
            return
        state["feedback_sent"] = True
        print(json.dumps({"surprise_id": surprise_id, "score": score}))
        sys.stdout.flush()
        fade_out()

    ctk.CTkButton(
        btn_frame,
        text="\u2764\ufe0f  Love it",
        width=115,
        height=36,
        corner_radius=18,
        font=_font(13, "bold", FONT_BODY),
        fg_color=BTN_POSITIVE,
        hover_color=BTN_POSITIVE_HOVER,
        command=lambda: send_feedback(1),
    ).pack(side="left", padx=(0, 8))

    ctk.CTkButton(
        btn_frame,
        text="\U0001f44e  Nah",
        width=90,
        height=36,
        corner_radius=18,
        font=_font(13, family=FONT_BODY),
        fg_color=BTN_NEGATIVE,
        hover_color=BTN_NEGATIVE_HOVER,
        command=lambda: send_feedback(-1),
    ).pack(side="left", padx=(0, 8))

    ctk.CTkButton(
        btn_frame,
        text="Dismiss",
        width=85,
        height=36,
        corner_radius=18,
        font=_font(12, family=FONT_BODY),
        fg_color="transparent",
        hover_color="#242430",
        border_width=1,
        border_color=BORDER_SUBTLE,
        text_color=TEXT_SECONDARY,
        command=fade_out,
    ).pack(side="right")

    # ── Progress bar — slim accent ────────────────────────────────────
    progress_bar = ctk.CTkProgressBar(
        card,
        height=2,
        corner_radius=1,
        fg_color=PROGRESS_BG,
        progress_color=PROGRESS_FG,
    )
    progress_bar.pack(fill="x", side="bottom", padx=18, pady=(14, 8))
    progress_bar.set(1.0)

    # ── Progress tick ─────────────────────────────────────────────────
    def tick() -> None:
        if state["paused"]:
            root.after(PROGRESS_TICK_MS, tick)
            return
        state["elapsed_ms"] += PROGRESS_TICK_MS
        remaining = max(0.0, 1.0 - state["elapsed_ms"] / POPUP_DURATION_MS)
        try:
            progress_bar.set(remaining)
        except Exception:
            return
        if remaining <= 0:
            fade_out()
        else:
            root.after(PROGRESS_TICK_MS, tick)

    # ── Click-to-hold / click-to-resume ───────────────────────────────
    def toggle_pause(event=None) -> None:
        if state["paused"]:
            state["paused"] = False
            progress_bar.configure(progress_color=PROGRESS_FG)
            status_label.configure(text="just now", text_color=TEXT_MUTED)
            hint_label.configure(text="")
            accent_bar.configure(fg_color=ACCENT_GOLD)
        else:
            state["paused"] = True
            progress_bar.configure(progress_color=PAUSED_COLOR)
            status_label.configure(text="\u23f8 held", text_color=PAUSED_COLOR)
            hint_label.configure(
                text="click anywhere to resume",
                text_color=TEXT_MUTED,
            )
            accent_bar.configure(fg_color=PAUSED_COLOR)

    # Bind click-to-hold on the card and all children
    def _bind_recursive(widget) -> None:
        widget.bind("<Button-1>", toggle_pause, add="+")
        for child in widget.winfo_children():
            _bind_recursive(child)

    # ── Compute height and finalize ───────────────────────────────────
    root.update_idletasks()
    card.update_idletasks()

    req_h = card.winfo_reqheight() + 16
    total_h = max(POPUP_MIN_HEIGHT, min(req_h, POPUP_MAX_HEIGHT))
    root.geometry(f"{POPUP_WIDTH}x{total_h}+{x_pos}+{y_pos}")

    # Bind pause AFTER layout so buttons still get their own clicks first
    for widget in [card, header, body_label, hint_label, msg_frame]:
        widget.bind("<Button-1>", toggle_pause, add="+")
    if greeting:
        for child in msg_frame.winfo_children():
            if isinstance(child, ctk.CTkLabel) and child.cget("text") == greeting:
                child.bind("<Button-1>", toggle_pause, add="+")
                break

    # ── Fade in ───────────────────────────────────────────────────────
    def fade_in(step: int = 0) -> None:
        steps = 12
        if step >= steps:
            try:
                root.attributes("-alpha", POPUP_ALPHA)
            except Exception:
                pass
            root.after(150, tick)
            return
        alpha = POPUP_ALPHA * (step / steps)
        try:
            root.attributes("-alpha", alpha)
            root.after(22, lambda: fade_in(step + 1))
        except Exception:
            pass

    root.after(50, fade_in)
    root.mainloop()


if __name__ == "__main__":
    main()
