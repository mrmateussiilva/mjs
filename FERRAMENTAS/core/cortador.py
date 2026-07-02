import os
import math
import gc
from pathlib import Path

from PIL import Image, ImageOps, ImageDraw

from core.config import EXTENSOES_IMAGEM
from core.utils import get_font, notify


Image.MAX_IMAGE_PIXELS = None


def add_contour(image, origin=(None, None)):
    image = image.crop((1, 1, origin[0], origin[1]))
    image = ImageOps.expand(image, border=1, fill="black")
    return image


def add_template_and_number(
    image, number, pad_cm, name_file, template,
    plate="start", origin=(0, 0), dpi=(72, 72), text_color="black", font=None,
):
    tmpl_w = math.ceil(template.size[0] * dpi[0] / template.info.get("dpi", (72, 72))[0])
    tmpl_h = math.ceil(template.size[1] * dpi[1] / template.info.get("dpi", (72, 72))[1])
    template_new = template.resize((tmpl_w, tmpl_h))

    if font is None:
        font = get_font(math.ceil(30 * (dpi[0] / 72)))

    pad_px = math.ceil((pad_cm * dpi[0]) / 2.54)
    double_pad_px = math.ceil((2 * pad_cm * dpi[0]) / 2.54)
    draw = ImageDraw.Draw(image)
    num_str = f"{number:02d}"

    if plate == "start":
        image.paste(template_new, origin)
        draw.text((image.size[0] - double_pad_px, 0), num_str, fill=text_color, font=font)
    elif plate == "middle":
        image.paste(template_new, (0, 0))
        image.paste(template_new, origin)
        draw.text((pad_px, 0), num_str, fill=text_color, font=font)
        draw.text((image.size[0] - double_pad_px, 0), f"{number + 1:02d}", fill=text_color, font=font)
    else:
        image.paste(template_new, (0, 0))
        draw.text((pad_px, 0), num_str, fill=text_color, font=font)

    draw.text((pad_px, image.size[1] - pad_px), name_file, fill=text_color, font=font)


def cut_boards(
    image_path,
    output_dir,
    medidas_cm,
    gabarito_path="gabarito.png",
    add_cut_cm=0.5,
    pad_cm=1.0,
    type_of_court="vertical",
    invert_cut=False,
    text_color="black",
    log_callback=None,
    progress_callback=None,
):
    def log(msg):
        if log_callback:
            log_callback(msg)

    def prog(cur, total):
        if progress_callback:
            progress_callback(cur, total)

    images = sorted([
        f for f in Path(image_path).iterdir()
        if f.suffix.lower() in EXTENSOES_IMAGEM
    ])

    if not images:
        log("Nenhuma imagem encontrada na pasta de entrada.")
        return False

    os.makedirs(output_dir, exist_ok=True)

    try:
        with Image.open(gabarito_path) as template:
            for idx, img_file in enumerate(images):
                try:
                    with Image.open(img_file) as panel:
                        icc = panel.info.get("icc_profile")
                        dpi = panel.info.get("dpi", (72, 72))

                        if invert_cut:
                            panel = panel.transpose(Image.Transpose.ROTATE_180)
                        if type_of_court.lower() == "horizontal":
                            panel = panel.transpose(Image.Transpose.ROTATE_90)

                        w, h = panel.size
                        w_cm = w * 2.54 / dpi[0]
                        h_cm = h * 2.54 / dpi[1]
                        log(f"{img_file.name}  ({w_cm:.1f}x{h_cm:.1f} cm, DPI {dpi[0]})")

                        font = get_font(math.ceil(30 * (dpi[0] / 72)))
                        n_placas = len(medidas_cm)
                        cut_end = 0
                        x_orig = 0

                        for i, medida in enumerate(medidas_cm, 1):
                            plate_type = "start" if i == 1 else ("end" if i == n_placas else "middle")

                            if i == 1:
                                cut_end = ((medida + add_cut_cm) * dpi[0]) / 2.54
                                x0, x1 = 0, cut_end
                            else:
                                x0 = cut_end - ((2 * add_cut_cm) * dpi[0]) / 2.54
                                cut_end = cut_end + (medida * dpi[0]) / 2.54
                                if i == n_placas:
                                    cut_end = min(cut_end, w)
                                x1 = cut_end

                            plate = panel.crop((x0, 0, x1, h))
                            plate = add_contour(plate, (plate.size[0] - 1, h - 1))
                            pad_px = math.ceil((pad_cm * dpi[0]) / 2.54)
                            plate = ImageOps.expand(plate, border=pad_px, fill="white")

                            num = i if plate_type == "start" else (2 * i - 2)
                            add_template_and_number(
                                image=plate, number=num, pad_cm=pad_cm,
                                name_file=img_file.stem, template=template,
                                plate=plate_type,
                                origin=(plate.size[0] - pad_px, 0),
                                dpi=dpi, text_color=text_color, font=font,
                            )

                            if type_of_court.lower() == "horizontal":
                                plate = plate.transpose(Image.Transpose.ROTATE_270)
                            if invert_cut:
                                plate = plate.transpose(Image.Transpose.ROTATE_180)

                            out_name = f"{img_file.stem} - P{i:02d}{img_file.suffix}"
                            plate.save(os.path.join(output_dir, out_name), dpi=dpi, icc_profile=icc)
                            del plate
                            gc.collect()
                            log(f"  Placa {i}/{n_placas} salva.")

                except Exception as e:
                    log(f"ERRO em {img_file.name}: {e}")

                prog(idx + 1, len(images))

        log("Processo finalizado!")
        return True

    except Exception as e:
        log(f"Erro crítico: {e}")
        return False
