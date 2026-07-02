#!/usr/bin/env python3
"""
MJS — Interface de linha de comando

Uso:
    mjs start           Inicia o agente autonomo (vigia pastas)
    mjs stop            Para o agente
    mjs status          Mostra status do agente

    mjs bolsinhas       Gera miniaturas pendentes agora
    mjs conf            Processa TIFFs pendentes agora
    mjs pastas          Cria estrutura de pastas do dia

    mjs cortar          Corta paineis em placas (menu interativo)
    mjs config          Mostra config atual
"""

import sys
import os
import json
import signal
import time
import datetime
import threading
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

PID_FILE = ROOT / ".mjs_agent.pid"


def _carregar_config():
    """Carrega config do mjs.yaml. Se nao existir, usa defaults."""
    try:
        import yaml
    except ImportError:
        print("AVISO: PyYAML nao instalado. Usando defaults.\n  pip install pyyaml")
        return _defaults()

    cfg_path = ROOT / "mjs.yaml"
    if cfg_path.exists():
        try:
            return yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Erro lendo mjs.yaml: {e}")
    else:
        print(f"Config nao encontrado: {cfg_path}")
        print(f"Copie mjs.yaml.example para mjs.yaml e edite\n")
        return _defaults()


def _defaults():
    return {
        "paths": {"raiz": "Z:\\"},
        "vigilantes": {},
        "diario": {"criar_pastas": False},
        "notepad": {"ativo": False},
    }


# ── Comandos ────────────────────────────────────────────────────────────────

def cmd_start():
    if _agente_rodando():
        print("Agente ja esta rodando (PID {})".format(_ler_pid()))
        return

    config = _carregar_config()
    from core.agent import Agent
    agent = Agent(config)

    pid = os.getpid()
    PID_FILE.write_text(str(pid), encoding="utf-8")
    print(f"MJS Agent iniciado (PID {pid})")
    print("Pastas sendo vigiadas:")
    for nome, v in config.get("vigilantes", {}).items():
        if v.get("ativo", True):
            print(f"  {nome}: {v.get('pasta', '?')} -> {v.get('acao', '?')}")

    # Handler pra parar graciosamente
    def _parar(sig, frame):
        agent.stop()
        PID_FILE.unlink(missing_ok=True)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _parar)
    signal.signal(signal.SIGINT, _parar)

    agent.start()

    # Mantem vivo
    while True:
        time.sleep(1)


def cmd_stop():
    pid = _ler_pid()
    if not pid:
        print("Agente nao esta rodando.")
        return
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"Agente (PID {pid}) parado.")
    except ProcessLookupError:
        print("Agente nao estava rodando.")
        PID_FILE.unlink(missing_ok=True)


def cmd_status():
    if _agente_rodando():
        pid = _ler_pid()
        print(f"Agente: RODANDO (PID {pid})")
        print(f"Log: {ROOT / 'agent.log'}")
    else:
        print("Agente: PARADO")


def cmd_bolsinhas():
    config = _carregar_config()
    pasta = sys.argv[2] if len(sys.argv) > 2 else _get_vigilante_pasta(config, "bolsinhas")
    if not pasta or not Path(pasta).exists():
        print("Pasta nao encontrada. Use: mjs bolsinhas <caminho>")
        return
    from core.bolsinhas import process_all
    ok, erros = process_all(Path(pasta), log_callback=print)
    print(f"OK: {ok}  Erros: {erros}")


def cmd_conf():
    config = _carregar_config()
    pasta = sys.argv[2] if len(sys.argv) > 2 else _get_vigilante_pasta(config, "conf")
    if not pasta or not Path(pasta).exists():
        print("Pasta nao encontrada. Use: mjs conf <caminho>")
        return
    from core.conf import process_tiff, FileLog
    flog = FileLog(Path(pasta))
    for f in sorted(Path(pasta).iterdir()):
        if f.suffix.lower() in (".tif", ".tiff") and f.name != "processados.log":
            if flog.already_done(f.name):
                print(f"  [SKIP] {f.name} (ja processado)")
                continue
            try:
                info = process_tiff(str(f), emit=print)
                flog.mark_done(f.name)
                f.unlink()
                print(f"  [OK] {f.name}")
            except Exception as e:
                print(f"  [ERRO] {f.name}: {e}")


def cmd_pastas():
    config = _carregar_config()
    base = Path(config.get("diario", {}).get("raiz", "Z:\\"))
    sub = config.get("diario", {}).get("subpastas", ["BOLSINHAS", "PAINEL_CUT", "CONF"])
    target = base / datetime.datetime.now().strftime("%d %m %Y")
    target.mkdir(exist_ok=True)
    for s in sub:
        (target / s).mkdir(parents=True, exist_ok=True)
    print(f"Pastas criadas em: {target}")


def cmd_cortar():
    print("Modo interativo nao implementado via CLI ainda.")
    print("Use: python cort_gui.py para interface grafica")
    print("Ou edite cort_color_correct.py com os parametros diretos")


def cmd_config():
    config = _carregar_config()
    print(json.dumps(config, indent=2, ensure_ascii=False))


# ── Utilitarios ─────────────────────────────────────────────────────────────

def _agente_rodando():
    pid = _ler_pid()
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _ler_pid():
    if PID_FILE.exists():
        try:
            return int(PID_FILE.read_text().strip())
        except (ValueError, OSError):
            return None
    return None


def _get_vigilante_pasta(config, nome):
    v = config.get("vigilantes", {}).get(nome, {})
    return v.get("pasta", "")


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]
    cmds = {
        "start": cmd_start,
        "stop": cmd_stop,
        "status": cmd_status,
        "bolsinhas": cmd_bolsinhas,
        "conf": cmd_conf,
        "pastas": cmd_pastas,
        "cortar": cmd_cortar,
        "config": cmd_config,
    }

    if cmd in cmds:
        cmds[cmd]()
    else:
        print(f"Comando desconhecido: {cmd}\n")
        print(__doc__)


if __name__ == "__main__":
    main()
