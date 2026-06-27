/**
 * app.js - Frontend do Classificador KNN v3
 * Com preview, dimensoes (px/cm/DPI) e explicacao detalhada
 */

document.addEventListener('DOMContentLoaded', () => {
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('fileInput');
    const uploadSection = document.getElementById('uploadSection');
    const loadingSection = document.getElementById('loadingSection');
    const loadingFilename = document.getElementById('loadingFilename');
    const resultSection = document.getElementById('resultSection');
    const resultCard = document.getElementById('resultCard');
    const resultMachine = document.getElementById('resultMachine');
    const resultConfidence = document.getElementById('resultConfidence');
    const resultTime = document.getElementById('resultTime');
    const probBars = document.getElementById('probBars');
    const resultPreviewImage = document.getElementById('resultPreviewImage');
    const previewInfo = document.getElementById('previewInfo');
    const btnNew = document.getElementById('btnNew');
    const errorSection = document.getElementById('errorSection');
    const errorMessage = document.getElementById('errorMessage');
    const btnRetry = document.getElementById('btnRetry');
    const statusBadge = document.getElementById('statusBadge');
    const statusText = document.getElementById('statusText');
    const bgParticles = document.getElementById('bgParticles');
    const historySection = document.getElementById('historySection');
    const historyList = document.getElementById('historyList');
    const explanationSummary = document.getElementById('explanationSummary');
    const factorsGrid = document.getElementById('factorsGrid');
    const colorBars = document.getElementById('colorBars');

    let selectedFile = null;
    let history = [];

    // -- Particulas --
    const colors = ['#818cf8', '#c084fc', '#22d3ee', '#34d399', '#f472b6'];
    for (let i = 0; i < 20; i++) {
        const p = document.createElement('div');
        p.classList.add('particle');
        const size = Math.random() * 4 + 2;
        p.style.cssText = `width:${size}px;height:${size}px;background:${colors[Math.floor(Math.random()*colors.length)]};left:${Math.random()*100}%;top:${Math.random()*100}%;animation-delay:${Math.random()*8}s;animation-duration:${6+Math.random()*6}s;`;
        bgParticles.appendChild(p);
    }

    // -- Status --
    (async () => {
        try {
            const r = await fetch('/api/status');
            const d = await r.json();
            statusBadge.className = d.modelo_carregado ? 'status-badge online' : 'status-badge offline';
            statusText.textContent = d.modelo_carregado ? 'Modelo ativo' : 'Sem modelo';
        } catch { statusBadge.className = 'status-badge offline'; statusText.textContent = 'Offline'; }
    })();

    // -- Drag & Drop --
    dropzone.addEventListener('click', () => fileInput.click());
    dropzone.addEventListener('dragenter', e => { e.preventDefault(); dropzone.classList.add('drag-over'); });
    dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('drag-over'); });
    dropzone.addEventListener('dragleave', e => { e.preventDefault(); dropzone.classList.remove('drag-over'); });
    dropzone.addEventListener('drop', e => { e.preventDefault(); dropzone.classList.remove('drag-over'); if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]); });
    fileInput.addEventListener('change', e => { if (e.target.files.length) handleFile(e.target.files[0]); });

    function handleFile(file) {
        selectedFile = file;
        classifyImage(file);
    }

    function formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
        if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + ' MB';
        return (bytes / 1073741824).toFixed(2) + ' GB';
    }

    // Mapa de cores para barras visuais
    const colorMap = {
        'Vermelho': '#ef4444',
        'Laranja': '#f97316',
        'Amarelo': '#eab308',
        'Verde-Lima': '#84cc16',
        'Verde': '#22c55e',
        'Ciano': '#06b6d4',
        'Azul': '#3b82f6',
        'Violeta': '#8b5cf6',
        'Magenta': '#ec4899',
        'Neutro/Cinza': '#94a3b8'
    };

    // -- Classificar --
    async function classifyImage(file) {
        showSection('loading');
        loadingFilename.textContent = file.name;

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/api/classify', { method: 'POST', body: formData });
            const data = await response.json();
            if (!response.ok) { showError(data.error || 'Erro desconhecido.'); return; }
            showResult(data);
        } catch (err) {
            showError('Nao foi possivel conectar ao servidor.');
        }
    }

    // -- Renderizar resultado --
    function showResult(data) {
        const machineType = data.categoria.toLowerCase().includes('aps') ? 'aps' : 'tex';
        resultCard.className = `result-card ${machineType}`;

        resultMachine.textContent = data.categoria;
        resultConfidence.textContent = `${(data.confianca * 100).toFixed(1)}%`;
        resultTime.textContent = data.tempo_processamento;

        // Preview
        if (data.preview && data.preview.preview_base64) {
            resultPreviewImage.src = data.preview.preview_base64;
            resultPreviewImage.style.display = 'block';
        } else {
            resultPreviewImage.style.display = 'none';
        }

        // Info do arquivo com dimensoes em px, cm e DPI
        renderPreviewInfo(data);

        // Probabilidades
        renderProbBars(data.probabilidades);

        // Explicacao
        renderExplanation(data);

        // Cores dominantes
        renderColorBars(data);

        // Historico
        addToHistory(data, machineType);

        showSection('result');
    }

    function renderPreviewInfo(data) {
        let rows = [];

        rows.push({ label: 'Arquivo', value: data.arquivo });

        if (data.metadata) {
            const m = data.metadata;
            rows.push({
                label: 'Dimensoes (px)',
                value: `${m.largura_px} x ${m.altura_px} px`
            });
            rows.push({
                label: 'Dimensoes (cm)',
                value: `${m.largura_cm} x ${m.altura_cm} cm`
            });
            rows.push({
                label: 'DPI',
                value: typeof m.dpi === 'number' ? `${m.dpi} dpi` : `${m.dpi} dpi`
            });
            rows.push({
                label: 'Modo de Cor',
                value: m.modo_cor
            });
        }

        if (data.tamanho_arquivo) {
            rows.push({ label: 'Tamanho', value: formatFileSize(data.tamanho_arquivo) });
        }

        previewInfo.innerHTML = rows.map(r => `
            <div class="preview-info-row">
                <span class="preview-info-label">${r.label}</span>
                <span class="preview-info-value">${r.value}</span>
            </div>
        `).join('');
    }

    function renderProbBars(probabilidades) {
        probBars.innerHTML = '';
        Object.entries(probabilidades).sort((a, b) => b[1] - a[1]).forEach(([name, prob]) => {
            const barType = name.toLowerCase().includes('aps') ? 'aps' : name.toLowerCase().includes('tex') ? 'tex' : 'generic';
            const item = document.createElement('div');
            item.className = 'prob-bar-item';
            item.innerHTML = `
                <div class="prob-bar-header">
                    <span class="prob-bar-name">${name}</span>
                    <span class="prob-bar-value">${(prob * 100).toFixed(1)}%</span>
                </div>
                <div class="prob-bar-track">
                    <div class="prob-bar-fill ${barType}" style="width: 0%"></div>
                </div>
            `;
            probBars.appendChild(item);
            requestAnimationFrame(() => requestAnimationFrame(() => {
                item.querySelector('.prob-bar-fill').style.width = `${prob * 100}%`;
            }));
        });
    }

    function renderExplanation(data) {
        // Resumo
        if (data.explicacao && data.explicacao.resumo) {
            explanationSummary.textContent = data.explicacao.resumo;
        }

        // Fatores
        factorsGrid.innerHTML = '';
        if (data.explicacao && data.explicacao.fatores) {
            data.explicacao.fatores.forEach(f => {
                const card = document.createElement('div');
                card.className = 'factor-card';
                card.innerHTML = `
                    <div class="factor-header">
                        <span class="factor-name">${f.fator}</span>
                        <span class="factor-value">${f.valor}</span>
                    </div>
                    <p class="factor-desc">${f.descricao}</p>
                `;
                factorsGrid.appendChild(card);
            });
        }
    }

    function renderColorBars(data) {
        colorBars.innerHTML = '';
        if (!data.analise || !data.analise.cores_dominantes) return;

        data.analise.cores_dominantes.forEach(c => {
            const barColor = colorMap[c.cor] || '#94a3b8';
            const item = document.createElement('div');
            item.className = 'color-bar-item';
            item.innerHTML = `
                <div class="color-bar-header">
                    <span class="color-swatch" style="background:${barColor}"></span>
                    <span class="color-name">${c.cor}</span>
                    <span class="color-pct">${c.percentual.toFixed(1)}%</span>
                </div>
                <div class="color-bar-track">
                    <div class="color-bar-fill" style="background:${barColor};width:0%"></div>
                </div>
            `;
            colorBars.appendChild(item);
            requestAnimationFrame(() => requestAnimationFrame(() => {
                item.querySelector('.color-bar-fill').style.width = `${Math.min(c.percentual, 100)}%`;
            }));
        });
    }

    // -- Historico --
    function addToHistory(data, machineType) {
        history.unshift({
            filename: data.arquivo,
            categoria: data.categoria,
            confianca: data.confianca,
            machineType,
            preview: data.preview ? data.preview.preview_base64 : null,
            dims: data.metadata ? `${data.metadata.largura_cm}x${data.metadata.altura_cm}cm` : '',
            timestamp: new Date()
        });
        if (history.length > 10) history.pop();
        renderHistory();
    }

    function renderHistory() {
        if (history.length <= 1) { historySection.style.display = 'none'; return; }
        historySection.style.display = 'block';
        historyList.innerHTML = '';
        history.slice(1).forEach(e => {
            const item = document.createElement('div');
            item.className = 'history-item';
            const thumb = e.preview ? `<img class="history-thumb" src="${e.preview}" alt="">` : `<div class="history-thumb"></div>`;
            item.innerHTML = `
                ${thumb}
                <div class="history-info">
                    <div class="history-filename">${e.filename}</div>
                    <div class="history-details">${e.dims} - ${e.timestamp.toLocaleTimeString('pt-BR')}</div>
                </div>
                <span class="history-badge ${e.machineType}">${e.categoria}</span>
                <span class="history-confidence">${(e.confianca * 100).toFixed(0)}%</span>
            `;
            historyList.appendChild(item);
        });
    }

    // -- Zoom --
    resultPreviewImage.addEventListener('click', () => {
        if (!resultPreviewImage.src || resultPreviewImage.style.display === 'none') return;
        const overlay = document.createElement('div');
        overlay.className = 'zoom-overlay';
        const img = document.createElement('img');
        img.src = resultPreviewImage.src;
        overlay.appendChild(img);
        overlay.addEventListener('click', () => { overlay.style.opacity = '0'; setTimeout(() => overlay.remove(), 200); });
        document.addEventListener('keydown', function esc(e) { if (e.key === 'Escape') { overlay.style.opacity = '0'; setTimeout(() => overlay.remove(), 200); document.removeEventListener('keydown', esc); } });
        document.body.appendChild(overlay);
    });

    // -- Controle de secoes --
    function showSection(s) {
        [uploadSection, loadingSection, resultSection, errorSection].forEach(el => el.style.display = 'none');
        ({ upload: uploadSection, loading: loadingSection, result: resultSection, error: errorSection })[s].style.display = 'block';
    }

    function showError(msg) { errorMessage.textContent = msg; showSection('error'); }
    function resetToUpload() { selectedFile = null; fileInput.value = ''; showSection('upload'); }

    btnNew.addEventListener('click', resetToUpload);
    btnRetry.addEventListener('click', () => { selectedFile ? classifyImage(selectedFile) : resetToUpload(); });
});
