"""
train.py — Script para treinar o modelo KNN com as imagens de treinamento.

Uso:
    python train.py
    python train.py --data "Z:\\TREINAMENTO\\COR" --output "./modelo"
"""

import argparse
import os
import sys
import time
from knn_model import load_training_data, train_knn, save_model

# Diretório padrão das imagens de treinamento
DEFAULT_TRAINING_DIR = r"Z:\TREINAMENTO\COR"
# Diretório padrão para salvar o modelo
DEFAULT_MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modelo")


def main():
    parser = argparse.ArgumentParser(
        description="Treina o classificador KNN para imagens de impressão colorida."
    )
    parser.add_argument(
        "--data", "-d",
        default=DEFAULT_TRAINING_DIR,
        help=f"Diretório com as imagens de treinamento (padrão: {DEFAULT_TRAINING_DIR})"
    )
    parser.add_argument(
        "--output", "-o",
        default=DEFAULT_MODEL_DIR,
        help=f"Diretório para salvar o modelo (padrão: {DEFAULT_MODEL_DIR})"
    )

    args = parser.parse_args()

    if not os.path.isdir(args.data):
        print(f"ERRO: Diretório de treinamento não encontrado: {args.data}")
        sys.exit(1)

    print("=" * 60)
    print("  TREINAMENTO KNN - Classificador de Imagens")
    print("=" * 60)
    print(f"\n[>] Dados:   {args.data}")
    print(f"[>] Saida:   {args.output}\n")

    # 1. Carregar dados
    print("-" * 60)
    print("ETAPA 1: Carregando imagens e extraindo features...")
    print("-" * 60)
    start = time.time()

    X, y, filenames, categories = load_training_data(args.data)

    elapsed = time.time() - start
    print(f"\n[OK] {len(X)} imagens processadas em {elapsed:.1f}s")
    print(f"[>] Vetor de features: {X.shape[1]} dimensoes")
    print(f"[>] Categorias: {categories}")
    for idx, cat in categories.items():
        count = sum(1 for label in y if label == idx)
        print(f"   [{idx}] {cat}: {count} imagens")

    # 2. Treinar modelo
    print("\n" + "-" * 60)
    print("ETAPA 2: Treinando KNN com GridSearchCV + Leave-One-Out CV...")
    print("-" * 60)
    start = time.time()

    pipeline, best_params, cv_score = train_knn(X, y)

    elapsed = time.time() - start
    print(f"\n[OK] Treinamento concluido em {elapsed:.1f}s")
    print(f"[>] Acuracia LOO-CV: {cv_score:.2%}")
    print(f"[>] Melhores parametros:")
    for param, value in best_params.items():
        print(f"   {param}: {value}")

    # 3. Salvar modelo
    print("\n" + "-" * 60)
    print("ETAPA 3: Salvando modelo...")
    print("-" * 60)

    save_model(pipeline, categories, args.output)

    print("\n" + "=" * 60)
    print("  TREINAMENTO CONCLUIDO COM SUCESSO!")
    print("=" * 60)
    print(f"\n[>] Acuracia: {cv_score:.2%}")
    print(f"[>] Modelo salvo em: {os.path.join(args.output, 'knn_model.pkl')}")
    print(f"\nProximos passos:")
    print(f"  - Iniciar o servidor web:  python app.py")
    print(f"  - Classificar em lote:     python batch_classify.py --input <pasta>")


if __name__ == "__main__":
    main()
