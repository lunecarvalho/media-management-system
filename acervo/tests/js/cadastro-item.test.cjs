const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const {readFileSync} = require('node:fs');
const {resolve} = require('node:path');
const source = readFileSync(resolve(__dirname, '../../../static/js/cadastro-item.js'), 'utf8');

function setup(selected = 'novo') {
    const select = {value: '7', disabled: false};
    const title = {value: 'Titulo preservado', disabled: false};
    const existing = {querySelector: () => select, querySelectorAll: () => [select]};
    const product = {querySelectorAll: () => [title]};
    const radios = ['existente', 'novo'].map(value => ({value, checked: value === selected,
        addEventListener(name, callback) { this[name] = callback; }}));
    const choice = {hidden: true, querySelectorAll: () => radios};
    const fallback = {hidden: false};
    const panels = {'[data-product-choice]': choice, '[data-existing-product]': existing,
        '[data-new-product]': product, '[data-product-fallback]': fallback};
    const form = {querySelector: selector => panels[selector] || radios.find(radio => radio.checked)};
    const events = {};
    vm.runInNewContext(source, {document: {querySelector: () => form, addEventListener: (_, callback) => callback()},
        window: {addEventListener: (name, callback) => { events[name] = callback; }}});
    const choose = value => {
        radios.forEach(radio => { radio.checked = radio.value === value; });
        radios.find(radio => radio.checked).change();
    };
    return {select, title, existing, product, choice, fallback, choose, events, radios};
}

test('new product hides and disables existing selection without deleting it', () => {
    const ui = setup();
    assert.equal(ui.existing.hidden, true);
    assert.equal(ui.select.disabled, true);
    assert.equal(ui.select.required, false);
    assert.equal(ui.product.hidden, false);
    assert.equal(ui.title.disabled, false);
    assert.equal(ui.choice.hidden, false);
    assert.equal(ui.fallback.hidden, true);
    assert.equal(ui.select.value, '7');
});

test('existing product disables new fields and requires selection', () => {
    const ui = setup('existente');
    assert.equal(ui.existing.hidden, false);
    assert.equal(ui.select.disabled, false);
    assert.equal(ui.select.required, true);
    assert.equal(ui.product.hidden, true);
    assert.equal(ui.title.disabled, true);
});

test('switching both ways preserves typed values', () => {
    const ui = setup();
    ui.choose('existente');
    assert.equal(ui.title.disabled, true);
    ui.choose('novo');
    assert.equal(ui.title.disabled, false);
    assert.equal(ui.title.value, 'Titulo preservado');
    assert.equal(ui.select.value, '7');
});

test('history restoration reapplies current radio choice', () => {
    const ui = setup();
    ui.radios[0].checked = true;
    ui.radios[1].checked = false;
    ui.events.pageshow();
    assert.equal(ui.product.hidden, true);
    assert.equal(ui.select.disabled, false);
});

test('script is inert outside registration page', () => {
    vm.runInNewContext(source, {document: {querySelector: () => null, addEventListener: (_, callback) => callback()}});
});
