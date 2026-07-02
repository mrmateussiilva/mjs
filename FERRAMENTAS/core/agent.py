import sys, os, time, json, threading, subprocess, shutil, datetime
from pathlib import Path

from core.bolsinhas import process_all as _bolsinhas
from core.conf import process_tiff, FileLog
from core.utils import notify, wait_until_stable

ROOT = Path(__file__).parent.parent
LOG = ROOT / "agent.log"


def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


class Watcher:
    """Monitora uma pasta e executa uma acao para cada arquivo novo."""

    def __init__(self, nome, pasta, ext, acao, stop_evt):
        self.nome = nome
        self.pasta = Path(pasta)
        self.ext = ext
        self.acao = acao
        self.stop_evt = stop_evt
        self.processados = set()

    def start(self):
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()
        return t

    def _loop(self):
        log(f"  Viglando: {self.pasta} ({self.ext}) -> {self.acao}")
        while not self.stop_evt.is_set():
            try:
                for f in self.pasta.iterdir():
                    if self.stop_evt.is_set():
                        break
                    if f.is_file() and f.suffix.lower() in self.ext and f.name not in self.processados:
                        if f.stem.lower().startswith("bolsinha_"):
                            continue
                        self.processados.add(f.name)
                        log(f"  Novo arquivo: {f.name}")
                        threading.Thread(target=self._executar, args=(f,), daemon=True).start()
            except Exception:
                pass
            self.stop_evt.wait(5)

    def _executar(self, f):
        try:
            if self.acao == "conf":
                wait_until_stable(str(f))
                flog = FileLog(self.pasta)
                if flog.already_done(f.name):
                    dest = self.pasta.parent / f.name
                    if dest.exists():
                        dest = dest.with_name(f"{dest.stem}_dup_{f.name}")
                    shutil.move(str(f), str(dest))
                    log(f"  Duplicado movido: {dest.name}")
                    return
                info = process_tiff(str(f), emit=log)
                flog.mark_done(f.name)
                f.unlink()
                log(f"  CONF OK: {f.name}")
                notify("CONF", f"Processado: {f.name}")

            elif self.acao == "bolsinhas":
                ok, _ = _bolsinhas(self.pasta, log_callback=log)
                if ok:
                    notify("Bolsinhas", f"{ok} miniaturas geradas")

        except Exception as e:
            log(f"  ERRO em {f.name}: {e}")


class Agent:
    def __init__(self, config: dict):
        self.config = config
        self.running = False
        self._threads = {}
        self._watchers = {}
        self._stop_evt = threading.Event()

    def start(self):
        if self.running:
            return
        self.running = True
        self._stop_evt.clear()
        log("=" * 50)
        log("MJS Agent iniciado")

        cfg = self.config

        # Notepad
        if cfg.get("notepad", {}).get("ativo", True):
            self._iniciar_notepad()

        # Vigilantes
        vigilantes = cfg.get("vigilantes", {})
        for nome, v in vigilantes.items():
            if not v.get("ativo", True):
                continue
            ext = set(e.strip().lower() for e in v.get("ext", ".tif,.tiff").split(","))
            w = Watcher(nome, v["pasta"], ext, v["acao"], self._stop_evt)
            w.start()
            self._watchers[nome] = w

        # Agendador diario
        if cfg.get("diario", {}).get("criar_pastas", False):
            t = threading.Thread(target=self._agendador, daemon=True)
            t.start()
            self._threads["agendador"] = t

        log("Agente pronto")

    def stop(self):
        log("Parando agente...")
        self.running = False
        self._stop_evt.set()
        self._parar_notepad()

    def _iniciar_notepad(self):
        ws = ROOT / "notepad" / "ws_server.py"
        if not ws.exists():
            log("  ws_server.py nao encontrado")
            return
        try:
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            self._proc_notepad = subprocess.Popen(
                [sys.executable, str(ws)],
                cwd=str(ws.parent), creationflags=flags,
            )
            log(f"  Notepad iniciado (PID {self._proc_notepad.pid})")
        except Exception as e:
            log(f"  Erro notepad: {e}")

    def _parar_notepad(self):
        if hasattr(self, "_proc_notepad") and self._proc_notepad:
            try:
                self._proc_notepad.terminate()
                log("  Notepad parado")
            except Exception:
                pass

    def _agendador(self):
        log(f"  Agendador diario ativo (hora: {self.config.get('diario', {}).get('horario', '07:30')})")
        while self.running:
            agora = datetime.datetime.now().strftime("%H:%M")
            hora = self.config.get("diario", {}).get("horario", "07:30")
            hoje = datetime.date.today()

            if agora == hora and getattr(self, "_ultimo_dia", None) != hoje:
                self._ultimo_dia = hoje
                self._criar_pastas()

            time.sleep(30)

    def _criar_pastas(self):
        cfg = self.config.get("diario", {})
        base = Path(cfg.get("raiz", "Z:\\"))
        subpastas = cfg.get("subpastas", ["BOLSINHAS", "BOLSINHAS/PARA FAZER", "PAINEL_CUT", "CONF", "APS", "TEX"])
        target = base / datetime.datetime.now().strftime("%d %m %Y")
        try:
            target.mkdir(exist_ok=True)
            for s in subpastas:
                (target / s).mkdir(parents=True, exist_ok=True)
            log(f"  Pastas criadas: {target}")
            notify("MJS", f"Pastas do dia criadas: {target}")
        except Exception as e:
            log(f"  Erro ao criar pastas: {e}")
