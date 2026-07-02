from pathlib import Path

from PIL import Image

from core.config import EXTENSOES_TIFF
from core.utils import notify, log_time

Image.MAX_IMAGE_PIXELS = None

REGISTRO_FILENAME = "registro_bolsinhas.txt"
SCALE = 0.10
QUALITY = 85


def load_registro(pasta: Path) -> set:
    arq = pasta / REGISTRO_FILENAME
    if arq.exists():
        return set(l.strip() for l in arq.read_text("utf-8").splitlines() if l.strip())
    return set()


def save_registro(pasta: Path, nome: str):
    with open(pasta / REGISTRO_FILENAME, "a", encoding="utf-8") as f:
        f.write(nome + "\n")


def bolsinha_path(tiff: Path) -> Path:
    return tiff.parent / ("bolsinha_" + tiff.stem + ".jpeg")


def bolsinha_existe(tiff: Path) -> bool:
    return bolsinha_path(tiff).exists()


def get_pending(pasta: Path, registro: set = None) -> list[Path]:
    if registro is None:
        registro = load_registro(pasta)
    return sorted([
        f for f in pasta.iterdir()
        if f.is_file()
        and f.suffix.lower() in EXTENSOES_TIFF
        and not f.stem.lower().startswith("bolsinha_")
        and f.name not in registro
        and not bolsinha_existe(f)
    ])


def generate_thumbnail(tiff: Path, output: Path = None, scale: float = SCALE, quality: int = QUALITY) -> Path:
    if output is None:
        output = bolsinha_path(tiff)
    with Image.open(tiff) as img:
        w, h = img.size
        nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
        img.convert("RGB").resize((nw, nh), Image.LANCZOS).save(
            output, "JPEG", quality=quality, optimize=True
        )
    return output


def clean_processed(pasta: Path):
    registro = load_registro(pasta)
    for f in pasta.iterdir():
        if f.is_file() and f.suffix.lower() in EXTENSOES_TIFF and not f.stem.lower().startswith("bolsinha_"):
            if f.name in registro or bolsinha_existe(f):
                try:
                    f.unlink()
                    if f.name not in registro:
                        save_registro(pasta, f.name)
                except Exception:
                    pass


def process_all(pasta: Path, log_callback=None) -> tuple[int, int]:
    def log(msg):
        if log_callback:
            log_callback(msg)

    registro = load_registro(pasta)
    pendentes = get_pending(pasta, registro)

    if not pendentes:
        return 0, 0

    log(f"{len(pendentes)} TIFF(s) para processar")
    ok = erros = 0

    for tiff in pendentes:
        try:
            saida = bolsinha_path(tiff)
            mb_orig = tiff.stat().st_size / (1024 * 1024)

            generate_thumbnail(tiff, saida, SCALE, QUALITY)
            kb_novo = saida.stat().st_size / 1024

            save_registro(pasta, tiff.name)
            tiff.unlink()

            log(f"  {tiff.name}: {mb_orig:.1f}MB -> {kb_novo:.1f}KB")
            ok += 1
        except Exception as e:
            log(f"  ERRO {tiff.name}: {e}")
            erros += 1

    log(f"Lote concluído — OK: {ok}  Erro: {erros}")
    if ok > 0:
        notify("Bolsinhas", f"{ok} bolsinha(s) gerada(s).")
    return ok, erros
