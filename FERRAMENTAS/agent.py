#!/usr/bin/env python3
"""
MJS Agent — Motor Autônomo
===========================
Executa em background lendo as regras definidas no regras.md.
Possui suporte a hot-reload de regras, controle de processos sempre_ativo,
monitoramento de pastas e encadeamentos de ações.
"""

import sys
import os
import time
import json
import threading
import subprocess
import shutil
import datetime
from pathlib import Path

from PIL import Image

from core.utils import notify
from core.bolsinhas import generate_thumbnail
from core.conf import process_tiff, FileLog

Image.MAX_IMAGE_PIXELS = None

# ── Caminhos ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
REGRAS_MD = ROOT / "regras.md"
LOG_FILE = ROOT / "agent_log.txt"

# ── Utilitários de Log ──────────────────────────────────────────────────────────
def agent_log(mensagem: str):
    hora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"[{hora}] {mensagem}"
    print(linha)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(linha + "\n")
    except Exception as e:
        print(f"Erro ao gravar log do agente: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# Parser de regras.md
# ══════════════════════════════════════════════════════════════════════════════

def parse_regras_md(caminho: Path) -> tuple[dict, list]:
    regras = {}
    encadeamentos = []
    
    if not caminho.exists():
        return regras, encadeamentos

    content = caminho.read_text(encoding="utf-8")
    current_regra = None
    current_encad = None
    
    for line in content.splitlines():
        line_strip = line.strip()
        if not line_strip or line_strip.startswith("#"):
            continue
            
        if line_strip.startswith("## REGRA:"):
            name = line_strip.replace("## REGRA:", "").strip()
            current_regra = {"nome": name}
            regras[name] = current_regra
            current_encad = None
        elif line_strip.startswith("## ENCADEAMENTO:"):
            name = line_strip.replace("## ENCADEAMENTO:", "").strip()
            current_encad = {"nome": name}
            encadeamentos.append(current_encad)
            current_regra = None
        elif line_strip.startswith("- "):
            raw = line_strip[2:].strip()
            if ":" in raw:
                k, v = raw.split(":", 1)
                k = k.strip().lower()
                v = v.strip()
                if current_regra is not None:
                    current_regra[k] = v
                elif current_encad is not None:
                    current_encad[k] = v
                    
    return regras, encadeamentos


# ══════════════════════════════════════════════════════════════════════════════
# Motor Principal do Agente
# ══════════════════════════════════════════════════════════════════════════════

class MjsAgent:
    def __init__(self):
        self.running = False
        self.regras = {}
        self.encadeamentos = []
        self.last_modified = 0
        self.threads = {}
        self.processos = {}
        self.watcher_stops = {}
        self.lock = threading.Lock()
        
    def start(self):
        if self.running:
            return
        self.running = True
        agent_log("🤖 MJS Agent Iniciado.")
        
        # Thread para ler e monitorar mudanças no regras.md (Hot-reload)
        threading.Thread(target=self._hot_reload_loop, daemon=True).start()
        
        # Thread para verificar agendamento de horários diariamente
        threading.Thread(target=self._scheduler_loop, daemon=True).start()

    def stop(self):
        self.running = False
        agent_log("⏹️ MJS Agent Desligando...")
        self._cleanup_all()

    def _cleanup_all(self):
        with self.lock:
            # Para todos os watchers de arquivo novo
            for pasta, stop_evt in list(self.watcher_stops.items()):
                stop_evt.set()
            self.watcher_stops.clear()

            # Mata processos do Notepad ou outros subprocessos ativos
            for nome, proc in list(self.processos.items()):
                try:
                    proc.terminate()
                    agent_log(f"Processo finalizado: {nome}")
                except Exception:
                    pass
            self.processos.clear()
            
            # Limpa threads ativas
            self.threads.clear()

    def _hot_reload_loop(self):
        while self.running:
            try:
                if REGRAS_MD.exists():
                    mtime = REGRAS_MD.stat().st_mtime
                    if mtime > self.last_modified:
                        agent_log("⚙️ Detectada alteração em regras.md. Carregando configurações...")
                        self._reload_regras()
                        self.last_modified = mtime
            except Exception as e:
                agent_log(f"Erro no loop de Hot-reload: {e}")
            time.sleep(2)

    def _reload_regras(self):
        novas_regras, novos_encad = parse_regras_md(REGRAS_MD)
        
        with self.lock:
            # 1. Parar o que não existe mais ou mudou de configuração
            regras_para_parar = []
            for nome in self.regras:
                if nome not in novas_regras or self.regras[nome] != novas_regras[nome]:
                    regras_para_parar.append(nome)
            
            for nome in regras_para_parar:
                self._stop_regra_action(nome)

            # 2. Atualizar estado interno de regras e encadeamentos
            self.regras = novas_regras
            self.encadeamentos = novos_encad

            # 3. Iniciar novas regras ou regras atualizadas
            for nome, config in self.regras.items():
                gatilho = config.get("gatilho")
                if gatilho == "sempre_ativo":
                    if nome not in self.processos and nome not in self.threads:
                        self._start_regra_action(nome, config)
                elif gatilho == "arquivo_novo":
                    if nome not in self.threads:
                        self._start_regra_action(nome, config)

    def _start_regra_action(self, nome: str, config: dict):
        acao = config.get("acao")
        gatilho = config.get("gatilho")
        
        agent_log(f"▶️ Ativando regra: '{nome}' [{gatilho}]")
        
        if gatilho == "sempre_ativo":
            if acao == "notepad_servidor":
                proc_thread = threading.Thread(target=self._keep_alive_process, args=(nome, config, [sys.executable, str(ROOT / "notepad" / "ws_server.py")], str(ROOT / "notepad")), daemon=True)
                self.threads[nome] = proc_thread
                proc_thread.start()
            # Outras tarefas sempre_ativo podem ir aqui se criadas.
            
        elif gatilho == "arquivo_novo":
            pasta = config.get("pasta")
            exts = [e.strip().lower() for e in config.get("ext", "").split(",") if e.strip()]
            if pasta:
                stop_evt = threading.Event()
                self.watcher_stops[nome] = stop_evt
                t = threading.Thread(target=self._watch_directory, args=(nome, config, Path(pasta), exts, stop_evt), daemon=True)
                self.threads[nome] = t
                t.start()

    def _stop_regra_action(self, nome: str):
        agent_log(f"⏹️ Parando regra: '{nome}'")
        # Finaliza processo se for sempre_ativo
        if nome in self.processos:
            try:
                self.processos[nome].terminate()
            except Exception:
                pass
            del self.processos[nome]
        
        # Para monitoramento se for arquivo_novo
        if nome in self.watcher_stops:
            self.watcher_stops[nome].set()
            del self.watcher_stops[nome]
            
        if nome in self.threads:
            del self.threads[nome]

    # ── Mecanismo de Loop para processos Sempre Ativos ────────────────────────
    def _keep_alive_process(self, nome: str, config: dict, cmd: list, cwd: str):
        reiniciar = config.get("reiniciar_se_cair", "sim").lower() in ("sim", "yes", "true", "1")
        
        while self.running and nome in self.threads:
            try:
                flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                proc = subprocess.Popen(cmd, cwd=cwd, creationflags=flags)
                with self.lock:
                    self.processos[nome] = proc
                
                agent_log(f"Processo '{nome}' iniciado com PID {proc.pid}")
                proc.wait()
                
                with self.lock:
                    if nome in self.processos:
                        del self.processos[nome]
                
                if not self.running or not reiniciar or nome not in self.threads:
                    break
                    
                agent_log(f"⚠️ Processo '{nome}' caiu. Reiniciando em 5 segundos...")
                time.sleep(5)
            except Exception as e:
                agent_log(f"Erro ao manter processo '{nome}': {e}")
                time.sleep(10)

    # ── Mecanismo de Monitoramento de Pastas (arquivo_novo) ───────────────────
    def _watch_directory(self, nome: str, config: dict, pasta: Path, exts: list, stop_evt: threading.Event):
        agent_log(f"Monitorando arquivos novos em '{pasta}' para regra '{nome}'")
        pasta.mkdir(parents=True, exist_ok=True)
        
        # Dicionário local para ignorar arquivos já processados
        processed = set()
        
        # Caso seja ação bolsinhas ou conf, precisamos instanciar/carregar o histórico do log do arquivo se aplicável
        # Mas para simplificar o fluxo autônomo, agiremos com base nas ferramentas que já lidam com isso internamente.
        
        while not stop_evt.is_set() and self.running:
            try:
                for f in pasta.iterdir():
                    if stop_evt.is_set():
                        break
                    if f.is_file() and f.suffix.lower() in exts and f.name not in processed:
                        # Ignora bolsinhas criadas para evitar loop se a mesma pasta for monitorada
                        if f.stem.lower().startswith("bolsinha_"):
                            continue
                            
                        processed.add(f.name)
                        agent_log(f"🔔 Novo arquivo detectado para regra '{nome}': {f.name}")
                        
                        # Executa a ação da regra em background
                        threading.Thread(target=self._executar_acao_regra, args=(nome, config, f), daemon=True).start()
            except Exception as e:
                pass
            stop_evt.wait(5)

    def _executar_acao_regra(self, nome: str, config: dict, arquivo_disparador: Path = None):
        acao = config.get("acao")
        agent_log(f"⚙️ Executando ação '{acao}' da regra '{nome}'...")
        
        try:
            sucesso = False
            if acao == "bolsinhas":
                if arquivo_disparador and arquivo_disparador.exists():
                    self._esperar_estabilizar(arquivo_disparador)
                    generate_thumbnail(arquivo_disparador)
                    arquivo_disparador.unlink()
                    agent_log(f"✅ Bolsinha gerada para: {arquivo_disparador.name}")
                    sucesso = True
                    
            elif acao == "conf":
                if arquivo_disparador and arquivo_disparador.exists():
                    self._esperar_estabilizar(arquivo_disparador)
                    log_obj = FileLog(arquivo_disparador.parent)
                    if not log_obj.already_done(arquivo_disparador.name):
                        info = process_tiff(str(arquivo_disparador), emit=agent_log)
                        log_obj.mark_done(arquivo_disparador.name, f"AUTO: {info['width_cm']}x{info['height_cm']} cm")
                        arquivo_disparador.unlink()
                        agent_log(f"✅ CONF processado: {arquivo_disparador.name}")
                        sucesso = True
                    else:
                        dest = arquivo_disparador.parent.parent / arquivo_disparador.name
                        if dest.exists():
                            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                            dest = dest.with_name(f"{dest.stem}_duplicado_{stamp}{dest.suffix}")
                        shutil.move(str(arquivo_disparador), str(dest))
                        agent_log(f"📦 Duplicado movido: {dest.name}")
                        sucesso = True

            elif acao == "criar_pastas":
                base = Path(config.get("base", "Z:\\"))
                subpastas = [s.strip() for s in config.get("subpastas", "").split(",") if s.strip()]
                target = base / datetime.datetime.now().strftime("%d %m %Y")
                target.mkdir(exist_ok=True)
                for sub in subpastas:
                    (target / sub).mkdir(parents=True, exist_ok=True)
                agent_log(f"✅ Pastas criadas: {target}")
                sucesso = True

            elif acao == "notificar":
                msg = config.get("mensagem", "Ação concluída pelo agente.")
                notify("MJS Agent", msg)
                sucesso = True

            if sucesso:
                self._verificar_encadeamentos(nome)
                
        except Exception as e:
            agent_log(f"❌ Erro ao executar ação '{acao}' da regra '{nome}': {e}")

    def _esperar_estabilizar(self, filepath: Path):
        prev = -1
        while True:
            try:
                cur = filepath.stat().st_size
            except OSError:
                cur = -1
            if cur == prev and cur >= 0:
                break
            prev = cur
            time.sleep(1.5)

    # ── Mecanismo de Encadeamento de Regras ───────────────────────────────────
    def _verificar_encadeamentos(self, nome_regra_concluida: str):
        for encad in self.encadeamentos:
            primeiro = encad.get("primeiro")
            depois = encad.get("depois")
            notificacao = encad.get("notificar")
            
            if primeiro == nome_regra_concluida:
                agent_log(f"🔗 Encadeamento ativado! Regra '{primeiro}' disparou '{depois}'")
                
                # Executa a regra seguinte
                if depois in self.regras:
                    # Roda em thread separada
                    threading.Thread(target=self._executar_acao_regra, args=(depois, self.regras[depois]), daemon=True).start()
                    
                if notificacao:
                    # Remove as aspas do MD se houver
                    notif_clean = notificacao.strip('"').strip("'")
                    notify("MJS Agent - Encadeamento", notif_clean)

    # ── Loop do Agendamento Diário (horario_diario) ───────────────────────────
    def _scheduler_loop(self):
        disparos_hoje = {} # Guarda regras que já rodaram hoje
        
        while self.running:
            hoje = datetime.date.today()
            agora = datetime.datetime.now().strftime("%H:%M")
            
            with self.lock:
                for nome, config in self.regras.items():
                    gatilho = config.get("gatilho")
                    if gatilho == "horario_diario":
                        hora_alvo = config.get("hora")
                        if hora_alvo == agora:
                            chave = (nome, hoje)
                            if chave not in disparos_hoje:
                                disparos_hoje[chave] = True
                                agent_log(f"⏰ Horário atingido ({agora}) para regra: '{nome}'")
                                threading.Thread(target=self._executar_acao_regra, args=(nome, config), daemon=True).start()
            
            # Limpa chaves antigas do dicionário de disparos para economizar memória
            for k in list(disparos_hoje.keys()):
                if k[1] < hoje:
                    del disparos_hoje[k]
                    
            time.sleep(30)


# ══════════════════════════════════════════════════════════════════════════════
# Entrada para execução autônoma/CLI
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    agent = MjsAgent()
    try:
        agent.start()
        # Mantém a thread principal rodando
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        agent.stop()
