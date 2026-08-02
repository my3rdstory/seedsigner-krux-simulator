#!/usr/bin/env python

import ctypes
import json
import logging
import os
import subprocess
import time
import tkinter as tk
import uuid
from ctypes import wintypes
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LOGS = ROOT / "logs"
STATE_FILE = ROOT / "panel-state.json"
WINDOW_TITLE = "SeedSigner + Krux"
MUTEX_NAME = "Local\\SeedSignerKruxSimulatorPanel"

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


class Rect(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

user32.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
user32.SetParent.restype = wintypes.HWND
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
user32.SetWindowPos.restype = wintypes.BOOL


def find_window(title, visible_only=False):
    result = []

    def visit(hwnd, _):
        length = user32.GetWindowTextLengthW(hwnd)
        if length:
            text = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, text, length + 1)
            if text.value == title and (not visible_only or user32.IsWindowVisible(hwnd)):
                result.append(hwnd)
                return False
        return True

    user32.EnumWindows(EnumWindowsProc(visit), 0)
    return result[0] if result else None


def show_window(hwnd):
    if hwnd:
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)


def work_area():
    rect = Rect()
    user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
    return rect


def embed_window(child_hwnd, owner_hwnd, x, y, width, height):
    gwl_style = -16
    gwl_exstyle = -20
    gwl_hwnd_parent = -8
    ws_popup = 0x80000000
    ws_visible = 0x10000000
    ws_clipchildren = 0x02000000
    ws_clipsiblings = 0x04000000
    decoration_styles = 0x00C00000 | 0x00040000 | 0x00080000 | 0x00020000 | 0x00010000
    ws_ex_appwindow = 0x00040000
    ws_ex_toolwindow = 0x00000080

    style = user32.GetWindowLongPtrW(child_hwnd, gwl_style)
    style = (style & ~decoration_styles & ~0x40000000) | ws_popup | ws_visible | ws_clipchildren | ws_clipsiblings
    user32.SetWindowLongPtrW(child_hwnd, gwl_style, style)

    exstyle = user32.GetWindowLongPtrW(child_hwnd, gwl_exstyle)
    exstyle = (exstyle & ~ws_ex_toolwindow) | ws_ex_appwindow
    user32.SetWindowLongPtrW(child_hwnd, gwl_exstyle, exstyle)

    # Keep the simulator as a normal borderless top-level window owned by the
    # panel. Tk and SDL retain their native mouse handling without SetParent.
    user32.SetWindowLongPtrW(child_hwnd, gwl_hwnd_parent, owner_hwnd)
    flags = 0x0020 | 0x0040
    user32.SetWindowPos(child_hwnd, 0, x, y, max(1, width), max(1, height), flags)
    user32.ShowWindow(child_hwnd, 8)


def resize_embedded_window(child_hwnd, x, y, width, height):
    flags = 0x0020 | 0x0040
    user32.SetWindowPos(child_hwnd, 0, x, y, max(1, width), max(1, height), flags)


def send_key(hwnd, virtual_key):
    if not hwnd:
        return
    user32.PostMessageW(hwnd, 0x0100, virtual_key, 0)
    user32.PostMessageW(hwnd, 0x0101, virtual_key, 0)


class Simulator:
    def __init__(self, name, title, command, working_directory, environment, log_prefix):
        self.name = name
        self.title = title
        self.command = command
        self.working_directory = working_directory
        self.environment = environment
        self.log_prefix = log_prefix
        self.process = None
        self.started_at = 0
        self.desired_on = True
        self.embedded_hwnd = None
        self.last_reported_hwnd = None
        self.stdout_handle = None
        self.stderr_handle = None

    @property
    def hwnd(self):
        if self.embedded_hwnd and user32.IsWindow(self.embedded_hwnd):
            if self.last_reported_hwnd != self.embedded_hwnd:
                self.last_reported_hwnd = self.embedded_hwnd
            return self.embedded_hwnd
        if self.last_reported_hwnd is not None:
            self.last_reported_hwnd = None
        self.embedded_hwnd = None
        hwnd = find_window(self.title)
        if hwnd:
            self.last_reported_hwnd = hwnd
        return hwnd

    @property
    def state(self):
        if self.hwnd and not self.desired_on:
            return "Stopping"
        if self.hwnd:
            return "On"
        if self.desired_on and time.monotonic() - self.started_at < 20:
            return "Starting"
        return "Off"

    def start(self):
        if self.hwnd:
            self.desired_on = True
            return

        self._close_logs()
        LOGS.mkdir(parents=True, exist_ok=True)
        self.stdout_handle = (LOGS / f"{self.log_prefix}-output.log").open("w", encoding="utf-8")
        self.stderr_handle = (LOGS / f"{self.log_prefix}-error.log").open("w", encoding="utf-8")
        self.process = subprocess.Popen(
            self.command,
            cwd=self.working_directory,
            env=self.environment,
            stdout=self.stdout_handle,
            stderr=self.stderr_handle,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self.started_at = time.monotonic()
        self.desired_on = True
        self.embedded_hwnd = None

    def stop(self):
        self.desired_on = False
        hwnd = self.hwnd
        if hwnd:
            user32.PostMessageW(hwnd, 0x0010, 0, 0)
        self.embedded_hwnd = None

    def close_logs(self):
        self._close_logs()

    def _close_logs(self):
        for handle_name in ("stdout_handle", "stderr_handle"):
            handle = getattr(self, handle_name)
            if handle:
                handle.close()
                setattr(self, handle_name, None)


class ApplicationPane:
    def __init__(self, parent, simulator, column, select_callback):
        self.simulator = simulator
        self.select_callback = select_callback
        self.frame = tk.Frame(
            parent,
            background="#17191b",
            highlightthickness=3,
            highlightbackground="#17191b",
            highlightcolor="#17191b",
        )
        self.frame.grid(row=0, column=column, sticky="nsew")
        self.frame.grid_rowconfigure(1, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)

        header = tk.Frame(self.frame, background="#202326", height=50)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.grid_columnconfigure(0, weight=1)
        header.bind("<Button-1>", lambda event: self.select_callback(self))

        title = tk.Label(
            header,
            text=simulator.name,
            background="#202326",
            foreground="#f2f2f2",
            font=("Segoe UI", 11, "bold"),
        )
        title.grid(row=0, column=0, sticky="w", padx=16, pady=13)
        title.bind("<Button-1>", lambda event: self.select_callback(self))

        self.status = tk.Label(
            header,
            text="\u25cf Starting",
            background="#202326",
            foreground="#d7a744",
            font=("Segoe UI", 9),
        )
        self.status.grid(row=0, column=1, padx=(8, 10))

        self.toggle = tk.Button(
            header,
            text="Close App",
            width=10,
            command=self._toggle,
            background="#934747",
            foreground="#ffffff",
            activebackground="#b45a5a",
            activeforeground="#ffffff",
            relief="flat",
            borderwidth=0,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        )
        self.toggle.grid(row=0, column=2, padx=(0, 14), pady=10)

        self.host = tk.Frame(self.frame, background="#080909", highlightthickness=0)
        self.host.grid(row=1, column=0, sticky="nsew")
        self.loading_index = 0
        self.loading = tk.Label(
            self.host,
            text="Starting...",
            background="#080909",
            foreground="#ff9d1f",
            font=("Segoe UI", 11, "bold"),
        )
        self.embedded_hwnd = None
        self.last_host_rect = None

    def _toggle(self):
        if self.simulator.desired_on:
            self.simulator.stop()
        else:
            self.simulator.start()

    def update(self):
        state = self.simulator.state
        if state == "Off" and self.simulator.desired_on and time.monotonic() - self.simulator.started_at >= 20:
            self.simulator.desired_on = False

        colors = {
            "On": "#58b878",
            "Starting": "#d7a744",
            "Stopping": "#d7a744",
            "Off": "#c86a6a",
        }
        self.status.configure(text=f"\u25cf {state}", foreground=colors[state])
        if state == "Starting":
            spinner = ("|", "/", "-", "\\")[self.loading_index % 4]
            self.loading_index += 1
            self.loading.configure(text=f"{spinner}  Starting...")
            self.loading.place(relx=0.5, rely=0.5, anchor="center")
        else:
            self.loading.place_forget()
        if self.simulator.desired_on:
            self.toggle.configure(
                text="Close App",
                background="#934747",
                activebackground="#b45a5a",
                state="disabled" if state in ("Starting", "Stopping") else "normal",
            )
        else:
            self.toggle.configure(
                text="Open App",
                background="#287a4b",
                activebackground="#34965f",
                state="normal",
            )

    def set_selected(self, selected):
        color = "#ff9d1f" if selected else "#17191b"
        self.frame.configure(highlightbackground=color, highlightcolor=color)

    def embed(self):
        hwnd = self.simulator.hwnd
        if not hwnd:
            self.simulator.embedded_hwnd = None
            self.embedded_hwnd = None
            self.last_host_rect = None
            return

        self.host.update_idletasks()
        owner_hwnd = self.host.winfo_toplevel().winfo_id()
        x = self.host.winfo_rootx()
        y = self.host.winfo_rooty()
        width = self.host.winfo_width()
        height = self.host.winfo_height()
        host_rect = (x, y, width, height)
        if self.embedded_hwnd != hwnd:
            embed_window(hwnd, owner_hwnd, x, y, width, height)
            self.embedded_hwnd = hwnd
            self.simulator.embedded_hwnd = hwnd
        else:
            resize_embedded_window(hwnd, x, y, width, height)
        self.last_host_rect = host_rect


class CombinedWindow:
    def __init__(self):
        LOGS.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=LOGS / "control-panel.log",
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
        )
        self.saved_state = self._load_state()
        self.save_after_id = None

        instance_id = uuid.uuid4().hex[:8]
        seed_root = ROOT / "seedsigner"
        krux_root = ROOT / "krux"
        seed_title = f"SeedSigner Simulator [{instance_id}]"
        krux_title = f"Krux Simulator [{instance_id}]"

        seed_env = os.environ.copy()
        krux_env = os.environ.copy()
        krux_env["KRUX_SIMULATOR_TITLE"] = krux_title
        krux_env["KRUX_SIMULATOR_START_HIDDEN"] = "1"
        krux_env["SDL_VIDEO_WINDOW_POS"] = "-10000,-10000"

        self.seed = Simulator(
            "SeedSigner",
            seed_title,
            [
                str(seed_root / ".venv" / "Scripts" / "pythonw.exe"),
                str(seed_root / "desktop_emulator.py"),
                "--geometry",
                "480x768-10000-10000",
                "--title",
                seed_title,
            ],
            seed_root,
            seed_env,
            "seedsigner",
        )
        self.krux = Simulator(
            "Krux",
            krux_title,
            [
                str(krux_root / ".venv" / "Scripts" / "pythonw.exe"),
                str(krux_root / "simulator" / "simulator.py"),
                "--device",
                "maixpy_amigo",
                "--sd",
            ],
            krux_root,
            krux_env,
            "krux",
        )

        self.root = tk.Tk()
        self.root.title(WINDOW_TITLE)
        self.root.configure(background="#111315")
        self.root.minsize(800, 650)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._restore_geometry()

        content = tk.Frame(self.root, background="#0b0c0d")
        content.pack(fill="both", expand=True)
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1, uniform="app-pane")
        content.grid_columnconfigure(2, weight=1, uniform="app-pane")

        self.seed_pane = ApplicationPane(content, self.seed, 0, self._select_pane)
        divider = tk.Frame(content, background="#3b3f43", width=1)
        divider.grid(row=0, column=1, sticky="ns")
        self.krux_pane = ApplicationPane(content, self.krux, 2, self._select_pane)
        self.selected_pane = self.seed_pane
        self.seed_pane.set_selected(True)
        self.krux_pane.set_selected(False)

        self.root.bind_all("<Control-Left>", lambda event: self._select_pane(self.seed_pane))
        self.root.bind_all("<Control-Right>", lambda event: self._select_pane(self.krux_pane))
        self.root.bind_all("<Tab>", self._toggle_selected_pane)
        self.root.bind_all("<Up>", lambda event: self._forward_key(0x26))
        self.root.bind_all("<Down>", lambda event: self._forward_key(0x28))
        self.root.bind_all("<Left>", lambda event: self._forward_key(0x25))
        self.root.bind_all("<Right>", lambda event: self._forward_key(0x27))
        self.root.bind_all("<Return>", lambda event: self._forward_key(0x0D))
        self.root.bind_all("<space>", lambda event: self._forward_key(0x20))
        self.root.bind_all("1", lambda event: self._forward_key(0x31))
        self.root.bind_all("2", lambda event: self._forward_key(0x32))
        self.root.bind_all("3", lambda event: self._forward_key(0x33))

        self.root.bind("<Configure>", self._geometry_changed)
        self.root.after(100, self._start_all)
        self.root.after(300, self._tick)

    def _select_pane(self, pane):
        self.selected_pane = pane
        self.seed_pane.set_selected(pane is self.seed_pane)
        self.krux_pane.set_selected(pane is self.krux_pane)
        return "break"

    def _toggle_selected_pane(self, event=None):
        target = self.krux_pane if self.selected_pane is self.seed_pane else self.seed_pane
        return self._select_pane(target)

    def _forward_key(self, virtual_key):
        send_key(self.selected_pane.simulator.hwnd, virtual_key)
        return "break"

    def _load_state(self):
        try:
            with STATE_FILE.open("r", encoding="utf-8") as state_file:
                state = json.load(state_file)
            return state if isinstance(state, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

    def _restore_geometry(self):
        host = self.saved_state.get("host")
        if host and all(key in host for key in ("width", "height", "x", "y")):
            self.root.geometry(f"{host['width']}x{host['height']}+{host['x']}+{host['y']}")
            return

        area = work_area()
        width = min(1040, area.right - area.left - 60)
        height = min(900, area.bottom - area.top - 60)
        x = area.left + ((area.right - area.left - width) // 2)
        y = area.top + ((area.bottom - area.top - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _geometry_changed(self, event):
        if event.widget is not self.root:
            return
        if self.save_after_id:
            self.root.after_cancel(self.save_after_id)
        self.save_after_id = self.root.after(500, self._save_state)

    def _save_state(self):
        self.save_after_id = None
        if self.root.state() != "normal":
            return
        state = {
            "host": {
                "width": self.root.winfo_width(),
                "height": self.root.winfo_height(),
                "x": self.root.winfo_x(),
                "y": self.root.winfo_y(),
            }
        }
        STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _start_all(self):
        self.seed.start()
        self.krux.start()

    def _tick(self):
        try:
            self.seed_pane.update()
            self.krux_pane.update()
            self.seed_pane.embed()
            self.krux_pane.embed()
        except Exception:
            logging.exception("Combined window update failed")
        self.root.after(250, self._tick)

    def close(self):
        self._save_state()
        self.seed.stop()
        self.krux.stop()
        self.seed.close_logs()
        self.krux.close_logs()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not mutex:
        return
    if kernel32.GetLastError() == 183:
        show_window(find_window(WINDOW_TITLE))
        return

    window = CombinedWindow()
    window.run()


if __name__ == "__main__":
    main()
