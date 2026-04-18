"""SurpriseSage — Standalone popup window (launched as subprocess).

Clean quote-card design:
- Minimal layout, maximum readability
- Smooth fade-in/out + progress bar
- Click anywhere to pause, click again to resume
- Scrollable for longer deep-dive text
"""

import json
import platform
import sys
from pathlib import Path

import customtkinter as ctk

sys.path.insert(0, str(Path(__file__).parent))
import config

# ── Layout constants ──────────────────────────────────────────────────────
POPUP_WIDTH = config.POPUP_WIDTH
POPUP_MIN_HEIGHT = 200
POPUP_MAX_HEIGHT = 600
POPUP_ALPHA = config.POPUP_ALPHA
POPUP_DURATION_MS = config.POPUP_DURATION_SEC * 1000
PROGRESS_TICK_MS = 40

# Pixel math for wraplength:
#   popup 460 - root padx 2×4=8 - card border 2 - scroll padx 2×12=24
#   - scrollbar ~18 - text padx 2×16=32 - extra safety 6 = 370px safe wrap
_TEXT_WRAP = 350
_TEXT_WRAP_DEEP = 340       # slightly less for deep dive (scrollbar always visible)

# ── Colors ────────────────────────────────────────────────────────────────
BG = "#0e0e14"
CARD = "#17171f"
CARD_MSG = "#1c1c26"
GOLD = "#e8b84b"
WHITE = "#f2efe8"
GRAY = "#9a9aa6"
DIM = "#55556a"
GREEN = "#1d7d55"
GREEN_H = "#25a06d"
DARK = "#2e2e3c"
DARK_H = "#3e3e50"
BLUE = "#2c4e72"
BLUE_H = "#3c6090"
BORDER = "#2c2c3c"
GLOW = "#342e4a"
PROG_BG = "#1e1e2c"
PAUSE = "#e07850"
COPIED = "#25a06d"

# ── Fonts ─────────────────────────────────────────────────────────────────
_MAC = platform.system() == "Darwin"
_DISPLAY = "SF Pro Display" if _MAC else "Segoe UI"
_TEXT = "SF Pro Text" if _MAC else "Segoe UI"
_MONO = "SF Mono" if _MAC else "Cascadia Code"


def _f(size: int, weight: str = "normal", fam: str | None = None) -> ctk.CTkFont:
    return ctk.CTkFont(family=fam or _DISPLAY, size=size, weight=weight)


def main() -> None:
    if len(sys.argv) < 3:
        print("Error: Missing arguments", file=sys.stderr)
        sys.exit(1)

    message = sys.argv[1]
    surprise_id = sys.argv[2]
    is_deep = surprise_id.startswith("deep_")
    duration = POPUP_DURATION_MS * 2 if is_deep else POPUP_DURATION_MS
    wrap = _TEXT_WRAP_DEEP if is_deep else _TEXT_WRAP

    state = {"elapsed_ms": 0, "paused": False, "sent": False}

    # ── Window ────────────────────────────────────────────────────────
    ctk.set_appearance_mode("dark")
    root = ctk.CTk()
    root.title("")
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.0)
    root.configure(fg_color=BG)
    root.geometry(f"{POPUP_WIDTH}x{POPUP_MIN_HEIGHT}+24+48")
    root.update_idletasks()

    # ── Card ──────────────────────────────────────────────────────────
    card = ctk.CTkFrame(root, corner_radius=16, fg_color=CARD,
                        border_width=1, border_color=GLOW)
    card.pack(fill="both", expand=True, padx=4, pady=4)

    # ── Header — clean: owl + title ··· copy icon ─────────────────────
    hdr = ctk.CTkFrame(card, fg_color="transparent")
    hdr.pack(fill="x", padx=20, pady=(14, 0))

    ctk.CTkLabel(hdr, text="\U0001f989", font=_f(18)).pack(side="left")

    title = "Surprise Sage  \u00b7  Deep Dive" if is_deep else "Surprise Sage"
    ctk.CTkLabel(hdr, text=title, font=_f(13, "bold"),
                 text_color=GOLD).pack(side="left", padx=(8, 0))

    # Copy icon — top right
    cp_lbl = ctk.CTkLabel(hdr, text="\U0001f4cb", font=_f(14),
                          text_color=DIM, cursor="hand2")
    cp_lbl.pack(side="right")

    # Hint label — reused for "copied", "held", "brewing..."
    hint = ctk.CTkLabel(card, text="", font=_f(10, fam=_MONO),
                        text_color=DIM, anchor="w")

    def _copy(event=None):
        root.clipboard_clear()
        root.clipboard_append(message)
        root.update()
        cp_lbl.configure(text="\u2713", text_color=COPIED)
        hint.configure(text="copied!", text_color=COPIED)
        root.after(1500, lambda: (
            cp_lbl.configure(text="\U0001f4cb", text_color=DIM),
            hint.configure(text=""),
        ))
    cp_lbl.bind("<Button-1>", _copy)

    # ── Gold line ─────────────────────────────────────────────────────
    bar = ctk.CTkFrame(card, fg_color=GOLD, height=1)
    bar.pack(fill="x", padx=20, pady=(10, 0))

    # ── Message area (scrollable) ─────────────────────────────────────
    scroll = ctk.CTkScrollableFrame(
        card, fg_color=CARD_MSG, corner_radius=10,
        scrollbar_button_color=BORDER, scrollbar_button_hover_color=DIM,
    )
    scroll.pack(fill="both", expand=True, padx=12, pady=(8, 0))

    # ── Parse greeting + body ─────────────────────────────────────────
    greeting = ""
    body = message
    if message.startswith("Hey "):
        parts = message.split("\n", 1)
        if len(parts) == 2:
            greeting = parts[0]
            body = parts[1].strip()
        elif "," in parts[0]:
            ci = parts[0].index(",")
            greeting = parts[0][:ci + 1]
            body = parts[0][ci + 1:].strip()

    if greeting:
        ctk.CTkLabel(
            scroll, text=greeting, font=_f(14, "bold"),
            text_color=GOLD, wraplength=wrap, justify="left", anchor="w",
        ).pack(padx=16, pady=(12, 0), anchor="w")

    body_lbl = ctk.CTkLabel(
        scroll, text=body, font=_f(14, fam=_TEXT),
        wraplength=wrap, justify="left", text_color=WHITE, anchor="nw",
    )
    body_lbl.pack(padx=(16, 20), pady=(6 if greeting else 12, 12), anchor="w", fill="x")

    # ── Hint (below message, above buttons) ───────────────────────────
    hint.pack(padx=20, pady=(3, 0), anchor="w")

    # ── Buttons ───────────────────────────────────────────────────────
    btns = ctk.CTkFrame(card, fg_color="transparent")
    btns.pack(fill="x", padx=16, pady=(6, 0))

    def fade_out(step=0):
        if step >= 10:
            try: root.destroy()
            except: pass
            return
        try:
            root.attributes("-alpha", max(POPUP_ALPHA * (1 - step / 10), 0))
            root.after(25, lambda: fade_out(step + 1))
        except:
            try: root.destroy()
            except: pass

    def send(score, reason=""):
        if state["sent"]:
            return
        state["sent"] = True
        d = {"surprise_id": surprise_id, "score": score}
        if reason:
            d["reason"] = reason
        print(json.dumps(d))
        sys.stdout.flush()
        if score == 1:
            _on_love()
        else:
            fade_out()

    def _on_love():
        for w in btns.winfo_children():
            w.pack_forget()
        ctk.CTkLabel(btns, text="\u2728  Glad you loved it!",
                     font=_f(12, "bold", _TEXT), text_color=GOLD).pack(side="left")
        if not is_deep:
            ctk.CTkButton(
                btns, text="Tell me more", width=110, height=28,
                corner_radius=14, font=_f(11, "bold", _TEXT),
                fg_color=BLUE, hover_color=BLUE_H, command=_deep,
            ).pack(side="left", padx=(10, 0))
        # Re-add close button so user can always dismiss
        ctk.CTkButton(
            btns, text="\u00d7", width=32, height=32, corner_radius=16,
            font=_f(14, fam=_TEXT), fg_color="transparent", hover_color="#242430",
            border_width=1, border_color=BORDER, text_color=GRAY, command=fade_out,
        ).pack(side="right")
        root.after(8000, fade_out)

    def _deep():
        if not state.get("deep_sent"):
            state["deep_sent"] = True
            print(json.dumps({"surprise_id": surprise_id, "action": "deep_dive",
                               "original_text": message}))
            sys.stdout.flush()
            hint.configure(text="brewing a deeper surprise...", text_color=GOLD)

    def _nah_reasons():
        if state["sent"]:
            return
        for w in btns.winfo_children():
            w.pack_forget()
        ctk.CTkLabel(btns, text="What missed?", font=_f(10, fam=_TEXT),
                     text_color=DIM).pack(side="left", padx=(0, 8))
        for lbl, r in [("Obvious", "too_obvious"), ("Knew it", "already_knew"), ("Off topic", "not_relevant")]:
            ctk.CTkButton(
                btns, text=lbl, width=68, height=26, corner_radius=13,
                font=_f(11, fam=_TEXT), fg_color=DARK, hover_color=DARK_H,
                command=lambda r=r: send(-1, r),
            ).pack(side="left", padx=(0, 4))
        # Re-add close button
        ctk.CTkButton(
            btns, text="\u00d7", width=32, height=26, corner_radius=13,
            font=_f(14, fam=_TEXT), fg_color="transparent", hover_color="#242430",
            border_width=1, border_color=BORDER, text_color=GRAY, command=fade_out,
        ).pack(side="right")

    # Primary buttons
    ctk.CTkButton(
        btns, text="\u2764\ufe0f  Love it", width=100, height=32, corner_radius=16,
        font=_f(12, "bold", _TEXT), fg_color=GREEN, hover_color=GREEN_H,
        command=lambda: send(1),
    ).pack(side="left", padx=(0, 6))

    ctk.CTkButton(
        btns, text="Nah", width=50, height=32, corner_radius=16,
        font=_f(12, fam=_TEXT), fg_color=DARK, hover_color=DARK_H,
        command=_nah_reasons,
    ).pack(side="left")

    ctk.CTkButton(
        btns, text="\u00d7", width=32, height=32, corner_radius=16,
        font=_f(14, fam=_TEXT), fg_color="transparent", hover_color="#242430",
        border_width=1, border_color=BORDER, text_color=GRAY, command=fade_out,
    ).pack(side="right")

    # ── Progress bar ──────────────────────────────────────────────────
    prog = ctk.CTkProgressBar(card, height=2, corner_radius=1,
                              fg_color=PROG_BG, progress_color=GOLD)
    prog.pack(fill="x", side="bottom", padx=16, pady=(8, 6))
    prog.set(1.0)

    # ── Tick ──────────────────────────────────────────────────────────
    def tick():
        if state["paused"]:
            root.after(PROGRESS_TICK_MS, tick)
            return
        state["elapsed_ms"] += PROGRESS_TICK_MS
        rem = max(0.0, 1.0 - state["elapsed_ms"] / duration)
        try: prog.set(rem)
        except: return
        if rem <= 0:
            fade_out()
        else:
            root.after(PROGRESS_TICK_MS, tick)

    # ── Pause toggle ──────────────────────────────────────────────────
    def toggle(event=None):
        if state["paused"]:
            state["paused"] = False
            prog.configure(progress_color=GOLD)
            hint.configure(text="")
            bar.configure(fg_color=GOLD)
        else:
            state["paused"] = True
            prog.configure(progress_color=PAUSE)
            hint.configure(text="click anywhere to resume", text_color=DIM)
            bar.configure(fg_color=PAUSE)

    # ── Finalize size ─────────────────────────────────────────────────
    root.update_idletasks()
    card.update_idletasks()
    h = max(POPUP_MIN_HEIGHT, min(card.winfo_reqheight() + 12, POPUP_MAX_HEIGHT))
    root.geometry(f"{POPUP_WIDTH}x{h}+24+48")

    for w in [card, hdr, body_lbl, hint, scroll]:
        w.bind("<Button-1>", toggle, add="+")
    if greeting:
        for ch in scroll.winfo_children():
            if isinstance(ch, ctk.CTkLabel) and ch.cget("text") == greeting:
                ch.bind("<Button-1>", toggle, add="+")
                break

    # ── Fade in ───────────────────────────────────────────────────────
    def fade_in(step=0):
        if step >= 12:
            try: root.attributes("-alpha", POPUP_ALPHA)
            except: pass
            root.after(150, tick)
            return
        try:
            root.attributes("-alpha", POPUP_ALPHA * step / 12)
            root.after(22, lambda: fade_in(step + 1))
        except: pass

    root.after(50, fade_in)
    root.mainloop()


if __name__ == "__main__":
    main()
