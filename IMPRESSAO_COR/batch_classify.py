"""
batch_classify.py — Classifica todas as imagens de uma pasta usando o modelo treinado.

Uso:
    python batch_classify.py --input "Z:\\pasta_com_imagens"
    python batch_classify.py --input "Z:\\pasta" --output "resultados.csv"
    python batch_classify.py --input "Z:\\pasta" --model "./modelo/knn_model.pkl"
"""

import argparse
import csv
import os
import sys
import time
from knn_model import load_model, classify_image, SUPPORTED_EXTENSIONS


DEFAULT_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modelo", "knn_model.pkl")


def main():
    parser = argparse.ArgumentParser(
        description="Classifica todas as imagens de uma pasta usando o modelo KNN treinado."
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Pasta com as imagens a classificar"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Arquivo CSV de saída (padrão: resultados_<nome_pasta>.csv)"
    )
    parser.add_argument(
        "--model", "-m",
        default=DEFAULT_MODEL_PATH,
        help=f"Caminho do modelo treinado (padrão: {DEFAULT_MODEL_PATH})"
    )

    args = parser.parse_args()

    if not os.path.isdir(args.input):
        print(f"ERRO: Pasta não encontrada: {args.input}")
        sys.exit(1)

    if not os.path.isfile(args.model):
        print(f"ERRO: Modelo não encontrado: {args.model}")
        print("Execute 'python train.py' primeiro para treinar o modelo.")
        sys.exit(1)

    # Nome do CSV de saída
    if args.output is None:
        folder_name = os.path.basename(os.path.normpath(args.input))
        args.output = f"resultados_{folder_name}.csv"

    print("=" * 60)
    print("  CLASSIFICACAO EM LOTE - KNN Impressao Cor")
    print("=" * 60)
    print(f"\n[>] Entrada: {args.input}")
    print(f"[>] Saida:   {args.output}")
    print(f"[>] Modelo:  {args.model}\n")

    # Carregar modelo
    print("Carregando modelo...")
    pipeline, categories = load_model(args.model)
    print(f"[OK] Modelo carregado. Categorias: {list(categories.values())}\n")

    # Listar imagens
    image_files = []
    for fname in os.listdir(args.input):
        ext = os.path.splitext(fname)[1].lower()
        if ext in SUPPORTED_EXTENSIONS:
            image_files.append(fname)

    if not image_files:
        print("[!] Nenhuma imagem encontrada na pasta!")
        sys.exit(0)

    print(f"[>] {len(image_files)} imagens encontradas\n")
    print("-" * 60)

    # Classificar cada imagem
    results = []
    start = time.time()

    for i, fname in enumerate(image_files, 1):
        filepath = os.path.join(args.input, fname)
        print(f"[{i}/{len(image_files)}] {fname}...", end=" ")

        result = classify_image(filepath, pipeline, categories)

        if result:
            cat = result['categoria']
            conf = result['confianca']
            print(f"-> {cat} ({conf:.1%})")

            row = {
                'arquivo': fname,
                'classificacao': cat,
                'confianca': f"{conf:.4f}",
            }
            # Adiciona probabilidades por categoria
            for cat_name, prob in result['probabilidades'].items():
                row[f'prob_{cat_name}'] = f"{prob:.4f}"

            results.append(row)
        else:
            print("-> ERRO (nao processada)")
            results.append({
                'arquivo': fname,
                'classificacao': 'ERRO',
                'confianca': '0',
            })

    elapsed = time.time() - start
    print("-" * 60)

    # Salvar CSV
    if results:
        fieldnames = list(results[0].keys())
        with open(args.output, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
            writer.writeheader()
            writer.writerows(results)

    # Resumo
    print(f"\n[OK] {len(results)} imagens classificadas em {elapsed:.1f}s")
    print(f"[>] Resultados salvos em: {args.output}")

    # Contagem por categoria
    print("\n[>] Resumo:")
    for cat_name in categories.values():
        count = sum(1 for r in results if r['classificacao'] == cat_name)
        print(f"   {cat_name}: {count} imagens")

    erros = sum(1 for r in results if r['classificacao'] == 'ERRO')
    if erros > 0:
        print(f"   ERROS: {erros} imagens")


if __name__ == "__main__":
    main()
