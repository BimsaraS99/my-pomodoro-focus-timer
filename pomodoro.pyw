"""
Pomodoro Timer  -  a tiny, lightweight floating desktop timer for Windows 11.

- Frameless floating widget you can drag anywhere on the monitor.
- Shows the countdown and the task ("what we need to do").
- Gear (settings) button opens a small settings window.
- Start / Pause / Reset / Skip controls.
- Work / Short break / Long break cycle with a session counter.
- Stays on top (toggleable), remembers its position and settings.
- Pure standard library: no external dependencies. Uses winsound for the
  end-of-session beep on Windows (silently skipped elsewhere).

Double-click the .exe (or this .pyw) to open it. It just runs while open and
closes when you press X - it does NOT auto-start with Windows.
"""

import os
import json
import tkinter as tk
from tkinter import font as tkfont

# Windows-only beep. Falls back to a silent no-op on other systems.
try:
    import winsound
    HAS_WINSOUND = True
except Exception:
    HAS_WINSOUND = False

APP_TITLE = "Pomodoro"

# ---- colours (clean flat dark theme) -----------------------------------
BG        = "#1f2230"   # widget background
PANEL     = "#282c3d"   # slightly lighter panel
TEXT      = "#f5f6fa"   # primary text
MUTED     = "#9aa0b4"   # secondary text
BTN       = "#343a52"   # button background
BTN_HOVER = "#3f4666"   # button hover
ACCENT = {              # accent per mode
    "work":  "#ff6b5e",
    "short": "#37c98b",
    "long":  "#4d89ff",
}
MODE_NAME = {"work": "FOCUS", "short": "SHORT BREAK", "long": "LONG BREAK"}

DEFAULTS = {
    "work_min": 25,
    "short_break_min": 5,
    "long_break_min": 15,
    "sessions_before_long": 4,
    "always_on_top": True,
    "sound": True,
    "auto_start": True,
    "opacity": 100,
    "task": "Focus",
    "pos_x": None,
    "pos_y": None,
}


def config_path():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    folder = os.path.join(base, "PomodoroTimer")
    try:
        os.makedirs(folder, exist_ok=True)
    except Exception:
        folder = os.path.expanduser("~")
    return os.path.join(folder, "settings.json")


def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(config_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        for k in DEFAULTS:
            if k in data:
                cfg[k] = data[k]
    except Exception:
        pass
    return cfg


def save_config(cfg):
    try:
        with open(config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


class PomodoroApp:
    def __init__(self, root):
        self.root = root
        self.cfg = load_config()

        self.mode = "work"          # work | short | long
        self.work_done = 0          # completed focus sessions
        self.remaining = self.cfg["work_min"] * 60
        self.running = False
        self._tick_job = None
        self.compact = False
        self._drag = {"x": 0, "y": 0}

        # window setup ---------------------------------------------------
        root.title(APP_TITLE)
        root.overrideredirect(True)              # frameless
        root.configure(bg=BG)
        self._apply_topmost()
        self._apply_opacity()

        # place at saved position, else near top-right
        self.root.update_idletasks()
        w, h = 250, 168
        if self.cfg["pos_x"] is not None and self.cfg["pos_y"] is not None:
            x, y = int(self.cfg["pos_x"]), int(self.cfg["pos_y"])
        else:
            sw = root.winfo_screenwidth()
            x, y = sw - w - 40, 60
        root.geometry(f"{w}x{h}+{x}+{y}")

        self._build_ui()
        self._refresh()

        # keyboard shortcut: space toggles start/pause
        root.bind("<space>", lambda e: self.toggle())
        root.protocol("WM_DELETE_WINDOW", self.close)

    # ---- fonts ---------------------------------------------------------
    def f(self, size, weight="normal"):
        return tkfont.Font(family="Segoe UI", size=size, weight=weight)

    def mono(self, size, weight="bold"):
        return tkfont.Font(family="Consolas", size=size, weight=weight)

    # ---- UI ------------------------------------------------------------
    def _build_ui(self):
        self.outer = tk.Frame(self.root, bg=BG, highlightthickness=1,
                              highlightbackground="#3a3f57")
        self.outer.pack(fill="both", expand=True)

        # top accent strip (also the drag handle) --------------------
        self.strip = tk.Frame(self.outer, bg=ACCENT[self.mode], height=4)
        self.strip.pack(fill="x", side="top")

        # header row -------------------------------------------------
        header = tk.Frame(self.outer, bg=BG)
        header.pack(fill="x", padx=10, pady=(6, 0))

        self.mode_lbl = tk.Label(header, text=MODE_NAME[self.mode], bg=BG,
                                 fg=ACCENT[self.mode], font=self.f(9, "bold"))
        self.mode_lbl.pack(side="left")

        self._icon_btn(header, "\u2715", self.close).pack(side="right")      # X
        self._icon_btn(header, "\u2013", self.minimize).pack(side="right")   # –
        self._icon_btn(header, "\u2699", self.open_settings).pack(side="right")  # gear

        # time -------------------------------------------------------
        self.time_lbl = tk.Label(self.outer, text="25:00", bg=BG, fg=TEXT,
                                 font=self.mono(40, "bold"))
        self.time_lbl.pack(pady=(0, 0))

        # task -------------------------------------------------------
        self.task_lbl = tk.Label(self.outer, text=self.cfg["task"], bg=BG,
                                 fg=MUTED, font=self.f(10), wraplength=228)
        self.task_lbl.pack(pady=(0, 4))

        # controls ---------------------------------------------------
        ctr = tk.Frame(self.outer, bg=BG)
        ctr.pack(pady=(0, 8))
        self.start_btn = self._text_btn(ctr, "Start", self.toggle, accent=True)
        self.start_btn.pack(side="left", padx=3)
        self._text_btn(ctr, "Reset", self.reset).pack(side="left", padx=3)
        self._text_btn(ctr, "Skip", self.skip).pack(side="left", padx=3)

        # make widget draggable by its body --------------------------
        for w in (self.outer, self.strip, header, self.mode_lbl,
                  self.time_lbl, self.task_lbl):
            w.bind("<Button-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)
            w.bind("<ButtonRelease-1>", self._drag_end)

    def _icon_btn(self, parent, ch, cmd):
        b = tk.Label(parent, text=ch, bg=BG, fg=MUTED, font=self.f(11),
                     cursor="hand2", padx=5)
        b.bind("<Button-1>", lambda e: cmd())
        b.bind("<Enter>", lambda e: b.config(fg=TEXT))
        b.bind("<Leave>", lambda e: b.config(fg=MUTED))
        return b

    def _text_btn(self, parent, label, cmd, accent=False):
        bg = ACCENT[self.mode] if accent else BTN
        b = tk.Label(parent, text=label, bg=bg, fg=TEXT, font=self.f(9, "bold"),
                     padx=12, pady=4, cursor="hand2")
        b._accent = accent
        b.bind("<Button-1>", lambda e: cmd())
        def enter(e):
            b.config(bg=self._btn_hover(b))
        def leave(e):
            b.config(bg=(ACCENT[self.mode] if b._accent else BTN))
        b.bind("<Enter>", enter)
        b.bind("<Leave>", leave)
        return b

    def _btn_hover(self, b):
        if b._accent:
            return self._lighten(ACCENT[self.mode])
        return BTN_HOVER

    @staticmethod
    def _lighten(hexcol, amt=20):
        r = min(255, int(hexcol[1:3], 16) + amt)
        g = min(255, int(hexcol[3:5], 16) + amt)
        bl = min(255, int(hexcol[5:7], 16) + amt)
        return f"#{r:02x}{g:02x}{bl:02x}"

    # ---- dragging ------------------------------------------------------
    def _drag_start(self, e):
        self._drag["x"] = e.x_root - self.root.winfo_x()
        self._drag["y"] = e.y_root - self.root.winfo_y()

    def _drag_move(self, e):
        x = e.x_root - self._drag["x"]
        y = e.y_root - self._drag["y"]
        self.root.geometry(f"+{x}+{y}")

    def _drag_end(self, e):
        self.cfg["pos_x"] = self.root.winfo_x()
        self.cfg["pos_y"] = self.root.winfo_y()
        save_config(self.cfg)

    # ---- timer logic ---------------------------------------------------
    def duration_for(self, mode):
        return {
            "work":  self.cfg["work_min"],
            "short": self.cfg["short_break_min"],
            "long":  self.cfg["long_break_min"],
        }[mode] * 60

    def toggle(self):
        self.running = not self.running
        if self.running:
            self.start_btn.config(text="Pause")
            self._schedule()
        else:
            self.start_btn.config(text="Start")
            self._cancel()

    def _schedule(self):
        self._cancel()
        self._tick_job = self.root.after(1000, self._tick)

    def _cancel(self):
        if self._tick_job:
            self.root.after_cancel(self._tick_job)
            self._tick_job = None

    def _tick(self):
        if not self.running:
            return
        if self.remaining > 0:
            self.remaining -= 1
            self._refresh()
            self._tick_job = self.root.after(1000, self._tick)
        else:
            self._session_complete()

    def _session_complete(self):
        self.running = False
        self._cancel()
        self._beep()
        if self.mode == "work":
            self.work_done += 1
            if self.work_done % max(1, self.cfg["sessions_before_long"]) == 0:
                self.mode = "long"
            else:
                self.mode = "short"
        else:
            self.mode = "work"
        self.remaining = self.duration_for(self.mode)
        self._recolor()
        self._refresh()
        if self.cfg["auto_start"]:
            self.running = True
            self.start_btn.config(text="Pause")
            self._schedule()
        else:
            self.start_btn.config(text="Start")

    def reset(self):
        self.running = False
        self._cancel()
        self.remaining = self.duration_for(self.mode)
        self.start_btn.config(text="Start")
        self._refresh()

    def skip(self):
        # jump straight to the next mode without beeping
        self.running = False
        self._cancel()
        if self.mode == "work":
            self.work_done += 1
            self.mode = "long" if self.work_done % max(1, self.cfg["sessions_before_long"]) == 0 else "short"
        else:
            self.mode = "work"
        self.remaining = self.duration_for(self.mode)
        self.start_btn.config(text="Start")
        self._recolor()
        self._refresh()

    def _beep(self):
        if self.cfg["sound"] and HAS_WINSOUND:
            try:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                pass

    # ---- rendering -----------------------------------------------------
    def _refresh(self):
        m, s = divmod(max(0, self.remaining), 60)
        if self.compact:
            self.compact_lbl.config(text=f"{m:02d}:{s:02d}",
                                    fg=ACCENT[self.mode])
        else:
            self.time_lbl.config(text=f"{m:02d}:{s:02d}")
            self.mode_lbl.config(text=f"{MODE_NAME[self.mode]}  \u00b7  #{self.work_done + (1 if self.mode=='work' else 0)}")
            self.task_lbl.config(text=self.cfg["task"] if self.mode == "work" else "Take a break")

    def _recolor(self):
        col = ACCENT[self.mode]
        self.strip.config(bg=col)
        self.mode_lbl.config(fg=col)
        if self.start_btn._accent:
            self.start_btn.config(bg=col)

    # ---- compact (minimize) mode --------------------------------------
    def minimize(self):
        self.compact = True
        self.outer.pack_forget()
        self.root.geometry("110x40")
        self.compact_frame = tk.Frame(self.root, bg=BG, highlightthickness=1,
                                      highlightbackground="#3a3f57")
        self.compact_frame.pack(fill="both", expand=True)
        self.compact_lbl = tk.Label(self.compact_frame, text="", bg=BG,
                                    fg=ACCENT[self.mode], font=self.mono(16, "bold"))
        self.compact_lbl.pack(side="left", padx=(10, 4), pady=6)
        exp = tk.Label(self.compact_frame, text="\u2b1c", bg=BG, fg=MUTED,
                       font=self.f(9), cursor="hand2")
        exp.pack(side="right", padx=(0, 8))
        exp.bind("<Button-1>", lambda e: self.restore())
        for w in (self.compact_frame, self.compact_lbl):
            w.bind("<Button-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)
            w.bind("<ButtonRelease-1>", self._drag_end)
        self._refresh()

    def restore(self):
        self.compact = False
        self.compact_frame.destroy()
        self.root.geometry("250x168")
        self.outer.pack(fill="both", expand=True)
        self._refresh()

    # ---- window attributes --------------------------------------------
    def _apply_topmost(self):
        try:
            self.root.attributes("-topmost", bool(self.cfg["always_on_top"]))
        except Exception:
            pass

    def _apply_opacity(self):
        try:
            self.root.attributes("-alpha", max(30, min(100, self.cfg["opacity"])) / 100.0)
        except Exception:
            pass

    def close(self):
        self.cfg["pos_x"] = self.root.winfo_x()
        self.cfg["pos_y"] = self.root.winfo_y()
        save_config(self.cfg)
        self.root.destroy()

    # ---- settings window ----------------------------------------------
    def open_settings(self):
        if getattr(self, "_settings_win", None) and tk.Toplevel.winfo_exists(self._settings_win):
            self._settings_win.lift()
            return
        win = tk.Toplevel(self.root)
        self._settings_win = win
        win.title("Settings")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.attributes("-topmost", True)
        # place next to the widget
        win.geometry(f"+{self.root.winfo_x()}+{self.root.winfo_y() + 180}")

        pad = {"padx": 12, "pady": 4}
        vars_ = {}

        def row(label, key, frm=0, to=180):
            fr = tk.Frame(win, bg=BG)
            fr.pack(fill="x", **pad)
            tk.Label(fr, text=label, bg=BG, fg=TEXT, font=self.f(9),
                     width=20, anchor="w").pack(side="left")
            v = tk.IntVar(value=self.cfg[key])
            vars_[key] = v
            tk.Spinbox(fr, from_=frm, to=to, textvariable=v, width=6,
                       font=self.f(9), justify="center").pack(side="right")

        tk.Label(win, text="TIMER", bg=BG, fg=MUTED,
                 font=self.f(8, "bold")).pack(anchor="w", padx=12, pady=(10, 0))
        row("Focus (minutes)", "work_min", 1, 180)
        row("Short break (min)", "short_break_min", 1, 60)
        row("Long break (min)", "long_break_min", 1, 120)
        row("Sessions before long", "sessions_before_long", 1, 12)

        tk.Label(win, text="TASK", bg=BG, fg=MUTED,
                 font=self.f(8, "bold")).pack(anchor="w", padx=12, pady=(10, 0))
        tfr = tk.Frame(win, bg=BG)
        tfr.pack(fill="x", **pad)
        task_var = tk.StringVar(value=self.cfg["task"])
        tk.Entry(tfr, textvariable=task_var, font=self.f(9)).pack(fill="x")

        tk.Label(win, text="OPTIONS", bg=BG, fg=MUTED,
                 font=self.f(8, "bold")).pack(anchor="w", padx=12, pady=(10, 0))
        top_var   = tk.BooleanVar(value=self.cfg["always_on_top"])
        snd_var   = tk.BooleanVar(value=self.cfg["sound"])
        auto_var  = tk.BooleanVar(value=self.cfg["auto_start"])

        def check(text, var):
            tk.Checkbutton(win, text=text, variable=var, bg=BG, fg=TEXT,
                           selectcolor=PANEL, activebackground=BG,
                           activeforeground=TEXT, font=self.f(9),
                           highlightthickness=0, bd=0).pack(anchor="w", padx=10)
        check("Always on top", top_var)
        check("Play sound when a session ends", snd_var)
        check("Auto-start next session", auto_var)

        ofr = tk.Frame(win, bg=BG)
        ofr.pack(fill="x", **pad)
        tk.Label(ofr, text="Opacity %", bg=BG, fg=TEXT, font=self.f(9),
                 width=20, anchor="w").pack(side="left")
        op_var = tk.IntVar(value=self.cfg["opacity"])
        tk.Scale(ofr, from_=30, to=100, orient="horizontal", variable=op_var,
                 bg=BG, fg=TEXT, troughcolor=PANEL, highlightthickness=0,
                 length=120).pack(side="right")

        def apply_and_close():
            for k, v in vars_.items():
                try:
                    self.cfg[k] = int(v.get())
                except Exception:
                    pass
            self.cfg["task"] = task_var.get().strip() or "Focus"
            self.cfg["always_on_top"] = bool(top_var.get())
            self.cfg["sound"] = bool(snd_var.get())
            self.cfg["auto_start"] = bool(auto_var.get())
            self.cfg["opacity"] = int(op_var.get())
            save_config(self.cfg)
            self._apply_topmost()
            self._apply_opacity()
            # if idle, refresh remaining to new duration
            if not self.running:
                self.remaining = self.duration_for(self.mode)
            self._refresh()
            win.destroy()

        btns = tk.Frame(win, bg=BG)
        btns.pack(fill="x", padx=12, pady=12)
        save_b = tk.Label(btns, text="Save", bg=ACCENT["work"], fg=TEXT,
                          font=self.f(9, "bold"), padx=16, pady=5, cursor="hand2")
        save_b.pack(side="right")
        save_b.bind("<Button-1>", lambda e: apply_and_close())
        cancel_b = tk.Label(btns, text="Cancel", bg=BTN, fg=TEXT,
                            font=self.f(9, "bold"), padx=14, pady=5, cursor="hand2")
        cancel_b.pack(side="right", padx=6)
        cancel_b.bind("<Button-1>", lambda e: win.destroy())


def main():
    root = tk.Tk()
    PomodoroApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
