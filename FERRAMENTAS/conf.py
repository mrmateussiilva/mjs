import os
import sys
import threading
import datetime
from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog, messagebox

from core.conf import Monitor, FileLog, process_tiff
from core.utils import notify

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

HAS_WATCHDOG = False
try:
    from watchdog.observers import Observer
    HAS_WATCHDOG = True
except ImportError:
    pass


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("TIFF Processor — Monitor Automatico")
        self.geometry("1100x720")
        self.minsize(750, 500)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.folder_path = ctk.StringVar()
        self.debug_info: list[dict] = []
        self.grid_row_idx = 0
        self.grid_col_idx = 0
        self.max_cols = 4

        self._monitor: Monitor | None = None
        self._monitoring = False
        self._cnt_ok = self._cnt_skip = self._cnt_err = self._cnt_tot = 0

        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 4))
        top.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top, text="Pasta monitorada:").grid(row=0, column=0, padx=(0, 6))
        ctk.CTkEntry(top, textvariable=self.folder_path, state="readonly").grid(row=0, column=1, sticky="ew", padx=4)
        ctk.CTkButton(top, text="Selecionar", width=140, command=self._select_folder).grid(row=0, column=2, padx=(4, 0))

        self.btn_monitor = ctk.CTkButton(top, text="Iniciar Monitor", width=165, fg_color="#1a7f37", hover_color="#15632c", command=self._toggle_monitor)
        self.btn_monitor.grid(row=0, column=3, padx=(8, 0))

        self.lbl_status = ctk.CTkLabel(top, text="Parado", text_color="#e74c3c", font=ctk.CTkFont(weight="bold"))
        self.lbl_status.grid(row=0, column=4, padx=(12, 0))

        wd_txt = "watchdog OK" if HAS_WATCHDOG else "watchdog (polling)"
        wd_clr = "#2ecc71" if HAS_WATCHDOG else "#e67e22"
        ctk.CTkLabel(top, text=wd_txt, text_color=wd_clr, font=ctk.CTkFont(size=11)).grid(row=0, column=5, padx=(10, 0))

        self.tabs = ctk.CTkTabview(self)
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=16, pady=(4, 14))

        self.tab_monitor = self.tabs.add("Monitor")
        self.tab_log = self.tabs.add("Log detalhado")
        self.tab_debug = self.tabs.add("Grid de Arquivos")

        self._build_tab_monitor()
        self._build_tab_log()
        self._build_tab_debug()

    def _build_tab_monitor(self):
        t = self.tab_monitor
        t.grid_columnconfigure(0, weight=1)
        t.grid_rowconfigure(1, weight=1)

        cnt = ctk.CTkFrame(t, corner_radius=8, fg_color="#161622")
        cnt.grid(row=0, column=0, sticky="ew", padx=4, pady=(6, 10))
        for col in range(4):
            cnt.grid_columnconfigure(col, weight=1)

        def _counter(label, col, color):
            f = ctk.CTkFrame(cnt, corner_radius=8, fg_color="#1e1e2e")
            f.grid(row=0, column=col, padx=8, pady=8, sticky="ew")
            ctk.CTkLabel(f, text=label, text_color="#888", font=ctk.CTkFont(size=11)).pack(pady=(8, 0))
            lbl = ctk.CTkLabel(f, text="0", text_color=color, font=ctk.CTkFont(size=32, weight="bold"))
            lbl.pack(pady=(0, 8))
            return lbl

        self.cnt_ok = _counter("Processados", 0, "#2ecc71")
        self.cnt_skip = _counter("Duplicados", 1, "#e67e22")
        self.cnt_err = _counter("Erros", 2, "#e74c3c")
        self.cnt_tot = _counter("Lotes", 3, "#5b9bd5")

        self.feed = ctk.CTkTextbox(t, wrap="word", font=("Courier", 11))
        self.feed.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 4))
        self.feed.configure(state="disabled")

    def _build_tab_log(self):
        t = self.tab_log
        t.grid_columnconfigure(0, weight=1)
        t.grid_rowconfigure(0, weight=1)
        self.log_box = ctk.CTkTextbox(t, wrap="word", font=("Courier", 11))
        self.log_box.grid(row=0, column=0, sticky="nsew")
        self.log_box.configure(state="disabled")

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

    def _feed_append(self, msg: str):
        def _do():
            self.feed.configure(state="normal")
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            self.feed.insert("end", f"[{ts}]  {msg}\n")
            self.feed.see("end")
            self.feed.configure(state="disabled")
        self.after(0, _do)

    def _log_append(self, msg: str):
        def _do():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", msg + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")

            stripped = msg.strip()
            if stripped and (stripped.startswith("[") or "rotacionado" in stripped or "salvo" in stripped):
                self.feed.configure(state="normal")
                ts = datetime.datetime.now().strftime("%H:%M:%S")
                self.feed.insert("end", f"[{ts}]  {stripped}\n")
                self.feed.see("end")
                self.feed.configure(state="disabled")
        self.after(0, _do)

    def _add_debug_row(self, info: dict):
        def _do():
            if not self._grid_started:
                self.lbl_empty.destroy()
                self._grid_started = True

            card = ctk.CTkFrame(self.debug_scroll, corner_radius=8, fg_color="#252538")
            card.grid(row=self.grid_row_idx, column=self.grid_col_idx, padx=10, pady=10, sticky="nsew")

            if "thumb" in info:
                ctk_img = ctk.CTkImage(light_image=info["thumb"], dark_image=info["thumb"], size=info["thumb"].size)
                ctk.CTkLabel(card, image=ctk_img, text="").pack(pady=(12, 6), padx=10)

            ctk.CTkLabel(card, text=info["name"], font=ctk.CTkFont(weight="bold", size=13), text_color="white", wraplength=140).pack(padx=8)
            ctk.CTkLabel(card, text=f"Modo: {info['mode']}", text_color="#5b9bd5", font=ctk.CTkFont(size=11)).pack()
            ctk.CTkLabel(card, text=f"{info['width_cm']:.0f} x {info['height_cm']:.0f} cm", text_color="#2ecc71", font=ctk.CTkFont(size=12, weight="bold")).pack()
            ctk.CTkLabel(card, text=f"DPI: {info['dpi']:.0f}", text_color="#aaa", font=ctk.CTkFont(size=11)).pack(pady=(0, 12))

            self.grid_col_idx += 1
            if self.grid_col_idx >= self.max_cols:
                self.grid_col_idx = 0
                self.grid_row_idx += 1
        self.after(0, _do)

    def _on_log(self, msg: str):
        self._log_append(msg)

    def _on_debug(self, info: dict):
        self.debug_info.append(info)
        self._add_debug_row(info)
        self._cnt_ok += 1
        self.after(0, lambda: self.cnt_ok.configure(text=str(self._cnt_ok)))

    def _on_batch_done(self, n_ok: int, n_skip: int, n_err: int):
        self._cnt_skip += n_skip
        self._cnt_err += n_err
        self._cnt_tot += 1
        self.after(0, lambda: (
            self.cnt_skip.configure(text=str(self._cnt_skip)),
            self.cnt_err.configure(text=str(self._cnt_err)),
            self.cnt_tot.configure(text=str(self._cnt_tot)),
        ))
        total = n_ok + n_skip + n_err
        if total == 0:
            return
        parts = []
        if n_ok: parts.append(f"{n_ok} processada(s)")
        if n_skip: parts.append(f"{n_skip} duplicada(s)")
        if n_err: parts.append(f"{n_err} erro(s)")
        self._feed_append(f"Lote concluido — {' | '.join(parts)}")
        threading.Thread(target=notify, args=("TIFF Processor", f"Lote: {' | '.join(parts)}"), daemon=True).start()

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
            messagebox.showerror("Erro", "Pasta nao encontrada.")
            return

        self._monitoring = True
        self.btn_monitor.configure(text="Parar Monitor", fg_color="#7f1a1a", hover_color="#631515")
        self.lbl_status.configure(text="Monitorando", text_color="#2ecc71")

        self._monitor = Monitor(
            folder=folder,
            on_log=self._on_log,
            on_debug=self._on_debug,
            on_batch_done=self._on_batch_done,
        )
        self._monitor.start()
        self._log_append(f"=== Monitor iniciado: {folder} ===\n")
        self._feed_append(f"Monitor iniciado -> {folder}")
        self.tabs.set("Monitor")

    def _stop_monitor(self):
        if self._monitor:
            self._monitor.stop()
            self._monitor = None
        self._monitoring = False
        self.btn_monitor.configure(text="Iniciar Monitor", fg_color="#1a7f37", hover_color="#15632c")
        self.lbl_status.configure(text="Parado", text_color="#e74c3c")
        self._log_append("=== Monitor parado ===\n")
        self._feed_append("Monitor parado.")

    def _on_close(self):
        self._stop_monitor()
        self.destroy()


if __name__ == "__main__":
    if not HAS_WATCHDOG:
        print("AVISO: watchdog nao instalado. Usando polling.\nInstale: pip install watchdog")
    app = App()
    app.mainloop()
