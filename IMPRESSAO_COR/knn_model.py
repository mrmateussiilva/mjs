"""
knn_model.py — Módulo de extração de features e classificação KNN de imagens.

Extrai múltiplas categorias de features de imagens para treinar um
classificador KNN que determina em qual máquina (APS ou TEX) a imagem
será melhor impressa.
"""

import os
import cv2
import numpy as np
from skimage.feature import local_binary_pattern
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import LeaveOneOut, GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.decomposition import PCA
import joblib
import logging
from PIL import Image

# Permite imagens muito grandes (TIFs de impressão podem ter centenas de megapixels)
Image.MAX_IMAGE_PIXELS = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Tamanho padrão para redimensionar imagens antes da extração de features
IMG_SIZE = (512, 512)

# Extensões de imagem suportadas
SUPPORTED_EXTENSIONS = {'.tif', '.tiff', '.png', '.jpg', '.jpeg', '.bmp', '.webp'}


def load_image(filepath, target_size=IMG_SIZE):
    """
    Carrega uma imagem, redimensiona e retorna em BGR e HSV.

    Args:
        filepath: Caminho absoluto para a imagem.
        target_size: Tupla (largura, altura) para redimensionar.

    Returns:
        Tupla (img_bgr, img_hsv) ou (None, None) se falhar.
    """
    try:
        # Abre o arquivo em modo binario para suportar caminhos com caracteres especiais (acentos) no Windows com OpenCV
        with open(filepath, 'rb') as f:
            file_bytes = np.frombuffer(f.read(), dtype=np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

        if img is None:
            # Tenta com Pillow para formatos que o OpenCV não suporta bem
            from PIL import Image
            pil_img = Image.open(filepath).convert('RGB')
            img = np.array(pil_img)
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        if img is None:
            logger.error(f"Não foi possível carregar: {filepath}")
            return None, None

        # Redimensiona mantendo proporção não é necessário para features
        img_resized = cv2.resize(img, target_size, interpolation=cv2.INTER_AREA)
        img_hsv = cv2.cvtColor(img_resized, cv2.COLOR_BGR2HSV)

        return img_resized, img_hsv
    except Exception as e:
        logger.error(f"Erro ao carregar {filepath}: {e}")
        return None, None


def extract_color_histogram(img_hsv, bins=(8, 8, 8)):
    """
    Extrai histograma de cores no espaço HSV.

    Args:
        img_hsv: Imagem no espaço de cor HSV.
        bins: Número de bins para cada canal (H, S, V).

    Returns:
        Vetor normalizado do histograma (512 dimensões com bins padrão).
    """
    hist = cv2.calcHist([img_hsv], [0, 1, 2], None, bins,
                        [0, 180, 0, 256, 0, 256])
    hist = cv2.normalize(hist, hist).flatten()
    return hist


def extract_color_statistics(img_bgr, img_hsv):
    """
    Extrai estatísticas de cor (média, desvio padrão, skewness) por canal.

    Args:
        img_bgr: Imagem em BGR.
        img_hsv: Imagem em HSV.

    Returns:
        Vetor de 18 dimensões (3 stats × 6 canais).
    """
    stats = []
    # Canais BGR
    for i in range(3):
        channel = img_bgr[:, :, i].astype(np.float64)
        stats.append(np.mean(channel))
        stats.append(np.std(channel))
        # Skewness
        mean = np.mean(channel)
        std = np.std(channel)
        if std > 0:
            stats.append(np.mean(((channel - mean) / std) ** 3))
        else:
            stats.append(0.0)
    # Canais HSV
    for i in range(3):
        channel = img_hsv[:, :, i].astype(np.float64)
        stats.append(np.mean(channel))
        stats.append(np.std(channel))
        mean = np.mean(channel)
        std = np.std(channel)
        if std > 0:
            stats.append(np.mean(((channel - mean) / std) ** 3))
        else:
            stats.append(0.0)
    return np.array(stats)


def extract_lbp_features(img_bgr, radius=3, n_points=24, n_bins=26):
    """
    Extrai features de textura usando Local Binary Patterns.

    Args:
        img_bgr: Imagem em BGR.
        radius: Raio do LBP.
        n_points: Número de pontos no LBP.
        n_bins: Número de bins no histograma.

    Returns:
        Vetor normalizado do histograma LBP (26 dimensões).
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    lbp = local_binary_pattern(gray, n_points, radius, method='uniform')
    hist, _ = np.histogram(lbp.ravel(), bins=n_bins, range=(0, n_bins), density=True)
    return hist


def extract_gradient_features(img_bgr, n_bins=36):
    """
    Extrai histograma de gradientes orientados (HOG simplificado).

    Args:
        img_bgr: Imagem em BGR.
        n_bins: Número de bins para orientação dos gradientes.

    Returns:
        Vetor normalizado (36 dimensões).
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    # Gradientes Sobel
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    magnitude = np.sqrt(gx ** 2 + gy ** 2)
    orientation = np.arctan2(gy, gx) * (180 / np.pi) % 360

    hist, _ = np.histogram(orientation.ravel(), bins=n_bins, range=(0, 360),
                           weights=magnitude.ravel(), density=True)
    return hist


def extract_dominant_colors(img_hsv, n_ranges=10):
    """
    Extrai a proporção de pixels em faixas de cor pré-definidas.

    As faixas cobrem as cores principais do espectro HSV:
    vermelho, laranja, amarelo, verde-lima, verde, ciano, azul,
    violeta, magenta, escala de cinza/neutro (baixa saturação).

    Args:
        img_hsv: Imagem no espaço HSV.
        n_ranges: Número de faixas de cor.

    Returns:
        Vetor de proporções (10 dimensões).
    """
    h = img_hsv[:, :, 0].ravel()  # Hue: 0-179 no OpenCV
    s = img_hsv[:, :, 1].ravel()  # Saturation: 0-255
    total = len(h)

    # Faixas de matiz (Hue ranges no OpenCV: 0-179)
    hue_ranges = [
        (0, 10),    # Vermelho
        (10, 25),   # Laranja
        (25, 35),   # Amarelo
        (35, 50),   # Verde-lima
        (50, 75),   # Verde
        (75, 95),   # Ciano
        (95, 125),  # Azul
        (125, 145), # Violeta
        (145, 170), # Magenta
    ]

    proportions = []
    for low, high in hue_ranges:
        mask = (h >= low) & (h < high) & (s > 40)  # Ignora neutros
        proportions.append(np.sum(mask) / total)

    # Última faixa: pixels neutros (baixa saturação)
    neutral_mask = s <= 40
    proportions.append(np.sum(neutral_mask) / total)

    return np.array(proportions)


def extract_features(filepath):
    """
    Extrai todas as features de uma imagem.

    Args:
        filepath: Caminho absoluto para a imagem.

    Returns:
        Vetor numpy com todas as features concatenadas, ou None se falhar.
    """
    img_bgr, img_hsv = load_image(filepath)
    if img_bgr is None:
        return None

    features = []

    # 1. Histograma de cores HSV (512 dim)
    color_hist = extract_color_histogram(img_hsv)
    features.append(color_hist)

    # 2. Estatísticas de cor (18 dim)
    color_stats = extract_color_statistics(img_bgr, img_hsv)
    features.append(color_stats)

    # 3. Textura LBP (26 dim)
    lbp = extract_lbp_features(img_bgr)
    features.append(lbp)

    # 4. Gradientes (36 dim)
    gradients = extract_gradient_features(img_bgr)
    features.append(gradients)

    # 5. Cores dominantes (10 dim)
    dominant = extract_dominant_colors(img_hsv)
    features.append(dominant)

    return np.concatenate(features)


def load_training_data(training_dir):
    """
    Carrega todas as imagens de treinamento e extrai features usando cache de metadados.

    Args:
        training_dir: Diretório raiz com subpastas por categoria.
                      Ex: Z:\\TREINAMENTO\\COR com subpastas MELHOR_APS e MELHOR_TEX.

    Returns:
        Tupla (X, y, filenames, categories) onde:
            X: Array numpy de features (n_samples, n_features)
            y: Array numpy de labels (inteiros)
            filenames: Lista de nomes dos arquivos
            categories: Dicionário {índice: nome_categoria}
    """
    X = []
    y = []
    filenames = []
    categories = {}

    # Caminho do cache de features
    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modelo")
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, "features_cache.pkl")

    # Carrega cache existente
    cache = {}
    if os.path.exists(cache_path):
        try:
            cache = joblib.load(cache_path)
            logger.info(f"Cache de features carregado: {cache_path} ({len(cache)} imagens cacheadas)")
        except Exception as e:
            logger.warning(f"Não foi possível carregar o cache de features: {e}. Criando novo cache.")

    cache_dirty = False
    valid_paths = set()

    # Ordena as subpastas para garantir índices consistentes
    subdirs = sorted([d for d in os.listdir(training_dir)
                      if os.path.isdir(os.path.join(training_dir, d))])

    for idx, subdir in enumerate(subdirs):
        categories[idx] = subdir
        subdir_path = os.path.join(training_dir, subdir)
        files = os.listdir(subdir_path)

        logger.info(f"Processando categoria '{subdir}' ({len(files)} arquivos)...")

        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                logger.warning(f"  Ignorando {fname} (extensão não suportada)")
                continue

            filepath = os.path.join(subdir_path, fname)
            valid_paths.add(filepath)

            # Obter metadados para validação do cache
            try:
                mtime = os.path.getmtime(filepath)
                size = os.path.getsize(filepath)
            except Exception as e:
                logger.warning(f"  Não foi possível ler metadados de {fname}: {e}")
                mtime = 0
                size = 0

            features = None
            # Verifica se podemos usar a versão em cache
            if filepath in cache:
                cached = cache[filepath]
                if cached.get('mtime') == mtime and cached.get('size') == size:
                    features = cached.get('features')

            if features is None:
                logger.info(f"  [EXTRACAO] Extraindo features de: {fname}")
                features = extract_features(filepath)
                if features is not None:
                    cache[filepath] = {
                        'mtime': mtime,
                        'size': size,
                        'features': features
                    }
                    cache_dirty = True
                else:
                    logger.warning(f"  FALHA ao processar: {fname}")
            else:
                # Opcional: log bem discreto do cache
                logger.info(f"  [CACHE] Usando features de: {fname}")

            if features is not None:
                X.append(features)
                y.append(idx)
                filenames.append(fname)

    # Limpar itens do cache que foram apagados do disco
    keys_to_remove = [k for k in cache if k not in valid_paths]
    if keys_to_remove:
        for k in keys_to_remove:
            del cache[k]
        cache_dirty = True
        logger.info(f"Removidos {len(keys_to_remove)} itens órfãos do cache.")

    # Salva o cache de volta se houve alteração
    if cache_dirty:
        try:
            joblib.dump(cache, cache_path)
            logger.info(f"Cache de features salvo em: {cache_path}")
        except Exception as e:
            logger.error(f"Não foi possível salvar o cache de features: {e}")

    if len(X) == 0:
        raise ValueError("Nenhuma imagem foi processada com sucesso!")

    return np.array(X), np.array(y), filenames, categories


def train_knn(X, y):
    """
    Treina o classificador KNN com busca automática dos melhores hiperparâmetros.

    Usa Leave-One-Out Cross-Validation (ideal para datasets pequenos).

    Args:
        X: Array de features (n_samples, n_features).
        y: Array de labels.

    Returns:
        Tupla (pipeline, best_params, cv_score) onde:
            pipeline: Pipeline treinada (StandardScaler + KNN)
            best_params: Melhores hiperparâmetros encontrados
            cv_score: Acurácia média da cross-validation
    """
    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('pca', PCA()),
        ('knn', KNeighborsClassifier())
    ])

    # Grid de hiperparâmetros
    param_grid = {
        'pca__n_components': [2, 4, 6, 8, 10, 12, 15, None],
        'knn__n_neighbors': list(range(1, min(8, len(y)))),
        'knn__weights': ['uniform', 'distance'],
        'knn__metric': ['euclidean', 'manhattan', 'minkowski'],
    }

    # Leave-One-Out CV
    loo = LeaveOneOut()

    grid_search = GridSearchCV(
        pipeline,
        param_grid,
        cv=loo,
        scoring='accuracy',
        n_jobs=-1,
        verbose=0
    )

    logger.info("Iniciando GridSearchCV com Leave-One-Out...")
    grid_search.fit(X, y)

    best_pipeline = grid_search.best_estimator_
    best_params = grid_search.best_params_
    best_score = grid_search.best_score_

    logger.info(f"Melhores parâmetros: {best_params}")
    logger.info(f"Acurácia LOO-CV: {best_score:.2%}")

    return best_pipeline, best_params, best_score


def save_model(pipeline, categories, model_dir):
    """
    Salva o modelo treinado e metadados.

    Args:
        pipeline: Pipeline treinada.
        categories: Dicionário {índice: nome_categoria}.
        model_dir: Diretório para salvar o modelo.
    """
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, 'knn_model.pkl')

    model_data = {
        'pipeline': pipeline,
        'categories': categories,
    }

    joblib.dump(model_data, model_path)
    logger.info(f"Modelo salvo em: {model_path}")


def load_model(model_path):
    """
    Carrega o modelo treinado.

    Args:
        model_path: Caminho para o arquivo .pkl.

    Returns:
        Tupla (pipeline, categories).
    """
    model_data = joblib.load(model_path)
    return model_data['pipeline'], model_data['categories']


def get_image_metadata(filepath):
    """
    Extrai metadados da imagem: dimensoes em px, DPI, dimensoes em cm.

    Args:
        filepath: Caminho para a imagem.

    Returns:
        Dicionario com metadados.
    """
    try:
        img = Image.open(filepath)
        width_px, height_px = img.size

        # Extrair DPI (pode estar no metadata do arquivo)
        dpi_x, dpi_y = 72, 72  # padrao
        if hasattr(img, 'info') and 'dpi' in img.info:
            dpi_info = img.info['dpi']
            if isinstance(dpi_info, tuple) and len(dpi_info) >= 2:
                dpi_x = float(dpi_info[0])
                dpi_y = float(dpi_info[1])
            elif isinstance(dpi_info, (int, float)):
                dpi_x = dpi_y = float(dpi_info)

        # TIF pode ter resolutions diferentes
        if hasattr(img, 'tag_v2'):
            try:
                # Tag 282 = XResolution, 283 = YResolution
                if 282 in img.tag_v2:
                    res = img.tag_v2[282]
                    if isinstance(res, tuple):
                        dpi_x = float(res[0]) / float(res[1]) if len(res) == 2 else float(res[0])
                    else:
                        dpi_x = float(res)
                if 283 in img.tag_v2:
                    res = img.tag_v2[283]
                    if isinstance(res, tuple):
                        dpi_y = float(res[0]) / float(res[1]) if len(res) == 2 else float(res[0])
                    else:
                        dpi_y = float(res)
            except Exception:
                pass

        # Garantir DPI valido
        if dpi_x <= 0 or dpi_x > 10000:
            dpi_x = 72
        if dpi_y <= 0 or dpi_y > 10000:
            dpi_y = 72

        # Calcular dimensoes em cm
        width_cm = (width_px / dpi_x) * 2.54
        height_cm = (height_px / dpi_y) * 2.54

        return {
            'largura_px': width_px,
            'altura_px': height_px,
            'dpi_x': round(dpi_x),
            'dpi_y': round(dpi_y),
            'dpi': round(dpi_x) if dpi_x == dpi_y else f"{round(dpi_x)}x{round(dpi_y)}",
            'largura_cm': round(width_cm, 1),
            'altura_cm': round(height_cm, 1),
            'modo_cor': img.mode,
        }
    except Exception as e:
        logger.error(f"Erro ao extrair metadados de {filepath}: {e}")
        return None


def analyze_features(filepath):
    """
    Analisa as features da imagem e retorna uma descricao legivel.

    Args:
        filepath: Caminho para a imagem.

    Returns:
        Dicionario com analise detalhada das features.
    """
    img_bgr, img_hsv = load_image(filepath)
    if img_bgr is None:
        return None

    analysis = {}

    # --- Cores Dominantes ---
    color_names = [
        'Vermelho', 'Laranja', 'Amarelo', 'Verde-Lima', 'Verde',
        'Ciano', 'Azul', 'Violeta', 'Magenta', 'Neutro/Cinza'
    ]
    dominant = extract_dominant_colors(img_hsv)

    cores_list = []
    for i, (name, pct) in enumerate(zip(color_names, dominant)):
        if pct > 0.01:  # mais de 1%
            cores_list.append({
                'cor': name,
                'percentual': round(float(pct * 100), 1),
            })
    cores_list.sort(key=lambda x: x['percentual'], reverse=True)
    analysis['cores_dominantes'] = cores_list

    # --- Estatisticas de Cor ---
    color_stats = extract_color_statistics(img_bgr, img_hsv)
    # Medias por canal BGR
    analysis['media_azul'] = round(float(color_stats[0]), 1)
    analysis['media_verde'] = round(float(color_stats[3]), 1)
    analysis['media_vermelho'] = round(float(color_stats[6]), 1)
    # Saturacao media (HSV canal S)
    analysis['saturacao_media'] = round(float(color_stats[12]), 1)
    # Brilho medio (HSV canal V)
    analysis['brilho_medio'] = round(float(color_stats[15]), 1)

    # --- Complexidade de Textura ---
    lbp = extract_lbp_features(img_bgr)
    # Entropia do LBP como medida de complexidade
    lbp_nonzero = lbp[lbp > 0]
    if len(lbp_nonzero) > 0:
        entropy = -np.sum(lbp_nonzero * np.log2(lbp_nonzero))
    else:
        entropy = 0
    analysis['complexidade_textura'] = round(float(entropy), 2)
    # Classificar textura
    if entropy < 2.5:
        analysis['tipo_textura'] = 'Simples (cor lisa ou gradiente suave)'
    elif entropy < 3.5:
        analysis['tipo_textura'] = 'Moderada (padroes regulares)'
    else:
        analysis['tipo_textura'] = 'Complexa (muitos detalhes e texturas)'

    # --- Intensidade de Gradiente (nitidez/detalhes) ---
    gradients = extract_gradient_features(img_bgr)
    gradient_intensity = float(np.max(gradients))
    analysis['intensidade_gradiente'] = round(gradient_intensity, 4)
    if gradient_intensity < 0.01:
        analysis['nivel_detalhes'] = 'Baixo (imagem suave/desfocada)'
    elif gradient_intensity < 0.03:
        analysis['nivel_detalhes'] = 'Medio (detalhes moderados)'
    else:
        analysis['nivel_detalhes'] = 'Alto (muitas bordas e contrastes)'

    # --- Variancia de cores (uniformidade) ---
    std_b = float(color_stats[1])
    std_g = float(color_stats[4])
    std_r = float(color_stats[7])
    avg_std = (std_b + std_g + std_r) / 3
    analysis['variancia_cor'] = round(avg_std, 1)
    if avg_std < 30:
        analysis['uniformidade_cor'] = 'Alta (cores muito uniformes)'
    elif avg_std < 60:
        analysis['uniformidade_cor'] = 'Media (variacao moderada de cores)'
    else:
        analysis['uniformidade_cor'] = 'Baixa (grande variacao de cores)'

    return analysis


def classify_image(filepath, pipeline, categories):
    """
    Classifica uma unica imagem com analise detalhada.

    Args:
        filepath: Caminho para a imagem.
        pipeline: Pipeline treinada (scaler + KNN).
        categories: Dicionario de categorias.

    Returns:
        Dicionario com resultado completo incluindo analise e explicacao.
        Ou None se a imagem nao puder ser processada.
    """
    features = extract_features(filepath)
    if features is None:
        return None

    features_reshaped = features.reshape(1, -1)

    # Predicao
    prediction = pipeline.predict(features_reshaped)[0]
    probabilities = pipeline.predict_proba(features_reshaped)[0]

    # Obter vizinhos mais proximos para explicacao
    knn = pipeline.named_steps['knn']
    scaler = pipeline.named_steps['scaler']
    features_scaled = scaler.transform(features_reshaped)
    
    # Se PCA estiver no pipeline, aplica a transformacao nele
    if 'pca' in pipeline.named_steps:
        pca = pipeline.named_steps['pca']
        features_transformed = pca.transform(features_scaled)
    else:
        features_transformed = features_scaled
        
    distances, indices = knn.kneighbors(features_transformed)

    # Analise detalhada das features
    feature_analysis = analyze_features(filepath)

    # Metadados da imagem
    metadata = get_image_metadata(filepath)

    # Construir explicacao
    explicacao = build_explanation(
        prediction, categories, probabilities,
        feature_analysis, distances[0], indices[0],
        knn.classes_, pipeline
    )

    result = {
        'categoria': categories[prediction],
        'confianca': float(np.max(probabilities)),
        'probabilidades': {
            categories[i]: float(prob)
            for i, prob in enumerate(probabilities)
        },
        'analise': feature_analysis,
        'metadata': metadata,
        'explicacao': explicacao,
    }

    return result


def build_explanation(prediction, categories, probabilities,
                      analysis, distances, indices, classes, pipeline):
    """
    Constroi uma explicacao em texto de por que a maquina foi escolhida.

    Returns:
        Dicionario com:
            'resumo': texto curto
            'fatores': lista de fatores que influenciaram
            'detalhes': texto detalhado
    """
    chosen = categories[prediction]
    confidence = float(np.max(probabilities))

    fatores = []

    if analysis:
        # Analisar saturacao
        sat = analysis.get('saturacao_media', 0)
        if sat > 140:
            fatores.append({
                'fator': 'Saturacao alta',
                'valor': f"{sat:.0f}/255",
                'descricao': 'Cores muito vivas e saturadas'
            })
        elif sat > 80:
            fatores.append({
                'fator': 'Saturacao media',
                'valor': f"{sat:.0f}/255",
                'descricao': 'Cores com saturacao moderada'
            })
        else:
            fatores.append({
                'fator': 'Saturacao baixa',
                'valor': f"{sat:.0f}/255",
                'descricao': 'Cores pouco saturadas, tendencia a neutro'
            })

        # Analisar brilho
        brilho = analysis.get('brilho_medio', 0)
        if brilho > 180:
            fatores.append({
                'fator': 'Imagem clara',
                'valor': f"{brilho:.0f}/255",
                'descricao': 'Predominancia de tons claros'
            })
        elif brilho > 90:
            fatores.append({
                'fator': 'Brilho medio',
                'valor': f"{brilho:.0f}/255",
                'descricao': 'Equilibrio entre claros e escuros'
            })
        else:
            fatores.append({
                'fator': 'Imagem escura',
                'valor': f"{brilho:.0f}/255",
                'descricao': 'Predominancia de tons escuros'
            })

        # Textura
        fatores.append({
            'fator': 'Textura',
            'valor': f"Entropia {analysis.get('complexidade_textura', 0):.1f}",
            'descricao': analysis.get('tipo_textura', '')
        })

        # Detalhes/Gradiente
        fatores.append({
            'fator': 'Nivel de detalhes',
            'valor': f"{analysis.get('intensidade_gradiente', 0):.4f}",
            'descricao': analysis.get('nivel_detalhes', '')
        })

        # Uniformidade
        fatores.append({
            'fator': 'Uniformidade de cor',
            'valor': f"Variancia {analysis.get('variancia_cor', 0):.0f}",
            'descricao': analysis.get('uniformidade_cor', '')
        })

        # Cores dominantes (top 3)
        cores = analysis.get('cores_dominantes', [])[:3]
        if cores:
            cores_desc = ', '.join([f"{c['cor']} ({c['percentual']:.0f}%)" for c in cores])
            fatores.append({
                'fator': 'Cores predominantes',
                'valor': cores_desc,
                'descricao': 'Cores com maior presenca na imagem'
            })

    # Distancia media dos vizinhos
    avg_dist = float(np.mean(distances))
    fatores.append({
        'fator': 'Similaridade KNN',
        'valor': f"Distancia media: {avg_dist:.2f}",
        'descricao': f'Baseado nos {len(distances)} vizinhos mais proximos no treinamento'
    })

    # Resumo
    if confidence >= 0.8:
        certeza = "alta confianca"
    elif confidence >= 0.6:
        certeza = "confianca moderada"
    else:
        certeza = "baixa confianca"

    resumo = (
        f"A imagem foi classificada como {chosen} com {certeza} "
        f"({confidence:.0%}). A analise das caracteristicas de cor, textura "
        f"e gradiente indica que esta imagem se encaixa melhor no perfil "
        f"de impressao da maquina {chosen.replace('MELHOR_', '')}."
    )

    return {
        'resumo': resumo,
        'fatores': fatores,
    }

