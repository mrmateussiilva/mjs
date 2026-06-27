#!/usr/bin/env python3
"""
MJS — Hub de Ferramentas
=========================
Interface unificada com abas. Cada aba É o script, com toda sua lógica
e controles embutidos diretamente — sem janelas separadas.
"""

import sys, os, json, math, gc, shutil, threading, subprocess, webbrowser, datetime, time
from pathlib import Path
from tkinter import filedialog, messagebox

# ── Auto-instalação ────────────────────────────────────────────────────────────
def _pip(*pkgs):
    os.system(f"{sys.executable} -m pip install {' '.join(pkgs)} -q")

try:
    import customtkinter as ctk
except ImportError:
    _pip("customtkinter"); import customtkinter as ctk

try:
    from PIL import Image, ImageOps, ImageDraw, ImageFont
except ImportError:
    _pip("Pillow"); from PIL import Image, ImageOps, ImageDraw, ImageFont

Image.MAX_IMAGE_PIXELS = None

# ── Caminhos ───────────────────────────────────────────────────────────────────
ROOT         = Path(__file__).parent
NOTEPAD_DIR  = ROOT / "notepad"
WS_SERVER    = NOTEPAD_DIR / "ws_server.py"
NOTEPAD_HTML = NOTEPAD_DIR / "notepad.html"

# ── Watchdog (opcional) ────────────────────────────────────────────────────────
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False

# ── Tema ───────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

C_GREEN  = "#22c55e";  C_RED    = "#ef4444"
C_YELLOW = "#f59e0b";  C_BLUE   = "#3b82f6"
C_MUTED  = "#94a3b8";  C_CARD   = "#1e2030"
C_DARK   = "#374151";  C_BG     = "#0f1117"


# ══════════════════════════════════════════════════════════════════════════════
# Widgets auxiliares
# ══════════════════════════════════════════════════════════════════════════════

def _logbox(parent, height=180) -> ctk.CTkTextbox:
    box = ctk.CTkTextbox(parent, height=height, state="disabled",
                          font=ctk.CTkFont(family="Consolas", size=11),
                          fg_color=C_BG, text_color="#a3e635")
    return box

def _log_write(box: ctk.CTkTextbox, msg: str, ts=True):
    prefix = f"[{datetime.datetime.now():%H:%M:%S}]  " if ts else ""
    box.configure(state="normal")
    box.insert("end", prefix + msg + "\n")
    box.see("end")
    box.configure(state="disabled")

def _section(parent, text: str):
    ctk.CTkLabel(parent, text=text,
                 font=ctk.CTkFont(size=12, weight="bold"),
                 text_color=C_MUTED, anchor="w").pack(fill="x", pady=(10, 2))

def _divider(parent):
    ctk.CTkFrame(parent, height=1, fg_color="#2a2d3e").pack(fill="x", pady=6)

def _browse_folder(var: ctk.StringVar, title="Selecionar pasta"):
    f = filedialog.askdirectory(title=title)
    if f: var.set(f)

def _browse_file(var: ctk.StringVar, title="Selecionar arquivo", filetypes=None):
    ft = filetypes or [("Imagens", "*.tif *.tiff *.png *.jpg")]
    f = filedialog.askopenfilename(title=title, filetypes=ft)
    if f: var.set(f)

def _row(parent, label: str, var: ctk.StringVar, browse_fn=None, browse_label="📁"):
    ctk.CTkLabel(parent, text=label, anchor="w",
                 font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x")
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    frame.pack(fill="x", pady=(2, 8))
    ctk.CTkEntry(frame, textvariable=var, height=32).pack(
        side="left", fill="x", expand=True, padx=(0, 6))
    if browse_fn:
        ctk.CTkButton(frame, text=browse_label, width=38, height=32,
                      command=browse_fn).pack(side="left")


# ══════════════════════════════════════════════════════════════════════════════
# ABA 1 — Criar Estrutura do Dia
# ══════════════════════════════════════════════════════════════════════════════

class TabCriarPastas(ctk.CTkFrame):

    SUBPASTAS = ["BOLSINHAS", r"BOLSINHAS\PARA FAZER",
                 "PAINEL_CUT", "CONF", "APS", "TEX"]

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self._build()

    def _build(self):
        # ── Layout em 2 colunas ──
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        left  = ctk.CTkFrame(self, fg_color=C_CARD, corner_radius=12)
        right = ctk.CTkFrame(self, fg_color=C_CARD, corner_radius=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=0)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=0)

        # ── Painel esquerdo — formulário ──
        ctk.CTkLabel(left, text="🗂️  Configuração",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=20, pady=(18, 4))
        _divider(left)

        form = ctk.CTkFrame(left, fg_color="transparent")
        form.pack(fill="x", padx=20)

        # Pasta raiz
        self._var_base = ctk.StringVar(value="Z:\\")
        _row(form, "Pasta raiz:", self._var_base,
             browse_fn=lambda: _browse_folder(self._var_base, "Selecionar pasta raiz"))

        # Nome da pasta do dia (auto-preenchido)
        self._var_day = ctk.StringVar(value=datetime.datetime.now().strftime("%d %m %Y"))
        _row(form, "Nome da pasta do dia:", self._var_day)

        ctk.CTkLabel(form, text="(preenchido com a data de hoje — edite se precisar)",
                     text_color=C_MUTED, font=ctk.CTkFont(size=11)).pack(anchor="w", pady=(0, 10))

        _divider(form)

        ctk.CTkButton(form, text="✅  Criar Estrutura de Pastas", height=42,
                      fg_color=C_BLUE, hover_color="#2563eb",
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._criar).pack(fill="x", pady=8)

        ctk.CTkButton(form, text="🔄  Preencher data de hoje", height=32,
                      fg_color=C_DARK, hover_color="#4b5563",
                      command=self._reset_date).pack(fill="x")

        # ── Painel direito — preview ──
        ctk.CTkLabel(right, text="📋  Preview — Estrutura que será criada",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=20, pady=(18, 4))
        _divider(right)

        self._lbl_target = ctk.CTkLabel(right, text="",
                                         text_color=C_BLUE,
                                         font=ctk.CTkFont(size=13, weight="bold"))
        self._lbl_target.pack(anchor="w", padx=20, pady=(0, 10))

        tree_frame = ctk.CTkScrollableFrame(right, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self._tree_label = ctk.CTkLabel(tree_frame, text="",
                                         text_color=C_MUTED,
                                         font=ctk.CTkFont(family="Consolas", size=12),
                                         justify="left", anchor="w")
        self._tree_label.pack(fill="x")

        # Atualiza preview ao digitar
        self._var_base.trace_add("write", self._update_preview)
        self._var_day.trace_add("write", self._update_preview)
        self._update_preview()

    def _reset_date(self):
        self._var_day.set(datetime.datetime.now().strftime("%d %m %Y"))

    def _update_preview(self, *_):
        base = self._var_base.get().strip().rstrip("\\")
        day  = self._var_day.get().strip()
        if not base or not day:
            self._tree_label.configure(text="")
            self._lbl_target.configure(text="")
            return

        target = Path(base) / day
        self._lbl_target.configure(text=str(target))

        lines  = [f"📁 {day}/"]
        for s in self.SUBPASTAS:
            parts = s.split("\\")
            indent = "   " * len(parts)
            lines.append(f"{indent}📂 {parts[-1]}")

        self._tree_label.configure(text="\n".join(lines))

    def _criar(self):
        base_str = self._var_base.get().strip()
        day_str  = self._var_day.get().strip()

        if not base_str or not day_str:
            messagebox.showwarning("Atenção", "Preencha a pasta raiz e o nome do dia.")
            return

        base = Path(base_str)
        if not base.exists():
            messagebox.showerror("Erro", f"Pasta raiz não encontrada:\n{base_str}")
            return

        target = base / day_str
        try:
            target.mkdir(exist_ok=True)
            for sub in self.SUBPASTAS:
                (target / sub).mkdir(parents=True, exist_ok=True)
            messagebox.showinfo("✅ Sucesso",
                                f"Estrutura criada com sucesso em:\n{target}")
        except Exception as e:
            messagebox.showerror("Erro ao criar pastas", str(e))


# ══════════════════════════════════════════════════════════════════════════════
# ABA 2 — Gerador de Bolsinhas
# ══════════════════════════════════════════════════════════════════════════════

class TabBolsinhas(ctk.CTkFrame):

    EXTS      = {".tif", ".tiff"}
    REGISTRO  = "registro_bolsinhas.txt"
    INTERVALO = 10   # segundos

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self._stop_evt = threading.Event()
        self._thread: threading.Thread | None = None
        self._count = 0
        self._build()

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(0, weight=1)

        left  = ctk.CTkFrame(self, fg_color=C_CARD, corner_radius=12)
        right = ctk.CTkFrame(self, fg_color=C_CARD, corner_radius=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        # ── Controles ──
        ctk.CTkLabel(left, text="🖼️  Configuração",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=20, pady=(18, 4))
        _divider(left)

        form = ctk.CTkFrame(left, fg_color="transparent")
        form.pack(fill="x", padx=20)

        self._var_pasta = ctk.StringVar(value=r"Z:\BOLSINHAS\PARA FAZER")
        _row(form, "Pasta para monitorar:", self._var_pasta,
             browse_fn=lambda: _browse_folder(self._var_pasta, "Pasta de monitoramento"))

        # Status e contador
        self._lbl_status = ctk.CTkLabel(
            left, text="⬤  Parado", text_color=C_MUTED,
            font=ctk.CTkFont(size=13, weight="bold"))
        self._lbl_status.pack(anchor="w", padx=20, pady=(0, 4))

        self._lbl_count = ctk.CTkLabel(
            left, text="Bolsinhas geradas: 0",
            text_color=C_BLUE, font=ctk.CTkFont(size=12))
        self._lbl_count.pack(anchor="w", padx=20, pady=(0, 14))

        _divider(left)

        btn_frame = ctk.CTkFrame(left, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=8)

        self._btn = ctk.CTkButton(
            btn_frame, text="▶  Iniciar Monitor", height=42,
            fg_color=C_GREEN, hover_color="#16a34a",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._toggle)
        self._btn.pack(fill="x", pady=(0, 6))

        ctk.CTkButton(btn_frame, text="🗑  Limpar Log", height=32,
                      fg_color=C_DARK, hover_color="#4b5563",
                      command=self._clear_log).pack(fill="x")

        # ── Log ──
        ctk.CTkLabel(right, text="📋  Log em tempo real",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=20, pady=(18, 4))
        _divider(right)

        log_wrap = ctk.CTkFrame(right, fg_color="transparent")
        log_wrap.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        log_wrap.rowconfigure(0, weight=1)
        log_wrap.columnconfigure(0, weight=1)

        self._log = ctk.CTkTextbox(log_wrap, state="disabled",
                                    font=ctk.CTkFont(family="Consolas", size=11),
                                    fg_color=C_BG, text_color="#a3e635")
        self._log.grid(row=0, column=0, sticky="nsew")

    # ── Lógica ──────────────────────────────────────────────────────────────────

    def _toggle(self):
        if self._thread and self._thread.is_alive():
            self._parar()
        else:
            self._iniciar()

    def _iniciar(self):
        pasta_str = self._var_pasta.get().strip()
        pasta     = Path(pasta_str)

        if not pasta_str:
            messagebox.showwarning("Atenção", "Selecione uma pasta para monitorar.")
            return
        if not pasta.exists() or not pasta.is_dir():
            messagebox.showerror("Erro", f"Pasta inválida:\n{pasta_str}")
            return

        # Teste de permissão de escrita
        test = pasta / ".hub_test"
        try:
            test.touch(); test.unlink()
        except PermissionError:
            messagebox.showerror("Sem permissão",
                                 f"Sem permissão de escrita:\n{pasta_str}")
            return

        self._stop_evt.clear()
        self._thread = threading.Thread(
            target=self._loop, args=(pasta,), daemon=True)
        self._thread.start()

        self._lbl_status.configure(text="⬤  Rodando", text_color=C_GREEN)
        self._btn.configure(text="⏹  Parar Monitor",
                            fg_color=C_RED, hover_color="#dc2626")

    def _parar(self):
        self._stop_evt.set()
        self._lbl_status.configure(text="⬤  Parado", text_color=C_MUTED)
        self._btn.configure(text="▶  Iniciar Monitor",
                            fg_color=C_GREEN, hover_color="#16a34a")
        self._emit("⏹  Monitor encerrado.")

    def _loop(self, pasta: Path):
        self._emit(f"▶  Monitorando: {pasta}")

        def carregar():
            arq = pasta / self.REGISTRO
            if arq.exists():
                return set(l.strip() for l in
                           arq.read_text("utf-8").splitlines() if l.strip())
            return set()

        def salvar(nome: str):
            with open(pasta / self.REGISTRO, "a", encoding="utf-8") as f:
                f.write(nome + "\n")

        def bolsinha_ok(tiff: Path) -> bool:
            return (tiff.parent / ("bolsinha_" + tiff.stem + ".jpeg")).exists()

        while not self._stop_evt.is_set():
            registro  = carregar()
            pendentes = sorted([
                f for f in pasta.iterdir()
                if f.is_file()
                and f.suffix.lower() in self.EXTS
                and not f.stem.lower().startswith("bolsinha_")
                and f.name not in registro
                and not bolsinha_ok(f)
            ])

            for tiff in pendentes:
                if self._stop_evt.is_set():
                    break
                saida = tiff.parent / ("bolsinha_" + tiff.stem + ".jpeg")
                try:
                    self._emit(f"  ⚙  {tiff.name}")
                    with Image.open(tiff) as img:
                        w, h = img.size
                        nw, nh = max(1, round(w*.10)), max(1, round(h*.10))
                        img.convert("RGB").resize((nw, nh), Image.LANCZOS)\
                           .save(saida, "JPEG", quality=85, optimize=True)
                    salvar(tiff.name)
                    tiff.unlink()
                    self._count += 1
                    self.after(0, self._update_count)
                    self._emit(f"  ✅  {saida.name}")
                except Exception as e:
                    self._emit(f"  ❌  Erro: {tiff.name}: {e}")

            self._stop_evt.wait(self.INTERVALO)

    def _emit(self, msg: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.after(0, lambda m=f"[{ts}]  {msg}": self._insert(m))

    def _insert(self, msg: str):
        self._log.configure(state="normal")
        self._log.insert("end", msg + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    def _clear_log(self):
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")

    def _update_count(self):
        self._lbl_count.configure(text=f"Bolsinhas geradas: {self._count}")

    def stop(self):
        self._stop_evt.set()


# ══════════════════════════════════════════════════════════════════════════════
# ABA 3 — Cortador de Painéis  (cort_gui.py embutido)
# ══════════════════════════════════════════════════════════════════════════════

class TabCortador(ctk.CTkFrame):

    COLOR_MAP = {"Preto": "black", "Branco": "white",
                 "Azul": "blue", "Vermelho": "red",
                 "Rosa": "#FF1493", "Roxo": "purple", "Verde": "green"}
    CONFIG_FILE = ROOT / "configuracoes_cortador.json"

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self._build()
        self._load_config()

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(0, weight=1)

        left  = ctk.CTkFrame(self, fg_color=C_CARD, corner_radius=12)
        right = ctk.CTkFrame(self, fg_color=C_CARD, corner_radius=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        # ── Formulário ──────────────────────────────────────────────────────────
        ctk.CTkLabel(left, text="✂️  Configuração do Corte",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=20, pady=(18, 4))
        _divider(left)

        scroll = ctk.CTkScrollableFrame(left, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        self._v_input   = ctk.StringVar()
        self._v_output  = ctk.StringVar()
        self._v_gab     = ctk.StringVar()
        self._v_medidas = ctk.StringVar(value="95, 150, 100")
        self._v_overlap = ctk.StringVar(value="0.5")
        self._v_pad     = ctk.StringVar(value="1.0")
        self._v_tipo    = ctk.StringVar(value="vertical")
        self._v_cor     = ctk.StringVar(value="Preto")
        self._v_inv     = ctk.BooleanVar(value=False)

        _row(scroll, "Pasta de entrada (imagens):", self._v_input,
             browse_fn=lambda: _browse_folder(self._v_input, "Pasta de entrada"))
        _row(scroll, "Pasta de saída (resultado):", self._v_output,
             browse_fn=lambda: _browse_folder(self._v_output, "Pasta de saída"))
        _row(scroll, "Arquivo do gabarito:", self._v_gab,
             browse_fn=lambda: _browse_file(self._v_gab, "Gabarito"))

        _section(scroll, "Medidas das placas (cm, separadas por vírgula):")
        ctk.CTkLabel(scroll, text="Exemplo: 95, 150, 100",
                     text_color=C_MUTED, font=ctk.CTkFont(size=11)).pack(anchor="w")
        ctk.CTkEntry(scroll, textvariable=self._v_medidas,
                     height=32).pack(fill="x", pady=(2, 10))

        grid_cfg = ctk.CTkFrame(scroll, fg_color="transparent")
        grid_cfg.pack(fill="x")
        grid_cfg.columnconfigure((0, 1), weight=1)

        def _cfg_field(parent, label, var, row, col, widget_fn=None):
            ctk.CTkLabel(parent, text=label, anchor="w",
                         font=ctk.CTkFont(size=12)).grid(
                row=row*2, column=col, sticky="w", pady=(6, 0))
            w = widget_fn(parent, var) if widget_fn else \
                ctk.CTkEntry(parent, textvariable=var, height=30, width=120)
            w.grid(row=row*2+1, column=col, sticky="ew", padx=(0, 8), pady=(2, 0))
            return w

        _cfg_field(grid_cfg, "Sobreposição (cm):", self._v_overlap, 0, 0)
        _cfg_field(grid_cfg, "Margem/Pad (cm):", self._v_pad, 0, 1)

        def _combo(parent, var, values):
            c = ctk.CTkComboBox(parent, variable=var, values=values,
                                state="readonly", width=120)
            return c

        _cfg_field(grid_cfg, "Tipo de corte:", self._v_tipo, 1, 0,
                   lambda p, v: _combo(p, v, ["vertical", "horizontal"]))
        _cfg_field(grid_cfg, "Cor do texto:", self._v_cor, 1, 1,
                   lambda p, v: _combo(p, v, list(self.COLOR_MAP.keys())))

        ctk.CTkCheckBox(scroll, text="Inverter corte (180°)",
                        variable=self._v_inv).pack(anchor="w", pady=10)

        # Barra de progresso
        self._prog = ctk.CTkProgressBar(scroll, mode="determinate")
        self._prog.set(0)
        self._prog.pack(fill="x", pady=(8, 4))

        # Botão principal
        self._btn_proc = ctk.CTkButton(
            scroll, text="🚀  Processar Imagens", height=44,
            fg_color=C_BLUE, hover_color="#2563eb",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._start_thread)
        self._btn_proc.pack(fill="x", pady=(4, 0))

        # ── Log ──────────────────────────────────────────────────────────────────
        ctk.CTkLabel(right, text="📋  Log de processamento",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=20, pady=(18, 4))
        _divider(right)

        log_wrap = ctk.CTkFrame(right, fg_color="transparent")
        log_wrap.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        log_wrap.rowconfigure(0, weight=1)
        log_wrap.columnconfigure(0, weight=1)

        self._log = ctk.CTkTextbox(log_wrap, state="disabled",
                                    font=ctk.CTkFont(family="Consolas", size=11),
                                    fg_color=C_BG, text_color="#a3e635")
        self._log.grid(row=0, column=0, sticky="nsew")

        ctk.CTkButton(right, text="🗑  Limpar Log", height=28,
                      fg_color=C_DARK, hover_color="#4b5563",
                      command=self._clear_log).pack(padx=20, pady=(0, 14))

    # ── Persistência ──────────────────────────────────────────────────────────

    def _save_config(self):
        data = {
            "input": self._v_input.get(), "output": self._v_output.get(),
            "gabarito": self._v_gab.get(), "measures": self._v_medidas.get(),
            "overlap": self._v_overlap.get(), "pad": self._v_pad.get(),
            "cut_type": self._v_tipo.get(), "text_color": self._v_cor.get(),
            "invert": self._v_inv.get(),
        }
        try:
            self.CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _load_config(self):
        if not self.CONFIG_FILE.exists():
            return
        try:
            data = json.loads(self.CONFIG_FILE.read_text(encoding="utf-8"))
            self._v_input.set(data.get("input", ""))
            self._v_output.set(data.get("output", ""))
            self._v_gab.set(data.get("gabarito", ""))
            self._v_medidas.set(data.get("measures", "95, 150, 100"))
            self._v_overlap.set(data.get("overlap", "0.5"))
            self._v_pad.set(data.get("pad", "1.0"))
            self._v_tipo.set(data.get("cut_type", "vertical"))
            self._v_cor.set(data.get("text_color", "Preto"))
            self._v_inv.set(data.get("invert", False))
        except Exception:
            pass

    # ── Processamento ─────────────────────────────────────────────────────────

    def _start_thread(self):
        if not self._v_input.get() or not self._v_output.get() or not self._v_gab.get():
            messagebox.showwarning("Atenção",
                                   "Preencha os campos: Entrada, Saída e Gabarito.")
            return

        if not Path(self._v_input.get()).is_dir():
            messagebox.showerror("Erro", "Pasta de entrada não encontrada.")
            return
        if not Path(self._v_output.get()).is_dir():
            messagebox.showerror("Erro", "Pasta de saída não encontrada.")
            return
        if not Path(self._v_gab.get()).is_file():
            messagebox.showerror("Erro", "Arquivo de gabarito não encontrado.")
            return

        try:
            parts    = [m.strip() for m in self._v_medidas.get().split(",") if m.strip()]
            medidas  = [float(m) for m in parts]
            overlap  = float(self._v_overlap.get())
            pad      = float(self._v_pad.get())
        except ValueError:
            messagebox.showerror("Erro", "Verifique as medidas — apenas números e vírgulas.")
            return

        if not medidas:
            messagebox.showerror("Erro", "Informe ao menos uma medida.")
            return

        self._btn_proc.configure(state="disabled", text="⏳  Processando...")
        self._prog.set(0)
        self._emit("─" * 50)
        self._emit("Iniciando processamento...")

        invert_str  = "sim" if self._v_inv.get() else "não"
        text_color  = self.COLOR_MAP.get(self._v_cor.get(), "black")

        threading.Thread(
            target=self._run,
            args=(self._v_input.get(), self._v_output.get(), self._v_gab.get(),
                  medidas, overlap, pad, self._v_tipo.get(), invert_str, text_color),
            daemon=True
        ).start()

    def _run(self, image_path, output_dir, gabarito_path,
             medidas, add_cut, pad, tipo, invert, text_color):

        def log(msg): self._emit(msg)
        def prog(cur, tot): self.after(0, lambda: self._prog.set(cur / tot))

        try:
            images = [f for f in Path(image_path).iterdir()
                      if f.suffix.lower() in ('.png','.jpg','.jpeg','.tif','.tiff')]
            total  = len(images)
            if total == 0:
                log("❌  Nenhuma imagem encontrada na pasta de entrada.")
                self.after(0, self._reset_btn)
                return

            with Image.open(gabarito_path) as tmpl:
                for idx, img_path in enumerate(images):
                    self._process_image(img_path, output_dir, tmpl, medidas,
                                        add_cut, pad, tipo, invert, text_color, log)
                    prog(idx + 1, total)

            log("─" * 50)
            log(f"🎉  Processo finalizado! {total} imagem(ns) processada(s).")
            self.after(0, self._save_config)
            self.after(0, lambda: messagebox.showinfo(
                "Concluído!", f"{total} imagem(ns) processada(s) com sucesso!"))

        except Exception as e:
            log(f"❌  Erro crítico: {e}")

        self.after(0, self._reset_btn)

    def _process_image(self, img_file, output_dir, template,
                        medidas, add_cut, pad_cm, tipo, invert, text_color, log):
        tipo = tipo.lower()
        name = Path(img_file).name

        with Image.open(img_file) as panel:
            icc    = panel.info.get("icc_profile")
            dpi_t  = panel.info.get("dpi", (72, 72))

            if invert != "não":
                panel = panel.transpose(Image.Transpose.ROTATE_180)
            if tipo == "horizontal":
                panel = panel.transpose(Image.Transpose.ROTATE_90)

            dpi = dpi_t
            w, h = panel.size
            log(f"✂️  {name}  ({w/dpi[0]*2.54:.1f}x{h/dpi[1]*2.54:.1f} cm, DPI {dpi[0]})")

            n_placas = len(medidas)
            cut_end  = 0
            x_orig   = 0
            tmpl_w   = math.ceil(template.size[0] * dpi[0] / template.info.get('dpi', (72,72))[0])
            tmpl_h   = math.ceil(template.size[1] * dpi[1] / template.info.get('dpi', (72,72))[1])
            tmpl_res = template.resize((tmpl_w, tmpl_h))

            try:
                fnt = ImageFont.truetype("C:/Windows/Fonts/arial.ttf",
                                         math.ceil(30*(dpi[0]/72)))
            except Exception:
                fnt = ImageFont.load_default()

            for i, mед in enumerate(medidas, 1):
                plate_type = ("start" if i == 1 else
                              "end"   if i == n_placas else "middle")

                if i == 1:
                    cut_end = ((mед + add_cut) * dpi[0]) / 2.54
                    x0, x1  = 0, cut_end
                else:
                    x0      = cut_end - ((2*add_cut) * dpi[0]) / 2.54
                    cut_end = cut_end + (mед * dpi[0]) / 2.54
                    if i == n_placas:
                        cut_end = min(cut_end, w)
                    x1 = cut_end

                plate = panel.crop((x0, 0, x1, h))

                # Contorno + padding
                plate = plate.crop((1, 1, plate.size[0]-1, plate.size[1]-1))
                plate = ImageOps.expand(plate, border=1, fill="black")
                pad_px = math.ceil((pad_cm * dpi[0]) / 2.54)
                plate  = ImageOps.expand(plate, border=pad_px, fill="white")

                pw, ph = plate.size
                draw   = ImageDraw.Draw(plate)
                dpad   = math.ceil((2*pad_cm*dpi[0]) / 2.54)
                num    = f"{(2*i-1 if plate_type != 'start' else i):02d}"

                if plate_type == "start":
                    plate.paste(tmpl_res, (pw - pad_px, 0))
                    draw.text((pw - dpad, 0), num, fill=text_color, font=fnt)
                elif plate_type == "middle":
                    plate.paste(tmpl_res, (0, 0))
                    plate.paste(tmpl_res, (pw - pad_px, 0))
                    draw.text((pad_px, 0), num, fill=text_color, font=fnt)
                    draw.text((pw - dpad, 0), f"{int(num)+1:02d}",
                              fill=text_color, font=fnt)
                else:
                    plate.paste(tmpl_res, (0, 0))
                    draw.text((pad_px, 0), num, fill=text_color, font=fnt)

                draw.text((pad_px, ph - pad_px), name, fill=text_color, font=fnt)

                if tipo == "horizontal":
                    plate = plate.transpose(Image.Transpose.ROTATE_270)
                if invert != "não":
                    plate = plate.transpose(Image.Transpose.ROTATE_180)

                out_name = name.replace(".", f" - P{i:02d}.")
                plate.save(str(Path(output_dir) / out_name),
                           dpi=dpi, icc_profile=icc)

                del plate; gc.collect()
                log(f"  ✅  Placa {i}/{n_placas} salva.")

    def _emit(self, msg: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.after(0, lambda m=f"[{ts}]  {msg}": self._insert(m))

    def _insert(self, msg):
        self._log.configure(state="normal")
        self._log.insert("end", msg + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    def _clear_log(self):
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")

    def _reset_btn(self):
        self._btn_proc.configure(state="normal", text="🚀  Processar Imagens")


# ══════════════════════════════════════════════════════════════════════════════
# ABA 4 — CONF (embutido)
# ══════════════════════════════════════════════════════════════════════════════

class TabConf(ctk.CTkFrame):
    """
    Versão embutida do conf.py.
    Importa as classes Monitor, FileLog e process_tiff diretamente.
    """

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self._monitoring = False
        self._monitor    = None
        self._cnt        = {"ok": 0, "skip": 0, "err": 0, "lotes": 0}
        self._grid_r     = 0
        self._grid_c     = 0
        self._MAX_COLS   = 4
        self._build()

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # ── Barra de controle ──
        bar = ctk.CTkFrame(self, fg_color=C_CARD, corner_radius=12)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        bar.columnconfigure(1, weight=1)

        ctk.CTkLabel(bar, text="Pasta monitorada:").grid(
            row=0, column=0, padx=(16, 6), pady=14)

        self._v_pasta = ctk.StringVar()
        ctk.CTkEntry(bar, textvariable=self._v_pasta,
                     state="readonly").grid(row=0, column=1, sticky="ew", padx=4)

        ctk.CTkButton(bar, text="📂  Selecionar", width=140,
                      command=self._sel_pasta).grid(row=0, column=2, padx=4)

        self._btn_mon = ctk.CTkButton(
            bar, text="▶  Iniciar Monitor", width=170,
            fg_color="#1a7f37", hover_color="#15632c",
            command=self._toggle)
        self._btn_mon.grid(row=0, column=3, padx=4)

        self._lbl_status = ctk.CTkLabel(
            bar, text="● Parado", text_color=C_RED,
            font=ctk.CTkFont(weight="bold"))
        self._lbl_status.grid(row=0, column=4, padx=(10, 16))

        wd_txt = "watchdog ✔" if HAS_WATCHDOG else "watchdog ✘ (polling)"
        wd_clr = C_GREEN if HAS_WATCHDOG else C_YELLOW
        ctk.CTkLabel(bar, text=wd_txt, text_color=wd_clr,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=5, padx=(0, 16))

        # ── Sub-abas internas ──
        self._tabs = ctk.CTkTabview(self)
        self._tabs.grid(row=1, column=0, sticky="nsew")

        t_mon   = self._tabs.add("Monitor")
        t_log   = self._tabs.add("Log Detalhado")
        t_debug = self._tabs.add("Grid de Arquivos")

        self._build_tab_monitor(t_mon)
        self._build_tab_log(t_log)
        self._build_tab_debug(t_debug)

    def _build_tab_monitor(self, t):
        t.grid_columnconfigure(0, weight=1)
        t.grid_rowconfigure(1, weight=1)

        # Contadores
        cnt = ctk.CTkFrame(t, corner_radius=8, fg_color="#161622")
        cnt.grid(row=0, column=0, sticky="ew", padx=4, pady=(6, 10))
        for c in range(4):
            cnt.grid_columnconfigure(c, weight=1)

        def _counter(label, col, color):
            f = ctk.CTkFrame(cnt, corner_radius=8, fg_color="#1e1e2e")
            f.grid(row=0, column=col, padx=8, pady=8, sticky="ew")
            ctk.CTkLabel(f, text=label, text_color="#888",
                         font=ctk.CTkFont(size=11)).pack(pady=(8, 0))
            lbl = ctk.CTkLabel(f, text="0", text_color=color,
                               font=ctk.CTkFont(size=32, weight="bold"))
            lbl.pack(pady=(0, 8))
            return lbl

        self._c_ok    = _counter("✔  Processados", 0, C_GREEN)
        self._c_skip  = _counter("📦  Duplicados",  1, C_YELLOW)
        self._c_err   = _counter("✘  Erros",        2, C_RED)
        self._c_lotes = _counter("🔁  Lotes",        3, "#5b9bd5")

        self._feed = ctk.CTkTextbox(t, wrap="word",
                                     font=ctk.CTkFont(family="Consolas", size=11))
        self._feed.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 4))
        self._feed.configure(state="disabled")

    def _build_tab_log(self, t):
        t.grid_columnconfigure(0, weight=1)
        t.grid_rowconfigure(0, weight=1)
        self._logbox = ctk.CTkTextbox(t, wrap="word",
                                       font=ctk.CTkFont(family="Consolas", size=11))
        self._logbox.grid(row=0, column=0, sticky="nsew")
        self._logbox.configure(state="disabled")

    def _build_tab_debug(self, t):
        t.grid_columnconfigure(0, weight=1)
        t.grid_rowconfigure(0, weight=1)
        self._debug_scroll = ctk.CTkScrollableFrame(t)
        self._debug_scroll.grid(row=0, column=0, sticky="nsew")
        for i in range(self._MAX_COLS):
            self._debug_scroll.grid_columnconfigure(i, weight=1)
        self._lbl_empty = ctk.CTkLabel(
            self._debug_scroll,
            text="Nenhum arquivo processado ainda.", text_color="gray")
        self._lbl_empty.grid(row=0, column=0, columnspan=self._MAX_COLS, pady=20)
        self._grid_started = False

    # ── Controles ─────────────────────────────────────────────────────────────

    def _sel_pasta(self):
        f = filedialog.askdirectory(title="Pasta para monitorar (CONF)")
        if f:
            self._v_pasta.set(f)

    def _toggle(self):
        if self._monitoring: self._parar()
        else:                self._iniciar()

    def _iniciar(self):
        folder = self._v_pasta.get()
        if not folder:
            messagebox.showwarning("Aviso", "Selecione uma pasta primeiro.")
            return
        if not Path(folder).is_dir():
            messagebox.showerror("Erro", "Pasta não encontrada.")
            return

        self._monitoring = True
        self._btn_mon.configure(text="⏹  Parar Monitor",
                                fg_color="#7f1a1a", hover_color="#631515")
        self._lbl_status.configure(text="● Monitorando", text_color=C_GREEN)

        try:
            # Importa a lógica do conf.py
            sys.path.insert(0, str(ROOT))
            from conf import Monitor
            self._monitor = Monitor(
                folder=folder,
                on_log=self._on_log,
                on_debug=self._on_debug,
                on_batch_done=self._on_batch_done,
            )
            self._monitor.start()
            self._log_write(f"=== Monitor iniciado: {folder} ===\n")
            self._feed_write(f"Monitor iniciado → {folder}")
            self._tabs.set("Monitor")
        except Exception as e:
            messagebox.showerror("Erro ao iniciar monitor", str(e))
            self._monitoring = False
            self._btn_mon.configure(text="▶  Iniciar Monitor",
                                    fg_color="#1a7f37", hover_color="#15632c")
            self._lbl_status.configure(text="● Parado", text_color=C_RED)

    def _parar(self):
        if self._monitor:
            self._monitor.stop()
            self._monitor = None
        self._monitoring = False
        self._btn_mon.configure(text="▶  Iniciar Monitor",
                                fg_color="#1a7f37", hover_color="#15632c")
        self._lbl_status.configure(text="● Parado", text_color=C_RED)
        self._log_write("=== Monitor parado ===\n")
        self._feed_write("Monitor parado.")

    def stop(self):
        if self._monitoring:
            self._parar()

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _on_log(self, msg: str):
        self.after(0, lambda m=msg: self._log_write(m))

    def _on_debug(self, info: dict):
        self._cnt["ok"] += 1
        self.after(0, lambda: self._c_ok.configure(text=str(self._cnt["ok"])))
        self.after(0, lambda i=info: self._add_debug_card(i))

    def _on_batch_done(self, n_ok, n_skip, n_err):
        self._cnt["skip"]  += n_skip
        self._cnt["err"]   += n_err
        self._cnt["lotes"] += 1
        self.after(0, lambda: (
            self._c_skip.configure(text=str(self._cnt["skip"])),
            self._c_err.configure(text=str(self._cnt["err"])),
            self._c_lotes.configure(text=str(self._cnt["lotes"])),
        ))
        parts = []
        if n_ok:   parts.append(f"{n_ok} processada(s)")
        if n_skip: parts.append(f"{n_skip} duplicada(s)")
        if n_err:  parts.append(f"{n_err} erro(s)")
        self.after(0, lambda: self._feed_write(
            f"✅  Lote concluído — {' | '.join(parts)}"))

    def _add_debug_card(self, info: dict):
        if not self._grid_started:
            self._lbl_empty.destroy()
            self._grid_started = True

        card = ctk.CTkFrame(self._debug_scroll, corner_radius=8, fg_color="#252538")
        card.grid(row=self._grid_r, column=self._grid_c,
                  padx=10, pady=10, sticky="nsew")

        if "thumb" in info:
            try:
                ctk_img = ctk.CTkImage(
                    light_image=info["thumb"],
                    dark_image=info["thumb"],
                    size=info["thumb"].size)
                ctk.CTkLabel(card, image=ctk_img, text="").pack(pady=(12, 6), padx=10)
            except Exception:
                pass

        ctk.CTkLabel(card, text=info["name"],
                     font=ctk.CTkFont(weight="bold", size=12),
                     text_color="white", wraplength=140).pack(padx=8)
        ctk.CTkLabel(card, text=f"Modo: {info['mode']}",
                     text_color="#5b9bd5", font=ctk.CTkFont(size=11)).pack()
        ctk.CTkLabel(card,
                     text=f"{info['width_cm']:.0f} x {info['height_cm']:.0f} cm",
                     text_color=C_GREEN,
                     font=ctk.CTkFont(size=12, weight="bold")).pack()
        ctk.CTkLabel(card, text=f"DPI: {info['dpi']:.0f}",
                     text_color="#aaa", font=ctk.CTkFont(size=11)).pack(pady=(0, 12))

        self._grid_c += 1
        if self._grid_c >= self._MAX_COLS:
            self._grid_c = 0
            self._grid_r += 1

    def _log_write(self, msg: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._logbox.configure(state="normal")
        self._logbox.insert("end", f"[{ts}]  {msg}\n")
        self._logbox.see("end")
        self._logbox.configure(state="disabled")

        stripped = msg.strip()
        if stripped and any(c in stripped for c in ("[", "✔", "⚠", "↻")):
            self._feed_write(stripped)

    def _feed_write(self, msg: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._feed.configure(state="normal")
        self._feed.insert("end", f"[{ts}]  {msg}\n")
        self._feed.see("end")
        self._feed.configure(state="disabled")


# ══════════════════════════════════════════════════════════════════════════════
# ABA 5 — Notepad Compartilhado
# ══════════════════════════════════════════════════════════════════════════════

class TabNotepad(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self._ws_proc: subprocess.Popen | None = None
        self._build()

    def _build(self):
        self.columnconfigure((0, 1), weight=1)
        self.rowconfigure(0, weight=1)

        left  = ctk.CTkFrame(self, fg_color=C_CARD, corner_radius=12)
        right = ctk.CTkFrame(self, fg_color=C_CARD, corner_radius=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        # ── Servidor WS ──
        ctk.CTkLabel(left, text="🌐  Servidor WebSocket",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=20, pady=(18, 4))
        _divider(left)

        info = ctk.CTkFrame(left, fg_color=C_BG, corner_radius=8)
        info.pack(fill="x", padx=20, pady=8)

        rows = [("Porta:", "8765"), ("Protocolo:", "ws://"),
                ("Acesso na rede:", "ws://[IP do PC]:8765"),
                ("Arquivo de estado:", str(NOTEPAD_DIR / "notes_state.json"))]
        for label, val in rows:
            r = ctk.CTkFrame(info, fg_color="transparent")
            r.pack(fill="x", padx=12, pady=4)
            ctk.CTkLabel(r, text=label, text_color=C_MUTED,
                         font=ctk.CTkFont(size=11), width=130,
                         anchor="w").pack(side="left")
            ctk.CTkLabel(r, text=val, text_color="white",
                         font=ctk.CTkFont(family="Consolas", size=11),
                         anchor="w").pack(side="left")

        self._lbl_ws = ctk.CTkLabel(left,
                                     text="⏳  Inicializando servidor...",
                                     text_color=C_YELLOW,
                                     font=ctk.CTkFont(size=13, weight="bold"))
        self._lbl_ws.pack(anchor="w", padx=20, pady=(12, 4))

        btn_frame = ctk.CTkFrame(left, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=8)
        btn_frame.columnconfigure((0, 1), weight=1)

        self._btn_ws = ctk.CTkButton(
            btn_frame, text="▶  Iniciar Servidor",
            fg_color=C_GREEN, hover_color="#16a34a",
            command=self._toggle_server)
        self._btn_ws.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        ctk.CTkButton(
            btn_frame, text="🌐  Abrir no Navegador",
            fg_color=C_BLUE, hover_color="#2563eb",
            command=self._open_browser
        ).grid(row=0, column=1, padx=(5, 0), sticky="ew")

        # ── Conteúdo atual ──
        ctk.CTkLabel(right, text="📋  Conteúdo atual do notepad",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=20, pady=(18, 4))
        _divider(right)

        self._notes_box = ctk.CTkTextbox(right, state="disabled",
                                          font=ctk.CTkFont(family="Consolas", size=12))
        self._notes_box.pack(fill="both", expand=True, padx=20, pady=(4, 8))

        ctk.CTkButton(right, text="🔄  Atualizar conteúdo", height=32,
                      fg_color=C_DARK, hover_color="#4b5563",
                      command=self._reload_notes).pack(padx=20, pady=(0, 14))

        self._reload_notes()

    # ── Servidor ──────────────────────────────────────────────────────────────

    def start_server(self):
        """Chamado pelo hub ao iniciar (auto-start)."""
        if not WS_SERVER.exists():
            self._lbl_ws.configure(text="❌  ws_server.py não encontrado",
                                    text_color=C_RED)
            return
        try:
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            self._ws_proc = subprocess.Popen(
                [sys.executable, str(WS_SERVER)],
                cwd=str(NOTEPAD_DIR), creationflags=flags)
            # Aguarda 1.5s e verifica
            self.after(1500, self._check_server)
            self._btn_ws.configure(text="⏹  Parar Servidor",
                                    fg_color=C_RED, hover_color="#dc2626")
        except Exception as e:
            self._lbl_ws.configure(text=f"❌  {e}", text_color=C_RED)

    def _check_server(self):
        if self._ws_proc and self._ws_proc.poll() is None:
            self._lbl_ws.configure(
                text=f"✅  Servidor ativo  (PID {self._ws_proc.pid})",
                text_color=C_GREEN)
        else:
            self._lbl_ws.configure(text="❌  Servidor não iniciou",
                                    text_color=C_RED)
            self._btn_ws.configure(text="▶  Iniciar Servidor",
                                    fg_color=C_GREEN, hover_color="#16a34a")

    def _toggle_server(self):
        if self._ws_proc and self._ws_proc.poll() is None:
            # Parar
            try: self._ws_proc.terminate()
            except Exception: pass
            self._ws_proc = None
            self._lbl_ws.configure(text="⬤  Servidor parado", text_color=C_MUTED)
            self._btn_ws.configure(text="▶  Iniciar Servidor",
                                    fg_color=C_GREEN, hover_color="#16a34a")
        else:
            # Iniciar
            self.start_server()

    def _open_browser(self):
        if not NOTEPAD_HTML.exists():
            messagebox.showerror("Erro", f"Arquivo não encontrado:\n{NOTEPAD_HTML}")
            return
        webbrowser.open(NOTEPAD_HTML.as_uri())

    def _reload_notes(self):
        state_file = NOTEPAD_DIR / "notes_state.json"
        if state_file.exists():
            try:
                data = json.loads(state_file.read_text(encoding="utf-8"))
                text = data.get("text", "")
                self._notes_box.configure(state="normal")
                self._notes_box.delete("1.0", "end")
                self._notes_box.insert("end", text)
                self._notes_box.configure(state="disabled")
            except Exception:
                pass

    def stop(self):
        if self._ws_proc:
            try: self._ws_proc.terminate()
            except Exception: pass


# ══════════════════════════════════════════════════════════════════════════════
# ABA 6 — Agente Autônomo
# ══════════════════════════════════════════════════════════════════════════════

class TabAgent(ctk.CTkFrame):

    def __init__(self, master, agent):
        super().__init__(master, fg_color="transparent")
        self.agent = agent
        self._log_pos = 0
        self._build()
        self._refresh_agent_status()
        self._read_log_periodically()

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(0, weight=1)

        left  = ctk.CTkFrame(self, fg_color=C_CARD, corner_radius=12)
        right = ctk.CTkFrame(self, fg_color=C_CARD, corner_radius=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        # ── Painel Esquerdo (Controles e Regras) ─────────────────────────────
        ctk.CTkLabel(left, text="🤖  MJS Agent Autônomo",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=20, pady=(18, 4))
        _divider(left)

        # Botão Ligar/Desligar Agente Geral
        self._btn_toggle = ctk.CTkButton(
            left, text="▶  Ligar Agente", height=42,
            fg_color=C_GREEN, hover_color="#16a34a",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._toggle_agent
        )
        self._btn_toggle.pack(fill="x", padx=20, pady=(10, 6))

        self._btn_reload = ctk.CTkButton(
            left, text="🔄  Recarregar regras.md", height=32,
            fg_color=C_DARK, hover_color="#4b5563",
            command=self._reload_rules
        )
        self._btn_reload.pack(fill="x", padx=20, pady=(0, 10))

        # Status Geral
        self._lbl_status = ctk.CTkLabel(
            left, text="Status Geral: Desligado", text_color=C_MUTED,
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self._lbl_status.pack(anchor="w", padx=20, pady=(4, 12))

        _divider(left)

        # Seção de Regras Detectadas
        ctk.CTkLabel(left, text="📋 Regras Ativas no Config:",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=C_MUTED).pack(anchor="w", padx=20, pady=(4, 6))

        self._rules_scroll = ctk.CTkScrollableFrame(left, fg_color="transparent", height=250)
        self._rules_scroll.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        self._rule_labels = []

        # Botão para editar regras.md diretamente
        ctk.CTkButton(left, text="📝 Editar regras.md", height=32,
                      fg_color=C_BLUE, hover_color="#2563eb",
                      command=self._open_rules_file).pack(fill="x", padx=20, pady=(0, 15))

        # ── Painel Direito (Logs do Agente) ──────────────────────────────────
        ctk.CTkLabel(right, text="📋 Log de Eventos do Agente",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=20, pady=(18, 4))
        _divider(right)

        log_wrap = ctk.CTkFrame(right, fg_color="transparent")
        log_wrap.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        log_wrap.rowconfigure(0, weight=1)
        log_wrap.columnconfigure(0, weight=1)

        self._log = ctk.CTkTextbox(log_wrap, state="disabled",
                                    font=ctk.CTkFont(family="Consolas", size=11),
                                    fg_color=C_BG, text_color="#a3e635")
        self._log.grid(row=0, column=0, sticky="nsew")

    def _toggle_agent(self):
        if self.agent.running:
            self.agent.stop()
        else:
            self.agent.start()
        self._refresh_agent_status()

    def _reload_rules(self):
        if self.agent.running:
            # Força o recarregamento manual disparando uma modificação fictícia no mtime
            try:
                os.utime(str(ROOT / "regras.md"), None)
                _log_write(self._log, "Solicitado recarregamento de regras...", ts=True)
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível sinalizar recarga de regras: {e}")
        else:
            messagebox.showwarning("Aviso", "O agente precisa estar ligado para recarregar as regras.")

    def _open_rules_file(self):
        rules_path = ROOT / "regras.md"
        if rules_path.exists():
            try:
                os.startfile(rules_path)
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível abrir o arquivo regras.md: {e}")

    def _refresh_agent_status(self):
        # Atualiza Status e Botão
        if self.agent.running:
            self._lbl_status.configure(text="Status Geral: LIGADO", text_color=C_GREEN)
            self._btn_toggle.configure(text="⏹  Desligar Agente", fg_color=C_RED, hover_color="#dc2626")
        else:
            self._lbl_status.configure(text="Status Geral: DESLIGADO", text_color=C_MUTED)
            self._btn_toggle.configure(text="▶  Ligar Agente", fg_color=C_GREEN, hover_color="#16a34a")

        # Atualiza lista de regras
        for widget in self._rule_labels:
            widget.destroy()
        self._rule_labels.clear()

        sys.path.insert(0, str(ROOT))
        from agent import parse_regras_md
        regras, _ = parse_regras_md(ROOT / "regras.md")

        if not regras:
            lbl = ctk.CTkLabel(self._rules_scroll, text="Nenhuma regra encontrada ou erro no arquivo.", text_color=C_MUTED)
            lbl.pack(anchor="w", padx=10, pady=5)
            self._rule_labels.append(lbl)
        else:
            for nome, config in regras.items():
                f = ctk.CTkFrame(self._rules_scroll, fg_color="#1e1e2e", corner_radius=6)
                f.pack(fill="x", pady=4, padx=5)
                self._rule_labels.append(f)
                
                status_color = C_GREEN if self.agent.running else C_MUTED
                status_text = "● Ativa" if self.agent.running else "● Parada"
                
                ctk.CTkLabel(f, text=status_text, text_color=status_color, font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=8, pady=4)
                ctk.CTkLabel(f, text=f"{nome} ({config.get('gatilho', 'desconhecido')})", font=ctk.CTkFont(size=11), text_color="white").pack(side="left", padx=5, pady=4)

    def _read_log_periodically(self):
        log_file = ROOT / "agent_log.txt"
        if log_file.exists():
            try:
                # Lê a partir da última posição lida para economizar recursos e evitar piscadas
                size = log_file.stat().st_size
                if size < self._log_pos:
                    self._log_pos = 0 # Reiniciou o arquivo
                
                if size > self._log_pos:
                    with open(log_file, "r", encoding="utf-8") as f:
                        f.seek(self._log_pos)
                        new_lines = f.read()
                        self._log_pos = f.tell()
                        
                    if new_lines:
                        self._log.configure(state="normal")
                        self._log.insert("end", new_lines)
                        self._log.see("end")
                        self._log.configure(state="disabled")
                        
                        # Sempre que houver novo log, atualiza a lista de regras para refletir qualquer mudança de status
                        self._refresh_agent_status()
            except Exception:
                pass
        
        self.after(1000, self._read_log_periodically)


# ══════════════════════════════════════════════════════════════════════════════
# Janela Principal — Hub com CTkTabview
# ══════════════════════════════════════════════════════════════════════════════

class HubApp(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("MJS — Hub de Ferramentas")
        self.geometry("1180x800")
        self.minsize(1000, 680)

        # Instancia o motor do Agente
        sys.path.insert(0, str(ROOT))
        from agent import MjsAgent
        self.agent = MjsAgent()

        self._build_ui()
        self._tick_clock()

        # Auto-start do servidor Notepad
        self.after(500, self._tab_notepad.start_server)
        
        # Auto-start do Agente
        self.after(800, self._start_agent_automatically)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _start_agent_automatically(self):
        self.agent.start()
        # Atualiza a aba do Agente para mostrar que ele ligou
        if "🤖 Agente" in self._tab_refs:
            self._tab_refs["🤖 Agente"]._refresh_agent_status()

    def _build_ui(self):
        # ── Header ────────────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color=C_BG, corner_radius=0, height=62)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(header,
                     text="🛠  MJS — Hub de Ferramentas",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(side="left", padx=22)

        self._lbl_clock = ctk.CTkLabel(header, text="",
                                        font=ctk.CTkFont(size=13),
                                        text_color=C_MUTED)
        self._lbl_clock.pack(side="right", padx=22)

        # ── Abas ──────────────────────────────────────────────────────────────
        tabs = ctk.CTkTabview(self, anchor="nw")
        tabs.pack(fill="both", expand=True, padx=16, pady=(10, 16))

        ABAS = [
            ("🤖 Agente",           lambda f: TabAgent(f, self.agent)),
            ("🗂️  Criar Pastas",     TabCriarPastas),
            ("🖼️  Bolsinhas",        TabBolsinhas),
            ("✂️  Cortador",         TabCortador),
            ("📄  CONF",             TabConf),
            ("📋  Notepad",          TabNotepad),
        ]

        self._tab_refs = {}
        for nome, Cls in ABAS:
            frame = tabs.add(nome)
            frame.grid_columnconfigure(0, weight=1)
            frame.grid_rowconfigure(0, weight=1)

            widget = Cls(frame)
            widget.grid(row=0, column=0, sticky="nsew")
            self._tab_refs[nome] = widget

        self._tab_notepad  = self._tab_refs["📋  Notepad"]
        self._tab_bolsinhas = self._tab_refs["🖼️  Bolsinhas"]
        self._tab_conf      = self._tab_refs["📄  CONF"]

    def _tick_clock(self):
        now = datetime.datetime.now().strftime("%A, %d/%m/%Y   %H:%M:%S")
        self._lbl_clock.configure(text=now)
        self.after(1000, self._tick_clock)

    def _on_close(self):
        self._tab_bolsinhas.stop()
        self._tab_conf.stop()
        self._tab_notepad.stop()
        self.agent.stop()
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = HubApp()
    app.mainloop()
