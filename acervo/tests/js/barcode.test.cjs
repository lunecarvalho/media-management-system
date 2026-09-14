// Run with: node --test acervo/tests/js/barcode.test.cjs
// Minimal DOM double: exercises the real app.js without browser dependencies.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {resolve} = require('node:path');
const vm = require('node:vm');
const source = readFileSync(resolve(__dirname, '../../../static/js/app.js'), 'utf8');

class Element {
    constructor(tag = 'div') {
        this.tag = tag;
        this.children = [];
        this.attributes = {};
        this.listeners = {};
        this.value = '';
        this.focusCalls = 0;
        this.selectCalls = 0;
        const classes = new Set();
        this.classList = {
            remove: name => classes.delete(name),
            toggle: name => { if (classes.has(name)) { classes.delete(name); return false; } classes.add(name); return true; },
            contains: name => classes.has(name),
        };
    }
    set textContent(value) { this.text = String(value); this.children = []; }
    get textContent() { return (this.text || '') + this.children.map(child => child.textContent).join(''); }
    set innerHTML(value) { throw new Error('Unsafe HTML insertion'); }
    append(...nodes) { this.children.push(...nodes); }
    replaceChildren(...nodes) { this.text = ''; this.children = nodes; }
    setAttribute(name, value) { this.attributes[name] = value; }
    contains(node) { return node === this || this.children.some(child => child.contains(node)); }
    addEventListener(name, callback) { this.listeners[name] = callback; }
    focus() {
        this.focusCalls += 1;
        this.focused = true;
        if (this.ownerDocument.activeElement !== this) {
            this.ownerDocument.activeElement = this;
            this.listeners.focus?.();
            this.ownerDocument.emit('focusin', {target: this});
        }
    }
    select() { this.selectCalls += 1; this.selected = true; }
}

function setup({legacy = false, animation = false} = {}) {
    const input = new Element('input');
    const form = new Element('form');
    form.dataset = {apiUrl: '/api/exemplares/codigo/CODIGO/', detailUrl: '/acervo/item/0/',
        createUrl: '/acervo/cadastrar/', metadataUrl: '/acervo/metadados/'};
    const mode = new Element('select');
    mode.value = 'auto';
    form.elements = {modo: mode};
    const results = new Element();
    const status = new Element();
    const heading = new Element('h2');
    heading.textContent = 'Aguardando leitura';
    const steps = [1, 2, 3, 4].map(() => new Element('li'));
    const newScan = new Element('button');
    newScan.hidden = true;
    const shell = legacy ? {'menu-toggler': new Element('button'), sidebar: new Element('aside'),
        'data-atual': new Element('span'), 'contador-acervo': new Element('span')} : {};
    const requests = [];
    const timers = new Map();
    let timerId = 0;
    const frames = new Map();
    let frameId = 0;
    const fetch = (url, options) => new Promise((resolve, reject) => requests.push({url, options, resolve, reject}));
    const document = {
        activeElement: null,
        listeners: {},
        addEventListener(name, callback) { (this.listeners[name] ||= []).push(callback); },
        emit(name, event = {}) { for (const callback of this.listeners[name] || []) callback(event); },
        getElementById: id => ({'barcode-results': results, 'barcode-status': status, 'barcode-heading': heading,
            'barcode-new-scan': newScan, ...Object.fromEntries(steps.map((node, i) => [`barcode-step-${i + 1}`, node])), ...shell}[id] || null),
        querySelector: selector => ({'[data-barcode]': input, '[data-barcode-form]': form}[selector] || null),
        createElement(tag) { const node = new Element(tag); node.ownerDocument = this; return node; },
        createTextNode: text => { const node = new Element('#text'); node.textContent = text; return node; },
    };
    for (const node of [input, form, mode, results, status, heading, newScan, ...steps, ...Object.values(shell)]) node.ownerDocument = document;
    vm.runInNewContext(source, {document, fetch, URL, Intl, AbortController, DOMException, TypeError, SyntaxError,
        window: {fetch, AbortController, location: {href: 'http://localhost/codigo-barras/'},
            ...(animation ? {requestAnimationFrame: callback => { frames.set(++frameId, callback); return frameId; }, cancelAnimationFrame: id => frames.delete(id)} : {}),
            setTimeout: callback => { timers.set(++timerId, callback); return timerId; },
            clearTimeout: id => timers.delete(id)}});
    document.emit('DOMContentLoaded');
    const submit = (code, submitter) => {
        input.value = code;
        input.focused = input.selected = false;
        let prevented = false;
        form.listeners.submit({submitter, preventDefault: () => { prevented = true; }});
        return prevented;
    };
    const type = value => {
        input.listeners.beforeinput?.();
        input.value = value;
        input.selected = false;
        input.listeners.input?.();
    };
    const paintFrame = () => { const entries = [...frames.values()]; frames.clear(); entries.forEach(callback => callback()); };
    return {input, form, mode, document, results, status, heading, requests, timers, submit, type, shell, steps, newScan, paintFrame};
}
const flush = () => new Promise(resolve => setImmediate(resolve));
const respond = (request, data, status = 200) => request.resolve({status, ok: status < 400, json: async () => data});
const item = (code = 'MT1') => ({id: 7, codigo_interno: code, status: 'disponivel',
    estado_conservacao: 'bom', preco: '0.00', produto_detalhe: {titulo: '<img src=x onerror=alert(1)>', tipo: 'DVD'}});
const descendants = node => [node, ...node.children.flatMap(descendants)];
const currentStep = ui => ui.steps.findIndex(node => node.attributes['aria-current'] === 'step') + 1;
const actionNamed = (ui, text) => descendants(ui.results).find(node => node.textContent === text && ['button', 'a'].includes(node.tag));
const externalEdition = (title = 'Edição real') => ({tipo: 'CD', titulo: title, ean: '7891234567895',
    artista_diretor: 'Autor', cadastro_url: '/acervo/cadastrar/?leitura=opaque-token&codigo=7891234567895&modo=ean'});

test('only one main card is presented from loading to external success and reset', async () => {
    const ui = setup();
    assert.equal(ui.form.attributes['data-presentation'], 'entry');
    ui.submit('7891234567895');
    assert.equal(ui.form.attributes['data-presentation'], 'collapsed');
    assert.equal(ui.results.children.length, 1);
    assert.match(ui.results.textContent, /Buscando informações/);
    assert.match(ui.results.textContent, /7891234567895/);
    assert.equal(descendants(ui.results).some(node => ['input', 'button', 'a', 'form'].includes(node.tag)), false);
    respond(ui.requests[0], {tipo_codigo: 'externo', fonte: 'MusicBrainz', results: [{...externalEdition('Título retornado'), ano: 2005}]});
    await flush();
    assert.equal(ui.form.attributes['data-presentation'], 'collapsed');
    assert.equal(ui.results.children.length, 1);
    assert.match(ui.results.textContent, /Título retornado/);
    assert.match(ui.results.textContent, /2005/);
    assert.doesNotMatch(ui.results.textContent, /Buscando|The Wall|Pink Floyd/);
    assert.equal(descendants(ui.results).some(node => node.tag === 'img'), false);
    assert.ok(descendants(ui.results).some(node => node.attributes['aria-label'] === 'Capa não disponível'));
    assert.ok(actionNamed(ui, 'Cadastrar item'));
    assert.equal(currentStep(ui), 4);
    assert.equal(ui.steps.slice(0, 3).every(step => step.attributes['data-state'] === 'complete'), true);
    actionNamed(ui, 'Nova leitura').listeners.click();
    assert.equal(currentStep(ui), 1);
    assert.equal(ui.form.attributes['data-presentation'], 'entry');
    assert.equal(ui.results.children.length, 0);
    assert.equal(ui.document.activeElement, ui.input);
});

test('local and missing states replace loading without claiming a local item is absent', async () => {
    const ui = setup();
    ui.submit('MT1');
    respond(ui.requests[0], item());
    await flush();
    assert.equal(ui.results.children.length, 1);
    assert.match(ui.results.textContent, /Item identificado com sucesso/);
    assert.match(ui.results.textContent, /Item localizado no acervo/);
    assert.equal(ui.form.attributes['data-presentation'], 'collapsed');
    ui.submit('UNKNOWN');
    assert.doesNotMatch(ui.results.textContent, /Item encontrado no acervo/);
    respond(ui.requests[1], {erro: {codigo: 'nao_encontrado'}}, 404);
    await flush();
    assert.equal(ui.results.children.length, 1);
    assert.match(ui.results.textContent, /Código não encontrado/);
    assert.equal(ui.form.attributes['data-presentation'], 'collapsed');
    assert.ok(actionNamed(ui, 'Nova leitura'));
});

test('found state renders real product data, status and only archive action', async () => {
    const ui = setup();
    ui.submit('MT1');
    respond(ui.requests[0], {id: 7, codigo_interno: 'MT1', status: 'reservado',
        produto_detalhe: {titulo: 'Título real', artista_diretor: 'Pessoa real', tipo: 'CD', ano: 2008,
            categoria_nome: 'Jazz', ean: '789123'}});
    await flush();
    assert.match(ui.results.textContent, /Título real/);
    assert.match(ui.results.textContent, /Pessoa real/);
    assert.match(ui.results.textContent, /2008/);
    assert.match(ui.results.textContent, /Jazz/);
    assert.match(ui.results.textContent, /789123/);
    assert.match(ui.results.textContent, /Status: Reservado/);
    assert.ok(actionNamed(ui, 'Ver no acervo'));
    assert.equal(actionNamed(ui, 'Cadastrar este item'), undefined);
    assert.equal(currentStep(ui), 4);
});

test('loading gets a browser paint opportunity before starting fetch', async () => {
    const ui = setup({animation: true});
    ui.submit('MT1');
    assert.equal(currentStep(ui), 2);
    assert.match(ui.results.textContent, /Buscando informações/);
    assert.equal(ui.requests.length, 0);
    ui.paintFrame();
    assert.equal(ui.requests.length, 0);
    ui.paintFrame();
    await flush();
    assert.equal(ui.requests.length, 1);
    respond(ui.requests[0], item());
    await flush();
    assert.match(ui.results.textContent, /Item identificado com sucesso/);
});

test('cancelling during paint does not launch a stale request', async () => {
    const ui = setup({animation: true});
    ui.submit('MT1');
    ui.newScan.listeners.click();
    ui.paintFrame();
    ui.paintFrame();
    await flush();
    assert.equal(ui.requests.length, 0);
    assert.equal(currentStep(ui), 1);
    assert.equal(ui.form.attributes['data-presentation'], 'entry');
    assert.equal(ui.results.children.length, 0);
});

test('new scanner input reveals entry and aborts the old lookup before it can hide the new code', async () => {
    const ui = setup();
    ui.submit('123');
    ui.type('1');
    assert.equal(ui.form.attributes['data-presentation'], 'entry');
    assert.equal(ui.requests[0].options.signal.aborted, true);
    ui.type('123');
    respond(ui.requests[0], item('123'));
    await flush();
    assert.equal(ui.form.attributes['data-presentation'], 'entry');
    assert.equal(ui.results.children.length, 0);
    ui.type('123456');
    assert.equal(ui.input.value, '123456');
});
async function startExternal(ui) {
    ui.submit('7891234567895');
    respond(ui.requests.at(-1), {erro: {codigo: 'nao_encontrado'}, metadados_disponiveis: true}, 404);
    await flush();
    const button = actionNamed(ui, 'Buscar informações de CD no MusicBrainz');
    button.focus();
    button.listeners.click();
}

test('stepper follows local lookup and never searches externally without an explicit action', async () => {
    const ui = setup();
    assert.equal(currentStep(ui), 1);
    assert.equal(ui.newScan.hidden, false);
    ui.submit('MT1');
    assert.equal(currentStep(ui), 2);
    assert.equal(ui.steps[0].attributes['data-state'], 'complete');
    assert.equal(ui.requests[0].url.searchParams.has('metadados'), false);
    respond(ui.requests[0], item());
    await flush();
    assert.equal(currentStep(ui), 4);
    assert.match(ui.results.textContent, /Item localizado no acervo/);
    assert.equal(ui.requests.length, 1);
    ui.submit('7891234567895');
    respond(ui.requests[1], {erro: {codigo: 'nao_encontrado'}, metadados_disponiveis: true}, 404);
    await flush();
    assert.equal(ui.requests.length, 2);
    assert.ok(actionNamed(ui, 'Buscar informações de CD no MusicBrainz'));
    assert.match(ui.results.textContent, /Buscar informações de CD no MusicBrainz/);
});

test('explicit metadata lookup goes through review to the real registration URL', async () => {
    const ui = setup();
    await startExternal(ui);
    assert.equal(currentStep(ui), 2);
    assert.equal(ui.requests[1].url.searchParams.get('metadados'), '1');
    assert.equal(ui.requests[1].options.credentials, 'same-origin');
    assert.equal(ui.document.activeElement, ui.results);
    respond(ui.requests[1], {tipo_codigo: 'externo', fonte: 'MusicBrainz', results: [externalEdition()]});
    await flush();
    assert.equal(currentStep(ui), 4);
    assert.match(ui.results.textContent, /ainda não está no acervo/);
    assert.equal(ui.document.activeElement, ui.results);
    const register = actionNamed(ui, 'Cadastrar item');
    const url = new URL(register.href);
    assert.equal(url.pathname, '/acervo/cadastrar/');
    assert.equal(url.searchParams.get('leitura'), 'opaque-token');
    assert.equal(url.searchParams.get('origem'), 'barcode');
    register.listeners.click();
    assert.equal(currentStep(ui), 4);
    assert.equal(ui.requests.length, 2);
});

test('ambiguous editions require explicit selection before registration', async () => {
    const ui = setup();
    await startExternal(ui);
    respond(ui.requests[1], {tipo_codigo: 'externo', fonte: 'MusicBrainz', results: [externalEdition('Primeira'), externalEdition('Segunda')]});
    await flush();
    assert.equal(ui.heading.textContent, 'Selecione uma edição');
    assert.equal(actionNamed(ui, 'Cadastrar item'), undefined);
    const buttons = descendants(ui.results).filter(node => node.tag === 'button');
    buttons[1].focus();
    buttons[1].listeners.click();
    assert.match(ui.results.textContent, /Segunda/);
    assert.doesNotMatch(ui.results.textContent, /Primeira/);
    assert.equal(ui.heading.textContent, 'Item identificado com sucesso');
    assert.ok(actionNamed(ui, 'Cadastrar item'));
    assert.equal(ui.document.activeElement, ui.results);
    actionNamed(ui, 'Voltar às opções').listeners.click();
    assert.equal(actionNamed(ui, 'Cadastrar item'), undefined);
    assert.equal(ui.heading.textContent, 'Selecione uma edição');
});

test('new scan cancels external request and late response cannot restore results or stepper', async () => {
    const ui = setup();
    await startExternal(ui);
    const old = ui.requests[1];
    ui.newScan.focus();
    ui.newScan.listeners.click();
    assert.equal(old.options.signal.aborted, true);
    assert.equal(ui.input.value, '');
    assert.equal(ui.status.textContent, '');
    assert.equal(ui.results.textContent, '');
    assert.equal(ui.results.attributes['aria-busy'], 'false');
    assert.equal(currentStep(ui), 1);
    assert.equal(ui.document.activeElement, ui.input);
    const selections = ui.input.selectCalls;
    respond(old, {tipo_codigo: 'externo', fonte: 'MusicBrainz', results: [externalEdition()]});
    await flush();
    assert.equal(currentStep(ui), 1);
    assert.equal(ui.results.textContent, '');
    assert.equal(ui.input.selectCalls, selections);
});

test('old metadata success cannot replace a newer local result or its registration target', async () => {
    const ui = setup();
    await startExternal(ui);
    ui.submit('NEW');
    respond(ui.requests[2], item('NEW'));
    await flush();
    respond(ui.requests[1], {tipo_codigo: 'externo', fonte: 'MusicBrainz', results: [externalEdition('Obsoleta')]});
    await flush();
    assert.match(ui.results.textContent, /NEW/);
    assert.doesNotMatch(ui.results.textContent, /Obsoleta/);
    assert.equal(currentStep(ui), 4);
    assert.equal(actionNamed(ui, 'Cadastrar item'), undefined);
});

test('metadata failures and timeout retain code and offer explicit retry or new scan', async () => {
    for (const kind of ['provider', 'network', 'timeout', 'invalid', 'empty']) {
        const ui = setup();
        await startExternal(ui);
        if (kind === 'provider') respond(ui.requests[1], {erro: {codigo: 'fonte_indisponivel', detalhes: 'Fonte indisponível'}}, 502);
        else if (kind === 'network') ui.requests[1].reject(new TypeError('offline'));
        else if (kind === 'timeout') ui.requests[1].reject(new DOMException('timeout', 'AbortError'));
        else if (kind === 'invalid') respond(ui.requests[1], {tipo_codigo: 'externo', results: [{}]});
        else respond(ui.requests[1], {erro: {codigo: 'nao_encontrado'}}, 404);
        await flush();
        assert.equal(ui.input.value, '7891234567895');
        assert.equal(currentStep(ui), kind === 'empty' ? 3 : 1);
        assert.equal(ui.results.attributes['aria-busy'], 'false');
        const retry = actionNamed(ui, 'Tentar MusicBrainz novamente');
        assert.ok(retry, kind);
        retry.listeners.click();
        assert.equal(currentStep(ui), 2);
        assert.equal(ui.requests.length, 3);
        ui.newScan.listeners.click();
        assert.equal(currentStep(ui), 1);
    }
});

test('metadata never renders an executable or foreign registration URL', async () => {
    for (const path of ['javascript:alert(1)', 'https://evil.example/acervo/cadastrar/', '/usuarios/']) {
        const ui = setup();
        await startExternal(ui);
        respond(ui.requests[1], {tipo_codigo: 'externo', fonte: 'MusicBrainz', results: [{...externalEdition(), cadastro_url: path}]});
        await flush();
        assert.equal(actionNamed(ui, 'Cadastrar item'), undefined);
        assert.equal(currentStep(ui), 1);
        assert.match(ui.status.textContent, /inválido/);
    }
});

test('duplicate pending lookup is suppressed but mode or code changes start a new request', async () => {
    const ui = setup();
    ui.submit('7891234567895');
    ui.submit('7891234567895');
    assert.equal(ui.requests.length, 1);
    ui.mode.value = 'ean';
    ui.submit('7891234567895');
    assert.equal(ui.requests.length, 2);
    assert.equal(ui.requests[0].options.signal.aborted, true);
    ui.submit('MT1');
    assert.equal(ui.requests.length, 3);
    assert.equal(ui.requests[1].options.signal.aborted, true);
});

test('manual registration preserves the queried code and mode even after input changes', async () => {
    const ui = setup();
    ui.mode.value = 'interno';
    ui.submit('MT-55');
    ui.mode.value = 'ean';
    respond(ui.requests[0], {erro: {codigo: 'nao_encontrado'}, metadados_disponiveis: false}, 404);
    await flush();
    const action = actionNamed(ui, 'Cadastrar este item');
    const url = new URL(action.href);
    assert.equal(url.searchParams.get('codigo'), 'MT-55');
    assert.equal(url.searchParams.get('modo'), 'interno');
    assert.equal(actionNamed(ui, 'Buscar informações de CD no MusicBrainz'), undefined);
    action.listeners.click();
    assert.equal(currentStep(ui), 4);
});

test('internal lookup uses session GET, safely renders text and restores focus', async () => {
    const ui = setup();
    assert.equal(ui.submit('MT1'), true);
    assert.match(ui.status.textContent, /Consultando/);
    assert.equal(ui.results.attributes['aria-busy'], 'true');
    assert.equal(ui.requests[0].url.pathname, '/api/exemplares/codigo/MT1/');
    assert.equal(ui.requests[0].options.credentials, 'same-origin');
    const selectionsAtSubmit = ui.input.selectCalls;
    const focusesAtSubmit = ui.input.focusCalls;
    respond(ui.requests[0], item());
    await flush();
    assert.match(ui.results.textContent, /<img src=x onerror=alert\(1\)>/);
    assert.equal(descendants(ui.results).some(node => node.tag === 'img'), false);
    assert.equal(descendants(ui.results).find(node => node.tag === 'a').href, 'http://localhost/acervo/item/7/');
    assert.equal(ui.results.attributes['aria-busy'], 'false');
    assert.ok(ui.input.focused && ui.input.selected);
    assert.equal(ui.input.selectCalls, selectionsAtSubmit + 1);
    assert.equal(ui.input.focusCalls, focusesAtSubmit);
    assert.equal(ui.document.activeElement, ui.input);
});

test('EAN results paginate asynchronously and preserve mode', async () => {
    const ui = setup();
    ui.form.elements.modo.value = 'ean';
    ui.submit('789123');
    const data = {tipo_codigo: 'ean', produto: {id: 1, titulo: 'Matrix', tipo: 'DVD', ean: '789123'},
        results: [item()], count: 21, next: 'http://localhost/api/exemplares/codigo/789123/?page=2', previous: null};
    respond(ui.requests[0], data);
    await flush();
    assert.match(ui.results.textContent, /Disponível/);
    assert.match(ui.results.textContent, /0,00/);
    const next = descendants(ui.results).find(node => node.tag === 'button');
    next.focus();
    const selectionsBeforePage = ui.input.selectCalls;
    next.listeners.click();
    assert.equal(ui.document.activeElement, ui.results);
    assert.equal(ui.requests[1].url.searchParams.get('page'), '2');
    assert.equal(ui.requests[1].url.searchParams.get('modo'), 'ean');
    respond(ui.requests[1], {...data, next: null, previous: 'page1'});
    await flush();
    assert.match(ui.status.textContent, /Página 2/);
    assert.equal(ui.document.activeElement, ui.results);
    assert.equal(ui.input.selectCalls, selectionsBeforePage);
    const previous = descendants(ui.results).find(node => node.tag === 'button');
    previous.focus();
    previous.listeners.click();
    assert.equal(ui.requests[2].url.searchParams.get('page'), '1');
    respond(ui.requests[2], data);
    await flush();
    assert.equal(ui.document.activeElement, ui.results);
});

test('EAN without copies and unknown code have useful results', async () => {
    const ui = setup();
    ui.submit('789123');
    respond(ui.requests[0], {tipo_codigo: 'ean', produto: {id: 1, titulo: 'Matrix', tipo: 'DVD', ean: '789123'},
        results: [], count: 0, next: null, previous: null});
    await flush();
    assert.match(ui.results.textContent, /Nenhum exemplar cadastrado/);
    ui.submit('missing');
    respond(ui.requests[1], {erro: {codigo: 'nao_encontrado'}}, 404);
    await flush();
    assert.match(ui.status.textContent, /não encontrado/);
    assert.match(ui.results.textContent, /Cadastrar este item/);
    assert.ok(ui.input.focused && ui.input.selected);
});

test('permission, server, network, malformed response and timeout failures recover', async () => {
    for (const kind of ['permission', 'server', 'network', 'invalid', 'timeout']) {
        const ui = setup();
        ui.submit('MT1');
        const selectionsAtSubmit = ui.input.selectCalls;
        const focusesAtSubmit = ui.input.focusCalls;
        const request = ui.requests[0];
        if (kind === 'permission') respond(request, {}, 403);
        if (kind === 'server') respond(request, {}, 500);
        if (kind === 'network') request.reject(new TypeError('Network unavailable'));
        if (kind === 'invalid') respond(request, {});
        if (kind === 'timeout') {
            [...ui.timers.values()][0]();
            assert.equal(request.options.signal.aborted, true);
            request.reject({name: 'AbortError'});
        }
        await flush();
        assert.match(ui.status.textContent, /página completa/, kind);
        assert.equal(ui.results.attributes['aria-busy'], 'false', kind);
        assert.ok(ui.input.focused && ui.input.selected, kind);
        assert.equal(ui.input.selectCalls, selectionsAtSubmit + 1, kind);
        assert.equal(ui.input.focusCalls, focusesAtSubmit, kind);
        assert.equal(ui.document.activeElement, ui.input, kind);
        assert.equal(ui.timers.size, 0, kind);
    }
});

test('consecutive scans cancel prior request and ignore late responses', async () => {
    const ui = setup();
    ui.submit('MT1');
    ui.submit('MT2');
    assert.equal(ui.requests[0].options.signal.aborted, true);
    respond(ui.requests[1], item('MT2'));
    await flush();
    const selectionsAfterLatest = ui.input.selectCalls;
    respond(ui.requests[0], item('MT1'));
    await flush();
    assert.match(ui.results.textContent, /MT2/);
    assert.doesNotMatch(ui.results.textContent, /MT1/);
    assert.match(ui.status.textContent, /MT2/);
    assert.equal(ui.input.selectCalls, selectionsAfterLatest);
});

test('does not select partial next scan and preserves native form fallback', async () => {
    const ui = setup();
    ui.submit('MT1');
    ui.type('MT');
    respond(ui.requests[0], item());
    await flush();
    assert.equal(ui.input.selected, false);
    assert.equal(ui.submit('MT1', {name: 'consulta_html'}), false);
    assert.equal(ui.submit('MT.1/2'), false);
    assert.equal(ui.submit(''), true);
    assert.equal(ui.requests.length, 1);
    assert.match(ui.status.textContent, /Informe um código/);
});

test('matching prefix of a new scan is never selected by the previous response', async () => {
    const ui = setup();
    ui.submit('123');
    ui.type('1');
    ui.type('12');
    ui.type('123');
    const selections = ui.input.selectCalls;
    respond(ui.requests[0], item('123'));
    await flush();
    assert.equal(ui.input.selectCalls, selections);
    assert.equal(ui.input.selected, false);
    ui.type(ui.input.value + '456');
    assert.equal(ui.input.value, '123456');
});

test('success, error and timeout respect deliberate focus navigation, including returning to input', async () => {
    for (const outcome of ['success', 'error', 'timeout']) {
        for (const returnToInput of [false, true]) {
            const ui = setup();
            ui.submit('MT1');
            ui.mode.focus();
            if (returnToInput) ui.input.focus();
            const selections = ui.input.selectCalls;
            const focuses = ui.input.focusCalls;
            if (outcome === 'success') respond(ui.requests[0], item());
            if (outcome === 'error') respond(ui.requests[0], {}, 500);
            if (outcome === 'timeout') {
                [...ui.timers.values()][0]();
                ui.requests[0].reject({name: 'AbortError'});
            }
            await flush();
            assert.equal(ui.document.activeElement, returnToInput ? ui.input : ui.mode);
            assert.equal(ui.input.selectCalls, selections);
            assert.equal(ui.input.focusCalls, focuses);
        }
    }
});

test('selection changes via pointer or keyboard prevent automatic reselection', async () => {
    for (const event of ['pointerdown', 'keydown']) {
        const ui = setup();
        ui.submit('MT1');
        ui.document.emit(event, {target: ui.input, key: 'ArrowLeft'});
        const selections = ui.input.selectCalls;
        respond(ui.requests[0], item());
        await flush();
        assert.equal(ui.input.selectCalls, selections);
    }
});

test('pagination does not steal focus after navigation away and handles errors', async () => {
    for (const failure of [false, true]) {
        const ui = setup();
        const product = {tipo_codigo: 'ean', produto: {id: 1, titulo: 'Matrix', tipo: 'DVD', ean: '789123'},
            results: [item()], count: 21, next: 'page2', previous: null};
        ui.submit('789123');
        respond(ui.requests[0], product);
        await flush();
        const next = descendants(ui.results).find(node => node.tag === 'button');
        next.focus();
        next.listeners.click();
        assert.equal(ui.document.activeElement, ui.results);
        ui.mode.focus();
        const selections = ui.input.selectCalls;
        respond(ui.requests[1], failure ? {} : {...product, next: null, previous: 'page1'}, failure ? 500 : 200);
        await flush();
        assert.equal(ui.document.activeElement, ui.mode);
        assert.equal(ui.input.selectCalls, selections);
        assert.equal(ui.results.attributes['aria-busy'], 'false');
    }
});

test('aborted old request cannot clear loading state or change focus of its replacement', async () => {
    const ui = setup();
    ui.submit('MT1');
    ui.submit('MT2');
    const selections = ui.input.selectCalls;
    ui.requests[0].reject({name: 'AbortError'});
    await flush();
    assert.match(ui.status.textContent, /Consultando MT2/);
    assert.equal(ui.results.attributes['aria-busy'], 'true');
    assert.equal(ui.input.selectCalls, selections);
    respond(ui.requests[1], item('MT2'));
    await flush();
    assert.equal(ui.input.selectCalls, selections + 1);
    assert.equal(ui.results.attributes['aria-busy'], 'false');
});

test('empty submission cancels pending lookup without a later focus change', async () => {
    const ui = setup();
    ui.submit('MT1');
    ui.submit('');
    const selections = ui.input.selectCalls;
    assert.equal(ui.requests[0].options.signal.aborted, true);
    respond(ui.requests[0], item());
    await flush();
    assert.match(ui.status.textContent, /Informe um código/);
    assert.equal(ui.results.textContent, '');
    assert.equal(ui.input.selectCalls, selections);
});

test('menu, counter, date and original focus behavior continue working together', async () => {
    const ui = setup({legacy: true});
    const toggle = ui.shell['menu-toggler'];
    const sidebar = ui.shell.sidebar;
    assert.equal(ui.shell['data-atual'].textContent, new Date().toLocaleDateString('pt-BR'));
    assert.equal(ui.requests[0].url, '/api/exemplares/');
    respond(ui.requests[0], {count: 42});
    await flush();
    assert.equal(ui.shell['contador-acervo'].textContent, '42');
    toggle.listeners.click();
    assert.equal(sidebar.classList.contains('aberto'), true);
    assert.equal(toggle.attributes['aria-expanded'], 'true');
    ui.document.emit('click', {target: sidebar});
    assert.equal(sidebar.classList.contains('aberto'), true);
    ui.document.emit('click', {target: ui.input});
    assert.equal(sidebar.classList.contains('aberto'), false);
    toggle.listeners.click();
    ui.document.emit('keydown', {key: 'Escape'});
    assert.equal(toggle.attributes['aria-expanded'], 'false');
    assert.equal(ui.document.activeElement, toggle);
    const selections = ui.input.selectCalls;
    ui.input.focus();
    assert.equal(ui.input.selectCalls, selections + 1);
    ui.submit('MT1');
    respond(ui.requests[1], item());
    await flush();
    assert.match(ui.status.textContent, /encontrado/);

    const failure = setup({legacy: true});
    respond(failure.requests[0], {}, 500);
    await flush();
    assert.equal(failure.shell['contador-acervo'].textContent, '—');
    assert.equal(failure.shell['contador-acervo'].title, 'Contagem indisponível');
});

test('reading card reflects actual lookup outcomes without changing focus rules', async () => {
    for (const outcome of ['found', 'missing', 'error', 'timeout']) {
        const ui = setup();
        assert.equal(ui.heading.textContent, 'Aguardando leitura');
        ui.submit('MT1');
        assert.equal(ui.form.attributes['data-state'], 'loading');
        assert.match(ui.heading.textContent, /Buscando/);
        ui.mode.focus();
        if (outcome === 'found') respond(ui.requests[0], item());
        if (outcome === 'missing') respond(ui.requests[0], {erro: {codigo: 'nao_encontrado'}}, 404);
        if (outcome === 'error') respond(ui.requests[0], {}, 500);
        if (outcome === 'timeout') {
            [...ui.timers.values()][0]();
            ui.requests[0].reject({name: 'AbortError'});
        }
        await flush();
        assert.equal(ui.form.attributes['data-state'], outcome);
        assert.doesNotMatch(ui.heading.textContent, /Buscando/);
        assert.equal(ui.document.activeElement, ui.mode);
        ui.submit('');
        assert.equal(ui.form.attributes['data-state'], 'idle');
        assert.equal(ui.heading.textContent, 'Aguardando leitura');
    }
});

test('obsolete responses cannot replace the latest visual state', async () => {
    const ui = setup();
    ui.submit('MT1');
    ui.submit('MT2');
    respond(ui.requests[1], item('MT2'));
    await flush();
    ui.requests[0].reject({name: 'AbortError'});
    await flush();
    assert.equal(ui.form.attributes['data-state'], 'found');
    assert.equal(ui.heading.textContent, 'Item encontrado');
});
