"""SurpriseSage — Standalone popup window (launched as subprocess).

Top-left popup with:
- Smooth fade-in/out + progress bar countdown
- Click anywhere to pause/hold, click again to resume
- Owl mascot header with gold accent
- Feedback buttons
"""

import json
import sys

import customtkinter as ctk

# ── Configuration ─────────────────────────────────────────────────────────
POPUP_DURATION_MS = 18000       # 18 seconds
POPUP_WIDTH = 420
POPUP_MIN_HEIGHT = 220
POPUP_MAX_HEIGHT = 440
POPUP_ALPHA = 0.96
PROGRESS_TICK_MS = 40           # smooth progress bar update

# ── Colors ────────────────────────────────────────────────────────────────
BG_DARK = "#0f0f14"
BG_CARD = "#1a1a24"
ACCENT_GOLD = "#d4a34a"
TEXT_PRIMARY = "#ede9e3"
TEXT_SECONDARY = "#9a9a9a"
TEXT_MUTED = "#5a5a66"
BTN_POSITIVE = "#2d6a4f"
BTN_POSITIVE_HOVER = "#40916c"
BTN_NEGATIVE = "#3a3a44"
BTN_NEGATIVE_HOVER = "#52525e"
PROGRESS_BG = "#22222c"
PROGRESS_FG = ACCENT_GOLD
PAUSED_COLOR = "#e07850"        # warm orange when held


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
    root.attributes("-alpha", 0.0)  # invisible for fade-in
    root.configure(fg_color=BG_DARK)

    # ── Position: top-LEFT ────────────────────────────────────────────
    x_pos = 24
    y_pos = 48
    root.geometry(f"{POPUP_WIDTH}x{POPUP_MIN_HEIGHT}+{x_pos}+{y_pos}")
    root.update_idletasks()

    # ── Main card ─────────────────────────────────────────────────────
    card = ctk.CTkFrame(
        root,
        corner_radius=16,
        fg_color=BG_CARD,
        border_width=1,
        border_color="#28283a",
    )
    card.pack(fill="both", expand=True, padx=5, pady=5)

    # ── Header: owl + name + status ───────────────────────────────────
    header = ctk.CTkFrame(card, fg_color="transparent")
    header.pack(fill="x", padx=20, pady=(14, 0))

    ctk.CTkLabel(
        header,
        text="\U0001f989",
        font=ctk.CTkFont(size=22),
    ).pack(side="left")

    ctk.CTkLabel(
        header,
        text="SurpriseSage",
        font=ctk.CTkFont(size=13, weight="bold"),
        text_color=ACCENT_GOLD,
    ).pack(side="left", padx=(8, 0))

    status_label = ctk.CTkLabel(
        header,
        text="just now",
        font=ctk.CTkFont(size=11),
        text_color=TEXT_MUTED,
    )
    status_label.pack(side="right")

    # ── Separator ─────────────────────────────────────────────────────
    ctk.CTkFrame(card, fg_color="#28283a", height=1).pack(
        fill="x", padx=18, pady=(10, 0)
    )

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
            card,
            text=greeting,
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=ACCENT_GOLD,
            anchor="w",
        ).pack(padx=22, pady=(12, 0), anchor="w")

    body_label = ctk.CTkLabel(
        card,
        text=body,
        font=ctk.CTkFont(size=14),
        wraplength=POPUP_WIDTH - 70,
        justify="left",
        text_color=TEXT_PRIMARY,
        anchor="nw",
    )
    body_label.pack(
        padx=22, pady=(6 if greeting else 12, 0), anchor="w", fill="both", expand=True
    )

    # ── Pause hint (shown when hovered / held) ────────────────────────
    hint_label = ctk.CTkLabel(
        card,
        text="",
        font=ctk.CTkFont(size=10),
        text_color=TEXT_MUTED,
        anchor="w",
    )
    hint_label.pack(padx=22, pady=(4, 0), anchor="w")

    # ── Buttons ───────────────────────────────────────────────────────
    btn_frame = ctk.CTkFrame(card, fg_color="transparent")
    btn_frame.pack(fill="x", padx=18, pady=(10, 0))

    def fade_out(step: int = 0) -> None:
        steps = 8
        if step >= steps:
            try:
                root.destroy()
            except Exception:
                pass
            return
        alpha = POPUP_ALPHA * (1 - step / steps)
        try:
            root.attributes("-alpha", max(alpha, 0))
            root.after(30, lambda: fade_out(step + 1))
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
        width=110,
        height=34,
        corner_radius=8,
        font=ctk.CTkFont(size=13, weight="bold"),
        fg_color=BTN_POSITIVE,
        hover_color=BTN_POSITIVE_HOVER,
        command=lambda: send_feedback(1),
    ).pack(side="left", padx=(0, 8))

    ctk.CTkButton(
        btn_frame,
        text="\U0001f44e  Nah",
        width=90,
        height=34,
        corner_radius=8,
        font=ctk.CTkFont(size=13),
        fg_color=BTN_NEGATIVE,
        hover_color=BTN_NEGATIVE_HOVER,
        command=lambda: send_feedback(-1),
    ).pack(side="left", padx=(0, 8))

    ctk.CTkButton(
        btn_frame,
        text="Dismiss",
        width=80,
        height=34,
        corner_radius=8,
        font=ctk.CTkFont(size=12),
        fg_color="transparent",
        hover_color="#2a2a34",
        border_width=1,
        border_color="#3a3a44",
        text_color=TEXT_SECONDARY,
        command=fade_out,
    ).pack(side="right")

    # ── Progress bar ──────────────────────────────────────────────────
    progress_bar = ctk.CTkProgressBar(
        card,
        height=3,
        corner_radius=0,
        fg_color=PROGRESS_BG,
        progress_color=PROGRESS_FG,
    )
    progress_bar.pack(fill="x", side="bottom", pady=(12, 0))
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
            # Resume
            state["paused"] = False
            progress_bar.configure(progress_color=PROGRESS_FG)
            status_label.configure(text="just now")
            hint_label.configure(text="")
        else:
            # Pause
            state["paused"] = True
            progress_bar.configure(progress_color=PAUSED_COLOR)
            status_label.configure(text="\u23f8 held", text_color=PAUSED_COLOR)
            hint_label.configure(
                text="click anywhere to resume",
                text_color=TEXT_MUTED,
            )

    # Bind click-to-hold on the card and all children
    def _bind_recursive(widget) -> None:
        widget.bind("<Button-1>", toggle_pause, add="+")
        for child in widget.winfo_children():
            _bind_recursive(child)

    # ── Compute height and finalize ───────────────────────────────────
    root.update_idletasks()
    card.update_idletasks()

    req_h = card.winfo_reqheight() + 14  # card padding
    total_h = max(POPUP_MIN_HEIGHT, min(req_h, POPUP_MAX_HEIGHT))
    root.geometry(f"{POPUP_WIDTH}x{total_h}+{x_pos}+{y_pos}")

    # Bind pause AFTER layout so buttons still get their own clicks first
    # We bind on card background and non-button widgets
    for widget in [card, header, body_label, hint_label]:
        widget.bind("<Button-1>", toggle_pause, add="+")
    if greeting:
        # greeting label is packed in card — find it
        for child in card.winfo_children():
            if isinstance(child, ctk.CTkLabel) and child.cget("text") == greeting:
                child.bind("<Button-1>", toggle_pause, add="+")
                break

    # ── Fade in ───────────────────────────────────────────────────────
    def fade_in(step: int = 0) -> None:
        steps = 10
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
            root.after(25, lambda: fade_in(step + 1))
        except Exception:
            pass

    root.after(50, fade_in)
    root.mainloop()


if __name__ == "__main__":
    main()
