"""
TIFF Processor — Monitor Automático com Grid Visual
===================================================
Fluxo:
  1. Monitora uma pasta continuamente (watchdog).
  2. Novo TIFF detectado:
       a) Se o nome já está em processados.log → MOVE o arquivo para um nível
          acima (sem apagar). Se já existir um arquivo com esse nome no
          destino (o já processado), o duplicado é renomeado com sufixo
          "_duplicado_AAAAMMDD_HHMMSS" para não sobrescrever o resultado bom.
       b) Se não está → processa:
            - Rotaciona 90° se a ALTURA for ~155 cm (para a LARGURA ficar 155 cm)
            - Contorno preto de 1px em todos os lados
            - Padding de 1 cm na altura (embaixo), fundo branco
            - Nome do cliente à esquerda (~1 cm de fonte)
            - Salva sobrescrevendo um nível acima, preservando ICC e DPI
            - Apaga o original da pasta de monitoramento
            - Registra no processados.log
  3. Ao terminar um lote → notificação nativa do Windows.

Dependências:
    pip install pillow customtkinter watchdog win10toast
"""

import os
import time
import shutil
import threading
import datetime
from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageDraw, ImageFont

# ── watchdog ──────────────────────────────────────────────────────────────────
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False

# ── notificação Windows ───────────────────────────────────────────────────────
def _notify(title: str, msg: str):
    """Notificação nativa Windows; fallback silencioso."""
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


# ── Parâmetros ────────────────────────────────────────────────────────────────
DPI_FALLBACK    = 300
TARGET_WIDTH_CM = 155.0
PAD_CM          = 1.0
BORDER_PX       = 1
TEXT_LEFT_CM    = 0.3
STABLE_WAIT     = 1.5    # segundos aguardando arquivo estabilizar
POLL_INTERVAL   = 3.0    # segundos entre varreduras (sem watchdog)
LOG_FILENAME    = "processados.log"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ═══════════════════════════════════════════════════════════════════════════════
# Utilitários de imagem
# ═══════════════════════════════════════════════════════════════════════════════

def cm_to_px(cm: float, dpi: float) -> int:
    return int(round(cm * dpi / 2.54))

def px_to_cm(px: int, dpi: float) -> float:
    return round(px * 2.54 / dpi, 2)

def get_client_name(filename: str) -> str:
    stem = Path(filename).stem
    return stem.split(" - ", maxsplit=1)[0].strip().upper()

def get_dpi(img: Image.Image) -> float:
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
    return DPI_FALLBACK

def find_font(size_px: int):
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    ]
    for fp in candidates:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size_px)
            except Exception:
                continue
    return ImageFont.load_default()

def black_color(mode: str):
    return {"CMYK":(0,0,0,255),"RGBA":(0,0,0,255),"LA":(0,255),"L":0,"1":0}.get(mode,(0,0,0))

def white_color(mode: str):
    return {"CMYK":(0,0,0,0),"RGBA":(255,255,255,255),"LA":(255,255),"L":255,"1":1}.get(mode,(255,255,255))


# ═══════════════════════════════════════════════════════════════════════════════
# Log em arquivo
# ═══════════════════════════════════════════════════════════════════════════════

class FileLog:
    """Gerencia o processados.log — lista de arquivos já processados."""

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


# ═══════════════════════════════════════════════════════════════════════════════
# Processamento de um TIFF
# ═══════════════════════════════════════════════════════════════════════════════

def wait_until_stable(filepath: str, wait: float = STABLE_WAIT):
    """Aguarda o arquivo parar de crescer (cópia em andamento)."""
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

    log(f"[{path.name}]")
    log(f"  modo={original_mode} | DPI={dpi:.1f} | ICC={'sim' if icc_profile else 'não'}")
    log(f"  cliente: {client_name}")
    log(f"  original: {img.width}x{img.height}px  "
        f"({px_to_cm(img.width,dpi)}x{px_to_cm(img.height,dpi)} cm)")

    # ── Rotação ───────────────────────────────────────────────────────────────
    target_px = cm_to_px(TARGET_WIDTH_CM, dpi)
    tol = 2
    w_is_155 = abs(img.width  - target_px) <= tol
    h_is_155 = abs(img.height - target_px) <= tol
    rotated = False

    if w_is_155:
        log(f"  largura já é ~{TARGET_WIDTH_CM} cm — sem rotação")
    elif h_is_155:
        img = img.rotate(90, expand=True)
        rotated = True
        log(f"  ↻ rotacionado 90° → {img.width}x{img.height}px  "
            f"({px_to_cm(img.width,dpi)}x{px_to_cm(img.height,dpi)} cm)")
    else:
        log(f"  ⚠ nenhum lado é ~{TARGET_WIDTH_CM} cm "
            f"(larg={px_to_cm(img.width,dpi)} cm, alt={px_to_cm(img.height,dpi)} cm) — sem rotação")

    w, h = img.size

    # ── Contorno 1px ──────────────────────────────────────────────────────────
    bordered = Image.new(original_mode, (w+2*BORDER_PX, h+2*BORDER_PX),
                         color=black_color(original_mode))
    bordered.paste(img, (BORDER_PX, BORDER_PX))
    img = bordered
    w, h = img.size
    log(f"  após contorno: {w}x{h}px")

    # ── Padding 1 cm embaixo ──────────────────────────────────────────────────
    pad_px = cm_to_px(PAD_CM, dpi)
    new_h = h + pad_px
    padded = Image.new(original_mode, (w, new_h), color=white_color(original_mode))
    padded.paste(img, (0, 0))
    img = padded
    log(f"  após padding: {w}x{new_h}px  "
        f"({px_to_cm(w,dpi)}x{px_to_cm(new_h,dpi)} cm)")

    # ── Texto à esquerda ──────────────────────────────────────────────────────
    draw = ImageDraw.Draw(img)
    font_size_px = cm_to_px(1.0, dpi)
    font = find_font(font_size_px)
    bbox = draw.textbbox((0, 0), client_name, font=font)
    text_h_px = bbox[3] - bbox[1]
    text_x = cm_to_px(TEXT_LEFT_CM, dpi)
    text_y = h + (pad_px - text_h_px) // 2
    draw.text((text_x, text_y), client_name,
              fill=black_color(original_mode), font=font)
    log(f"  texto '{client_name}' → {font_size_px}px | pos=({text_x},{text_y})")

    # ── Salvar (Um nível acima) ───────────────────────────────────────────────
    save_kwargs = {"dpi": (dpi, dpi), "compression": "tiff_lzw"}
    if icc_profile:
        save_kwargs["icc_profile"] = icc_profile
        
    output_filepath = path.parent.parent / path.name
    img.save(output_filepath, format="TIFF", **save_kwargs)
    log(f"  ✔ salvo em: {output_filepath}\n")

    # ── Gerar Preview para a UI ───────────────────────────────────────────────
    # CTkImage não renderiza CMYK. Convertendo cópia apenas para o preview.
    thumb = img.copy()
    if thumb.mode not in ("RGB", "RGBA"):
        thumb = thumb.convert("RGB")
    thumb.thumbnail((160, 160)) # Reduz para caber no card

    return {
        "name":      path.name,
        "client":    client_name,
        "mode":      original_mode,
        "dpi":       dpi,
        "icc":       bool(icc_profile),
        "rotated":   rotated,
        "width_px":  img.width,
        "height_px": img.height,
        "width_cm":  px_to_cm(img.width, dpi),
        "height_cm": px_to_cm(img.height, dpi),
        "thumb":     thumb,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Motor de monitoramento
# ═══════════════════════════════════════════════════════════════════════════════

class Monitor:
    """Monitora uma pasta e processa TIFFs novos automaticamente."""

    def __init__(self, folder: str, on_log, on_debug, on_batch_done):
        self.folder        = Path(folder)
        self.on_log        = on_log           # callback(str)
        self.on_debug      = on_debug         # callback(dict)
        self.on_batch_done = on_batch_done    # callback(n_ok, n_skip, n_err)
        self.file_log      = FileLog(self.folder)
        self._stop_evt     = threading.Event()
        self._queue: list[str] = []
        self._queue_lock   = threading.Lock()
        self._in_queue: set[str] = set()
        self._observer     = None

    def start(self):
        self._stop_evt.clear()
        self._enqueue_existing()
        threading.Thread(target=self._worker, daemon=True).start()
        if HAS_WATCHDOG:
            self._start_watchdog()
        else:
            threading.Thread(target=self._poll, daemon=True).start()

    def stop(self):
        self._stop_evt.set()
        if self._observer:
            self._observer.stop()
            self._observer = None

    def _enqueue_existing(self):
        for p in sorted(self.folder.iterdir()):
            if p.suffix.lower() in (".tif", ".tiff",".jpg",".jpeg") and p.name != LOG_FILENAME:
                self._push(str(p))

    def _push(self, filepath: str):
        with self._queue_lock:
            if filepath not in self._in_queue:
                self._in_queue.add(filepath)
                self._queue.append(filepath)

    def _start_watchdog(self):
        monitor = self

        class Handler(FileSystemEventHandler):
            def on_created(self, event):
                if not event.is_directory:
                    p = Path(event.src_path)
                    if p.suffix.lower() in (".tif", ".tiff"):
                        monitor._push(str(p))

            def on_moved(self, event):
                if not event.is_directory:
                    p = Path(event.dest_path)
                    if p.suffix.lower() in (".tif", ".tiff"):
                        monitor._push(str(p))

        self._observer = Observer()
        self._observer.schedule(Handler(), str(self.folder), recursive=False)
        self._observer.start()

    def _poll(self):
        while not self._stop_evt.is_set():
            try:
                for p in self.folder.iterdir():
                    if p.suffix.lower() in (".tif", ".tiff"):
                        self._push(str(p))
            except Exception:
                pass
            self._stop_evt.wait(POLL_INTERVAL)

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
                self.on_log(f"[DUPLICADO] {p.name} — já processado anteriormente, movendo sem reprocessar.")
                try:
                    dest = p.parent.parent / p.name
                    if dest.exists():
                        # já existe o arquivo processado com esse nome no destino.
                        # renomeia o duplicado para não sobrescrever o resultado bom.
                        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        dest = dest.with_name(f"{dest.stem}_duplicado_{stamp}{dest.suffix}")
                    shutil.move(str(p), str(dest))
                    self.on_log(f"  📦 movido para: {dest}\n")
                except Exception as e:
                    self.on_log(f"  ⚠ não foi possível mover: {e}\n")
                batch_skip += 1
                with self._queue_lock:
                    self._in_queue.discard(filepath)
                continue

            self.on_log(f"[DETECTADO] {p.name} — aguardando estabilizar…")
            wait_until_stable(filepath)

            if not p.exists():
                with self._queue_lock:
                    self._in_queue.discard(filepath)
                continue

            try:
                info = process_tiff(filepath, emit=self.on_log)
                self.file_log.mark_done(
                    p.name,
                    f"rot={'sim' if info['rotated'] else 'não'} | "
                    f"{info['width_cm']}x{info['height_cm']} cm"
                )
                self.on_debug(info)
                batch_ok += 1
                
                # Exclui o original da pasta monitorada para limpar a fila
                try:
                    p.unlink()
                    self.on_log(f"  🗑 original limpo da fila: {p.name}\n")
                except Exception as e:
                    self.on_log(f"  ⚠ não foi possível excluir o original: {e}\n")
                    
            except Exception as e:
                self.on_log(f"[ERRO] {p.name}: {e}\n")
                batch_err += 1

            with self._queue_lock:
                self._in_queue.discard(filepath)


# ═══════════════════════════════════════════════════════════════════════════════
# Interface gráfica
# ═══════════════════════════════════════════════════════════════════════════════

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("TIFF Processor — Monitor Automático")
        self.geometry("1100x720")
        self.minsize(750, 500)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.folder_path = ctk.StringVar()
        self.debug_info: list[dict] = []
        self.grid_row_idx = 0
        self.grid_col_idx = 0
        self.max_cols = 4 # Quantidade de cards por linha
        
        self._monitor: Monitor | None = None
        self._monitoring = False
        self._cnt_ok = self._cnt_skip = self._cnt_err = self._cnt_tot = 0

        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Barra superior
        top = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 4))
        top.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top, text="Pasta monitorada:").grid(row=0, column=0, padx=(0,6))
        ctk.CTkEntry(top, textvariable=self.folder_path, state="readonly"
                     ).grid(row=0, column=1, sticky="ew", padx=4)
        ctk.CTkButton(top, text="📂  Selecionar", width=140,
                      command=self._select_folder
                      ).grid(row=0, column=2, padx=(4, 0))

        self.btn_monitor = ctk.CTkButton(
            top, text="▶  Iniciar Monitor", width=165,
            fg_color="#1a7f37", hover_color="#15632c",
            command=self._toggle_monitor)
        self.btn_monitor.grid(row=0, column=3, padx=(8, 0))

        self.lbl_status = ctk.CTkLabel(
            top, text="● Parado", text_color="#e74c3c",
            font=ctk.CTkFont(weight="bold"))
        self.lbl_status.grid(row=0, column=4, padx=(12, 0))

        wd_txt = "watchdog ✔" if HAS_WATCHDOG else "watchdog ✘ (polling)"
        wd_clr = "#2ecc71" if HAS_WATCHDOG else "#e67e22"
        ctk.CTkLabel(top, text=wd_txt, text_color=wd_clr,
                     font=ctk.CTkFont(size=11)
                     ).grid(row=0, column=5, padx=(10, 0))

        # Abas
        self.tabs = ctk.CTkTabview(self)
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=16, pady=(4, 14))

        self.tab_monitor = self.tabs.add("Monitor")
        self.tab_log     = self.tabs.add("Log detalhado")
        self.tab_debug   = self.tabs.add("Grid de Arquivos")

        self._build_tab_monitor()
        self._build_tab_log()
        self._build_tab_debug()

    # ── Aba Monitor ───────────────────────────────────────────────────────────

    def _build_tab_monitor(self):
        t = self.tab_monitor
        t.grid_columnconfigure(0, weight=1)
        t.grid_rowconfigure(1, weight=1)

        # Contadores
        cnt = ctk.CTkFrame(t, corner_radius=8, fg_color="#161622")
        cnt.grid(row=0, column=0, sticky="ew", padx=4, pady=(6, 10))
        for col in range(4):
            cnt.grid_columnconfigure(col, weight=1)

        def _counter(label, col, color):
            f = ctk.CTkFrame(cnt, corner_radius=8, fg_color="#1e1e2e")
            f.grid(row=0, column=col, padx=8, pady=8, sticky="ew")
            ctk.CTkLabel(f, text=label, text_color="#888",
                         font=ctk.CTkFont(size=11)).pack(pady=(8, 0))
            lbl = ctk.CTkLabel(f, text="0", text_color=color,
                               font=ctk.CTkFont(size=32, weight="bold"))
            lbl.pack(pady=(0, 8))
            return lbl

        self.cnt_ok   = _counter("✔ Processados", 0, "#2ecc71")
        self.cnt_skip = _counter("📦 Duplicados",  1, "#e67e22")
        self.cnt_err  = _counter("✘ Erros",        2, "#e74c3c")
        self.cnt_tot  = _counter("📦 Lotes",        3, "#5b9bd5")

        # Feed de eventos resumido
        self.feed = ctk.CTkTextbox(t, wrap="word", font=("Courier", 11))
        self.feed.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 4))
        self.feed.configure(state="disabled")

    def _feed_append(self, msg: str):
        def _do():
            self.feed.configure(state="normal")
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            self.feed.insert("end", f"[{ts}]  {msg}\n")
            self.feed.see("end")
            self.feed.configure(state="disabled")
        self.after(0, _do)

    # ── Aba Log ───────────────────────────────────────────────────────────────

    def _build_tab_log(self):
        t = self.tab_log
        t.grid_columnconfigure(0, weight=1)
        t.grid_rowconfigure(0, weight=1)
        self.log_box = ctk.CTkTextbox(t, wrap="word", font=("Courier", 11))
        self.log_box.grid(row=0, column=0, sticky="nsew")
        self.log_box.configure(state="disabled")

    def _log_append(self, msg: str):
        def _do():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", msg + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
            
            stripped = msg.strip()
            if stripped and (stripped.startswith("[") or "✔" in stripped
                             or "⚠" in stripped or "↻" in stripped):
                self.feed.configure(state="normal")
                ts = datetime.datetime.now().strftime("%H:%M:%S")
                self.feed.insert("end", f"[{ts}]  {stripped}\n")
                self.feed.see("end")
                self.feed.configure(state="disabled")
        self.after(0, _do)

    # ── Aba Grid de Arquivos ──────────────────────────────────────────────────

    def _build_tab_debug(self):
        t = self.tab_debug
        t.grid_columnconfigure(0, weight=1)
        t.grid_rowconfigure(0, weight=1)
        
        self.debug_scroll = ctk.CTkScrollableFrame(t)
        self.debug_scroll.grid(row=0, column=0, sticky="nsew")
        
        for i in range(self.max_cols):
            self.debug_scroll.grid_columnconfigure(i, weight=1)
            
        self.lbl_empty = ctk.CTkLabel(self.debug_scroll, text="Nenhum arquivo processado ainda.", text_color="gray")
        self.lbl_empty.grid(row=0, column=0, columnspan=self.max_cols, pady=20)
        self._grid_started = False

    def _add_debug_row(self, info: dict):
        def _do():
            if not self._grid_started:
                self.lbl_empty.destroy()
                self._grid_started = True

            # Cria o Card
            card = ctk.CTkFrame(self.debug_scroll, corner_radius=8, fg_color="#252538")
            card.grid(row=self.grid_row_idx, column=self.grid_col_idx, padx=10, pady=10, sticky="nsew")
            
            # Imagem (Preview)
            if "thumb" in info:
                ctk_img = ctk.CTkImage(light_image=info["thumb"], dark_image=info["thumb"], size=info["thumb"].size)
                img_lbl = ctk.CTkLabel(card, image=ctk_img, text="")
                img_lbl.pack(pady=(12, 6), padx=10)

            # Informações Técnicas
            ctk.CTkLabel(card, text=info["name"], font=ctk.CTkFont(weight="bold", size=13), text_color="white", wraplength=140).pack(padx=8)
            ctk.CTkLabel(card, text=f"Modo: {info['mode']}", text_color="#5b9bd5", font=ctk.CTkFont(size=11)).pack()
            ctk.CTkLabel(card, text=f"{info['width_cm']:.0f} x {info['height_cm']:.0f} cm", text_color="#2ecc71", font=ctk.CTkFont(size=12, weight="bold")).pack()
            ctk.CTkLabel(card, text=f"DPI: {info['dpi']:.0f}", text_color="#aaa", font=ctk.CTkFont(size=11)).pack(pady=(0, 12))

            # Controle da quebra de linha do Grid
            self.grid_col_idx += 1
            if self.grid_col_idx >= self.max_cols:
                self.grid_col_idx = 0
                self.grid_row_idx += 1

        self.after(0, _do)

    # ── Callbacks do Monitor ──────────────────────────────────────────────────

    def _on_log(self, msg: str):
        self._log_append(msg)

    def _on_debug(self, info: dict):
        self.debug_info.append(info)
        self._add_debug_row(info)
        self._cnt_ok += 1
        self.after(0, lambda: self.cnt_ok.configure(text=str(self._cnt_ok)))

    def _on_batch_done(self, n_ok: int, n_skip: int, n_err: int):
        self._cnt_skip += n_skip
        self._cnt_err  += n_err
        self._cnt_tot  += 1

        def _do():
            self.cnt_skip.configure(text=str(self._cnt_skip))
            self.cnt_err.configure(text=str(self._cnt_err))
            self.cnt_tot.configure(text=str(self._cnt_tot))
        self.after(0, _do)

        total = n_ok + n_skip + n_err
        if total == 0:
            return

        parts = []
        if n_ok:   parts.append(f"{n_ok} processada(s)")
        if n_skip: parts.append(f"{n_skip} duplicada(s) movida(s)")
        if n_err:  parts.append(f"{n_err} erro(s)")
        summary = " | ".join(parts)

        self._feed_append(f"✅  Lote concluído — {summary}")

        threading.Thread(
            target=_notify,
            args=("TIFF Processor", f"Lote concluído: {summary}"),
            daemon=True
        ).start()

    # ── Controle ──────────────────────────────────────────────────────────────

    def _select_folder(self):
        folder = filedialog.askdirectory(title="Selecionar pasta para monitorar")
        if folder:
            self.folder_path.set(folder)

    def _toggle_monitor(self):
        if self._monitoring:
            self._stop_monitor()
        else:
            self._start_monitor()

    def _start_monitor(self):
        folder = self.folder_path.get()
        if not folder:
            messagebox.showwarning("Aviso", "Selecione uma pasta primeiro.")
            return
        if not Path(folder).is_dir():
            messagebox.showerror("Erro", "Pasta não encontrada.")
            return

        self._monitoring = True
        self.btn_monitor.configure(text="⏹  Parar Monitor",
                                   fg_color="#7f1a1a", hover_color="#631515")
        self.lbl_status.configure(text="● Monitorando", text_color="#2ecc71")

        self._monitor = Monitor(
            folder=folder,
            on_log=self._on_log,
            on_debug=self._on_debug,
            on_batch_done=self._on_batch_done,
        )
        self._monitor.start()
        self._log_append(f"=== Monitor iniciado: {folder} ===\n")
        self._feed_append(f"Monitor iniciado → {folder}")
        self.tabs.set("Monitor")

    def _stop_monitor(self):
        if self._monitor:
            self._monitor.stop()
            self._monitor = None
        self._monitoring = False
        self.btn_monitor.configure(text="▶  Iniciar Monitor",
                                   fg_color="#1a7f37", hover_color="#15632c")
        self.lbl_status.configure(text="● Parado", text_color="#e74c3c")
        self._log_append("=== Monitor parado ===\n")
        self._feed_append("Monitor parado.")

    def _on_close(self):
        self._stop_monitor()
        self.destroy()


# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if not HAS_WATCHDOG:
        print(f"AVISO: 'watchdog' não instalado. Usando polling a cada {POLL_INTERVAL}s.\n"
              f"Instale com:  pip install watchdog")
    app = App()
    app.mainloop()