from PIL import Image, ImageOps, ImageDraw 
import os 
import math 
import gc 

Image.MAX_IMAGE_PIXELS = None 

db_malha = [ 
    "malha", "malia", "malhaaa", "malh", "malah", "maliaa", "maliah", 
    "mahla", "mahlaa", "malla", "mallha", "malahh", "malhja", "malahja", 
    "malhaaaah", "maia", "maiaa", "mya", "mala", "mahla", "maliaah", 
    "mhalha", "mahla", "marlha", "marla" 
] 

db_tactel = [ 
    "tactel", "taktel", "tacitel", "tacteel", "tacel", "takcel", "tacrel", 
    "takteo", "taketell", "taketel", "taktell", "tachtel", "takle", "taclel", 
    "takel", "taketeu", "tacteu", "takteu" 
] 

db_oxford = [ 
    "oxford", "oxfor", "oxfordd", "oxforde", "oxforf", "oxfod", "oxfrod", 
    "oxofrd", "oxfrod", "oxfird", "ofxord", "oxfrd", "oxfoed", "oxfored", 
    "oxofor", "oxfard", "oksford", "oxfo", "oxofor", "oxfordee", "oxforrd", 
    "oxfodr", "oxxford", "oxfird", "oxferd", "oxfird", "oxfourd", "oxfordr" 
] 

def add_contour( 
    image, 
    origin = (None, None) 
): 
    image = image.crop((1, 1, origin[0], origin[1])) 
    image = ImageOps.expand(image, border=1, fill='black') 
    return image 


def add_template_and_number( 
    image, 
    number, 
    pad_cm, 
    name_file, 
    template, 
    plate = 'start', 
    origin = (0, 0), 
    dpi = (None, None),
    text_color = 'black' ## NOVA COR AQUI ## -> Parâmetro adicionado com padrão 'black'
):  
    size_template = template.size 
    # Usando fallback para 72 dpi caso o arquivo venha sem a tag
    new_width = math.ceil((size_template[0] * dpi[0]) / template.info.get('dpi', (72, 72))[0]) 
    new_height = math.ceil((size_template[1] * dpi[1]) / template.info.get('dpi', (72, 72))[1]) 
    template_new = template.resize((new_width, new_height)) 
    size_template = template_new.size 
         
    if plate == 'start': 
        image.paste(template_new, origin) 
        draw = ImageDraw.Draw(image) 
        if number >= 10: 
            draw.text((image.size[0] - math.ceil(((2*pad_cm)*dpi[0]) / 2.54), 0), "{}".format(number), fill=text_color, font_size=math.ceil(30*(dpi[0]/72))) 
        else: 
            draw.text((image.size[0] - math.ceil(((2*pad_cm)*dpi[0]) / 2.54), 0), "0{}".format(number), fill=text_color, font_size=math.ceil(30*(dpi[0]/72))) 
        draw.text((math.ceil(((pad_cm)*dpi[0]) / 2.54), image.size[1] - math.ceil(((pad_cm)*dpi[0]) / 2.54)), "{}".format(name_file), fill=text_color, font_size=math.ceil(30*(dpi[0]/72))) 

    elif plate == 'middle': 
        image.paste(template_new, (0, 0)) 
        image.paste(template_new, origin) 
        draw = ImageDraw.Draw(image) 
        if number >= 10: 
            draw.text((math.ceil(((pad_cm)*dpi[0]) / 2.54), 0), "{}".format(number), fill=text_color, font_size=math.ceil(30*(dpi[0]/72))) 
            draw.text((image.size[0] - math.ceil(((2*pad_cm)*dpi[0]) / 2.54), 0), "{}".format(number + 1), fill=text_color, font_size=math.ceil(30*(dpi[0]/72))) 
        else: 
            draw.text((math.ceil(((pad_cm)*dpi[0]) / 2.54), 0), "0{}".format(number), fill=text_color, font_size=math.ceil(30*(dpi[0]/72))) 
            draw.text((image.size[0] - math.ceil(((2*pad_cm)*dpi[0]) / 2.54), 0), "0{}".format(number + 1), fill=text_color, font_size=math.ceil(30*(dpi[0]/72))) 
        draw.text((math.ceil(((pad_cm)*dpi[0]) / 2.54), image.size[1] - math.ceil(((pad_cm)*dpi[0]) / 2.54)), "{}".format(name_file), fill=text_color, font_size=math.ceil(30*(dpi[0]/72))) 

    else: 
        image.paste(template_new, (0, 0)) 
        draw = ImageDraw.Draw(image) 
        if number >= 10: 
            draw.text((math.ceil(((pad_cm)*dpi[0]) / 2.54), 0), "{}".format(number), fill=text_color, font_size=math.ceil(30*(dpi[0]/72))) 
        else: 
            draw.text((math.ceil(((pad_cm)*dpi[0]) / 2.54), 0), "0{}".format(number), fill=text_color, font_size=math.ceil(30*(dpi[0]/72))) 
        draw.text((math.ceil(((pad_cm)*dpi[0]) / 2.54), image.size[1] - math.ceil(((pad_cm)*dpi[0]) / 2.54)), "{}".format(name_file), fill=text_color, font_size=math.ceil(30*(dpi[0]/72))) 


def cut_boards_with_template( 
    image_path,  
    measure_cm=150,  
    add_cut_cm=0.5,  
    pad_cm=1.0,  
    gabarito_path='gabarito.png',  
    output_dir='placas_com_gabarito', 
    type_of_court = 'horizontal', 
    invert_cut = "não",
    text_color = 'black' ## NOVA COR AQUI ## -> Parâmetro adicionado na função principal
): 
    images_list = [] 
    name_file_list = [] 
    for image in os.listdir(image_path): 
        if image.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.tiff')): 
            images_list.append(os.path.join(image_path, image)) 
            name_file_list.append(image) 

    with Image.open(gabarito_path) as template: 

        for image, name_file in zip(images_list, name_file_list): 
            with Image.open(image) as panel: 
                
                # --- CORREÇÃO: CAPTURA O PERFIL ICC ORIGINAL ---
                icc_profile = panel.info.get("icc_profile")

                if invert_cut != 'não': 
                    panel = panel.transpose(Image.Transpose.ROTATE_180) 
                     
                if type_of_court == 'horizontal': 
                    panel = panel.transpose(Image.Transpose.ROTATE_90) 

                size_of_panel_px = panel.size 
                # Simplificação do DPI para evitar erros de NoneType no cálculo
                dpi_original = panel.info.get('dpi', (72, 72)) 
                
                size_of_panel_cm = ((size_of_panel_px[0]/dpi_original[0])*2.54,  
                                    (size_of_panel_px[1]/dpi_original[1])*2.54) 
                 
                print(7*'-=') 
                print('panel to be cut: ', name_file) 
                print(7*'-=') 
                print('size: {}cm X {}cm / dpi {}'.format(size_of_panel_cm[0], size_of_panel_cm[1], dpi_original)) 

                type_of_court = type_of_court.lower() 
                 
                if type_of_court in ('vertical', 'horizontal'): 
                    number_of_plates = size_of_panel_cm[0] / measure_cm 
                    number_of_plates = math.ceil(number_of_plates) 
                    print("number of plates: {}".format(number_of_plates)) 
                    print(7*'-=') 
                    size_of_cut = 0 
                    x_origin = 0 
                 
                    for plate in range(1, int( number_of_plates + 1 )): 
                        print('📐 cutting panel: plate {}'.format(plate)) 

                        if plate == 1: 
                            size_of_cut = ((measure_cm + add_cut_cm)*dpi_original[0]) / 2.54 
                            plate_1 = panel.crop((x_origin, 0, size_of_cut, size_of_panel_px[1])) 
                            plate_1 = add_contour(plate_1, (plate_1.size[0] - 1, size_of_panel_px[1] - 1)) 
                            plate_1 = ImageOps.expand(plate_1, border=math.ceil(((pad_cm)*dpi_original[0]) / 2.54), fill='white') 
                            size_of_plate_1_px = plate_1.size 
                            # ## NOVA COR AQUI ## Passando o text_color adiante
                            add_template_and_number(name_file=name_file, pad_cm=pad_cm, number=plate, dpi=dpi_original, image=plate_1, template=template, plate='start', origin=(size_of_plate_1_px[0] - math.ceil(((pad_cm)*dpi_original[0]) / 2.54), 0), text_color=text_color) 

                            if type_of_court == 'horizontal': 
                                plate_1 = plate_1.transpose(Image.Transpose.ROTATE_270) 
                             
                            if invert_cut != 'não': 
                                plate_1 = plate_1.transpose(Image.Transpose.ROTATE_180) 

                            name_file_1 = name_file.replace(".", " - P0{}.".format(plate)) 
                            
                            # --- CORREÇÃO: SALVA INJETANDO O PERFIL ICC ---
                            plate_1.save(os.path.join(output_dir, name_file_1), dpi=dpi_original, icc_profile=icc_profile) 
                            
                            del plate_1 
                            gc.collect() 
                            print('✅ cutted panel: plate {}'.format(name_file_1)) 

                        elif plate != int(number_of_plates): 
                            x_origin = size_of_cut - ((2*add_cut_cm)*dpi_original[0]) / 2.54 
                            size_of_cut = size_of_cut + ((measure_cm * dpi_original[0]) / 2.54) 
                            plate_n = panel.crop((x_origin, 0, size_of_cut, size_of_panel_px[1])) 
                            plate_n = add_contour(plate_n, (plate_n.size[0] - 1, size_of_panel_px[1] - 1)) 
                            plate_n = ImageOps.expand(plate_n, border=math.ceil(((pad_cm)*dpi_original[0]) / 2.54), fill='white') 
                            size_of_plate_n_px = plate_n.size 
                            # ## NOVA COR AQUI ## Passando o text_color adiante
                            add_template_and_number(name_file=name_file, pad_cm=pad_cm, number=((2*plate) - 2), dpi=dpi_original, image=plate_n, template=template, plate='middle', origin=(size_of_plate_n_px[0] - math.ceil(((pad_cm)*dpi_original[0]) / 2.54), 0), text_color=text_color) 

                            if type_of_court == 'horizontal': 
                                plate_n = plate_n.transpose(Image.Transpose.ROTATE_270) 
                                 
                            if invert_cut != 'não': 
                                plate_n = plate_n.transpose(Image.Transpose.ROTATE_180) 

                            name_file_n = name_file.replace(".", " - P0{}.".format(plate)) 
                            
                            # --- CORREÇÃO: SALVA INJETANDO O PERFIL ICC ---
                            plate_n.save(os.path.join(output_dir, name_file_n), dpi=dpi_original, icc_profile=icc_profile) 
                            
                            del plate_n 
                            gc.collect() 
                            print('✅ cutted panel: plate {}'.format(name_file_n)) 

                        else: 
                            x_origin = size_of_cut - ((2*add_cut_cm)*dpi_original[0]) / 2.54 
                            size_of_cut = size_of_panel_px[0] 
                            plate_end = panel.crop((x_origin, 0, size_of_cut, size_of_panel_px[1])) 
                            plate_end = add_contour(plate_end, (plate_end.size[0] - 1, size_of_panel_px[1] - 1)) 
                            plate_end = ImageOps.expand(plate_end, border=math.ceil(((pad_cm)*dpi_original[0]) / 2.54), fill='white') 
                            size_of_plate_end_px = plate_end.size 
                            # ## NOVA COR AQUI ## Passando o text_color adiante
                            add_template_and_number(name_file=name_file, pad_cm=pad_cm, number=((2*plate) - 2), dpi=dpi_original, image=plate_end, template=template, plate='end', origin=(size_of_plate_end_px[0] - math.ceil(((pad_cm)*dpi_original[0]) / 2.54), 0), text_color=text_color) 

                            if type_of_court == 'horizontal': 
                                plate_end = plate_end.transpose(Image.Transpose.ROTATE_270) 
                                 
                            if invert_cut != 'não': 
                                plate_end = plate_end.transpose(Image.Transpose.ROTATE_180) 

                            name_file_end = name_file.replace(".", " - P0{}.".format(plate)) 
                            
                            # --- CORREÇÃO: SALVA INJETANDO O PERFIL ICC ---
                            plate_end.save(os.path.join(output_dir, name_file_end), dpi=dpi_original, icc_profile=icc_profile) 
                            
                            del plate_end 
                            gc.collect()      
                            print('✅ cutted panel: plate {}'.format(name_file_end)) 
                else: 
                    print("⚠️  "*30) 
                    print(f"Você escreveu assim {type_of_court}, sempre escreva tudo minúsculo e da forma correta\nSempre uma das duas formas: 'vertical' ou 'horizontal'") 
                    break 

# --- Exemplo de Uso ---
cut_boards_with_template(
    r'Z:\26 06 2026\PAINEL_CUT', 
    output_dir=r'Z:\26 06 2026\PAINEL_CUT', 
    type_of_court='horizontal', 
    gabarito_path='gabarito.tif', 
    measure_cm=150,
    invert_cut="sim",
    text_color='black'  
)