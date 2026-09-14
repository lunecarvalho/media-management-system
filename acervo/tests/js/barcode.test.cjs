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

function setup({legacy = false} = {}) {
    const input = new Element('input');
    const form = new Element('form');
    form.dataset = {apiUrl: '/api/exemplares/codigo/CODIGO/', detailUrl: '/acervo/item/0/',
        createUrl: '/acervo/cadastrar/', metadataUrl: '/acervo/metadados/'};
    const mode = new Element('select');
    mode.value = 'auto';
    form.elements = {modo: mode};
    const results = new Element();
    const status = new Element();
    const shell = legacy ? {'menu-toggler': new Element('button'), sidebar: new Element('aside'),
        'data-atual': new Element('span'), 'contador-acervo': new Element('span')} : {};
    const requests = [];
    const timers = new Map();
    let timerId = 0;
    const fetch = (url, options) => new Promise((resolve, reject) => requests.push({url, options, resolve, reject}));
    const document = {
        activeElement: null,
        listeners: {},
        addEventListener(name, callback) { (this.listeners[name] ||= []).push(callback); },
        emit(name, event = {}) { for (const callback of this.listeners[name] || []) callback(event); },
        getElementById: id => ({'barcode-results': results, 'barcode-status': status, ...shell}[id] || null),
        querySelector: selector => ({'[data-barcode]': input, '[data-barcode-form]': form}[selector] || null),
        createElement(tag) { const node = new Element(tag); node.ownerDocument = this; return node; },
        createTextNode: text => { const node = new Element('#text'); node.textContent = text; return node; },
    };
    for (const node of [input, form, mode, results, status, ...Object.values(shell)]) node.ownerDocument = document;
    vm.runInNewContext(source, {document, fetch, URL, Intl, AbortController, TypeError, SyntaxError,
        window: {fetch, AbortController, location: {href: 'http://localhost/codigo-barras/'},
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
    return {input, form, mode, document, results, status, requests, timers, submit, type, shell};
}
const flush = () => new Promise(resolve => setImmediate(resolve));
const respond = (request, data, status = 200) => request.resolve({status, ok: status < 400, json: async () => data});
const item = (code = 'MT1') => ({id: 7, codigo_interno: code, status: 'disponivel',
    estado_conservacao: 'bom', preco: '0.00', produto_detalhe: {titulo: '<img src=x onerror=alert(1)>', tipo: 'DVD'}});
const descendants = node => [node, ...node.children.flatMap(descendants)];

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
    assert.match(ui.results.textContent, /Cadastrar manualmente/);
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
