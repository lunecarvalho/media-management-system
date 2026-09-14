document.addEventListener('DOMContentLoaded', () => {
    const form = document.querySelector('[data-item-registration]');
    if (!form) return;
    const choice = form.querySelector('[data-product-choice]');
    const existing = form.querySelector('[data-existing-product]');
    const product = form.querySelector('[data-new-product]');
    const select = existing.querySelector('select');
    const radios = choice.querySelectorAll('input[type="radio"]');
    const setPanel = (panel, visible) => {
        panel.hidden = !visible;
        panel.querySelectorAll('input, select, textarea').forEach(field => { field.disabled = !visible; });
    };
    const update = () => {
        const useExisting = form.querySelector('input[name="produto_modo"]:checked').value === 'existente';
        setPanel(existing, useExisting);
        setPanel(product, !useExisting);
        select.required = useExisting;
    };
    radios.forEach(radio => radio.addEventListener('change', update));
    // Reaplicar após restauração de formulário pelo histórico do navegador.
    window.addEventListener('pageshow', update);
    update();
    choice.hidden = false;
    form.querySelector('[data-product-fallback]').hidden = true;
});
