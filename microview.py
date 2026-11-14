#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Ptdxl
"""MicroView - viewer for USB microscopes (UVC cameras).

Live view, photos, video recording, image controls, rotate/mirror,
digital zoom and distance measurements with calibration.

Requires PySide6, and FFmpeg for video recording (from PATH or the
imageio-ffmpeg Python package).
"""

import math
import os
import queue
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QLocale, QPointF, QRectF, QSettings, QStandardPaths, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QDesktopServices,
    QFont,
    QIcon,
    QImage,
    QKeySequence,
    QPainter,
    QPen,
    QTransform,
)
from PySide6.QtMultimedia import QCamera, QMediaCaptureSession, QMediaDevices, QVideoSink
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

try:
    import fcntl  # Linux/Unix only; without it there are no camera controls
except ImportError:
    fcntl = None

APP_NAME = "MicroView"
APP_VERSION = "1.3"
APP_AUTHOR = "Ptdxl"
APP_LICENSE = "GPL-3.0-or-later"
APP_REPO = "https://github.com/ptdxl/microview"
ICON_PATH = Path(__file__).resolve().parent / "microview.svg"
MAX_ZOOM = 10.0
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # no console window on Windows

# ---------------------------------------------------------------------------
# Translations: English is the source language, Dutch is looked up here
# ---------------------------------------------------------------------------

NL = {
    # toolbar
    "Main": "Hoofd",
    "📷 Photo": "📷 Foto",
    "Save a photo": "Foto opslaan",
    "⏺ Record": "⏺ Opname",
    "⏹ Stop": "⏹ Stop",
    "Start/stop video recording": "Video-opname starten/stoppen",
    "⏸ Freeze": "⏸ Bevries",
    "Freeze the image": "Beeld bevriezen",
    "📏 Measure": "📏 Meten",
    "Measure: drag a line, right-click removes the last one":
        "Meten: sleep een lijn, rechtsklik verwijdert de laatste",
    "Calibrate…": "Kalibreren…",
    "Use the last measured line as a known length": "Laatste meetlijn gebruiken als bekende lengte",
    "Clear measurements": "Wis metingen",
    "Zoom −": "Zoom −",
    "Zoom out": "Uitzoomen",
    "Zoom 1×": "Zoom 1×",
    "Zoom +": "Zoom +",
    "Zoom in (also: mouse wheel over the image)": "Inzoomen (ook: muiswiel boven het beeld)",
    "Reset digital zoom: fit the whole image in the window":
        "Digitale zoom terugzetten: hele beeld passend in het venster",
    "⛶ Full screen": "⛶ Volledig scherm",
    "📂 Folder": "📂 Map",
    "Open the output folder": "Opslagmap openen",
    "ℹ About": "ℹ Info",
    "About MicroView": "Over MicroView",
    # panel
    "Settings": "Instellingen",
    "Camera": "Camera",
    "Resolution and frame rate offered by the camera": "Resolutie en beeldsnelheid die de camera aanbiedt",
    "Image": "Beeld",
    "No controls available": "Geen instellingen beschikbaar",
    "Defaults": "Standaardwaarden",
    "Orientation": "Oriëntatie",
    "⟲ Left": "⟲ Links",
    "⟳ Right": "⟳ Rechts",
    "Mirror horizontally": "Horizontaal spiegelen",
    "Mirror vertically": "Verticaal spiegelen",
    "Calibration": "Kalibratie",
    "Clear calibration": "Kalibratie wissen",
    "{ppm:.1f} px/mm  (1 px = {um:.2f} µm)\nOnly valid at the same magnification/focus.":
        "{ppm:.1f} px/mm  (1 px = {um:.2f} µm)\nGeldt alleen bij dezelfde vergroting/scherpstelling.",
    "Not calibrated – measurements in pixels.\nMeasure a known length (e.g. a ruler) and choose Calibrate.":
        "Niet gekalibreerd – metingen in pixels.\nMeet een bekende lengte (bijv. liniaal) en kies Kalibreren.",
    "Save": "Opslaan",
    "Change folder…": "Map wijzigen…",
    "Language": "Taal",
    "Automatic": "Automatisch",
    "Restart MicroView to apply the language": "Herstart MicroView om de taal toe te passen",
    # camera control names
    "Brightness": "Helderheid",
    "Contrast": "Contrast",
    "Saturation": "Verzadiging",
    "Hue": "Tint",
    "Auto white balance": "Auto witbalans",
    "Gamma": "Gamma",
    "Gain": "Versterking",
    "White balance": "Witbalans",
    "Sharpness": "Scherpte",
    "Backlight": "Tegenlicht",
    "Exposure": "Belichting",
    "Focus": "Focus",
    "Autofocus": "Autofocus",
    "Zoom (camera)": "Zoom (camera)",
    # camera
    "No camera": "Geen camera",
    "No camera found – connect the microscope": "Geen camera gevonden – sluit de microscoop aan",
    "Starting camera…": "Camera starten…",
    "Camera error: {}": "Camerafout: {}",
    # photo / video
    "No image to save": "Geen beeld om op te slaan",
    "Cannot create folder:\n{}": "Kan map niet aanmaken:\n{}",
    "Photo saved: {}": "Foto opgeslagen: {}",
    "Saving failed:\n{}": "Opslaan mislukt:\n{}",
    "No image to record": "Geen beeld om op te nemen",
    "Video recording needs FFmpeg.\nInstall the 'ffmpeg' package and try again.":
        "Voor video-opname is FFmpeg nodig.\nInstalleer het pakket 'ffmpeg' en probeer het opnieuw.",
    "Could not start recording:\n{}": "Opname starten mislukt:\n{}",
    "Recording stopped: the image size changed": "Opname gestopt: het beeldformaat is gewijzigd",
    "Video saved: {}": "Video opgeslagen: {}",
    "Recording failed ({encoder}): {error}.": "Opname mislukt ({encoder}): {error}.",
    " The next recording will use {}.": " De volgende opname gebruikt {}.",
    "FFmpeg exited with code {}": "FFmpeg stopte met code {}",
    # measuring
    "Turn on Measure and drag a line across a known length first\n"
    "(for example 1 mm on a ruler). Then choose Calibrate.":
        "Zet Meten aan en sleep eerst een lijn over een bekende lengte\n"
        "(bijvoorbeeld 1 mm op een liniaal). Kies daarna Kalibreren.",
    "Calibrate": "Kalibreren",
    "Real length of the last line ({:.0f} px) in mm:": "Werkelijke lengte van de laatste lijn ({:.0f} px) in mm:",
    # misc
    "Choose output folder": "Opslagmap kiezen",
    "FROZEN": "BEVROREN",
    "zoom {:.1f}×": "zoom {:.1f}×",
    "{} measurement(s)": "{} meting(en)",
    # about
    "About {}": "Over {}",
    "Viewer for USB microscopes (UVC cameras).": "Viewer voor USB-microscopen (UVC-camera's).",
    "<b>Photo</b> (Space) and <b>video</b> (R) are saved to the output folder as you see them: "
    "rotated, mirrored and with measurements.":
        "<b>Foto</b> (spatie) en <b>video</b> (R) worden in de opslagmap bewaard zoals je ze ziet: "
        "gedraaid, gespiegeld en met metingen.",
    "<b>Zoom</b> with the mouse wheel or the Zoom buttons (+ / −), drag to pan, <b>Zoom 1×</b> (0) shows the whole image again.":
        "<b>Zoomen</b> met het muiswiel of de zoomknoppen (+ / −), slepen verschuift het beeld, "
        "<b>Zoom 1×</b> (0) toont weer het hele beeld.",
    "<b>Measure</b> (M): drag a line; right-click removes the last one.":
        "<b>Meten</b> (M): sleep een lijn; rechtsklik verwijdert de laatste.",
    "<b>Calibrate</b> (K): measure a known length and enter it in mm.":
        "<b>Kalibreren</b> (K): meet een bekende lengte en vul die in mm in.",
    "Brightness, contrast, rotating and mirroring are in the panel on the right.":
        "Helderheid, contrast, draaien en spiegelen staan in het paneel rechts.",
    "Author": "Auteur",
    "License": "Licentie",
    "Source code": "Broncode",
}

_language = "en"


def choose_language(setting="auto"):
    """Sets the UI language: MICROVIEW_LANG, then the saved setting, then the system language."""
    global _language
    choice = os.environ.get("MICROVIEW_LANG", "").lower() or setting
    if choice not in ("en", "nl"):
        choice = "nl" if QLocale.system().language() == QLocale.Language.Dutch else "en"
    _language = choice


def tr(text):
    return NL.get(text, text) if _language == "nl" else text


def child_env():
    """Environment for external programs.

    In the portable build (PyInstaller) LD_LIBRARY_PATH points at the bundled
    libraries; an FFmpeg from the system must not load those.
    """
    env = dict(os.environ)
    if getattr(sys, "frozen", False):
        original = env.pop("LD_LIBRARY_PATH_ORIG", None)
        if original is not None:
            env["LD_LIBRARY_PATH"] = original
        else:
            env.pop("LD_LIBRARY_PATH", None)
    return env


# ---------------------------------------------------------------------------
# Camera controls (brightness, contrast, ...) straight through V4L2
# ---------------------------------------------------------------------------

VIDIOC_QUERYCTRL = 0xC0445624
VIDIOC_G_CTRL = 0xC008561B
VIDIOC_S_CTRL = 0xC008561C
V4L2_CTRL_FLAG_NEXT_CTRL = 0x80000000
V4L2_CTRL_FLAGS_SKIP = 0x0001 | 0x0004  # disabled or read-only
V4L2_CTRL_KINDS = {1: "int", 2: "bool"}
QUERYCTRL = struct.Struct("=II32siiiiI8x")  # struct v4l2_queryctrl
CONTROL = struct.Struct("=Ii")              # struct v4l2_control

CTRL_LABELS = {
    0x00980900: "Brightness",
    0x00980901: "Contrast",
    0x00980902: "Saturation",
    0x00980903: "Hue",
    0x0098090C: "Auto white balance",
    0x00980910: "Gamma",
    0x00980913: "Gain",
    0x0098091A: "White balance",
    0x0098091B: "Sharpness",
    0x0098091C: "Backlight",
    0x009A0902: "Exposure",
    0x009A090A: "Focus",
    0x009A090C: "Autofocus",
    0x009A090D: "Zoom (camera)",
}


def list_controls(device):
    """Returns the adjustable int/bool controls of a V4L2 device."""
    if fcntl is None or not device:
        return []
    try:
        fd = os.open(device, os.O_RDWR | os.O_NONBLOCK)
    except OSError:
        return []
    controls = []
    try:
        ctrl_id = 0
        for _ in range(256):
            buf = bytearray(QUERYCTRL.pack(ctrl_id | V4L2_CTRL_FLAG_NEXT_CTRL, 0, b"", 0, 0, 0, 0, 0))
            try:
                fcntl.ioctl(fd, VIDIOC_QUERYCTRL, buf)
            except OSError:
                break  # no more controls
            ctrl_id, ctype, name, low, high, step, default, flags = QUERYCTRL.unpack(buf)
            kind = V4L2_CTRL_KINDS.get(ctype)
            if kind is None or flags & V4L2_CTRL_FLAGS_SKIP:
                continue
            val = bytearray(CONTROL.pack(ctrl_id, 0))
            try:
                fcntl.ioctl(fd, VIDIOC_G_CTRL, val)
            except OSError:
                continue
            controls.append({
                "id": ctrl_id,
                "name": name.split(b"\0")[0].decode(errors="replace"),
                "kind": kind,
                "min": low,
                "max": high,
                "step": max(1, step),
                "default": default,
                "value": CONTROL.unpack(val)[1],
            })
    finally:
        os.close(fd)
    return controls


def set_control(device, ctrl_id, value):
    if fcntl is None or not device:
        return
    try:
        fd = os.open(device, os.O_RDWR | os.O_NONBLOCK)
    except OSError:
        return
    try:
        fcntl.ioctl(fd, VIDIOC_S_CTRL, CONTROL.pack(ctrl_id, int(value)))
    except OSError:
        pass
    finally:
        os.close(fd)


# ---------------------------------------------------------------------------
# Video recording through our own FFmpeg process
# ---------------------------------------------------------------------------

# Order of preference. Always 8-bit 4:2:0 in MP4, so it plays everywhere.
ENCODERS = [
    ("libx264", ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]),
    ("libopenh264", ["-c:v", "libopenh264", "-b:v", "8M"]),
    ("mpeg4", ["-c:v", "mpeg4", "-q:v", "3"]),
]
_ffmpeg_builds = None  # [(path, {encoder names})]


def _find_ffmpeg_builds():
    global _ffmpeg_builds
    if _ffmpeg_builds is None:
        paths = []
        system = shutil.which("ffmpeg")
        if system:
            paths.append(system)
        try:  # bundled with the portable build
            import imageio_ffmpeg
            paths.append(imageio_ffmpeg.get_ffmpeg_exe())
        except Exception:
            pass
        builds = []
        for exe in paths:
            try:
                out = subprocess.run([exe, "-hide_banner", "-encoders"], capture_output=True,
                                     text=True, timeout=15, creationflags=NO_WINDOW, env=child_env()).stdout
            except (OSError, subprocess.SubprocessError):
                continue
            names = {parts[1] for line in out.splitlines() if len(parts := line.split()) > 1}
            builds.append((exe, names))
        _ffmpeg_builds = builds
    return _ffmpeg_builds


def find_encoder(exclude=()):
    """Best available encoder as (ffmpeg path, name, arguments), or None."""
    for name, args in ENCODERS:
        if name in exclude:
            continue
        for exe, names in _find_ffmpeg_builds():
            if name in names:
                return exe, name, args
    return None


class VideoWriter:
    """Pipes frames to FFmpeg; the writing happens in its own thread."""

    def __init__(self, exe, encoder, codec_args, path, width, height, fps):
        self.path = Path(path)
        self.encoder = encoder
        self.size = (width, height)
        self.started = time.monotonic()
        self.dropped = 0
        self._queue = queue.Queue(maxsize=6)
        self._log = tempfile.TemporaryFile()
        cmd = [
            exe, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "rawvideo", "-pix_fmt", "bgr0", "-video_size", f"{width}x{height}",
            "-framerate", f"{fps:g}", "-use_wallclock_as_timestamps", "1", "-i", "pipe:0",
            # constant frame rate from the real arrival times, even dimensions, 4:2:0
            "-an", "-vf", f"fps={fps:g},scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
            *codec_args, "-movflags", "+faststart", str(self.path),
        ]
        self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                      stderr=self._log, creationflags=NO_WINDOW, env=child_env())
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        pipe = self._proc.stdin
        alive = True
        while True:
            data = self._queue.get()
            if data is None:
                break
            if alive:
                try:
                    pipe.write(data)
                except OSError:  # FFmpeg has exited
                    alive = False
        try:
            pipe.close()
        except OSError:
            pass
        try:
            self._proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait()

    def write(self, data):
        try:
            self._queue.put_nowait(data)
        except queue.Full:
            self.dropped += 1

    def crashed(self):
        return self._proc.poll() is not None

    def stop(self):
        self._queue.put(None)

    def finished(self):
        return not self._thread.is_alive()

    def wait(self, timeout):
        self._thread.join(timeout)

    def result(self):
        """(succeeded, error message) once the recording has been finalized."""
        self._log.seek(0)
        error = self._log.read().decode(errors="replace").strip()
        self._log.close()
        ok = self._proc.returncode == 0 and self.path.exists() and self.path.stat().st_size > 0
        if not ok and self.path.exists():
            try:
                self.path.unlink()
            except OSError:
                pass
        if error:
            return ok, error.splitlines()[-1]
        return ok, tr("FFmpeg exited with code {}").format(self._proc.returncode)


# ---------------------------------------------------------------------------
# Image view with zoom, panning and measurements
# ---------------------------------------------------------------------------

def format_length(px, px_per_mm):
    if px_per_mm <= 0:
        return f"{px:.0f} px"
    mm = px / px_per_mm
    if mm < 1:
        return f"{mm * 1000:.0f} µm"
    return f"{mm:.3f} mm"


def draw_measurements(painter, lines, px_per_mm, scale, ox, oy, ui=1.0):
    """Draws measurement lines; lines are in image pixels, (scale, ox, oy) maps them to the target."""
    if not lines:
        return
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    font = QFont(painter.font())
    font.setPointSizeF(11 * ui)
    font.setBold(True)
    painter.setFont(font)
    for a, b in lines:
        pa = QPointF(ox + a.x() * scale, oy + a.y() * scale)
        pb = QPointF(ox + b.x() * scale, oy + b.y() * scale)
        dx, dy = pb.x() - pa.x(), pb.y() - pa.y()
        length = math.hypot(dx, dy)
        for color, width in ((QColor(0, 0, 0, 200), 4 * ui), (QColor(255, 220, 0), 2 * ui)):
            painter.setPen(QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(pa, pb)
            if length > 0:  # end ticks
                nx, ny = -dy / length * 6 * ui, dx / length * 6 * ui
                for p in (pa, pb):
                    painter.drawLine(QPointF(p.x() - nx, p.y() - ny), QPointF(p.x() + nx, p.y() + ny))
        text = format_length(math.hypot(b.x() - a.x(), b.y() - a.y()), px_per_mm)
        metrics = painter.fontMetrics()
        w, h = metrics.horizontalAdvance(text) + 10 * ui, metrics.height() + 4 * ui
        mid = QPointF((pa.x() + pb.x()) / 2, (pa.y() + pb.y()) / 2)
        box = QRectF(mid.x() - w / 2, mid.y() - h - 6 * ui, w, h)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 170))
        painter.drawRoundedRect(box, 4 * ui, 4 * ui)
        painter.setPen(QColor(255, 220, 0))
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, text)
    painter.restore()


class CameraView(QWidget):
    zoomChanged = Signal(float)
    linesChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = None
        self.zoom = 1.0
        self.center = QPointF(0.5, 0.5)  # normalized image point shown at the widget centre
        self.measure_mode = False
        self.lines = []
        self.draft = None
        self.px_per_mm = 0.0
        self.message = tr("No camera")
        self._pan_from = None
        self.setMinimumSize(480, 270)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # -- geometry ---------------------------------------------------------
    def _geom(self):
        iw, ih = self.image.width(), self.image.height()
        s = min(self.width() / iw, self.height() / ih) * self.zoom
        ox = self.width() / 2 - self.center.x() * iw * s
        oy = self.height() / 2 - self.center.y() * ih * s
        return s, ox, oy

    def _to_image(self, pos):
        s, ox, oy = self._geom()
        x = min(max((pos.x() - ox) / s, 0), self.image.width())
        y = min(max((pos.y() - oy) / s, 0), self.image.height())
        return QPointF(x, y)

    def _clamp(self):
        if self.image is None:
            return
        iw, ih = self.image.width(), self.image.height()
        s = min(self.width() / iw, self.height() / ih) * self.zoom
        fx = min(1.0, self.width() / (iw * s)) / 2
        fy = min(1.0, self.height() / (ih * s)) / 2
        self.center = QPointF(
            min(max(self.center.x(), fx), 1 - fx),
            min(max(self.center.y(), fy), 1 - fy),
        )

    # -- public -----------------------------------------------------------
    def set_image(self, image):
        size_changed = self.image is None or image is None or self.image.size() != image.size()
        self.image = image
        if size_changed:
            self._clamp()
        self.update()

    def set_zoom(self, zoom, anchor=None):
        if self.image is None:
            return
        zoom = min(max(zoom, 1.0), MAX_ZOOM)
        if anchor is None:
            anchor = QPointF(self.width() / 2, self.height() / 2)
        before = self._to_image(anchor)
        self.zoom = zoom
        iw, ih = self.image.width(), self.image.height()
        s = min(self.width() / iw, self.height() / ih) * zoom
        self.center = QPointF(
            (before.x() - (anchor.x() - self.width() / 2) / s) / iw,
            (before.y() - (anchor.y() - self.height() / 2) / s) / ih,
        )
        self._clamp()
        self.zoomChanged.emit(self.zoom)
        self.update()

    def clear_lines(self):
        self.lines.clear()
        self.draft = None
        self.linesChanged.emit()
        self.update()

    def set_measure_mode(self, on):
        self.measure_mode = on
        self.draft = None
        self.setCursor(Qt.CursorShape.CrossCursor if on else Qt.CursorShape.ArrowCursor)
        self.update()

    def snapshot(self):
        """Current image at full resolution, including measurements."""
        if self.image is None:
            return None
        img = self.image.copy()
        if self.lines:
            painter = QPainter(img)
            draw_measurements(painter, self.lines, self.px_per_mm, 1.0, 0, 0, ui=max(1.0, img.width() / 1000))
            painter.end()
        return img

    # -- events -----------------------------------------------------------
    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(16, 16, 16))
        if self.image is None:
            painter.setPen(QColor(170, 170, 170))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.message)
            return
        s, ox, oy = self._geom()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, s < 3)
        painter.drawImage(QRectF(ox, oy, self.image.width() * s, self.image.height() * s), self.image)
        lines = self.lines + ([self.draft] if self.draft else [])
        draw_measurements(painter, lines, self.px_per_mm, s, ox, oy)

    def resizeEvent(self, _event):
        self._clamp()

    def wheelEvent(self, event):
        steps = event.angleDelta().y() / 120
        if steps:
            self.set_zoom(self.zoom * (1.2 ** steps), event.position())

    def mousePressEvent(self, event):
        if self.image is None:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            if self.measure_mode:
                p = self._to_image(event.position())
                self.draft = (p, p)
            else:
                self._pan_from = event.position()
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
        elif event.button() == Qt.MouseButton.RightButton and self.measure_mode and self.lines:
            self.lines.pop()
            self.linesChanged.emit()
            self.update()

    def mouseMoveEvent(self, event):
        if self.image is None:
            return
        if self.draft is not None:
            self.draft = (self.draft[0], self._to_image(event.position()))
            self.update()
        elif self._pan_from is not None:
            s, _, _ = self._geom()
            d = event.position() - self._pan_from
            self._pan_from = event.position()
            self.center = QPointF(
                self.center.x() - d.x() / (self.image.width() * s),
                self.center.y() - d.y() / (self.image.height() * s),
            )
            self._clamp()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self.draft is not None:
            a, b = self.draft
            self.draft = None
            if math.hypot(b.x() - a.x(), b.y() - a.y()) >= 3:
                self.lines.append((a, b))
                self.linesChanged.emit()
            self.update()
        if self._pan_from is not None:
            self._pan_from = None
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseDoubleClickEvent(self, event):
        if not self.measure_mode:
            self.set_zoom(1.0 if self.zoom > 1.0 else 2.0, event.position())


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.settings = QSettings("MicroView", "MicroView")

        self.active_id = None  # id of the camera that is running
        self.device_path = None
        self.frozen = False
        self.rotation = int(self.settings.value("rotation", 0))
        self.mirror_h = self.settings.value("mirror_h", "false") == "true"
        self.mirror_v = self.settings.value("mirror_v", "false") == "true"
        self.xform = QTransform()
        self._frames = 0
        self._fps = 0.0
        self._inputs = []
        self._formats = []
        self._ctrl_widgets = []
        self.writer = None            # recording in progress
        self._finishing = []          # recordings FFmpeg is still finalizing
        self._failed_encoders = set()

        pictures = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.PicturesLocation)
        self.out_dir = Path(self.settings.value("out_dir", str(Path(pictures) / APP_NAME)))

        self.view = CameraView()
        self.view.px_per_mm = float(self.settings.value("px_per_mm", 0.0))
        self.setCentralWidget(self.view)

        self.session = QMediaCaptureSession(self)
        self.sink = QVideoSink(self)
        self.sink.videoFrameChanged.connect(self.on_frame)
        self.session.setVideoSink(self.sink)
        # One QCamera for the whole lifetime: a new object right after stopping the
        # old one fails with "Camera is in use", because the device is not free yet.
        self.camera = QCamera(self)
        self.camera.errorOccurred.connect(self.on_camera_error)
        self.session.setCamera(self.camera)

        self.devices = QMediaDevices(self)
        self.devices.videoInputsChanged.connect(self.refresh_devices)

        self._build_actions()
        self._build_panel()
        self._update_xform()

        self.info = QLabel()
        self.statusBar().addPermanentWidget(self.info)
        self.view.zoomChanged.connect(lambda _z: self._update_info())
        self.view.linesChanged.connect(self._update_info)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)
        self.finish_timer = QTimer(self)
        self.finish_timer.timeout.connect(self._poll_finishing)

        self.resize(1360, 800)
        self.refresh_devices()
        # Look up FFmpeg in advance, so the first recording starts immediately
        threading.Thread(target=_find_ffmpeg_builds, daemon=True).start()

    # -- construction -------------------------------------------------------
    def _action(self, text, shortcut, slot, checkable=False, tip=None):
        act = QAction(text, self)
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
            act.setToolTip(f"{tip or text} ({shortcut})")
        act.setCheckable(checkable)
        act.triggered.connect(slot)
        self.addAction(act)
        return act

    def _build_actions(self):
        tb = self.addToolBar(tr("Main"))
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.toolbar = tb

        self.act_photo = self._action(tr("📷 Photo"), "Space", self.take_photo, tip=tr("Save a photo"))
        self.act_record = self._action(tr("⏺ Record"), "R", self.toggle_record, True,
                                       tr("Start/stop video recording"))
        self.act_freeze = self._action(tr("⏸ Freeze"), "P", self.toggle_freeze, True, tr("Freeze the image"))
        self.act_measure = self._action(tr("📏 Measure"), "M", self.view.set_measure_mode, True,
                                        tr("Measure: drag a line, right-click removes the last one"))
        self.act_calibrate = self._action(tr("Calibrate…"), "K", self.calibrate,
                                          tip=tr("Use the last measured line as a known length"))
        self.act_clear = self._action(tr("Clear measurements"), "Del", self.view.clear_lines)
        self.act_zoom_out = self._action(tr("Zoom −"), "-", lambda: self.view.set_zoom(self.view.zoom / 1.5),
                                         tip=tr("Zoom out"))
        self.act_zoom_reset = self._action(tr("Zoom 1×"), "0", lambda: self.view.set_zoom(1.0),
                                           tip=tr("Reset digital zoom: fit the whole image in the window"))
        self.act_zoom_in = self._action(tr("Zoom +"), "+", lambda: self.view.set_zoom(self.view.zoom * 1.5),
                                        tip=tr("Zoom in (also: mouse wheel over the image)"))
        # '+' is Shift+= on most layouts; accept every way it can arrive
        self.act_zoom_in.setShortcuts([QKeySequence("+"), QKeySequence("Shift++"), QKeySequence("=")])
        self.act_full = self._action(tr("⛶ Full screen"), "F11", self.toggle_fullscreen, True)
        self.act_folder = self._action(tr("📂 Folder"), "Ctrl+O", self.open_folder,
                                       tip=tr("Open the output folder"))
        self.act_about = self._action(tr("ℹ About"), "F1", self.show_about, tip=tr("About MicroView"))
        self._action("", "Esc", self.leave_fullscreen)

        for act in (self.act_photo, self.act_record, self.act_freeze):
            tb.addAction(act)
        tb.addSeparator()
        for act in (self.act_measure, self.act_calibrate, self.act_clear):
            tb.addAction(act)
        tb.addSeparator()
        for act in (self.act_zoom_out, self.act_zoom_reset, self.act_zoom_in):
            tb.addAction(act)
        tb.addSeparator()
        for act in (self.act_full, self.act_folder):
            tb.addAction(act)
        tb.addSeparator()
        tb.addAction(self.act_about)

    def _build_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)

        cam_box = QGroupBox(tr("Camera"))
        cam_layout = QVBoxLayout(cam_box)
        self.device_combo = QComboBox()
        self.device_combo.activated.connect(self.on_device_selected)
        cam_layout.addWidget(self.device_combo)
        self.format_combo = QComboBox()
        self.format_combo.setToolTip(tr("Resolution and frame rate offered by the camera"))
        self.format_combo.activated.connect(self.on_format_selected)
        cam_layout.addWidget(self.format_combo)
        layout.addWidget(cam_box)

        self.ctrl_box = QGroupBox(tr("Image"))
        self.ctrl_form = QFormLayout(self.ctrl_box)
        layout.addWidget(self.ctrl_box)

        orient_box = QGroupBox(tr("Orientation"))
        orient = QVBoxLayout(orient_box)
        row = QHBoxLayout()
        left = QPushButton(tr("⟲ Left"))
        right = QPushButton(tr("⟳ Right"))
        left.clicked.connect(lambda: self.rotate(-90))
        right.clicked.connect(lambda: self.rotate(90))
        row.addWidget(left)
        row.addWidget(right)
        orient.addLayout(row)
        self.chk_mirror_h = QCheckBox(tr("Mirror horizontally"))
        self.chk_mirror_v = QCheckBox(tr("Mirror vertically"))
        self.chk_mirror_h.setChecked(self.mirror_h)
        self.chk_mirror_v.setChecked(self.mirror_v)
        self.chk_mirror_h.toggled.connect(self.on_mirror)
        self.chk_mirror_v.toggled.connect(self.on_mirror)
        orient.addWidget(self.chk_mirror_h)
        orient.addWidget(self.chk_mirror_v)
        layout.addWidget(orient_box)

        cal_box = QGroupBox(tr("Calibration"))
        cal = QVBoxLayout(cal_box)
        self.cal_label = QLabel()
        self.cal_label.setWordWrap(True)
        cal.addWidget(self.cal_label)
        reset_cal = QPushButton(tr("Clear calibration"))
        reset_cal.clicked.connect(lambda: self.set_calibration(0.0))
        cal.addWidget(reset_cal)
        layout.addWidget(cal_box)

        save_box = QGroupBox(tr("Save"))
        save = QVBoxLayout(save_box)
        self.dir_label = QLabel()
        self.dir_label.setWordWrap(True)
        save.addWidget(self.dir_label)
        row = QHBoxLayout()
        change = QPushButton(tr("Change folder…"))
        change.clicked.connect(self.choose_folder)
        self.photo_format = QComboBox()
        self.photo_format.addItems(["PNG", "JPG"])
        self.photo_format.setCurrentText(self.settings.value("photo_format", "PNG"))
        self.photo_format.currentTextChanged.connect(lambda t: self.settings.setValue("photo_format", t))
        row.addWidget(change)
        row.addWidget(self.photo_format)
        save.addLayout(row)
        layout.addWidget(save_box)

        lang_box = QGroupBox(tr("Language"))
        lang = QVBoxLayout(lang_box)
        self.lang_combo = QComboBox()
        self._languages = ["auto", "en", "nl"]
        self.lang_combo.addItems([tr("Automatic"), "English", "Nederlands"])
        saved = self.settings.value("language", "auto")
        self.lang_combo.setCurrentIndex(self._languages.index(saved) if saved in self._languages else 0)
        self.lang_combo.activated.connect(self.on_language_selected)
        lang.addWidget(self.lang_combo)
        layout.addWidget(lang_box)

        layout.addStretch(1)
        self._update_labels()

        dock = QDockWidget(tr("Settings"), self)
        dock.setObjectName("settings")
        dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
        dock.setWidget(panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self.dock = dock

    def _update_labels(self):
        self.dir_label.setText(str(self.out_dir))
        ppm = self.view.px_per_mm
        if ppm > 0:
            self.cal_label.setText(
                tr("{ppm:.1f} px/mm  (1 px = {um:.2f} µm)\nOnly valid at the same magnification/focus.")
                .format(ppm=ppm, um=1000 / ppm))
        else:
            self.cal_label.setText(
                tr("Not calibrated – measurements in pixels.\n"
                   "Measure a known length (e.g. a ruler) and choose Calibrate."))

    def on_language_selected(self, index):
        self.settings.setValue("language", self._languages[index])
        self.statusBar().showMessage(tr("Restart MicroView to apply the language"), 8000)

    # -- camera -------------------------------------------------------------
    def refresh_devices(self):
        inputs = QMediaDevices.videoInputs()
        current = self.active_id
        self._inputs = inputs
        self.device_combo.clear()
        for dev in inputs:
            self.device_combo.addItem(dev.description())
        if not inputs:
            self.stop_camera(tr("No camera found – connect the microscope"))
            return
        ids = [d.id() for d in inputs]
        if current in ids:
            self.device_combo.setCurrentIndex(ids.index(current))
            return
        wanted = self.settings.value("device", "")
        index = next((i for i, d in enumerate(inputs) if d.description() == wanted), 0)
        self.device_combo.setCurrentIndex(index)
        self.start_camera(inputs[index])

    def on_device_selected(self, index):
        if 0 <= index < len(self._inputs):
            dev = self._inputs[index]
            self.settings.setValue("device", dev.description())
            self.start_camera(dev)

    @staticmethod
    def _format_label(fmt):
        size = fmt.resolution()
        pixel = fmt.pixelFormat().name.replace("Format_", "")
        return f"{size.width()}×{size.height()} · {fmt.maxFrameRate():.0f} fps · {pixel}"

    def on_format_selected(self, index):
        if self.active_id is None or not 0 <= index < len(self._formats):
            return
        self.stop_recording()
        self.camera.stop()
        self.camera.setCameraFormat(self._formats[index])
        self.camera.start()
        self.act_freeze.setChecked(False)
        self.frozen = False
        self.view.clear_lines()

    def stop_camera(self, message):
        self.stop_recording()
        self.camera.stop()
        self.active_id = None
        self.device_path = None
        self._formats = []
        self.format_combo.clear()
        self.view.message = message
        self.view.set_image(None)
        self._build_controls()

    def start_camera(self, device):
        self.stop_camera(tr("Starting camera…"))
        self.camera.setCameraDevice(device)
        # every format the camera offers, highest resolution and frame rate first
        seen = set()
        for fmt in sorted(device.videoFormats(), reverse=True,
                          key=lambda f: (f.resolution().width() * f.resolution().height(), f.maxFrameRate())):
            label = self._format_label(fmt)
            if label not in seen:
                seen.add(label)
                self._formats.append(fmt)
                self.format_combo.addItem(label)
        if self._formats:
            self.camera.setCameraFormat(self._formats[0])
        self.camera.start()
        self.active_id = device.id()
        self.device_path = bytes(device.id().data()).decode(errors="replace")
        self.act_freeze.setChecked(False)
        self.frozen = False
        self.view.clear_lines()
        self._build_controls()

    def on_camera_error(self, _error, text):
        if text:
            message = tr("Camera error: {}").format(text)
            self.view.message = message
            self.statusBar().showMessage(message, 8000)
            self.view.update()

    def on_frame(self, frame):
        self._frames += 1
        if not self.frozen:
            image = frame.toImage()
            if image.isNull():
                return
            if not self.xform.isIdentity():
                image = image.transformed(self.xform)
            self.view.set_image(image)
        if self.writer is not None:
            self._record_frame()

    def _record_frame(self):
        """Records what is shown: the rotated/mirrored image including measurements."""
        image = self.view.snapshot() if self.view.lines else self.view.image
        if image is None:
            return
        if (image.width(), image.height()) != self.writer.size:
            self.stop_recording(tr("Recording stopped: the image size changed"))
            return
        if image.format() != QImage.Format.Format_RGB32:
            image = image.convertToFormat(QImage.Format.Format_RGB32)
        self.writer.write(bytes(image.constBits()))

    # -- image controls -------------------------------------------------------
    def _build_controls(self):
        while self.ctrl_form.rowCount():
            self.ctrl_form.removeRow(0)
        self._ctrl_widgets = []
        controls = list_controls(self.device_path) if self.device_path else []
        if not controls:
            self.ctrl_form.addRow(QLabel(tr("No controls available")))
            return
        for ctrl in controls:
            label = tr(CTRL_LABELS[ctrl["id"]]) if ctrl["id"] in CTRL_LABELS else ctrl["name"]
            if ctrl["kind"] == "bool":
                box = QCheckBox()
                box.setChecked(bool(ctrl["value"]))
                box.toggled.connect(lambda on, c=ctrl: set_control(self.device_path, c["id"], int(on)))
                self.ctrl_form.addRow(label, box)
                self._ctrl_widgets.append((ctrl, box))
                continue
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(ctrl["min"], ctrl["max"])
            slider.setSingleStep(ctrl["step"])
            slider.setValue(ctrl["value"])
            value = QLabel(str(ctrl["value"]))
            value.setMinimumWidth(32)
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            def changed(v, c=ctrl, lab=value):
                lab.setText(str(v))
                set_control(self.device_path, c["id"], v)

            slider.valueChanged.connect(changed)
            row = QHBoxLayout()
            row.addWidget(slider, 1)
            row.addWidget(value)
            self.ctrl_form.addRow(label, row)
            self._ctrl_widgets.append((ctrl, slider))
        reset = QPushButton(tr("Defaults"))
        reset.clicked.connect(self.reset_controls)
        self.ctrl_form.addRow(reset)

    def reset_controls(self):
        for ctrl, widget in self._ctrl_widgets:
            if isinstance(widget, QCheckBox):
                widget.setChecked(bool(ctrl["default"]))
            else:
                widget.setValue(ctrl["default"])

    # -- orientation ----------------------------------------------------------
    def _update_xform(self):
        t = QTransform()
        t.scale(-1 if self.mirror_h else 1, -1 if self.mirror_v else 1)
        t.rotate(self.rotation)
        self.xform = t
        self.settings.setValue("rotation", self.rotation)
        self.settings.setValue("mirror_h", "true" if self.mirror_h else "false")
        self.settings.setValue("mirror_v", "true" if self.mirror_v else "false")

    def rotate(self, degrees):
        self.rotation = (self.rotation + degrees) % 360
        self._orientation_changed()

    def on_mirror(self):
        self.mirror_h = self.chk_mirror_h.isChecked()
        self.mirror_v = self.chk_mirror_v.isChecked()
        self._orientation_changed()

    def _orientation_changed(self):
        self._update_xform()
        self.view.clear_lines()  # the lines belong to the old orientation
        if self.frozen:
            self.act_freeze.setChecked(False)
            self.frozen = False

    # -- photo / video --------------------------------------------------------
    def _new_path(self, extension):
        self.out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.out_dir / f"microview_{stamp}.{extension}"
        n = 2
        while path.exists():
            path = self.out_dir / f"microview_{stamp}_{n}.{extension}"
            n += 1
        return path

    def take_photo(self):
        image = self.view.snapshot()
        if image is None:
            self.statusBar().showMessage(tr("No image to save"), 4000)
            return
        try:
            path = self._new_path(self.photo_format.currentText().lower())
        except OSError as exc:
            QMessageBox.warning(self, APP_NAME, tr("Cannot create folder:\n{}").format(exc))
            return
        if image.save(str(path), quality=95):
            self.statusBar().showMessage(tr("Photo saved: {}").format(path), 6000)
        else:
            QMessageBox.warning(self, APP_NAME, tr("Saving failed:\n{}").format(path))

    def toggle_record(self, on):
        if not on:
            self.stop_recording()
            return
        self.act_record.setChecked(False)  # set again once the recording really runs
        image = self.view.image
        if image is None:
            self.statusBar().showMessage(tr("No image to record"), 4000)
            return
        encoder = find_encoder(self._failed_encoders)
        if encoder is None:
            QMessageBox.warning(
                self, APP_NAME,
                tr("Video recording needs FFmpeg.\nInstall the 'ffmpeg' package and try again."))
            return
        exe, name, args = encoder
        fps = self.camera.cameraFormat().maxFrameRate() or 30
        try:
            path = self._new_path("mp4")
            self.writer = VideoWriter(exe, name, args, path, image.width(), image.height(), fps)
        except OSError as exc:
            QMessageBox.warning(self, APP_NAME, tr("Could not start recording:\n{}").format(exc))
            return
        self._set_recording(True)

    def stop_recording(self, message=None):
        writer, self.writer = self.writer, None
        if writer is None:
            return
        writer.stop()
        self._finishing.append(writer)
        self.finish_timer.start(200)
        self._set_recording(False)
        if message:
            self.statusBar().showMessage(message, 6000)

    def _set_recording(self, on):
        self.act_record.setChecked(on)
        self.act_record.setText(tr("⏹ Stop") if on else tr("⏺ Record"))
        self._update_info()

    def _poll_finishing(self):
        for writer in [w for w in self._finishing if w.finished()]:
            self._finishing.remove(writer)
            ok, error = writer.result()
            if ok:
                self.statusBar().showMessage(tr("Video saved: {}").format(writer.path), 6000)
                continue
            self._failed_encoders.add(writer.encoder)
            message = tr("Recording failed ({encoder}): {error}.").format(encoder=writer.encoder, error=error)
            fallback = find_encoder(self._failed_encoders)
            if fallback:
                message += tr(" The next recording will use {}.").format(fallback[1])
            self.statusBar().showMessage(message, 12000)
        if not self._finishing:
            self.finish_timer.stop()

    def toggle_freeze(self, on):
        self.frozen = on
        self._update_info()

    # -- measuring ------------------------------------------------------------
    def calibrate(self):
        if not self.view.lines:
            QMessageBox.information(
                self, APP_NAME,
                tr("Turn on Measure and drag a line across a known length first\n"
                   "(for example 1 mm on a ruler). Then choose Calibrate."))
            return
        a, b = self.view.lines[-1]
        px = math.hypot(b.x() - a.x(), b.y() - a.y())
        mm, ok = QInputDialog.getDouble(
            self, tr("Calibrate"), tr("Real length of the last line ({:.0f} px) in mm:").format(px),
            1.0, 0.001, 10000.0, 3)
        if ok and mm > 0:
            self.set_calibration(px / mm)

    def set_calibration(self, px_per_mm):
        self.view.px_per_mm = px_per_mm
        self.settings.setValue("px_per_mm", px_per_mm)
        self._update_labels()
        self.view.update()

    # -- misc -----------------------------------------------------------------
    def choose_folder(self):
        chosen = QFileDialog.getExistingDirectory(self, tr("Choose output folder"), str(self.out_dir))
        if chosen:
            self.out_dir = Path(chosen)
            self.settings.setValue("out_dir", chosen)
            self._update_labels()

    def open_folder(self):
        try:
            self.out_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.out_dir)))

    def show_about(self):
        box = QMessageBox(self)
        box.setWindowTitle(tr("About {}").format(APP_NAME))
        box.setIconPixmap(self.windowIcon().pixmap(96, 96))
        box.setTextFormat(Qt.TextFormat.RichText)
        help_lines = "<br>".join((
            tr("<b>Photo</b> (Space) and <b>video</b> (R) are saved to the output folder as you see them: "
               "rotated, mirrored and with measurements."),
            tr("<b>Zoom</b> with the mouse wheel or the Zoom buttons (+ / −), drag to pan, "
               "<b>Zoom 1×</b> (0) shows the whole image again."),
            tr("<b>Measure</b> (M): drag a line; right-click removes the last one."),
            tr("<b>Calibrate</b> (K): measure a known length and enter it in mm."),
            tr("Brightness, contrast, rotating and mirroring are in the panel on the right."),
        ))
        box.setText(
            f"<h3>{APP_NAME} {APP_VERSION}</h3>"
            f"<p>{tr('Viewer for USB microscopes (UVC cameras).')}</p>"
            f"<p>{help_lines}</p>"
            f"<p>{tr('Author')}: {APP_AUTHOR}<br>"
            f"{tr('License')}: {APP_LICENSE}<br>"
            f'{tr("Source code")}: <a href="{APP_REPO}">{APP_REPO.removeprefix("https://")}</a></p>')
        box.exec()

    def toggle_fullscreen(self, on):
        self.dock.setVisible(not on)
        self.toolbar.setVisible(not on)
        self.statusBar().setVisible(not on)
        if on:
            self.showFullScreen()
        else:
            self.showNormal()

    def leave_fullscreen(self):
        if self.isFullScreen():
            self.act_full.setChecked(False)
            self.toggle_fullscreen(False)

    def _tick(self):
        self._fps = self._frames
        self._frames = 0
        if self.writer is not None and self.writer.crashed():
            self.stop_recording()  # FFmpeg exited by itself; the message follows when it is finalized
        self._update_info()

    def _update_info(self):
        parts = []
        if self.writer is not None:
            secs = int(time.monotonic() - self.writer.started)
            parts.append(f"● REC {secs // 60:02d}:{secs % 60:02d}")
        if self.frozen:
            parts.append(tr("FROZEN"))
        if self.view.image is not None:
            parts.append(f"{self.view.image.width()}×{self.view.image.height()}")
            parts.append(f"{self._fps:.0f} fps")
            parts.append(tr("zoom {:.1f}×").format(self.view.zoom))
        if self.view.lines:
            parts.append(tr("{} measurement(s)").format(len(self.view.lines)))
        self.info.setText("   ".join(parts))
        # zoom buttons only where they do something
        has_image = self.view.image is not None
        self.act_zoom_in.setEnabled(has_image and self.view.zoom < MAX_ZOOM)
        self.act_zoom_out.setEnabled(has_image and self.view.zoom > 1.0)
        self.act_zoom_reset.setEnabled(has_image and self.view.zoom > 1.0)

    def closeEvent(self, event):
        self.stop_camera("")
        for writer in self._finishing:  # let FFmpeg finish recordings in progress
            writer.wait(30)
        self._poll_finishing()
        super().closeEvent(event)


def load_icon():
    """Icon next to the script (source tree, portable build) or from the installed icon folder."""
    if ICON_PATH.exists():
        return QIcon(str(ICON_PATH))
    icon = QIcon.fromTheme("microview")
    if icon.isNull():
        found = QStandardPaths.locate(
            QStandardPaths.StandardLocation.GenericDataLocation,
            "icons/hicolor/scalable/apps/microview.svg")
        if found:
            icon = QIcon(found)
    return icon


def self_test(app, folder):
    """Checks a build without user interaction: the window, FFmpeg encoding and, if present, the camera.

    Run with QT_QPA_PLATFORM=offscreen on a machine without a display. Returns the exit code.
    """
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    window = MainWindow()
    window.out_dir = folder
    window.show()
    ok = True

    encoder = find_encoder()
    print("ffmpeg:", f"{encoder[0]} ({encoder[1]})" if encoder else "not found")
    if encoder:
        exe, name, args = encoder
        frame = QImage(640, 480, QImage.Format.Format_RGB32)
        writer = VideoWriter(exe, name, args, folder / "selftest.mp4", 640, 480, 30)
        for i in range(30):
            frame.fill(QColor.fromHsv(i * 12, 255, 255))
            writer.write(bytes(frame.constBits()))
            time.sleep(1 / 30)
        writer.stop()
        writer.wait(60)
        encoded, error = writer.result()
        print("encode:", "ok" if encoded else f"FAILED: {error}")
        ok = ok and encoded
    else:
        ok = False

    deadline = time.monotonic() + 8
    while window.active_id is not None and window.view.image is None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)
    if window.active_id is None:
        print("camera: none found")
    elif window.view.image is None:
        print("camera: FAILED, no image from", window.device_path)
        ok = False
    else:
        image = window.view.image
        window.take_photo()
        print(f"camera: {window.device_path} {image.width()}x{image.height()}, "
              f"{len(window._ctrl_widgets)} controls")
    window.close()
    print("self-test:", "passed" if ok else "FAILED")
    return 0 if ok else 1


def main():
    if "--version" in sys.argv[1:]:
        print(APP_NAME, APP_VERSION)
        return
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setDesktopFileName("microview")
    choose_language(QSettings("MicroView", "MicroView").value("language", "auto"))
    icon = load_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
    if "--selftest" in sys.argv[1:]:
        rest = sys.argv[sys.argv.index("--selftest") + 1:]
        sys.exit(self_test(app, rest[0] if rest else tempfile.mkdtemp(prefix="microview-selftest-")))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
