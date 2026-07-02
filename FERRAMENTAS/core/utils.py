import os
import math
import time
import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from core.config import FONT_CANDIDATES

DPI_FALLBACK = 300

Image.MAX_IMAGE_PIXELS = None


def cm_to_px(cm: float, dpi: float) -> int:
    return int(round(cm * dpi / 2.54))


def px_to_cm(px: int, dpi: float) -> float:
    return round(px * 2.54 / dpi, 2)


def get_dpi(img: Image.Image, fallback=300) -> float:
    info = img.info or {}
    dpi = info.get("dpi")
    if dpi:
        val = dpi[0] if isinstance(dpi, (tuple, list)) else dpi
        if float(val) > 0:
            return float(val)
    for key in ("x_resolution", "XResolution"):
        xres = info.get(key)
        if xres is not None:
            if isinstance(xres, tuple) and len(xres) == 2 and xres[1]:
                return float(xres[0]) / float(xres[1])
            try:
                val = float(xres)
                if val > 0:
                    return val
            except (TypeError, ValueError):
                pass
    return fallback


def find_font(size_px: int):
    for fp in FONT_CANDIDATES:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size_px)
            except Exception:
                continue
    return ImageFont.load_default()


def get_font(size):
    for name in ("arial.ttf", "Arial.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except IOError:
            continue
    return ImageFont.load_default()


def black_color(mode: str):
    return {"CMYK": (0, 0, 0, 255), "RGBA": (0, 0, 0, 255),
            "LA": (0, 255), "L": 0, "1": 0}.get(mode, (0, 0, 0))


def white_color(mode: str):
    return {"CMYK": (0, 0, 0, 0), "RGBA": (255, 255, 255, 255),
            "LA": (255, 255), "L": 255, "1": 1}.get(mode, (255, 255, 255))


def get_client_name(filename: str) -> str:
    stem = Path(filename).stem
    return stem.split(" - ", maxsplit=1)[0].strip().upper()


def notify(title: str, msg: str):
    try:
        from win10toast import ToastNotifier
        ToastNotifier().show_toast(title, msg, duration=6, threaded=True)
        return
    except Exception:
        pass
    try:
        from plyer import notification
        notification.notify(title=title, message=msg, timeout=6)
    except Exception:
        pass


def wait_until_stable(filepath: str, wait: float = 1.5):
    prev = -1
    while True:
        try:
            cur = os.path.getsize(filepath)
        except OSError:
            cur = -1
        if cur == prev and cur >= 0:
            break
        prev = cur
        time.sleep(wait)


def stamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def log_time() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")
