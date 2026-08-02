#!/usr/bin/env python

import argparse
import json
import logging
import os
import queue
import re
import sys
import threading
import types
import tkinter as tk
from pathlib import Path

from PIL import Image, ImageTk


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT.parent))

from webcam_capture import WebcamError, WebcamStill, WebcamStream, frame_to_image

DISPLAY_QUEUE = queue.Queue(maxsize=2)
INPUT_QUEUE = queue.Queue()
ACTIVE_SCREEN = None


class HardwareButtonsConstants:
    KEY_UP = 31
    KEY_DOWN = 35
    KEY_LEFT = 29
    KEY_RIGHT = 37
    KEY_PRESS = 33
    KEY1 = 40
    KEY2 = 38
    KEY3 = 36
    OVERRIDE = 1000

    ALL_KEYS = [KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT, KEY_PRESS, KEY1, KEY2, KEY3]
    KEYS__LEFT_RIGHT_UP_DOWN = [KEY_LEFT, KEY_RIGHT, KEY_UP, KEY_DOWN]
    KEYS__ANYCLICK = [KEY_PRESS, KEY1, KEY2, KEY3]


class HardwareButtons:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def wait_for(self, keys=None):
        allowed = set(keys or HardwareButtonsConstants.ALL_KEYS)
        while True:
            key = INPUT_QUEUE.get()
            if key == HardwareButtonsConstants.OVERRIDE or key in allowed:
                return key

    def update_last_input_time(self):
        pass

    def trigger_override(self):
        INPUT_QUEUE.put(HardwareButtonsConstants.OVERRIDE)

    def check_for_low(self, key=None, keys=None):
        return False

    def has_any_input(self):
        return False


class CameraConnectionError(Exception):
    pass


class Camera:
    _instance = None

    def __init__(self):
        self._video_stream = None
        self._video_format = "bgr"
        self._single_frame = None
        try:
            self._rotation = int(os.environ.get("SEEDSIGNER_CAMERA_ROTATION", "0"))
        except ValueError:
            self._rotation = 0

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def start_video_stream_mode(
        self, resolution=(512, 384), framerate=12, format="bgr"
    ):
        self.stop_single_frame_mode()
        self.stop_video_stream_mode()
        try:
            self._video_format = format
            self._video_stream = WebcamStream(
                resolution=resolution,
                framerate=framerate,
                pixel_format=format,
                environment_name="SEEDSIGNER_CAMERA_INDEX",
            ).start()
        except WebcamError as exc:
            self._video_stream = None
            raise CameraConnectionError(str(exc)) from exc

    def read_video_stream(self, as_image=False):
        if self._video_stream is None:
            raise Exception("Must call start_video_stream first.")
        frame = self._video_stream.read()
        if as_image:
            return frame_to_image(frame, self._video_format, rotation=self._rotation)
        return frame

    def start_single_frame_mode(self, resolution=(720, 480)):
        self.stop_video_stream_mode()
        self.stop_single_frame_mode()
        try:
            self._single_frame = WebcamStill(
                resolution=resolution,
                environment_name="SEEDSIGNER_CAMERA_INDEX",
            )
        except WebcamError as exc:
            self._single_frame = None
            raise CameraConnectionError(str(exc)) from exc

    def capture_frame(self):
        if self._single_frame is None:
            raise Exception("Must call start_single_frame_mode first.")
        try:
            frame = self._single_frame.capture_frame()
        except WebcamError as exc:
            self.stop_single_frame_mode()
            raise CameraConnectionError(str(exc)) from exc
        return frame_to_image(frame, "bgr", rotation=self._rotation)

    def stop_video_stream_mode(self):
        if self._video_stream is not None:
            self._video_stream.stop()
            self._video_stream = None

    def stop_single_frame_mode(self):
        if self._single_frame is not None:
            self._single_frame.release()
            self._single_frame = None


def install_hardware_mocks():
    buttons_module = types.ModuleType("seedsigner.hardware.buttons")
    buttons_module.HardwareButtonsConstants = HardwareButtonsConstants
    buttons_module.HardwareButtons = HardwareButtons
    sys.modules[buttons_module.__name__] = buttons_module

    camera_module = types.ModuleType("seedsigner.hardware.camera")
    camera_module.CameraConnectionError = CameraConnectionError
    camera_module.Camera = Camera
    sys.modules[camera_module.__name__] = camera_module

    pivideostream_module = types.ModuleType("seedsigner.hardware.pivideostream")
    pivideostream_module.PiVideoStream = Camera
    sys.modules[pivideostream_module.__name__] = pivideostream_module


class DesktopDisplay:
    def __init__(self, _width, _height):
        self._width = _width
        self._height = _height

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    def show_image(self, image, x_start=0, y_start=0):
        while True:
            try:
                DISPLAY_QUEUE.get_nowait()
            except queue.Empty:
                break
        DISPLAY_QUEUE.put(image.copy())

    def invert(self, enabled=True):
        pass

    def cleanup(self):
        pass


class SeedSignerWindow:
    def __init__(self, geometry, title_text, start_hidden=False):
        geometry_match = re.match(r"^(\d+)x(\d+)", geometry)
        if not geometry_match:
            raise ValueError(f"Invalid window geometry: {geometry}")
        width, height = (int(value) for value in geometry_match.groups())

        self.root = tk.Tk()
        if start_hidden:
            self.root.withdraw()
        self.root.title(title_text)
        self.root.geometry(geometry)
        self.root.minsize(360, 576)
        self.root.configure(background="#111315")

        self.display_size = min(width - 72, int(height * 0.52), 380)
        self.display_size = max(260, self.display_size)
        self.photo = None
        title = tk.Label(
            self.root,
            text="SeedSigner",
            background="#111315",
            foreground="#f2f2f2",
            font=("Segoe UI", 15, "bold"),
            pady=12,
        )
        title.pack()

        screen_frame = tk.Frame(self.root, background="#26292c", padx=9, pady=9)
        screen_frame.pack()
        self.screen = tk.Label(
            screen_frame,
            width=self.display_size,
            height=self.display_size,
            background="#000000",
            borderwidth=0,
        )
        self.screen.pack()
        self.screen.bind("<Button-1>", self._on_screen_click)

        controls = tk.Frame(self.root, background="#111315", pady=14)
        controls.pack(fill="both", expand=True)

        action_row = tk.Frame(controls, background="#111315")
        action_row.pack(fill="x", padx=44, pady=(0, 10))
        self._button(action_row, "1", HardwareButtonsConstants.KEY1).pack(side="left")
        self._button(action_row, "2", HardwareButtonsConstants.KEY2).pack(side="left", expand=True)
        self._button(action_row, "3", HardwareButtonsConstants.KEY3).pack(side="right")

        dpad = tk.Frame(controls, background="#111315")
        dpad.pack()
        self._button(dpad, "\u2191", HardwareButtonsConstants.KEY_UP).grid(row=0, column=1, padx=4, pady=3)
        self._button(dpad, "\u2190", HardwareButtonsConstants.KEY_LEFT).grid(row=1, column=0, padx=4, pady=3)
        self._button(dpad, "OK", HardwareButtonsConstants.KEY_PRESS, accent=True).grid(row=1, column=1, padx=4, pady=3)
        self._button(dpad, "\u2192", HardwareButtonsConstants.KEY_RIGHT).grid(row=1, column=2, padx=4, pady=3)
        self._button(dpad, "\u2193", HardwareButtonsConstants.KEY_DOWN).grid(row=2, column=1, padx=4, pady=3)

        key_map = {
            "<Up>": HardwareButtonsConstants.KEY_UP,
            "<Down>": HardwareButtonsConstants.KEY_DOWN,
            "<Left>": HardwareButtonsConstants.KEY_LEFT,
            "<Right>": HardwareButtonsConstants.KEY_RIGHT,
            "<Return>": HardwareButtonsConstants.KEY_PRESS,
            "<space>": HardwareButtonsConstants.KEY_PRESS,
            "1": HardwareButtonsConstants.KEY1,
            "2": HardwareButtonsConstants.KEY2,
            "3": HardwareButtonsConstants.KEY3,
        }
        for key_sequence, value in key_map.items():
            self.root.bind(key_sequence, lambda event, key=value: INPUT_QUEUE.put(key))

        self.root.after(16, self._update_display)

    def _on_screen_click(self, event):
        """Forward a real Tk click to the simulator display immediately."""
        self._touch_screen(event)

    @staticmethod
    def _contains(component, x, y, scroll_y=0):
        left = component.screen_x
        top = component.screen_y - scroll_y
        return left <= x < left + component.width and top <= y < top + component.height

    def _touch_screen(self, event):
        screen = ACTIVE_SCREEN
        if screen is None:
            return

        x = int(event.x * screen.canvas_width / self.display_size)
        y = int(event.y * screen.canvas_height / self.display_size)
        input_key = None

        try:
            with screen.renderer.lock:
                top_nav = getattr(screen, "top_nav", None)
                if top_nav is not None:
                    nav_buttons = []
                    if getattr(top_nav, "show_back_button", False):
                        nav_buttons.append(getattr(top_nav, "left_button", None))
                    if getattr(top_nav, "show_power_button", False):
                        nav_buttons.append(getattr(top_nav, "right_button", None))
                    for nav_button in nav_buttons:
                        if nav_button and self._contains(nav_button, x, y):
                            top_nav.is_selected = True
                            # KeyboardEntryScreen keeps a separate navigation flag;
                            # mirror hardware navigation so a touch click is handled
                            # by the screen's normal back/power path.
                            if hasattr(screen, "is_input_in_top_nav"):
                                screen.is_input_in_top_nav = True
                            top_nav.render_buttons()
                            screen.renderer.show_image()
                            input_key = HardwareButtonsConstants.KEY_PRESS
                            break

                if input_key is None and hasattr(screen, "save_button"):
                    if self._contains(screen.save_button, x, y):
                        input_key = HardwareButtonsConstants.KEY3

                keyboard = getattr(screen, "keyboard", None)
                if input_key is None and keyboard is not None:
                    for row in keyboard.keys:
                        for key in row:
                            key_width = keyboard.key_width * key.size
                            if (
                                key.screen_x <= x < key.screen_x + key_width
                                and key.screen_y <= y < key.screen_y + keyboard.key_height
                            ):
                                current_key = keyboard.get_selected_key()
                                current_key.is_selected = False
                                current_key.render_key()
                                keyboard.selected_key["x"] = key.index_x
                                keyboard.selected_key["y"] = key.index_y
                                key.is_selected = True
                                key.render_key()
                                if top_nav is not None:
                                    top_nav.is_selected = False
                                    top_nav.render_buttons()
                                screen.renderer.show_image()
                                input_key = HardwareButtonsConstants.KEY_PRESS
                                break
                        if input_key is not None:
                            break

                buttons = getattr(screen, "buttons", None)
                if input_key is None and buttons and hasattr(screen, "selected_button"):
                    for index, button in enumerate(buttons):
                        scroll_y = getattr(button, "scroll_y", 0)
                        if self._contains(button, x, y, scroll_y=scroll_y):
                            current_button = buttons[screen.selected_button]
                            current_button.is_selected = False
                            current_button.render()
                            screen.selected_button = index
                            button.is_selected = True
                            button.render()
                            if top_nav is not None:
                                top_nav.is_selected = False
                                top_nav.render_buttons()
                            screen.renderer.show_image()
                            input_key = HardwareButtonsConstants.KEY_PRESS
                            break
        except Exception:
            logging.exception("SeedSigner touch input failed")
            return

        if input_key is not None:
            INPUT_QUEUE.put(input_key)

    def _button(self, parent, label, key, accent=False):
        background = "#f39a24" if accent else "#303438"
        foreground = "#111315" if accent else "#f5f5f5"
        button = tk.Button(
            parent,
            text=label,
            width=5,
            height=1,
            command=lambda: INPUT_QUEUE.put(key),
            background=background,
            foreground=foreground,
            activebackground="#ffad42" if accent else "#464b50",
            activeforeground=foreground,
            relief="flat",
            borderwidth=0,
            font=("Segoe UI", 12, "bold"),
            cursor="hand2",
        )
        button.hardware_key = key
        return button

    def _update_display(self):
        newest = None
        while True:
            try:
                newest = DISPLAY_QUEUE.get_nowait()
            except queue.Empty:
                break

        if newest is not None:
            rendered = newest.resize(
                (self.display_size, self.display_size),
                Image.Resampling.NEAREST,
            )
            self.photo = ImageTk.PhotoImage(rendered)
            self.screen.configure(image=self.photo)

        self.root.after(16, self._update_display)

    def run(self):
        self.root.mainloop()


def start_seedsigner():
    from seedsigner.controller import Controller

    try:
        Controller.get_instance().start()
    except Exception:
        logging.exception("SeedSigner simulator stopped unexpectedly")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--geometry", default="480x768+40+40")
    parser.add_argument("--title", default="SeedSigner Simulator")
    parser.add_argument("--start-hidden", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    install_hardware_mocks()

    settings_directory = ROOT / "simulator-data"
    settings_directory.mkdir(parents=True, exist_ok=True)
    from seedsigner.models.settings import Settings

    # Configure the simulator store before importing GUI modules. Some GUI class
    # defaults read Settings during import and would otherwise lock in English.
    Settings.SETTINGS_FILENAME = str(settings_directory / "settings.json")

    from seedsigner.hardware.displays.display_driver import DisplayDriverFactory
    from seedsigner.helpers.qr import QR
    from seedsigner.helpers.version import VersionUtils
    from seedsigner.gui.screens.screen import BaseScreen

    DisplayDriverFactory.instantiate_display_driver = classmethod(
        lambda cls, display_type="st7789", width=240, height=240: DesktopDisplay(width, height)
    )
    QR.qrimage_io = lambda self, data, width=240, height=240, border=3, background_color="808080": self.qrimage(
        data,
        width,
        height,
        border,
        background_color=background_color,
    )
    VersionUtils._get_version_name_from_git_shell = classmethod(lambda cls: None)
    VersionUtils._get_version_fork_from_git_shell = classmethod(lambda cls: None)
    VersionUtils._get_full_commit_hash_from_git_shell = classmethod(lambda cls: None)

    original_display = BaseScreen.display

    def tracked_display(screen):
        global ACTIVE_SCREEN
        ACTIVE_SCREEN = screen
        try:
            result = original_display(screen)
            return result
        finally:
            if ACTIVE_SCREEN is screen:
                ACTIVE_SCREEN = None

    BaseScreen.display = tracked_display

    def save_desktop_settings(settings):
        with open(Settings.SETTINGS_FILENAME, "w", encoding="utf-8") as settings_file:
            json.dump(settings._data, settings_file, indent=2)
            settings_file.flush()
            os.fsync(settings_file.fileno())

    Settings.save = save_desktop_settings

    window = SeedSignerWindow(args.geometry, args.title, start_hidden=args.start_hidden)
    controller_thread = threading.Thread(target=start_seedsigner, daemon=True)
    controller_thread.start()
    window.run()


if __name__ == "__main__":
    main()
