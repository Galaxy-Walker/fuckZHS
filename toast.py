#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A small bottom-right notification window, imitating a Windows toast.

This is intentionally a separate process: the main script can keep waiting for
the captcha while this window is shown.  It uses only the standard library.
"""
import argparse
import sys
import webbrowser

try:
    import tkinter as tk
except Exception:  # tkinter may be missing in some minimal Python builds
    tk = None


COLORS = {
    "info": "#0078d4",
    "warning": "#f7a600",
    "error": "#c42b1c",
    "success": "#107c10",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Show a bottom-right toast")
    parser.add_argument("--title", default="通知")
    parser.add_argument("--message", default="")
    parser.add_argument("--url", default="")
    parser.add_argument("--duration", type=float, default=20)
    parser.add_argument("--kind", default="info", choices=sorted(COLORS))
    parser.add_argument("--width", type=int, default=400)
    parser.add_argument("--height", type=int, default=150)
    return parser.parse_args()


def main():
    args = parse_args()
    if tk is None:
        print("tkinter is not available", file=sys.stderr)
        return 1

    root = tk.Tk()
    root.title(args.title)
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    try:
        root.attributes("-alpha", 0.97)
    except Exception:
        pass

    bg = "#202020"
    fg = "#ffffff"
    muted = "#c8c8c8"
    panel = "#2b2b2b"
    accent = COLORS.get(args.kind, COLORS["info"])

    root.configure(bg=bg)
    root.geometry(f"{args.width}x{args.height}")

    # left accent bar
    tk.Frame(root, bg=accent, width=5).pack(side="left", fill="y")

    content = tk.Frame(root, bg=bg, padx=14, pady=12)
    content.pack(side="left", fill="both", expand=True)

    title = tk.Label(
        content, text=args.title, bg=bg, fg=fg, anchor="w",
        font=("Microsoft YaHei UI", 11, "bold"),
    )
    title.pack(fill="x")

    message = tk.Label(
        content, text=args.message, bg=bg, fg=muted, anchor="nw",
        justify="left", wraplength=args.width - 50,
        font=("Microsoft YaHei UI", 9),
    )
    message.pack(fill="both", expand=True, pady=(6, 8))

    buttons = tk.Frame(content, bg=bg)
    buttons.pack(fill="x", side="bottom")

    def close():
        try:
            root.destroy()
        except Exception:
            pass

    def open_url():
        try:
            webbrowser.open(args.url)
        except Exception:
            pass
        close()

    def make_button(text, command):
        return tk.Button(
            buttons, text=text, command=command,
            bg=panel, fg=fg, activebackground="#3a3a3a", activeforeground=fg,
            relief="flat", bd=0, padx=10, pady=3, cursor="hand2",
            font=("Microsoft YaHei UI", 9),
        )

    if args.url:
        make_button("打开课程页", open_url).pack(side="right", padx=(6, 0))
    make_button("关闭", close).pack(side="right")

    root.update_idletasks()
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    x = max(0, screen_w - args.width - 24)
    # leave room for the taskbar
    y = max(0, screen_h - args.height - 72)
    root.geometry(f"{args.width}x{args.height}+{x}+{y}")

    if args.duration and args.duration > 0:
        root.after(int(args.duration * 1000), close)

    try:
        root.mainloop()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
