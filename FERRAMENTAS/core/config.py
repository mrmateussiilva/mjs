import os
import json
from pathlib import Path

DEFAULT_CONFIG = {
    "paths": {
        "raiz": "Z:\\",
        "monitor_bolsinhas": r"Z:\BOLSINHAS\PARA FAZER",
        "monitor_conf": r"Z:\CONF",
        "painel_cut": r"Z:\PAINEL_CUT",
        "notepad_host": "0.0.0.0",
        "notepad_port": 8765,
    },
    "conf": {
        "dpi_fallback": 300,
        "target_width_cm": 155.0,
        "pad_cm": 1.0,
        "border_px": 1,
        "text_left_cm": 0.3,
        "stable_wait": 1.5,
        "poll_interval": 3.0,
    },
    "bolsinhas": {
        "scale": 0.10,
        "quality": 85,
        "intervalo_segundos": 10,
        "extensoes": [".tif", ".tiff"],
    },
    "cortador": {
        "add_cut_cm": 0.5,
        "pad_cm": 1.0,
        "default_medidas": [95, 150, 100],
        "tipo": "vertical",
        "gabarito": "gabarito.png",
        "text_color": "black",
        "invert_cut": False,
    },
}

COLOR_MAP = {
    "Preto": "black", "Branco": "white",
    "Azul": "blue", "Vermelho": "red",
    "Rosa": "#FF1493", "Roxo": "purple", "Verde": "green",
}

SUBPASTAS_DIA = [
    "BOLSINHAS", r"BOLSINHAS\PARA FAZER",
    "PAINEL_CUT", "CONF", "APS", "TEX",
]

EXTENSOES_IMAGEM = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
EXTENSOES_TIFF = {".tif", ".tiff"}

VARIANTS_MALHA = [
    "malha", "malia", "malhaaa", "malh", "malah", "maliaa", "maliah",
    "mahla", "mahlaa", "malla", "mallha", "malahh", "malhja", "malahja",
    "malhaaaah", "maia", "maiaa", "mya", "mala", "mahla", "maliaah",
    "mhalha", "mahla", "marlha", "marla",
]
VARIANTS_TACTEL = [
    "tactel", "taktel", "tacitel", "tacteel", "tacel", "takcel", "tacrel",
    "takteo", "taketell", "taketel", "taktell", "tachtel", "takle", "taclel",
    "takel", "taketeu", "tacteu", "takteu",
]
VARIANTS_OXFORD = [
    "oxford", "oxfor", "oxfordd", "oxforde", "oxforf", "oxfod", "oxfrod",
    "oxofrd", "oxfrod", "oxfird", "ofxord", "oxfrd", "oxfoed", "oxfored",
    "oxofor", "oxfard", "oksford", "oxfo", "oxofor", "oxfordee", "oxforrd",
    "oxfodr", "oxxford", "oxfird", "oxferd", "oxfird", "oxfourd", "oxfordr",
]

FONT_CANDIDATES = [
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
]

CONFIG_FILE = Path(__file__).parent / "config.json"


def load() -> dict:
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            merged = DEFAULT_CONFIG.copy()
            _deep_merge(merged, data)
            return merged
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save(cfg: dict):
    try:
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _deep_merge(base, override):
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
