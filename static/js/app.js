document.addEventListener('DOMContentLoaded', () => {
    if (window.lucide) window.lucide.createIcons();
    const toggle = document.getElementById('menu-toggler');
    const sidebar = document.getElementById('sidebar');
    const closeMenu = () => {
        sidebar.classList.remove('aberto');
        toggle.setAttribute('aria-expanded', 'false');
    };
    if (toggle && sidebar) {
        toggle.addEventListener('click', () => {
            const opened = sidebar.classList.toggle('aberto');
            toggle.setAttribute('aria-expanded', String(opened));
        });
        document.addEventListener('click', event => {
            if (!sidebar.contains(event.target) && !toggle.contains(event.target)) closeMenu();
        });
        document.addEventListener('keydown', event => {
            if (event.key === 'Escape') { closeMenu(); toggle.focus(); }
        });
    }
    const date = document.getElementById('data-atual');
    if (date) date.textContent = new Date().toLocaleDateString('pt-BR');
    const count = document.getElementById('contador-acervo');
    if (count) {
        fetch('/api/exemplares/', {headers: {'Accept': 'application/json'}})
            .then(response => {
                if (!response.ok) throw new Error('Falha ao consultar acervo');
                return response.json();
            })
            .then(data => { count.textContent = data.count; })
            .catch(() => { count.textContent = '—'; count.title = 'Contagem indisponível'; });
    }
    const barcode = document.querySelector('[data-barcode]');
    if (barcode) {
        barcode.focus();
        barcode.select();
        barcode.addEventListener('focus', () => barcode.select());
    }
    const barcodeForm = document.querySelector('[data-barcode-form]');
    const results = document.getElementById('barcode-results');
    const status = document.getElementById('barcode-status');
    if (!barcode || !barcodeForm || !results || !status || !window.fetch || !window.AbortController) return;

    const labels = {
        disponivel: 'Disponível', reservado: 'Reservado', vendido: 'Vendido', cancelado: 'Cancelado',
        novo: 'Novo', excelente: 'Excelente', bom: 'Bom', regular: 'Regular', ruim: 'Ruim',
    };
    const money = new Intl.NumberFormat('pt-BR', {style: 'currency', currency: 'BRL'});
    const element = (tag, text) => {
        const node = document.createElement(tag);
        if (text !== undefined) node.textContent = text;
        return node;
    };
    const link = (text, path, params = {}) => {
        const node = element('a', text);
        const url = new URL(path, window.location.href);
        Object.entries(params).forEach(([key, value]) => url.searchParams.set(key, value));
        node.href = url.href;
        return node;
    };
    const detailLink = item => link(item.codigo_interno,
        barcodeForm.dataset.detailUrl.replace('/0/', `/${encodeURIComponent(item.id)}/`));
    const resultCard = () => {
        const card = element('section');
        card.className = 'card';
        return card;
    };
    const unknown = code => {
        const card = resultCard();
        card.append(element('h2', 'Código desconhecido'), element('p', code));
        const actions = element('ul');
        for (const action of [link('Pesquisar CD por EAN', barcodeForm.dataset.metadataUrl, {ean: code, fonte: 'musicbrainz'}),
            link('Pesquisar filme por título', barcodeForm.dataset.metadataUrl, {fonte: 'movies'}),
            link('Cadastrar manualmente', barcodeForm.dataset.createUrl)]) {
            const row = element('li');
            row.append(action);
            actions.append(row);
        }
        card.append(actions);
        results.replaceChildren(card);
    };
    const renderItem = data => {
        const card = resultCard();
        card.append(element('h2', `Exemplar ${data.codigo_interno}`),
            element('p', `${data.produto_detalhe.titulo} (${data.produto_detalhe.tipo}) · ${labels[data.status] || data.status}`));
        const detail = detailLink(data);
        detail.textContent = 'Abrir exemplar';
        card.append(detail);
        results.replaceChildren(card);
        status.textContent = `Exemplar ${data.codigo_interno} encontrado.`;
    };
    const renderPagination = (data, code, mode, page) => {
        const navigation = element('nav');
        navigation.setAttribute('aria-label', 'Paginação dos exemplares');
        for (const [available, text, target] of [[data.previous, 'Anterior', page - 1], [data.next, 'Próxima', page + 1]]) {
            if (!available) continue;
            const button = element('button', text);
            button.type = 'button';
            button.className = 'btn btn-secundaria';
            button.addEventListener('click', () => lookup(code, mode, target, true));
            navigation.append(button);
        }
        return navigation;
    };
    const renderProduct = (data, code, mode, page) => {
        const card = resultCard();
        card.append(element('h2', `${data.produto.titulo} (${data.produto.tipo})`),
            element('p', `EAN/UPC: ${data.produto.ean}`),
            link('Cadastrar exemplar deste produto', barcodeForm.dataset.createUrl, {produto: data.produto.id}));
        const list = element('ul');
        data.results.forEach(item => {
            const row = element('li');
            row.append(detailLink(item), document.createTextNode(
                ` · ${labels[item.estado_conservacao] || item.estado_conservacao} · ${labels[item.status] || item.status} · ${item.preco == null ? 'Preço não informado' : money.format(item.preco)}`));
            list.append(row);
        });
        card.append(list);
        if (data.count === 0) card.append(element('p', 'Nenhum exemplar cadastrado. Você pode cadastrar uma nova unidade.'));
        card.append(element('p', `Página ${page} · ${data.count} exemplares`), renderPagination(data, code, mode, page));
        results.replaceChildren(card);
        status.textContent = `Produto encontrado para ${code}. ${data.count} exemplares. Página ${page}.`;
    };
    const errorMessage = error => {
        if (error.name === 'AbortError') return 'A consulta demorou demais. Tente novamente ou consulte em página completa.';
        if (error instanceof TypeError || error instanceof SyntaxError) {
            return 'Falha de conexão ou resposta inválida da API. Tente novamente ou consulte em página completa.';
        }
        return error.message;
    };

    // O texto pode coincidir com uma leitura anterior. Registrar a interação,
    // inclusive navegação para outro controle e mudanças de seleção sem digitação.
    let interactionVersion = 0;
    const recordInteraction = () => { interactionVersion += 1; };
    barcode.addEventListener('beforeinput', recordInteraction);
    barcode.addEventListener('input', recordInteraction);
    for (const event of ['focusin', 'pointerdown', 'keydown']) {
        document.addEventListener(event, recordInteraction, true);
    }
    const finishFocus = (version, pagination) => {
        if (!pagination && version === interactionVersion && document.activeElement === barcode) {
            barcode.select();
        }
    };
    let activeRequest;
    const lookup = async (code, mode, page = 1, pagination = false) => {
        if (activeRequest) activeRequest.abort();
        const controller = new AbortController();
        activeRequest = controller;
        const timeout = window.setTimeout(() => controller.abort(), 15000);
        // Foco estável antes de remover o botão; Tab segue para os novos resultados.
        if (pagination) {
            results.setAttribute('tabindex', '-1');
            results.focus();
        }
        const interactionAtStart = interactionVersion;
        results.replaceChildren();
        results.setAttribute('aria-busy', 'true');
        status.textContent = `Consultando ${code}…`;
        try {
            const url = new URL(barcodeForm.dataset.apiUrl.replace('CODIGO', encodeURIComponent(code)), window.location.href);
            url.searchParams.set('modo', mode);
            url.searchParams.set('page', page);
            const response = await fetch(url, {
                headers: {Accept: 'application/json'}, credentials: 'same-origin', signal: controller.signal,
            });
            if (response.status === 401 || response.status === 403) {
                throw new Error('Consulta não autorizada. Verifique sua sessão e suas permissões usando a consulta em página completa.');
            }
            if (response.status !== 404 && !response.ok) throw new Error('A API está indisponível. Tente novamente ou consulte em página completa.');
            const data = await response.json();
            if (activeRequest !== controller) return;
            if (response.status === 404 && data.erro?.codigo === 'nao_encontrado') {
                unknown(code);
                status.textContent = `Código ${code} não encontrado.`;
                return;
            }
            if (!response.ok) throw new Error('Não foi possível carregar o resultado. Faça uma nova consulta.');
            if (data.tipo_codigo === 'ean' && data.produto && Array.isArray(data.results)) {
                renderProduct(data, code, mode, page);
            } else if (data.id != null && typeof data.codigo_interno === 'string' && data.produto_detalhe) {
                renderItem(data);
            } else {
                throw new Error('A API retornou um resultado inesperado. Consulte em página completa.');
            }
        } catch (error) {
            if (activeRequest !== controller) return;
            status.textContent = errorMessage(error);
        } finally {
            window.clearTimeout(timeout);
            if (activeRequest === controller) {
                results.setAttribute('aria-busy', 'false');
                activeRequest = null;
                finishFocus(interactionAtStart, pagination);
            }
        }
    };
    barcodeForm.addEventListener('submit', event => {
        if (event.submitter?.name === 'consulta_html') return;
        const code = barcode.value.trim();
        // A rota existente não aceita ponto ou barra; preservar o GET HTML nesses casos.
        if (/[/.]/.test(code)) return;
        event.preventDefault();
        if (!code) {
            if (activeRequest) activeRequest.abort();
            activeRequest = null;
            results.replaceChildren();
            results.setAttribute('aria-busy', 'false');
            status.textContent = 'Informe um código para consultar.';
            barcode.focus();
            return;
        }
        // Preparar a próxima leitura mesmo enquanto a API ainda está respondendo.
        barcode.focus();
        barcode.select();
        lookup(code, barcodeForm.elements.modo.value);
    });
});
