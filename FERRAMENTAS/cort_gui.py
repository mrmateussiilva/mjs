import os
import json
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from PIL import Image

from core.cortador import cut_boards
from core.config import COLOR_MAP

Image.MAX_IMAGE_PIXELS = None

CONFIG_FILE = Path(__file__).parent / "configuracoes_cortador.json"


def open_gui():
    root = tk.Tk()
    root.title("Cortador de Paineis")
    root.geometry("600x750")
    root.configure(padx=20, pady=20)

    vars_dict = {
        "input": tk.StringVar(),
        "output": tk.StringVar(),
        "gabarito": tk.StringVar(),
        "measures": tk.StringVar(value="95, 150, 100"),
        "overlap": tk.StringVar(value="0.5"),
        "pad": tk.StringVar(value="1.0"),
        "cut_type": tk.StringVar(value="vertical"),
        "text_color": tk.StringVar(value="Preto"),
    }
    invert_var = tk.BooleanVar(value=False)

    def load_config():
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                for key, val in data.items():
                    if key in vars_dict:
                        vars_dict[key].set(val)
                if "invert" in data:
                    invert_var.set(data["invert"])
            except Exception:
                pass

    def save_config():
        data = {key: var.get() for key, var in vars_dict.items()}
        data["invert"] = invert_var.get()
        try:
            CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def select_input():
        folder = filedialog.askdirectory(title="Pasta de entrada")
        if folder:
            vars_dict["input"].set(folder)

    def select_output():
        folder = filedialog.askdirectory(title="Pasta de saida")
        if folder:
            vars_dict["output"].set(folder)

    def select_gabarito():
        file = filedialog.askopenfilename(title="Gabarito", filetypes=[("Imagens", "*.png *.tif *.tiff *.jpg")])
        if file:
            vars_dict["gabarito"].set(file)

    def safe_log(msg):
        root.after(0, lambda: _insert_log(msg))

    def _insert_log(msg):
        text_log.config(state=tk.NORMAL)
        text_log.insert(tk.END, msg + "\n")
        text_log.see(tk.END)
        text_log.config(state=tk.DISABLED)

    def update_progress(current, total):
        percent = (current / total) * 100
        root.after(0, lambda: progress_bar.config(value=percent))

    def run_process():
        btn_run.config(state=tk.DISABLED, text="PROCESSANDO...")
        progress_bar.config(value=0)
        _insert_log("\nIniciando lote...")

        try:
            str_measures = vars_dict["measures"].get().split(",")
            custom_measures = [float(m.strip()) for m in str_measures if m.strip()]
            add_cut = float(vars_dict["overlap"].get())
            pad = float(vars_dict["pad"].get())
        except ValueError:
            safe_log("Erro: verifique as medidas (numeros e virgulas apenas).")
            root.after(0, lambda: btn_run.config(state=tk.NORMAL, text="PROCESSAR IMAGENS"))
            return

        sucesso = cut_boards(
            image_path=vars_dict["input"].get(),
            output_dir=vars_dict["output"].get(),
            medidas_cm=custom_measures,
            gabarito_path=vars_dict["gabarito"].get(),
            add_cut_cm=add_cut,
            pad_cm=pad,
            type_of_court=vars_dict["cut_type"].get(),
            invert_cut=invert_var.get(),
            text_color=COLOR_MAP.get(vars_dict["text_color"].get(), "black"),
            log_callback=safe_log,
            progress_callback=update_progress,
        )

        if sucesso:
            save_config()
            root.after(0, lambda: messagebox.showinfo("Pronto!", "Lote processado com sucesso!"))
        root.after(0, lambda: btn_run.config(state=tk.NORMAL, text="PROCESSAR IMAGENS"))

    def start_thread():
        if not vars_dict["input"].get() or not vars_dict["output"].get() or not vars_dict["gabarito"].get():
            messagebox.showwarning("Atencao", "Preencha Entrada, Saida e Gabarito.")
            return
        threading.Thread(target=run_process, daemon=True).start()

    load_config()

    tk.Label(root, text="Pasta de Entrada:", font=("Arial", 10, "bold")).pack(anchor="w")
    f1 = tk.Frame(root)
    f1.pack(fill="x", pady=(0, 5))
    tk.Entry(f1, textvariable=vars_dict["input"], width=50).pack(side="left", fill="x", expand=True, padx=(0, 10))
    tk.Button(f1, text="Procurar", command=select_input).pack(side="left")

    tk.Label(root, text="Pasta de Saida:", font=("Arial", 10, "bold")).pack(anchor="w")
    f2 = tk.Frame(root)
    f2.pack(fill="x", pady=(0, 5))
    tk.Entry(f2, textvariable=vars_dict["output"], width=50).pack(side="left", fill="x", expand=True, padx=(0, 10))
    tk.Button(f2, text="Procurar", command=select_output).pack(side="left")

    tk.Label(root, text="Arquivo do Gabarito:", font=("Arial", 10, "bold")).pack(anchor="w")
    f3 = tk.Frame(root)
    f3.pack(fill="x", pady=(0, 5))
    tk.Entry(f3, textvariable=vars_dict["gabarito"], width=50).pack(side="left", fill="x", expand=True, padx=(0, 10))
    tk.Button(f3, text="Procurar", command=select_gabarito).pack(side="left")

    tk.Label(root, text="-" * 80).pack(pady=5)
    tk.Label(root, text="Medidas (cm, separadas por virgula):", font=("Arial", 10, "bold")).pack(anchor="w")
    tk.Entry(root, textvariable=vars_dict["measures"], font=("Arial", 12)).pack(fill="x", pady=5)

    fc = tk.Frame(root)
    fc.pack(fill="x", pady=5)
    tk.Label(fc, text="Sangria (cm):").grid(row=0, column=0, sticky="w", pady=5)
    tk.Entry(fc, textvariable=vars_dict["overlap"], width=10).grid(row=0, column=1, sticky="w", padx=10)
    tk.Label(fc, text="Margem (cm):").grid(row=1, column=0, sticky="w", pady=5)
    tk.Entry(fc, textvariable=vars_dict["pad"], width=10).grid(row=1, column=1, sticky="w", padx=10)
    tk.Label(fc, text="Tipo de Corte:").grid(row=2, column=0, sticky="w", pady=5)
    ttk.Combobox(fc, textvariable=vars_dict["cut_type"], values=["vertical", "horizontal"], state="readonly", width=12).grid(row=2, column=1, sticky="w", padx=10)
    tk.Label(fc, text="Cor do Texto:").grid(row=3, column=0, sticky="w", pady=5)
    ttk.Combobox(fc, textvariable=vars_dict["text_color"], values=list(COLOR_MAP.keys()), state="readonly", width=12).grid(row=3, column=1, sticky="w", padx=10)
    tk.Checkbutton(fc, text="Inverter (180)", variable=invert_var).grid(row=4, column=0, columnspan=2, sticky="w", pady=5)

    progress_bar = ttk.Progressbar(root, orient="horizontal", length=100, mode="determinate")
    progress_bar.pack(fill="x", pady=(10, 5))

    btn_run = tk.Button(root, text="PROCESSAR IMAGENS", bg="green", fg="white", font=("Arial", 12, "bold"), command=start_thread, height=2)
    btn_run.pack(fill="x", pady=5)

    tk.Label(root, text="Log:").pack(anchor="w", pady=(5, 0))
    lf = tk.Frame(root)
    lf.pack(fill="both", expand=True)
    sb = tk.Scrollbar(lf)
    sb.pack(side="right", fill="y")
    text_log = tk.Text(lf, height=8, bg="black", fg="lime", font=("Consolas", 9), yscrollcommand=sb.set, state=tk.DISABLED)
    text_log.pack(side="left", fill="both", expand=True)
    sb.config(command=text_log.yview)

    def on_closing():
        save_config()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    open_gui()
