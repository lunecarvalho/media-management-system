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

    const readingHeading = document.getElementById('barcode-heading');
    const steps = [1, 2, 3, 4].map(n => document.getElementById(`barcode-step-${n}`));
    const newScan = document.getElementById('barcode-new-scan');
    let visualState = barcodeForm.dataset.state || 'idle';
    const showStep = current => steps.forEach((node, index) => {
        if (!node) return;
        node.setAttribute('aria-current', index + 1 === current ? 'step' : 'false');
        node.setAttribute('data-state', index + 1 < current ? 'complete' : index + 1 === current ? 'active' : 'inactive');
        node.setAttribute('aria-label', `${index + 1}. ${['Ler código', 'Buscar info', 'Conferir dados', 'Cadastrar'][index]}${index + 1 < current ? ', concluída' : index + 1 === current ? ', etapa atual' : ''}`);
    });
    const showReadingState = state => {
        visualState = state;
        barcodeForm.setAttribute('data-state', state);
        barcodeForm.setAttribute('data-presentation', state === 'idle' ? 'entry' : 'collapsed');
        // O campo continua recebendo o scanner. Os outros controles recolhidos
        // saem da navegação; Tab para o campo o torna visível novamente.
        for (const control of barcodeForm.querySelectorAll?.('button, select') || []) control.tabIndex = state === 'idle' ? 0 : -1;
        status.className = state === 'idle' ? 'leitura-status' : 'leitura-somente-leitor';
        showStep(['identified', 'found'].includes(state) ? 4 : state === 'loading' ? 2 : ['choices', 'missing'].includes(state) ? 3 : 1);
        if (readingHeading) readingHeading.textContent = {
            idle: 'Aguardando leitura', loading: 'Buscando informações...', found: 'Item encontrado',
            identified: 'Item identificado com sucesso',
            choices: 'Selecione uma edição',
            missing: 'Código não encontrado', error: 'Não foi possível consultar', timeout: 'Tempo de consulta esgotado',
        }[state];
    };
    showReadingState(barcodeForm.dataset.state || 'idle');
    results.addEventListener('click', event => {
        if (event.target?.closest?.('[data-barcode-register]')) showStep(4);
    });

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
    const resetButton = () => {
        const button = element('button', 'Nova leitura');
        button.type = 'button';
        button.className = 'btn btn-secundaria leitura-reset';
        button.addEventListener('click', () => resetReading());
        return button;
    };
    const actionRow = (...actions) => {
        const row = element('div');
        row.className = 'leitura-result-acoes';
        row.append(...actions);
        return row;
    };
    const productPreview = (product, compact = false) => {
        const preview = element('div');
        preview.className = `leitura-produto${compact ? ' leitura-produto-acervo' : ''}`;
        const cover = element('span');
        cover.className = 'leitura-capa-placeholder';
        cover.setAttribute('role', 'img');
        cover.setAttribute('aria-label', 'Capa não disponível');
        const metadata = product.metadados && typeof product.metadados === 'object' ? product.metadados : {};
        const coverUrl = [product.capa_url, product.imagem_url, metadata.capa_url, metadata.imagem_url]
            .find(value => typeof value === 'string' && /^https?:\/\//i.test(value));
        if (compact && coverUrl) {
            const image = element('img');
            image.alt = `Capa de ${product.titulo}`;
            image.loading = 'lazy';
            image.addEventListener('load', () => {
                image.hidden = false;
                cover.classList.add('leitura-capa-com-imagem');
            });
            image.addEventListener('error', () => { image.remove?.(); });
            image.hidden = true;
            cover.append(image);
            image.src = coverUrl;
        }
        const info = element('div');
        info.className = 'leitura-produto-info';
        info.append(element('h3', product.titulo));
        if (product.artista_diretor) info.append(element('p', product.artista_diretor));
        const badges = element('div');
        badges.className = 'leitura-badges';
        const genres = Array.isArray(product.metadados?.generos) ? product.metadados.generos.filter(value => typeof value === 'string') : [];
        for (const value of [product.tipo, product.ano, product.categoria_nome, product.categoria?.nome, ...genres]) {
            if (value == null || value === '') continue;
            badges.append(element('span', value));
        }
        info.append(badges);
        if (product.ean) info.append(element('code', product.ean));
        preview.append(cover, info);
        return preview;
    };
    const loadingCard = code => {
        const card = resultCard();
        card.className = 'card leitura-loading';
        const spinner = element('span');
        spinner.className = 'leitura-spinner';
        spinner.setAttribute('aria-hidden', 'true');
        const dots = element('span', '•••');
        dots.className = 'leitura-loading-pontos';
        dots.setAttribute('aria-hidden', 'true');
        card.append(spinner, element('h2', 'Buscando informações...'), element('code', code), dots);
        results.replaceChildren(card);
    };
    const registrationLink = (text, params = {}, path = barcodeForm.dataset.createUrl) => {
        const url = new URL(path, window.location.href);
        const target = new URL(barcodeForm.dataset.createUrl, window.location.href);
        if (url.origin !== target.origin || url.pathname !== target.pathname) throw new Error('Destino de cadastro inválido.');
        const action = link(text, url.href, {...params, origem: 'barcode'});
        action.addEventListener('click', () => showStep(4));
        return action;
    };
    const productDetails = (product, category) => {
        const list = element('dl');
        list.className = 'leitura-dados';
        for (const [label, value] of [['Tipo', product.tipo], ['Título', product.titulo],
            ['Artista/Diretor', product.artista_diretor], ['EAN/UPC', product.ean],
            ['Ano', product.ano], ['Categoria', category || product.categoria_nome],
            ['Gravadora/Distribuidora', product.gravadora_distribuidora], ['Descrição', product.descricao]]) {
            if (value != null && value !== '') list.append(element('dt', label), element('dd', value));
        }
        return list;
    };
    const unknown = (code, mode, data, external = false) => {
        const card = resultCard();
        card.className = 'card leitura-nao-encontrado';
        const title = element('h2', 'Código não encontrado no sistema');
        title.className = 'leitura-erro-titulo';
        const codeCard = element('div');
        codeCard.className = 'leitura-codigo-consultado';
        const codeIcon = element('span');
        codeIcon.className = 'leitura-codigo-icone';
        codeIcon.setAttribute('aria-hidden', 'true');
        const codeInfo = element('div');
        codeInfo.append(element('strong', code), element('p', 'Nenhum produto cadastrado com este código'));
        codeCard.append(codeIcon, codeInfo);
        const notice = element('div');
        notice.className = 'leitura-nao-cadastrado';
        notice.append(element('strong', 'Produto não cadastrado'), element('p', 'Você pode cadastrar este item manualmente informando os dados do produto. O código de barras será preenchido automaticamente.'));
        card.append(title, codeCard, notice);
        if (data.metadados_disponiveis || external) {
            const search = element('button', external ? 'Tentar MusicBrainz novamente' : 'Buscar informações de CD no MusicBrainz');
            search.type = 'button';
            search.className = 'btn btn-primaria';
            search.addEventListener('click', () => lookup(code, mode, 1, true, true));
            const help = element('details');
            help.className = 'leitura-ajuda-contextual';
            help.append(element('summary', 'Buscar informações externas'), search);
            card.append(help);
        }
        const register = registrationLink('Cadastrar este item', {codigo: code, modo: mode}, data.cadastro_url);
        register.className = 'btn btn-primaria';
        card.append(actionRow(resetButton(), register));
        results.replaceChildren(card);
    };
    const renderItem = data => {
        const card = resultCard();
        card.className = 'card leitura-encontrado';
        const title = element('h2', 'Item identificado com sucesso');
        title.className = 'leitura-sucesso-titulo';
        const product = {...data.produto_detalhe, ean: data.produto_detalhe.ean || data.codigo_interno};
        card.append(title, productPreview(product, true));
        const notice = element('p', `Item localizado no acervo · Status: ${labels[data.status] || data.status}`);
        notice.className = 'leitura-status-acervo';
        card.append(notice);
        const detail = detailLink(data);
        detail.textContent = 'Ver no acervo';
        detail.className = 'btn btn-primaria';
        card.append(actionRow(resetButton(), detail));
        results.replaceChildren(card);
        status.textContent = `Exemplar ${data.codigo_interno} encontrado.`;
        showReadingState('found');
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
        card.className = 'card leitura-encontrado';
        const title = element('h2', 'Item identificado com sucesso');
        title.className = 'leitura-sucesso-titulo';
        card.append(title, productPreview(data.produto, true));
        const exemplar = data.results.find(item => item.status) || null;
        const statusText = exemplar ? (labels[exemplar.status] || exemplar.status) : 'Nenhum exemplar cadastrado';
        const notice = element('p', `Item localizado no acervo · Status: ${statusText}`);
        notice.className = 'leitura-status-acervo';
        card.append(notice);
        const copies = element('details');
        copies.className = 'leitura-exemplares';
        copies.append(element('summary', `${data.count} exemplar${data.count === 1 ? '' : 'es'}`));
        const list = element('ul');
        data.results.forEach(item => {
            const row = element('li');
            row.append(detailLink(item), document.createTextNode(
                ` · ${labels[item.estado_conservacao] || item.estado_conservacao} · ${labels[item.status] || item.status} · ${item.preco == null ? 'Preço não informado' : money.format(item.preco)}`));
            list.append(row);
        });
        if (!data.results.length) list.append(element('li', 'Nenhum exemplar cadastrado.'));
        copies.append(list, renderPagination(data, code, mode, page));
        card.append(copies);
        const destination = exemplar ? detailLink(exemplar) : link('Ver no acervo', barcodeForm.dataset.catalogUrl);
        destination.textContent = 'Ver no acervo';
        destination.className = 'btn btn-primaria';
        card.append(actionRow(resetButton(), destination));
        results.replaceChildren(card);
        status.textContent = `Produto encontrado para ${code}. ${data.count} exemplares. Página ${page}.`;
        showReadingState('found');
    };
    const renderExternal = data => {
        if (!Array.isArray(data.results) || !data.results.length || data.results.some(product =>
            !product || product.tipo !== 'CD' || typeof product.titulo !== 'string' || !product.titulo || typeof product.cadastro_url !== 'string')) {
            throw new Error('Resposta externa inválida.');
        }
        // Validar destinos antes de permitir qualquer seleção.
        data.results.forEach(product => registrationLink('Cadastrar item', {}, product.cadastro_url));
        const select = product => {
            const card = resultCard();
            card.className = 'card leitura-identificado';
            const title = element('h2', 'Item identificado com sucesso');
            title.className = 'leitura-sucesso-titulo';
            const notice = element('p', 'Este item ainda não está no acervo — cadastre abaixo para adicioná-lo.');
            notice.className = 'leitura-sucesso-aviso';
            const register = registrationLink('Cadastrar item', {}, product.cadastro_url);
            register.className = 'btn btn-primaria';
            card.append(title, productPreview(product), notice, actionRow(resetButton(), register));
            const details = element('details');
            details.className = 'leitura-ajuda-contextual';
            details.append(element('summary', 'Mais informações'), element('p', `Fonte: ${data.fonte}. Revise a categoria no cadastro.`));
            for (const value of [product.gravadora_distribuidora, product.descricao]) {
                if (value) details.append(element('p', value));
            }
            card.append(details);
            if (data.results.length > 1) {
                const back = element('button', 'Voltar às opções');
                back.type = 'button';
                back.className = 'btn btn-secundaria';
                back.addEventListener('click', () => { focusResults(); renderExternal(data); });
                card.append(back);
            }
            results.replaceChildren(card);
            status.textContent = 'Item identificado. Confira os dados antes de cadastrar.';
            showReadingState('identified');
        };
        if (data.results.length === 1) select(data.results[0]);
        else {
            const card = resultCard();
            card.append(element('h2', 'Mais de uma edição encontrada'), element('p', 'Selecione a edição correta para conferir os dados.'));
            for (const product of data.results) {
                const button = element('button', `Conferir ${product.titulo} — ${product.artista_diretor || 'Artista não informado'} — ${product.ano || 'Ano não informado'}`);
                button.type = 'button';
                button.className = 'btn btn-secundaria';
                button.addEventListener('click', () => { focusResults(); select(product); });
                card.append(button);
            }
            results.replaceChildren(card);
            card.append(actionRow(resetButton()));
            status.textContent = `${data.results.length} edições encontradas. Selecione uma para conferir.`;
            showReadingState('choices');
        }
    };
    const focusResults = () => {
        results.setAttribute('tabindex', '-1');
        results.focus();
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
    let activeKey;
    const resetReading = (clearCode = true, focus = true) => {
        if (activeRequest) activeRequest.abort();
        activeRequest = null;
        activeKey = null;
        results.replaceChildren();
        results.setAttribute('aria-busy', 'false');
        status.textContent = '';
        if (clearCode) barcode.value = '';
        showReadingState('idle');
        if (focus) barcode.focus();
    };
    barcode.addEventListener('beforeinput', () => {
        recordInteraction();
        if (visualState !== 'idle') resetReading(false, false);
    });
    let tabNavigation = false;
    document.addEventListener('keydown', event => {
        tabNavigation = event.key === 'Tab';
        if (event.key === 'Escape' && visualState === 'loading' && [barcode, results].includes(event.target)) resetReading(false);
    });
    document.addEventListener('focusin', event => {
        if (event.target === barcode && tabNavigation && visualState !== 'idle') resetReading(false, false);
    });
    if (newScan) {
        newScan.hidden = false;
        newScan.addEventListener('click', () => resetReading());
    }
    const paintLoading = signal => new Promise(resolve => {
        let frame;
        const done = () => {
            window.cancelAnimationFrame(frame);
            signal.removeEventListener('abort', done);
            resolve();
        };
        signal.addEventListener('abort', done, {once: true});
        frame = window.requestAnimationFrame(() => { frame = window.requestAnimationFrame(done); });
    });
    // keepResultFocus cobre paginação e ações explícitas dentro da conferência.
    const lookup = async (code, mode, page = 1, keepResultFocus = false, external = false) => {
        const key = JSON.stringify([code, mode, page, external]);
        if (activeRequest && !activeRequest.signal.aborted && activeKey === key) return;
        if (activeRequest) activeRequest.abort();
        const controller = new AbortController();
        activeRequest = controller;
        activeKey = key;
        const timeout = window.setTimeout(() => controller.abort(), 15000);
        // Foco estável antes de remover o botão; Tab segue para os novos resultados.
        if (keepResultFocus) {
            results.setAttribute('tabindex', '-1');
            results.focus();
        }
        const interactionAtStart = interactionVersion;
        results.replaceChildren();
        results.setAttribute('aria-busy', 'true');
        status.textContent = external ? `Buscando informações de CD no MusicBrainz para ${code}…` : `Consultando ${code}…`;
        showReadingState('loading');
        loadingCard(code);
        let providerError = false;
        try {
            if (window.requestAnimationFrame && !document.hidden) await paintLoading(controller.signal);
            if (activeRequest !== controller) return;
            if (controller.signal.aborted) throw new DOMException('Consulta cancelada.', 'AbortError');
            const url = new URL(barcodeForm.dataset.apiUrl.replace('CODIGO', encodeURIComponent(code)), window.location.href);
            url.searchParams.set('modo', mode);
            url.searchParams.set('page', page);
            if (external) url.searchParams.set('metadados', '1');
            const response = await fetch(url, {
                headers: {Accept: 'application/json'}, credentials: 'same-origin', signal: controller.signal,
            });
            if (response.status === 401 || response.status === 403) {
                throw new Error('Consulta não autorizada. Verifique sua sessão e suas permissões usando a consulta em página completa.');
            }
            if (![400, 404, 502].includes(response.status) && !response.ok) throw new Error('A API está indisponível. Tente novamente ou consulte em página completa.');
            const data = await response.json();
            if (activeRequest !== controller) return;
            if (controller.signal.aborted) throw new DOMException('Consulta cancelada.', 'AbortError');
            if (data.erro?.codigo === 'fonte_indisponivel') {
                unknown(code, mode, data, true);
                providerError = true;
                throw new Error(data.erro.detalhes);
            }
            if (data.erro?.codigo === 'invalido') throw new Error(data.erro.detalhes);
            if (response.status === 404 && data.erro?.codigo === 'nao_encontrado') {
                unknown(code, mode, data, external);
                status.textContent = `Código ${code} não encontrado.`;
                showReadingState('missing');
                return;
            }
            if (!response.ok) throw new Error('Não foi possível carregar o resultado. Faça uma nova consulta.');
            if (data.tipo_codigo === 'externo') {
                renderExternal(data);
            } else if (data.tipo_codigo === 'ean' && data.produto && Array.isArray(data.results)) {
                renderProduct(data, code, mode, page);
            } else if (data.id != null && typeof data.codigo_interno === 'string' && data.produto_detalhe) {
                renderItem(data);
            } else {
                throw new Error('A API retornou um resultado inesperado. Consulte em página completa.');
            }
        } catch (error) {
            if (activeRequest !== controller) return;
            if (!providerError) {
                const card = resultCard();
                card.append(element('h2', error.name === 'AbortError' ? 'Tempo de consulta esgotado' : 'Não foi possível consultar'), element('p', errorMessage(error)));
                const retry = element('button', external ? 'Tentar MusicBrainz novamente' : 'Tentar novamente');
                retry.type = 'button';
                retry.className = 'btn btn-primaria';
                retry.addEventListener('click', () => lookup(code, mode, page, true, external));
                card.append(actionRow(resetButton(), retry), link('Consultar em página completa', barcodeForm.action || window.location.href, {codigo: code, modo: mode, consulta_html: '1'}));
                if (external) card.append(registrationLink('Cadastrar manualmente', {codigo: code, modo: mode}));
                results.replaceChildren(card);
            }
            status.textContent = errorMessage(error);
            showReadingState(error.name === 'AbortError' ? 'timeout' : 'error');
        } finally {
            window.clearTimeout(timeout);
            if (activeRequest === controller) {
                results.setAttribute('aria-busy', 'false');
                activeRequest = null;
                finishFocus(interactionAtStart, keepResultFocus);
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
            showReadingState('idle');
            barcode.focus();
            return;
        }
        // Preparar a próxima leitura mesmo enquanto a API ainda está respondendo.
        barcode.focus();
        barcode.select();
        lookup(code, barcodeForm.elements.modo.value);
    });
});
