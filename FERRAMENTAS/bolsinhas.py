#!/usr/bin/env python3
import sys
import time
from pathlib import Path

from PIL import Image

from core.bolsinhas import process_all, clean_processed, load_registro, EXTENSOES_TIFF
from core.utils import log_time, notify

Image.MAX_IMAGE_PIXELS = None

INTERVALO_SEGUNDOS = 10
REGISTRO_FILENAME = "registro_bolsinhas.txt"


def monitorar(pasta: Path):
    print(f"Monitorando: {pasta}")
    while True:
        clean_processed(pasta)
        ok, erros = process_all(pasta, log_callback=lambda m: print(f"  {m}"))
        time.sleep(INTERVALO_SEGUNDOS)


def main(p: Path):
    pasta = Path(p)
    if not pasta.exists():
        print(f"Pasta nao encontrada: {pasta}")
        sys.exit(1)
    try:
        monitorar(pasta)
    except KeyboardInterrupt:
        print("\nEncerrado.")


if __name__ == "__main__":
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"Z:\26 06 2026\BOLSINHAS\PARA FAZER")
    main(p)
