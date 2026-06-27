"""
app.py - Servidor Flask para classificacao de imagens via web.

Uso:
    python app.py
    python app.py --port 5000
"""

import argparse
import base64
import io
import os
import tempfile
import time
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
from PIL import Image
from knn_model import load_model, classify_image, SUPPORTED_EXTENSIONS

Image.MAX_IMAGE_PIXELS = None

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max (TIFs grandes)

# Caminhos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "modelo", "knn_model.pkl")

# Variáveis globais do modelo
pipeline = None
categories = None


def init_model():
    """Carrega o modelo ao iniciar o servidor."""
    global pipeline, categories
    if os.path.exists(MODEL_PATH):
        pipeline, categories = load_model(MODEL_PATH)
        print(f"[OK] Modelo carregado: {MODEL_PATH}")
        print(f"[>] Categorias: {list(categories.values())}")
    else:
        print(f"[!] Modelo nao encontrado em: {MODEL_PATH}")
        print("   Execute 'python train.py' primeiro.")


def generate_preview(filepath, max_size=800):
    """
    Gera um preview JPEG em base64 de qualquer imagem suportada.

    Args:
        filepath: Caminho para a imagem.
        max_size: Tamanho maximo do lado maior.

    Returns:
        Dicionario com preview_base64, largura, altura originais.
    """
    try:
        img = Image.open(filepath)
        original_width, original_height = img.size
        original_mode = img.mode

        # Converter para RGB se necessario (CMYK, RGBA, etc)
        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')
        elif img.mode == 'L':
            img = img.convert('RGB')

        # Redimensionar mantendo proporcao
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

        # Converter para JPEG base64
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=85)
        buffer.seek(0)
        b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

        return {
            'preview_base64': f'data:image/jpeg;base64,{b64}',
            'largura_original': original_width,
            'altura_original': original_height,
            'modo_cor': original_mode,
            'preview_largura': img.width,
            'preview_altura': img.height,
        }
    except Exception as e:
        return None


@app.route('/')
def index():
    """Pagina principal."""
    model_loaded = pipeline is not None
    cats = list(categories.values()) if categories else []
    return render_template('index.html', model_loaded=model_loaded, categories=cats)


@app.route('/api/classify', methods=['POST'])
def api_classify():
    """Endpoint de classificacao de imagem com preview."""
    if pipeline is None:
        return jsonify({'error': 'Modelo nao carregado. Execute train.py primeiro.'}), 503

    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado.'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nenhum arquivo selecionado.'}), 400

    # Verificar extensao
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return jsonify({
            'error': f'Formato nao suportado: {ext}. Use: {", ".join(SUPPORTED_EXTENSIONS)}'
        }), 400

    # Salvar temporariamente
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        # Tamanho do arquivo
        file_size = os.path.getsize(tmp_path)

        # Gerar preview
        preview_data = generate_preview(tmp_path)

        # Classificar
        start = time.time()
        result = classify_image(tmp_path, pipeline, categories)
        elapsed = time.time() - start

        if result is None:
            return jsonify({'error': 'Nao foi possivel processar a imagem.'}), 422

        result['tempo_processamento'] = f"{elapsed:.2f}s"
        result['arquivo'] = file.filename
        result['tamanho_arquivo'] = file_size

        # Adicionar dados do preview
        if preview_data:
            result['preview'] = preview_data

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    finally:
        # Limpar arquivo temporario
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


@app.route('/api/status')
def api_status():
    """Status do servidor e modelo."""
    return jsonify({
        'status': 'online',
        'modelo_carregado': pipeline is not None,
        'categorias': list(categories.values()) if categories else [],
    })


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Servidor web para classificacao de imagens.")
    parser.add_argument('--port', '-p', type=int, default=5000, help='Porta do servidor (padrao: 5000)')
    parser.add_argument('--host', default='0.0.0.0', help='Host (padrao: 0.0.0.0)')
    args = parser.parse_args()

    init_model()

    print(f"\n[>] Servidor iniciado em http://localhost:{args.port}")
    app.run(host=args.host, port=args.port, debug=False)

