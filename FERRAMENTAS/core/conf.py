import os
import time
import shutil
import threading
import datetime
from pathlib import Path

from PIL import Image, ImageDraw

from core.config import EXTENSOES_TIFF
from core.utils import (
    cm_to_px, px_to_cm, get_dpi, get_client_name,
    find_font, black_color, white_color, wait_until_stable,
    stamp, notify,
)


TARGET_WIDTH_CM = 155.0
PAD_CM = 1.0
BORDER_PX = 1
TEXT_LEFT_CM = 0.3
STABLE_WAIT = 1.5
POLL_INTERVAL = 3.0
LOG_FILENAME = "processados.log"


class FileLog:
    def __init__(self, folder: Path):
        self._lock = threading.Lock()
        self._processed: set[str] = set()
        self.reload(folder)

    def reload(self, folder: Path):
        with self._lock:
            self.path = folder / LOG_FILENAME
            self._processed.clear()
            if self.path.exists():
                with open(self.path, encoding="utf-8") as f:
                    for line in f:
                        name = line.split("|")[0].strip()
                        if name:
                            self._processed.add(name)

    def already_done(self, filename: str) -> bool:
        with self._lock:
            return filename in self._processed

    def mark_done(self, filename: str, extra: str = ""):
        with self._lock:
            self._processed.add(filename)
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(f"{filename}  |  {ts}  |  {extra}\n")


def process_tiff(filepath: str, emit=None) -> dict:
    path = Path(filepath)
    client_name = get_client_name(path.name)

    def log(msg):
        if emit:
            emit(msg)

    img = Image.open(filepath)
    icc_profile = img.info.get("icc_profile")
    dpi = get_dpi(img)
    original_mode = img.mode

    log(f"[{path.name}] modo={original_mode} DPI={dpi:.1f} ICC={'sim' if icc_profile else 'não'}")
    log(f"  cliente: {client_name}")
    log(f"  original: {img.width}x{img.height}px ({px_to_cm(img.width,dpi)}x{px_to_cm(img.height,dpi)} cm)")

    target_px = cm_to_px(TARGET_WIDTH_CM, dpi)
    tol = 2
    w_is_155 = abs(img.width - target_px) <= tol
    h_is_155 = abs(img.height - target_px) <= tol
    rotated = False

    if w_is_155:
        log(f"  largura ja e ~{TARGET_WIDTH_CM} cm — sem rotacao")
    elif h_is_155:
        img = img.rotate(90, expand=True)
        rotated = True
        log(f"  rotacionado 90 -> {img.width}x{img.height}px ({px_to_cm(img.width,dpi)}x{px_to_cm(img.height,dpi)} cm)")
    else:
        log(f"  nenhum lado e ~{TARGET_WIDTH_CM} cm (larg={px_to_cm(img.width,dpi)} alt={px_to_cm(img.height,dpi)} cm) — sem rotacao")

    w, h = img.size

    bordered = Image.new(original_mode, (w + 2 * BORDER_PX, h + 2 * BORDER_PX), color=black_color(original_mode))
    bordered.paste(img, (BORDER_PX, BORDER_PX))
    img = bordered
    w, h = img.size

    pad_px = cm_to_px(PAD_CM, dpi)
    new_h = h + pad_px
    padded = Image.new(original_mode, (w, new_h), color=white_color(original_mode))
    padded.paste(img, (0, 0))
    img = padded

    draw = ImageDraw.Draw(img)
    font_size_px = cm_to_px(1.0, dpi)
    font = find_font(font_size_px)
    bbox = draw.textbbox((0, 0), client_name, font=font)
    text_h_px = bbox[3] - bbox[1]
    text_x = cm_to_px(TEXT_LEFT_CM, dpi)
    text_y = h + (pad_px - text_h_px) // 2
    draw.text((text_x, text_y), client_name, fill=black_color(original_mode), font=font)

    save_kwargs = {"dpi": (dpi, dpi), "compression": "tiff_lzw"}
    if icc_profile:
        save_kwargs["icc_profile"] = icc_profile

    output_filepath = path.parent.parent / path.name
    img.save(output_filepath, format="TIFF", **save_kwargs)
    log(f"  salvo em: {output_filepath}")

    thumb = img.copy()
    if thumb.mode not in ("RGB", "RGBA"):
        thumb = thumb.convert("RGB")
    thumb.thumbnail((160, 160))

    return {
        "name": path.name,
        "client": client_name,
        "mode": original_mode,
        "dpi": dpi,
        "icc": bool(icc_profile),
        "rotated": rotated,
        "width_px": img.width,
        "height_px": img.height,
        "width_cm": px_to_cm(img.width, dpi),
        "height_cm": px_to_cm(img.height, dpi),
        "thumb": thumb,
    }


class Monitor:
    def __init__(self, folder: str, on_log, on_debug, on_batch_done):
        self.folder = Path(folder)
        self.on_log = on_log
        self.on_debug = on_debug
        self.on_batch_done = on_batch_done
        self.file_log = FileLog(self.folder)
        self._stop_evt = threading.Event()
        self._queue: list[str] = []
        self._queue_lock = threading.Lock()
        self._in_queue: set[str] = set()
        self._observer = None

    def start(self):
        self._stop_evt.clear()
        self._enqueue_existing()
        threading.Thread(target=self._worker, daemon=True).start()
        self._start_watchdog()

    def stop(self):
        self._stop_evt.set()
        if self._observer:
            self._observer.stop()
            self._observer = None

    def _enqueue_existing(self):
        for p in sorted(self.folder.iterdir()):
            if p.suffix.lower() in EXTENSOES_TIFF and p.name != LOG_FILENAME:
                self._push(str(p))

    def _push(self, filepath: str):
        with self._queue_lock:
            if filepath not in self._in_queue:
                self._in_queue.add(filepath)
                self._queue.append(filepath)

    def _start_watchdog(self):
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            monitor = self

            class Handler(FileSystemEventHandler):
                def on_created(self, event):
                    if not event.is_directory:
                        p = Path(event.src_path)
                        if p.suffix.lower() in EXTENSOES_TIFF:
                            monitor._push(str(p))

                def on_moved(self, event):
                    if not event.is_directory:
                        p = Path(event.dest_path)
                        if p.suffix.lower() in EXTENSOES_TIFF:
                            monitor._push(str(p))

            self._observer = Observer()
            self._observer.schedule(Handler(), str(self.folder), recursive=False)
            self._observer.start()
        except ImportError:
            self._start_poll()

    def _start_poll(self):
        def poll():
            while not self._stop_evt.is_set():
                try:
                    for p in self.folder.iterdir():
                        if p.suffix.lower() in EXTENSOES_TIFF:
                            self._push(str(p))
                except Exception:
                    pass
                self._stop_evt.wait(POLL_INTERVAL)
        threading.Thread(target=poll, daemon=True).start()

    def _worker(self):
        batch_ok = batch_skip = batch_err = 0
        idle_rounds = 0

        while not self._stop_evt.is_set():
            filepath = None
            with self._queue_lock:
                if self._queue:
                    filepath = self._queue.pop(0)

            if filepath is None:
                if batch_ok + batch_skip + batch_err > 0:
                    idle_rounds += 1
                    if idle_rounds >= 2:
                        self.on_batch_done(batch_ok, batch_skip, batch_err)
                        batch_ok = batch_skip = batch_err = 0
                        idle_rounds = 0
                else:
                    idle_rounds = 0
                time.sleep(0.5)
                continue

            idle_rounds = 0
            p = Path(filepath)

            if not p.exists():
                with self._queue_lock:
                    self._in_queue.discard(filepath)
                continue

            if self.file_log.already_done(p.name):
                self.on_log(f"[DUPLICADO] {p.name}")
                try:
                    dest = p.parent.parent / p.name
                    if dest.exists():
                        dest = dest.with_name(f"{dest.stem}_duplicado_{stamp()}{dest.suffix}")
                    shutil.move(str(p), str(dest))
                    self.on_log(f"  movido para: {dest}")
                except Exception as e:
                    self.on_log(f"  erro ao mover: {e}")
                batch_skip += 1
                with self._queue_lock:
                    self._in_queue.discard(filepath)
                continue

            self.on_log(f"[DETECTADO] {p.name}")
            wait_until_stable(filepath, STABLE_WAIT)

            if not p.exists():
                with self._queue_lock:
                    self._in_queue.discard(filepath)
                continue

            try:
                info = process_tiff(filepath, emit=self.on_log)
                self.file_log.mark_done(p.name, f"rot={'sim' if info['rotated'] else 'nao'} | {info['width_cm']}x{info['height_cm']} cm")
                self.on_debug(info)
                batch_ok += 1

                try:
                    p.unlink()
                except Exception as e:
                    self.on_log(f"  erro ao remover original: {e}")

            except Exception as e:
                self.on_log(f"[ERRO] {p.name}: {e}")
                batch_err += 1

            with self._queue_lock:
                self._in_queue.discard(filepath)
