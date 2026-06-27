from PIL import Image, ImageOps, ImageDraw, ImageFont
import os
import math
import gc
import json
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

Image.MAX_IMAGE_PIXELS = None

# Arquivo para salvar as configurações
CONFIG_FILE = "configuracoes_cortador.json"

# Bancos de dados de nomes
db_malha = ["malha", "malia", "malhaaa", "malh", "malah", "maliaa", "maliah", "mahla", "mahlaa", "malla", "mallha", "malahh", "malhja", "malahja", "malhaaaah", "maia", "maiaa", "mya", "mala", "mahla", "maliaah", "mhalha", "mahla", "marlha", "marla"]
db_tactel = ["tactel", "taktel", "tacitel", "tacteel", "tacel", "takcel", "tacrel", "takteo", "taketell", "taketel", "taktell", "tachtel", "takle", "taclel", "takel", "taketeu", "tacteu", "takteu"]
db_oxford = ["oxford", "oxfor", "oxfordd", "oxforde", "oxforf", "oxfod", "oxfrod", "oxofrd", "oxfrod", "oxfird", "ofxord", "oxfrd", "oxfoed", "oxfored", "oxofor", "oxfard", "oksford", "oxfo", "oxofor", "oxfordee", "oxforrd", "oxfodr", "oxxford", "oxfird", "oxferd", "oxfird", "oxfourd", "oxfordr"]

def get_font(size):
    """Tenta carregar Arial, se não conseguir, usa a fonte padrão."""
    try:
        return ImageFont.truetype("arial.ttf", size)
    except IOError:
        try:
            return ImageFont.truetype("Arial.ttf", size) # Algumas variações de OS
        except IOError:
            return ImageFont.load_default()

def add_contour(image, origin=(None, None)):
    image = image.crop((1, 1, origin[0], origin[1]))
    image = ImageOps.expand(image, border=1, fill='black')
    return image

def add_template_and_number(image, number, pad_cm, name_file, template, plate='start', origin=(0, 0), dpi=(72, 72), text_color='black'): 
    size_template = template.size
    new_width = math.ceil((size_template[0] * dpi[0]) / template.info.get('dpi', (72, 72))[0])
    new_height = math.ceil((size_template[1] * dpi[1]) / template.info.get('dpi', (72, 72))[1])
    template_new = template.resize((new_width, new_height))
    
    font_size = math.ceil(30*(dpi[0]/72))
    font = get_font(font_size)
    
    pad_px = math.ceil(((pad_cm)*dpi[0]) / 2.54)
    double_pad_px = math.ceil(((2*pad_cm)*dpi[0]) / 2.54)

    draw = ImageDraw.Draw(image)
    num_str = f"{number:02d}"

    if plate == 'start':
        image.paste(template_new, origin)
        draw.text((image.size[0] - double_pad_px, 0), num_str, fill=text_color, font=font)
        draw.text((pad_px, image.size[1] - pad_px), f"{name_file}", fill=text_color, font=font)

    elif plate == 'middle':
        image.paste(template_new, (0, 0))
        image.paste(template_new, origin)
        num_next_str = f"{number + 1:02d}"
        draw.text((pad_px, 0), num_str, fill=text_color, font=font)
        draw.text((image.size[0] - double_pad_px, 0), num_next_str, fill=text_color, font=font)
        draw.text((pad_px, image.size[1] - pad_px), f"{name_file}", fill=text_color, font=font)

    else:
        image.paste(template_new, (0, 0))
        draw.text((pad_px, 0), num_str, fill=text_color, font=font)
        draw.text((pad_px, image.size[1] - pad_px), f"{name_file}", fill=text_color, font=font)


def cut_boards_with_custom_template(image_path, measures_cm_list, add_cut_cm=0.5, pad_cm=1.0, 
                                    gabarito_path='gabarito.png', output_dir='placas_com_gabarito', 
                                    type_of_court='vertical', invert_cut="não", text_color="black",
                                    log_callback=None, progress_callback=None):
    
    def log(msg):
        if log_callback: log_callback(msg)
        else: print(msg)

    images_list = []
    name_file_list = []
    
    for image in os.listdir(image_path):
        if image.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.tiff')):
            images_list.append(os.path.join(image_path, image))
            name_file_list.append(image)

    total_images = len(images_list)
    if total_images == 0:
        log("❌ Nenhuma imagem encontrada na pasta de entrada.")
        return False

    try:
        with Image.open(gabarito_path) as template:
            for index, (image_file, name_file) in enumerate(zip(images_list, name_file_list)):
                try: # Try/except individualizado por imagem
                    with Image.open(image_file) as panel:
                        icc_profile = panel.info.get("icc_profile")

                        if invert_cut != 'não':
                            panel = panel.transpose(Image.Transpose.ROTATE_180)
                            
                        type_of_court_lower = type_of_court.lower()
                        if type_of_court_lower == 'horizontal':
                            panel = panel.transpose(Image.Transpose.ROTATE_90)

                        size_of_panel_px = panel.size
                        dpi_original = panel.info.get('dpi', (72, 72))
                        
                        size_of_panel_cm = ((size_of_panel_px[0]/dpi_original[0])*2.54, 
                                            (size_of_panel_px[1]/dpi_original[1])*2.54)
                        
                        log(40*'-')
                        log(f'✂️ Cortando: {name_file}')
                        log(f'Tamanho: {size_of_panel_cm[0]:.2f}cm X {size_of_panel_cm[1]:.2f}cm / DPI {dpi_original}')

                        if type_of_court_lower in ('vertical', 'horizontal'):
                            number_of_plates = len(measures_cm_list)
                            log(f"Número de placas configuradas: {number_of_plates}")
                            
                            size_of_cut = 0
                            x_origin = 0

                            for plate, measure_cm in enumerate(measures_cm_list, start=1):
                                if plate == 1:
                                    # PLACA 1 (START)
                                    size_of_cut = ((measure_cm + add_cut_cm)*dpi_original[0]) / 2.54
                                    plate_img = panel.crop((x_origin, 0, size_of_cut, size_of_panel_px[1]))
                                    plate_img = add_contour(plate_img, (plate_img.size[0] - 1, size_of_panel_px[1] - 1))
                                    plate_img = ImageOps.expand(plate_img, border=math.ceil(((pad_cm)*dpi_original[0]) / 2.54), fill='white')
                                    add_template_and_number(name_file=name_file, pad_cm=pad_cm, number=plate, dpi=dpi_original, image=plate_img, template=template, plate='start', origin=(plate_img.size[0] - math.ceil(((pad_cm)*dpi_original[0]) / 2.54), 0), text_color=text_color)

                                elif plate != number_of_plates:
                                    # PLACAS DO MEIO (MIDDLE)
                                    x_origin = size_of_cut - ((2*add_cut_cm)*dpi_original[0]) / 2.54
                                    size_of_cut = size_of_cut + ((measure_cm * dpi_original[0]) / 2.54)
                                    plate_img = panel.crop((x_origin, 0, size_of_cut, size_of_panel_px[1]))
                                    plate_img = add_contour(plate_img, (plate_img.size[0] - 1, size_of_panel_px[1] - 1))
                                    plate_img = ImageOps.expand(plate_img, border=math.ceil(((pad_cm)*dpi_original[0]) / 2.54), fill='white')
                                    add_template_and_number(name_file=name_file, pad_cm=pad_cm, number=((2*plate) - 2), dpi=dpi_original, image=plate_img, template=template, plate='middle', origin=(plate_img.size[0] - math.ceil(((pad_cm)*dpi_original[0]) / 2.54), 0), text_color=text_color)

                                else:
                                    # ULTIMA PLACA (END)
                                    x_origin = size_of_cut - ((2*add_cut_cm)*dpi_original[0]) / 2.54
                                    size_of_cut = size_of_cut + ((measure_cm * dpi_original[0]) / 2.54)
                                    if size_of_cut > size_of_panel_px[0]:
                                        size_of_cut = size_of_panel_px[0]
                                        
                                    plate_img = panel.crop((x_origin, 0, size_of_cut, size_of_panel_px[1]))
                                    plate_img = add_contour(plate_img, (plate_img.size[0] - 1, size_of_panel_px[1] - 1))
                                    plate_img = ImageOps.expand(plate_img, border=math.ceil(((pad_cm)*dpi_original[0]) / 2.54), fill='white')
                                    add_template_and_number(name_file=name_file, pad_cm=pad_cm, number=((2*plate) - 2), dpi=dpi_original, image=plate_img, template=template, plate='end', origin=(plate_img.size[0] - math.ceil(((pad_cm)*dpi_original[0]) / 2.54), 0), text_color=text_color)

                                # Rotações de salvamento
                                if type_of_court_lower == 'horizontal':
                                    plate_img = plate_img.transpose(Image.Transpose.ROTATE_270)
                                if invert_cut != 'não':
                                    plate_img = plate_img.transpose(Image.Transpose.ROTATE_180)

                                name_file_save = name_file.replace(".", f" - P{plate:02d}.")
                                plate_img.save(os.path.join(output_dir, name_file_save), dpi=dpi_original, icc_profile=icc_profile)
                                
                                del plate_img
                                gc.collect()
                                log(f'  ✅ Placa {plate} salva.')
                        else:
                            log("❌ Tipo de corte inválido.")
                            break
                except Exception as img_e:
                    log(f"⚠️ Erro ao processar a imagem '{name_file}': {str(img_e)}. Pulando...")
                
                # Atualizar progresso
                if progress_callback:
                    progress_callback(index + 1, total_images)

        log(40*'-')
        log("🎉 PROCESSO FINALIZADO COM SUCESSO!")
        return True
    except Exception as e:
        log(f"❌ Erro crítico: {str(e)}")
        return False

# =====================================================================
# INTERFACE GRÁFICA (GUI)
# =====================================================================
def open_gui():
    root = tk.Tk()
    root.title("Cortador de Painéis - Empresa (Versão Avançada)")
    root.geometry("600x750")
    root.configure(padx=20, pady=20)

    # Variaveis
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

    color_dict = {
        "Preto": "black",
        "Azul": "blue",
        "Rosa": "#FF1493", 
        "Roxo": "purple",
        "Vermelho": "red",
        "Verde": "green"
    }

    # -- Funções de Memória (Config JSON) --
    def load_config():
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    for key, val in data.items():
                        if key in vars_dict:
                            vars_dict[key].set(val)
                    if "invert" in data:
                        invert_var.set(data["invert"])
            except Exception:
                pass # Se der erro na leitura, ignora e usa o padrão

    def save_config():
        data = {key: var.get() for key, var in vars_dict.items()}
        data["invert"] = invert_var.get()
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(data, f)
        except Exception:
            pass

    # -- Funções auxiliares --
    def select_input():
        folder = filedialog.askdirectory(title="Selecione a pasta das imagens")
        if folder: vars_dict["input"].set(folder)

    def select_output():
        folder = filedialog.askdirectory(title="Selecione a pasta para salvar")
        if folder: vars_dict["output"].set(folder)

    def select_gabarito():
        file = filedialog.askopenfilename(title="Selecione o Gabarito (.tif, .png)", filetypes=[("Imagens", "*.png *.tif *.tiff *.jpg")])
        if file: vars_dict["gabarito"].set(file)

    def safe_log(msg):
        """Envia mensagem para o text_log com segurança usando a thread do Tkinter"""
        root.after(0, lambda: _insert_log(msg))

    def _insert_log(msg):
        text_log.config(state=tk.NORMAL)
        text_log.insert(tk.END, msg + "\n")
        text_log.see(tk.END)
        text_log.config(state=tk.DISABLED)

    def update_progress(current, total):
        """Atualiza a barra de progresso com segurança"""
        percent = (current / total) * 100
        root.after(0, lambda: progress_bar.config(value=percent))

    def run_process():
        btn_run.config(state=tk.DISABLED, text="PROCESSANDO...")
        progress_bar.config(value=0)
        _insert_log("\nIniciando lote...")

        invert_str = "sim" if invert_var.get() else "não"
        selected_color = color_dict.get(vars_dict["text_color"].get(), "black")

        # Conversão das medidas
        try:
            str_measures = vars_dict["measures"].get().split(',')
            custom_measures = [float(m.strip()) for m in str_measures if m.strip()]
            add_cut = float(vars_dict["overlap"].get())
            pad = float(vars_dict["pad"].get())
        except ValueError:
            safe_log("❌ Erro: Verifique se as medidas contém apenas números e vírgulas.")
            root.after(0, lambda: btn_run.config(state=tk.NORMAL, text="PROCESSAR IMAGENS"))
            return

        # Roda a função principal passando os callbacks
        sucesso = cut_boards_with_custom_template(
            image_path=vars_dict["input"].get(),
            output_dir=vars_dict["output"].get(),
            gabarito_path=vars_dict["gabarito"].get(),
            measures_cm_list=custom_measures,
            add_cut_cm=add_cut,
            pad_cm=pad,
            type_of_court=vars_dict["cut_type"].get(),
            invert_cut=invert_str,
            text_color=selected_color,
            log_callback=safe_log,
            progress_callback=update_progress
        )

        if sucesso:
            save_config() # Salva as configurações de sucesso
            root.after(0, lambda: messagebox.showinfo("Pronto!", "Lote processado com sucesso!"))
        
        # Restaura o botão
        root.after(0, lambda: btn_run.config(state=tk.NORMAL, text="PROCESSAR IMAGENS"))


    def start_thread():
        # Validações antes de jogar para a Thread
        if not vars_dict["input"].get() or not vars_dict["output"].get() or not vars_dict["gabarito"].get():
            messagebox.showwarning("Atenção", "Por favor, preencha todos os caminhos (Entrada, Saída e Gabarito).")
            return
        
        # Inicia a Thread para não travar a interface
        threading.Thread(target=run_process, daemon=True).start()


    # Carrega configs salvas antes de desenhar a interface
    load_config()

    # --- LAYOUT DOS ELEMENTOS ---
    tk.Label(root, text="Pasta das Imagens (Entrada):", font=('Arial', 10, 'bold')).pack(anchor="w")
    frame_in = tk.Frame(root)
    frame_in.pack(fill="x", pady=(0,5))
    tk.Entry(frame_in, textvariable=vars_dict["input"], width=50).pack(side="left", fill="x", expand=True, padx=(0, 10))
    tk.Button(frame_in, text="Procurar", command=select_input).pack(side="left")

    tk.Label(root, text="Pasta de Destino (Saída):", font=('Arial', 10, 'bold')).pack(anchor="w")
    frame_out = tk.Frame(root)
    frame_out.pack(fill="x", pady=(0,5))
    tk.Entry(frame_out, textvariable=vars_dict["output"], width=50).pack(side="left", fill="x", expand=True, padx=(0, 10))
    tk.Button(frame_out, text="Procurar", command=select_output).pack(side="left")

    tk.Label(root, text="Arquivo do Gabarito:", font=('Arial', 10, 'bold')).pack(anchor="w")
    frame_gab = tk.Frame(root)
    frame_gab.pack(fill="x", pady=(0,5))
    tk.Entry(frame_gab, textvariable=vars_dict["gabarito"], width=50).pack(side="left", fill="x", expand=True, padx=(0, 10))
    tk.Button(frame_gab, text="Procurar", command=select_gabarito).pack(side="left")

    tk.Label(root, text="-"*80).pack(pady=5)

    tk.Label(root, text="Medidas das Placas em CM (Separe por vírgula):", font=('Arial', 10, 'bold')).pack(anchor="w")
    tk.Label(root, text="Exemplo: 95, 150, 100", fg="gray").pack(anchor="w")
    tk.Entry(root, textvariable=vars_dict["measures"], font=('Arial', 12)).pack(fill="x", pady=5)

    frame_configs = tk.Frame(root)
    frame_configs.pack(fill="x", pady=5)

    tk.Label(frame_configs, text="Sobreposição/Sangria (cm):").grid(row=0, column=0, sticky="w", pady=5)
    tk.Entry(frame_configs, textvariable=vars_dict["overlap"], width=10).grid(row=0, column=1, sticky="w", padx=10)

    tk.Label(frame_configs, text="Pad/Margem (cm):").grid(row=1, column=0, sticky="w", pady=5)
    tk.Entry(frame_configs, textvariable=vars_dict["pad"], width=10).grid(row=1, column=1, sticky="w", padx=10)

    tk.Label(frame_configs, text="Tipo de Corte:").grid(row=2, column=0, sticky="w", pady=5)
    ttk.Combobox(frame_configs, textvariable=vars_dict["cut_type"], values=["vertical", "horizontal"], state="readonly", width=12).grid(row=2, column=1, sticky="w", padx=10)

    tk.Label(frame_configs, text="Cor do Texto:").grid(row=3, column=0, sticky="w", pady=5)
    ttk.Combobox(frame_configs, textvariable=vars_dict["text_color"], values=list(color_dict.keys()), state="readonly", width=12).grid(row=3, column=1, sticky="w", padx=10)

    tk.Checkbutton(frame_configs, text="Inverter Corte (180º)", variable=invert_var).grid(row=4, column=0, columnspan=2, sticky="w", pady=5)

    # Barra de Progresso
    progress_bar = ttk.Progressbar(root, orient="horizontal", length=100, mode="determinate")
    progress_bar.pack(fill="x", pady=(10, 5))

    # Botão de Execução
    btn_run = tk.Button(root, text="PROCESSAR IMAGENS", bg="green", fg="white", font=('Arial', 12, 'bold'), command=start_thread, height=2)
    btn_run.pack(fill="x", pady=5)

    # Caixa de Log Visual
    tk.Label(root, text="Log de Execução:", font=('Arial', 9)).pack(anchor="w", pady=(5,0))
    
    # Frame para a caixa de texto e scrollbar
    log_frame = tk.Frame(root)
    log_frame.pack(fill="both", expand=True)
    
    scrollbar = tk.Scrollbar(log_frame)
    scrollbar.pack(side="right", fill="y")
    
    text_log = tk.Text(log_frame, height=8, bg="black", fg="lime", font=("Consolas", 9), yscrollcommand=scrollbar.set, state=tk.DISABLED)
    text_log.pack(side="left", fill="both", expand=True)
    scrollbar.config(command=text_log.yview)

    # Salva as configs ao fechar a janela no "X"
    def on_closing():
        save_config()
        root.destroy()
        
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    open_gui()