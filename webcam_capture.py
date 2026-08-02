"""Small OpenCV webcam adapter shared by the desktop simulators."""

from __future__ import annotations

import os
import threading
import time


_CAMERA_LOCK_PATH = os.path.join(
    os.environ.get("TEMP", "."), "btc-inspector-webcam.lock"
)


class WebcamError(RuntimeError):
    """Raised when a usable webcam cannot be opened or read."""


class _CameraLease:
    """Hold an OS-level lease so only one simulator opens the webcam."""

    def __init__(self):
        self._fd = None

    def acquire(self):
        flags = os.O_CREAT | os.O_RDWR
        self._fd = os.open(_CAMERA_LOCK_PATH, flags)
        try:
            end = os.lseek(self._fd, 0, os.SEEK_END)
            if end == 0:
                os.write(self._fd, b"0")
            os.lseek(self._fd, 0, os.SEEK_SET)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError) as exc:
            self.release()
            raise WebcamError(
                "The webcam is already in use by the other simulator. "
                "Exit the current camera screen before opening it here."
            ) from exc
        return self

    def release(self):
        if self._fd is None:
            return
        try:
            os.lseek(self._fd, 0, os.SEEK_SET)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._fd, fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None


class _LeasedCapture:
    """Delegate OpenCV calls and release the process-wide lease with capture."""

    def __init__(self, capture, lease):
        self._capture = capture
        self._lease = lease
        self._released = False

    def isOpened(self):
        return self._capture.isOpened()

    def set(self, *args):
        return self._capture.set(*args)

    def read(self):
        return self._capture.read()

    def release(self):
        if self._released:
            return
        self._released = True
        try:
            self._capture.release()
        finally:
            self._lease.release()


def _import_cv2():
    try:
        import cv2
    except ImportError as exc:
        raise WebcamError(
            "OpenCV is not installed. Install the simulator webcam dependency."
        ) from exc
    return cv2


def _camera_indices(environment_name: str):
    value = os.environ.get(environment_name)
    if value is None:
        value = os.environ.get("BTC_INSPECTOR_CAMERA_INDEX", "0")

    value = str(value).strip().lower()
    if value in ("", "auto"):
        return range(0, 8)

    try:
        index = int(value)
    except ValueError as exc:
        raise WebcamError(
            f"Invalid webcam index {value!r}; use a non-negative number or auto."
        ) from exc

    if index < 0:
        raise WebcamError("Webcam index must be non-negative.")
    return (index,)


def _open_capture(cv2, index: int):
    backends = []
    if os.name == "nt" and hasattr(cv2, "CAP_DSHOW"):
        backends.append(cv2.CAP_DSHOW)
    backends.append(None)

    for backend in backends:
        capture = None
        try:
            capture = (
                cv2.VideoCapture(index)
                if backend is None
                else cv2.VideoCapture(index, backend)
            )
            if capture.isOpened():
                return capture
        except Exception:
            pass
        finally:
            if capture is not None:
                try:
                    if not capture.isOpened():
                        capture.release()
                except Exception:
                    pass
    return None


def open_webcam(environment_name: str, width=None, height=None, framerate=None):
    """Open the configured Windows webcam and return ``(capture, index)``.

    ``<environment_name>`` takes precedence over the shared
    ``BTC_INSPECTOR_CAMERA_INDEX`` variable. Set either to ``auto`` to try the
    first eight device indices. Only one simulator owns the camera at a time.
    """

    cv2 = _import_cv2()
    lease = _CameraLease().acquire()
    attempted = []
    try:
        for index in _camera_indices(environment_name):
            attempted.append(index)
            capture = _open_capture(cv2, index)
            if capture is None:
                continue

            if width:
                capture.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
            if height:
                capture.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))
            if framerate:
                capture.set(cv2.CAP_PROP_FPS, int(framerate))
            return _LeasedCapture(capture, lease), index
    except Exception:
        lease.release()
        raise

    lease.release()
    attempted_text = ", ".join(str(index) for index in attempted)
    raise WebcamError(
        "No usable webcam found. "
        f"Tried device index {attempted_text}. "
        f"Set {environment_name}=0..7 or auto to choose another camera."
    )


def convert_frame(frame, pixel_format: str):
    """Return a frame in the requested BGR/RGB format."""

    if frame is None or pixel_format.lower() != "rgb":
        return frame
    cv2 = _import_cv2()
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def frame_to_image(frame, pixel_format: str, rotation: int = 0):
    """Convert an OpenCV frame into the RGBA image used by SeedSigner."""

    from PIL import Image

    rgb_frame = convert_frame(frame, pixel_format)
    if rgb_frame is None:
        return None
    image = Image.fromarray(rgb_frame.astype("uint8"), "RGB").convert("RGBA")
    if rotation % 360:
        image = image.rotate(rotation)
    return image


class WebcamStream:
    """Background webcam reader matching the PiVideoStream read/stop API."""

    def __init__(
        self,
        resolution=(480, 480),
        framerate=6,
        pixel_format="bgr",
        environment_name="BTC_INSPECTOR_CAMERA_INDEX",
    ):
        self.capture, self.index = open_webcam(
            environment_name,
            width=resolution[0],
            height=resolution[1],
            framerate=framerate,
        )
        self.pixel_format = pixel_format
        self._frame = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return self
        self._stop.clear()
        self._thread = threading.Thread(target=self._update, daemon=True)
        self._thread.start()
        return self

    def _update(self):
        while not self._stop.is_set():
            ok, frame = self.capture.read()
            if ok and frame is not None:
                with self._lock:
                    self._frame = frame
            else:
                time.sleep(0.02)

    def read(self):
        with self._lock:
            frame = None if self._frame is None else self._frame.copy()
        return convert_frame(frame, self.pixel_format)

    def stop(self):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self.capture.release()
        self._thread = None


class WebcamStill:
    """Single-frame webcam reader used by the image-entropy screen."""

    def __init__(
        self,
        resolution=(480, 480),
        environment_name="BTC_INSPECTOR_CAMERA_INDEX",
    ):
        self.capture, self.index = open_webcam(
            environment_name,
            width=resolution[0],
            height=resolution[1],
        )

    def capture_frame(self):
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            ok, frame = self.capture.read()
            if ok and frame is not None:
                return frame
            time.sleep(0.02)
        raise WebcamError("The webcam opened but did not provide a frame.")

    def release(self):
        self.capture.release()
