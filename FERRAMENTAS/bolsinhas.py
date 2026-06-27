#!/usr/bin/env python3
"""
Monitora uma pasta e gera automaticamente bolsinhas JPEG (10% do tamanho)
para todo TIFF que ainda não foi processado.

Grava um registro das imagens feitas, remove os arquivos TIFF originais 
cujas bolsinhas já foram geradas e exibe uma notificação no Windows.

Pressione Ctrl+C para encerrar.
"""

import sys
import os
import time
from pathlib import Path
from datetime import datetime

# Bloco de auto-instalação das bibliotecas necessárias
try:
    from PIL import Image
    from plyer import notification
except ImportError:
    print("Instalando dependências (Pillow, plyer)...")
    os.system(f"{sys.executable} -m pip install Pillow plyer")
    from PIL import Image
    from plyer import notification

Image.MAX_IMAGE_PIXELS = None

EXTENSOES_TIFF = {".tif", ".tiff"}
INTERVALO_SEGUNDOS = 10  # verifica a pasta a cada 10 segundos
NOME_REGISTRO = "registro_bolsinhas.txt"


def log(mensagem: str) -> None:
    hora = datetime.now().strftime("%H:%M:%S")
    print(f"[{hora}] {mensagem}")


def avisar_windows(mensagem: str, titulo: str = "Bolsinhas Prontas!") -> None:
    """Envia uma notificação para o canto inferior direito do Windows."""
    try:
        notification.notify(
            title=titulo,
            message=mensagem,
            app_name="Gerador de Bolsinhas",
            timeout=5  # Tempo em segundos que a notificação fica na tela
        )
    except Exception as e:
        log(f"  [AVISO] Não foi possível exibir notificação no Windows: {e}")


def carregar_registro(pasta: Path) -> set:
    """Carrega o histórico de bolsinhas já geradas."""
    arquivo_registro = pasta / NOME_REGISTRO
    if arquivo_registro.exists():
        with open(arquivo_registro, "r", encoding="utf-8") as f:
            return set(linha.strip() for linha in f if linha.strip())
    return set()


def salvar_no_registro(pasta: Path, nome_tiff: str) -> None:
    """Salva o nome do TIFF processado no arquivo de registro."""
    arquivo_registro = pasta / NOME_REGISTRO
    with open(arquivo_registro, "a", encoding="utf-8") as f:
        f.write(nome_tiff + "\n")


def bolsinha_existe(tiff: Path) -> bool:
    """Verifica se a bolsinha JPEG correspondente já existe no disco."""
    nome_bolsinha = "bolsinha_" + tiff.stem + ".jpeg"
    return (tiff.parent / nome_bolsinha).exists()


def limpar_tiffs_processados(pasta: Path) -> None:
    """Verifica os TIFFs na pasta. Se a bolsinha já existir ou estiver no registro, remove o TIFF."""
    registro = carregar_registro(pasta)
    
    for arquivo in pasta.iterdir():
        if arquivo.is_file() and arquivo.suffix.lower() in EXTENSOES_TIFF and not arquivo.stem.lower().startswith("bolsinha_"):
            ja_registrado = arquivo.name in registro
            ja_tem_bolsinha = bolsinha_existe(arquivo)
            
            if ja_registrado or ja_tem_bolsinha:
                try:
                    arquivo.unlink()
                    motivo = "estava no registro" if ja_registrado else "bolsinha já existia"
                    log(f"  [LIMPEZA] TIFF removido ({motivo}): {arquivo.name}")
                    
                    # Garante que está no registro se a bolsinha já existia fisicamente
                    if not ja_registrado:
                        salvar_no_registro(pasta, arquivo.name)
                except Exception as e:
                    log(f"  [ERRO] Não foi possível remover {arquivo.name}: {e}")


def tiffs_pendentes(pasta: Path) -> list[Path]:
    """Retorna TIFFs que ainda não têm bolsinha gerada."""
    return sorted([
        f for f in pasta.iterdir()
        if f.is_file()
        and f.suffix.lower() in EXTENSOES_TIFF
        and not f.stem.lower().startswith("bolsinha_")
    ])


def redimensionar(tiff: Path) -> bool:
    """Gera a bolsinha JPEG de um TIFF e remove o TIFF original. Retorna True se OK."""
    caminho_saida = tiff.parent / ("bolsinha_" + tiff.stem + ".jpeg")

    try:
        with Image.open(tiff) as img:
            w, h = img.size
            novo_w = max(1, round(w * 0.10))
            novo_h = max(1, round(h * 0.10))

            log(f"  > Processando: {tiff.name}")
            log(f"    {w} x {h} px  ->  {novo_w} x {novo_h} px")

            img_redim = img.convert("RGB").resize((novo_w, novo_h), Image.LANCZOS)
            img_redim.save(caminho_saida, "JPEG", quality=85, optimize=True)

        mb_orig = tiff.stat().st_size / (1024 * 1024)
        kb_novo = caminho_saida.stat().st_size / 1024
        log(f"    {mb_orig:.1f} MB  ->  {kb_novo:.1f} KB  OK  {caminho_saida.name}")
        
        # Registra o sucesso e apaga o TIFF
        salvar_no_registro(tiff.parent, tiff.name)
        try:
            tiff.unlink()
            log(f"    [SUCESSO] TIFF original removido: {tiff.name}")
        except Exception as e:
            log(f"    [AVISO] Bolsinha criada, mas erro ao remover TIFF: {e}")
            
        return True

    except Exception as e:
        log(f"    ERRO ao processar {tiff.name}: {e}")
        if caminho_saida.exists():
            caminho_saida.unlink()
        return False


def processar_pendentes(pasta: Path) -> tuple[int, int]:
    """Processa todos os TIFFs pendentes. Retorna (ok, erros)."""
    pendentes = tiffs_pendentes(pasta)

    if not pendentes:
        return 0, 0

    log("=" * 50)
    log(f"{len(pendentes)} TIFF(s) para processar encontrados:")
    ok = erros = 0

    for tiff in pendentes:
        if redimensionar(tiff):
            ok += 1
        else:
            erros += 1

    log("=" * 50)
    log(f"Lote concluido — OK: {ok}  Erro: {erros}")
    
    # Se pelo menos uma bolsinha foi gerada com sucesso, avisa o Windows
    if ok > 0:
        avisar_windows(f"Lote concluído! {ok} bolsinha(s) gerada(s).")
        
    return ok, erros


def monitorar(pasta: Path) -> None:
    """Loop principal: verifica e processa em intervalos regulares."""
    log(f"Monitorando pasta: {pasta}")
    log(f"Verificacao a cada {INTERVALO_SEGUNDOS}s — Ctrl+C para encerrar\n")

    while True:
        # Primeiro, limpa qualquer TIFF que já tenha bolsinha ou esteja no registro
        limpar_tiffs_processados(pasta)
        
        # Depois, processa o que sobrou (os novos TIFFs)
        processar_pendentes(pasta)
        
        time.sleep(INTERVALO_SEGUNDOS)


def main(p: Path) -> None:
    pasta = Path(p)

    if not pasta.exists():
        print(f"Pasta nao encontrada: {pasta}")
        sys.exit(1)

    if not pasta.is_dir():
        print(f"O caminho informado nao e uma pasta: {pasta}")
        sys.exit(1)

    try:
        monitorar(pasta)
    except KeyboardInterrupt:
        print("\n\nMonitoramento encerrado.")


if __name__ == "__main__":
    p = Path(r"Z:\26 06 2026\BOLSINHAS\PARA FAZER")
    main(p)