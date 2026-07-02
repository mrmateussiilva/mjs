from PIL import Image

from core.cortador import cut_boards

Image.MAX_IMAGE_PIXELS = None


if __name__ == "__main__":
    cut_boards(
        image_path=r"Z:\26 06 2026\PAINEL_CUT",
        output_dir=r"Z:\26 06 2026\PAINEL_CUT",
        medidas_cm=[150],
        gabarito_path="gabarito.tif",
        add_cut_cm=0.5,
        pad_cm=1.0,
        type_of_court="horizontal",
        invert_cut=True,
        text_color="black",
    )
