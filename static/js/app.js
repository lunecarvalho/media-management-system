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
});
